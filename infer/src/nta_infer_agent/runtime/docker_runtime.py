from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from pathlib import Path
from textwrap import dedent

from nta_infer_agent.config import AgentSettings
from nta_infer_agent.process import run_command
from nta_infer_agent.schemas import DeploymentSpec

logger = logging.getLogger(__name__)

VLLM_RUNTIME_AUTH_MIDDLEWARE = dedent(
    """
    from __future__ import annotations

    import os

    from starlette.responses import JSONResponse


    async def require_runtime_token(request, call_next):
        token = os.environ.get("NTA_VLLM_RUNTIME_API_KEY", "").strip()
        expected = f"Bearer {token}" if token else ""
        if request.headers.get("authorization") != expected:
            return JSONResponse(status_code=401, content={"detail": "Invalid runtime token"})

        return await call_next(request)
    """
).strip()

VLLM_LORA_UNSUPPORTED_ARCHITECTURES = frozenset(
    {
        "Gemma4ForConditionalGeneration",
    }
)


def _docker_gpu_arg(gpu_ids: list[int]) -> str:
    if not gpu_ids:
        return "all"
    return f'"device={",".join(str(gpu_id) for gpu_id in gpu_ids)}"'


def _safe_mount_name(value: str) -> str:
    safe = "".join(ch if ch.isalnum() or ch in "-_" else "-" for ch in value.strip())
    return safe.strip("-") or "adapter"


@dataclass(frozen=True)
class ContainerState:
    status: str
    restart_count: int
    exit_code: int | None = None
    error: str | None = None


