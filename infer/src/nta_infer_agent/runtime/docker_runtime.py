from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

from nta_infer_agent.config import AgentSettings
from nta_infer_agent.process import run_command
from nta_infer_agent.schemas import DeploymentSpec


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

    async def start_vllm(self, spec: DeploymentSpec, model_path: Path) -> str:
        await self.stop_current()
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
            "all",
            "--ipc=host",
            "-p",
            f"{spec.engine.listen_port}:{self.settings.vllm_container_port}",
            "-v",
            f"{model_path}:/model:ro",
            spec.engine.image,
            "--model",
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
        ]
        if spec.engine.max_model_len is not None:
            command.extend(["--max-model-len", str(spec.engine.max_model_len)])
        if spec.engine.enable_prefix_caching:
            command.append("--enable-prefix-caching")
        if spec.engine.enable_lora:
            command.extend(["--enable-lora", "--max-loras", "16", "--max-lora-rank", "128"])
        command.extend(["--api-key", spec.engine.api_key.get_secret_value()])
        for key, value in spec.engine.extra_args.items():
            option = f"--{key.replace('_', '-')}"
            if isinstance(value, bool):
                if value:
                    command.append(option)
            else:
                command.extend([option, str(value)])

        return await run_command(command)

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