class DockerRuntime:
    def __init__(self, settings: AgentSettings) -> None:
        self.settings = settings

    async def stop_current(self) -> None:
        await run_command(
            [self.settings.docker_bin, "rm", "-f", self.settings.container_name],
            check=False,
        )

    async def start_vllm(
        self,
        spec: DeploymentSpec,
        model_path: Path,
        adapter_paths: dict[str, Path] | None = None,
    ) -> str:
        await self.stop_current()
        middleware_path = self._write_runtime_auth_middleware()
        runtime_api_key = spec.engine.api_key.get_secret_value()
        adapter_paths = adapter_paths or {}
        command = [
            self.settings.docker_bin,
            "run",
            "-d",
            "--name",
            self.settings.container_name,
            "--restart",
            (
                f"on-failure:{self.settings.max_runtime_restarts}"
                if self.settings.max_runtime_restarts > 0
                else "no"
            ),
            "--gpus",
            _docker_gpu_arg(spec.engine.gpu_ids),
            "--ipc=host",
            "-p",
            f"{spec.engine.listen_port}:{self.settings.vllm_container_port}",
            "-v",
            f"{model_path}:/model:ro",
            "-v",
            f"{middleware_path}:/nta-runtime/vllm_runtime_auth.py:ro",
            "-e",
            "PYTHONPATH=/nta-runtime",
            "-e",
            f"NTA_VLLM_RUNTIME_API_KEY={runtime_api_key}",
            spec.engine.image,
            "/model",
            "--served-model-name",
            spec.model.served_name,
            "--tensor-parallel-size",
            str(spec.engine.tensor_parallel_size),
            "--pipeline-parallel-size",
            str(spec.engine.pipeline_parallel_size),
            "--host",
            spec.engine.listen_host,
            "--port",
            str(self.settings.vllm_container_port),
            "--dtype",
            spec.engine.dtype,
            "--gpu-memory-utilization",
            str(spec.engine.gpu_memory_utilization),
            "--middleware",
            "vllm_runtime_auth.require_runtime_token",
        ]
        lora_modules: list[str] = []
        for adapter in spec.lora_adapters:
            adapter_path = adapter_paths.get(adapter.adapter_id)
            if adapter_path is None:
                continue
            mount_name = _safe_mount_name(adapter.adapter_id)
            command[command.index(spec.engine.image) : command.index(spec.engine.image)] = [
                "-v",
                f"{adapter_path}:/adapters/{mount_name}:ro",
            ]
            lora_modules.append(f"{adapter.served_name}=/adapters/{mount_name}")
        if spec.engine.max_model_len is not None:
            command.extend(["--max-model-len", str(spec.engine.max_model_len)])
        if spec.engine.enable_prefix_caching:
            command.append("--enable-prefix-caching")
        lora_enabled = _should_enable_lora(spec, model_path)
        if lora_modules and not lora_enabled:
            raise ValueError("LoRA adapters were requested, but LoRA is disabled for this model.")
        if lora_enabled:
            command.extend(["--enable-lora", "--max-loras", "16", "--max-lora-rank", "128"])
            if lora_modules:
                command.append("--lora-modules")
                command.extend(lora_modules)
        command.extend(["--api-key", spec.engine.api_key.get_secret_value()])
        for key, value in spec.engine.extra_args.items():
            option = f"--{key.replace('_', '-')}"
            if isinstance(value, bool):
                if value:
                    command.append(option)
            else:
                command.extend([option, str(value)])

        return await run_command(command)

    def _write_runtime_auth_middleware(self) -> Path:
        self.settings.runtime_root.mkdir(parents=True, exist_ok=True)
        middleware_path = self.settings.runtime_root / "vllm_runtime_auth.py"
        middleware_path.write_text(VLLM_RUNTIME_AUTH_MIDDLEWARE + "\n", encoding="utf-8")
        return middleware_path

    async def inspect_state(self) -> ContainerState | None:
        output = await run_command(
            [
                self.settings.docker_bin,
                "inspect",
                "-f",
                "{{json .State}}|{{.RestartCount}}",
                self.settings.container_name,
            ],
            check=False,
        )
        if not output or "|" not in output:
            return None

        state_json, restart_count = output.rsplit("|", 1)
        try:
            state = json.loads(state_json)
        except json.JSONDecodeError:
            return None

        return ContainerState(
            status=str(state.get("Status") or "unknown"),
            restart_count=int(restart_count.strip() or 0),
            exit_code=(
                int(state["ExitCode"])
                if isinstance(state.get("ExitCode"), int | float | str)
                and str(state.get("ExitCode")).lstrip("-").isdigit()
                else None
            ),
            error=str(state.get("Error") or "") or None,
        )

    async def inspect_container_id(self) -> str | None:
        output = await run_command(
            [
                self.settings.docker_bin,
                "inspect",
                "-f",
                "{{.Id}}",
                self.settings.container_name,
            ],
            check=False,
        )
        return output or None

    async def logs(self, tail: int = 200) -> str:
        return await run_command(
            [
                self.settings.docker_bin,
                "logs",
                "--tail",
                str(max(1, min(tail, 2000))),
                self.settings.container_name,
            ],
            check=False,
        )


def _should_enable_lora(spec: DeploymentSpec, model_path: Path) -> bool:
    if not spec.engine.enable_lora:
        return False

    unsupported_architectures = _lora_unsupported_architectures(model_path)
    if unsupported_architectures:
        logger.warning(
            "LoRA disabled for unsupported vLLM model architecture(s): %s",
            ", ".join(unsupported_architectures),
        )
        return False

    return True


def _lora_unsupported_architectures(model_path: Path) -> list[str]:
    config_path = model_path / "config.json"
    try:
        config = json.loads(config_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return []

    architectures = _model_config_architectures(config)
    return [
        architecture
        for architecture in architectures
        if architecture in VLLM_LORA_UNSUPPORTED_ARCHITECTURES
    ]


def _model_config_architectures(config: object) -> list[str]:
    if not isinstance(config, dict):
        return []

    architectures: list[str] = []
    sections: list[object] = [
        config,
        config.get("text_config"),
        config.get("llm_config"),
        config.get("language_config"),
    ]
    for section in sections:
        if not isinstance(section, dict):
            continue
        raw_architectures = section.get("architectures")
        if isinstance(raw_architectures, str):
            architectures.append(raw_architectures)
        elif isinstance(raw_architectures, list):
            architectures.extend(
                architecture
                for architecture in raw_architectures
                if isinstance(architecture, str)
            )

    return list(dict.fromkeys(architectures))
