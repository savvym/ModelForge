from pathlib import Path

import pytest

from nta_infer_agent.config import AgentSettings
from nta_infer_agent.runtime import docker_runtime
from nta_infer_agent.runtime.docker_runtime import DockerRuntime
from nta_infer_agent.schemas import DeploymentSpec, EngineSpec, ModelBinding, ModelSource


def _settings(tmp_path: Path) -> AgentSettings:
    return AgentSettings(
        INFER_AGENT_TOKEN="test-token",
        runtime_dir=tmp_path / "runtime",
        _env_file=None,
    )


@pytest.mark.asyncio
async def test_start_vllm_uses_selected_gpus(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    commands: list[list[str]] = []

    async def fake_run_command(command: list[str], **_: object) -> str:
        commands.append(command)
        return "container-id"

    monkeypatch.setattr(docker_runtime, "run_command", fake_run_command)
    runtime = DockerRuntime(_settings(tmp_path))
    spec = DeploymentSpec(
        deployment_id="deployment-id",
        generation=1,
        model=ModelBinding(
            model_id="model-id",
            name="Qwen",
            served_name="qwen",
            source=ModelSource(type="local", uri="local:///model"),
        ),
        engine=EngineSpec(
            api_key="runtime-token",
            image="vllm/vllm-openai:latest",
            gpu_ids=[0, 1, 2, 3],
            tensor_parallel_size=4,
        ),
    )

    await runtime.start_vllm(spec, Path("/tmp/model"))

    run_command = commands[1]
    gpus_index = run_command.index("--gpus")
    assert run_command[gpus_index + 1] == "device=0,1,2,3"
    restart_index = run_command.index("--restart")
    assert run_command[restart_index + 1] == "on-failure:3"
    api_key_index = run_command.index("--api-key")
    assert run_command[api_key_index + 1] == "runtime-token"
    assert "--enable-lora" in run_command
    assert "--disable-fastapi-docs" not in run_command
    middleware_index = run_command.index("--middleware")
    assert run_command[middleware_index + 1] == "vllm_runtime_auth.require_runtime_token"
    assert "PYTHONPATH=/nta-runtime" in run_command
    assert "NTA_VLLM_RUNTIME_API_KEY=runtime-token" in run_command
    middleware_mount = next(
        item
        for item in run_command
        if item.endswith(":/nta-runtime/vllm_runtime_auth.py:ro")
    )
    middleware_path = Path(middleware_mount.split(":", 1)[0])
    middleware_source = middleware_path.read_text(encoding="utf-8")
    assert "NTA_VLLM_RUNTIME_API_KEY" in middleware_source
    assert "DISABLED_PATHS" not in middleware_source
    image_index = run_command.index("vllm/vllm-openai:latest")
    assert run_command[image_index + 1] == "/model"
    assert "--model" not in run_command


@pytest.mark.asyncio
async def test_start_vllm_uses_all_gpus_when_gpu_ids_are_empty(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    commands: list[list[str]] = []

    async def fake_run_command(command: list[str], **_: object) -> str:
        commands.append(command)
        return "container-id"

    monkeypatch.setattr(docker_runtime, "run_command", fake_run_command)
    runtime = DockerRuntime(_settings(tmp_path))
    spec = DeploymentSpec(
        deployment_id="deployment-id",
        generation=1,
        model=ModelBinding(
            model_id="model-id",
            name="Qwen",
            served_name="qwen",
            source=ModelSource(type="local", uri="local:///model"),
        ),
        engine=EngineSpec(
            api_key="runtime-token",
            image="vllm/vllm-openai:latest",
            gpu_ids=[],
            tensor_parallel_size=4,
        ),
    )

    await runtime.start_vllm(spec, Path("/tmp/model"))

    run_command = commands[1]
    gpus_index = run_command.index("--gpus")
    assert run_command[gpus_index + 1] == "all"


@pytest.mark.asyncio
async def test_start_vllm_skips_lora_for_unsupported_model_architecture(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    commands: list[list[str]] = []

    async def fake_run_command(command: list[str], **_: object) -> str:
        commands.append(command)
        return "container-id"

    model_path = tmp_path / "model"
    model_path.mkdir()
    (model_path / "config.json").write_text(
        '{"architectures": ["Gemma4ForConditionalGeneration"]}\n',
        encoding="utf-8",
    )
    monkeypatch.setattr(docker_runtime, "run_command", fake_run_command)
    runtime = DockerRuntime(_settings(tmp_path))
    spec = DeploymentSpec(
        deployment_id="deployment-id",
        generation=1,
        model=ModelBinding(
            model_id="model-id",
            name="Gemma 4",
            served_name="gemma4",
            source=ModelSource(type="local", uri="local:///model"),
        ),
        engine=EngineSpec(
            api_key="runtime-token",
            image="vllm/vllm-openai:latest",
            gpu_ids=list(range(8)),
            tensor_parallel_size=8,
        ),
    )

    await runtime.start_vllm(spec, model_path)

    run_command = commands[1]
    assert "--enable-lora" not in run_command
    assert "--max-loras" not in run_command
    assert "--max-lora-rank" not in run_command


@pytest.mark.asyncio
async def test_start_vllm_passes_reasoning_parser_extra_arg(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    commands: list[list[str]] = []

    async def fake_run_command(command: list[str], **_: object) -> str:
        commands.append(command)
        return "container-id"

    monkeypatch.setattr(docker_runtime, "run_command", fake_run_command)
    runtime = DockerRuntime(_settings(tmp_path))
    spec = DeploymentSpec(
        deployment_id="deployment-id",
        generation=1,
        model=ModelBinding(
            model_id="model-id",
            name="Qwen3",
            served_name="qwen3",
            source=ModelSource(type="local", uri="local:///model"),
        ),
        engine=EngineSpec(
            api_key="runtime-token",
            image="vllm/vllm-openai:latest",
            gpu_ids=[0, 1],
            tensor_parallel_size=2,
            extra_args={"reasoning_parser": "qwen3"},
        ),
    )

    await runtime.start_vllm(spec, Path("/tmp/model"))

    run_command = commands[1]
    reasoning_parser_index = run_command.index("--reasoning-parser")
    assert run_command[reasoning_parser_index + 1] == "qwen3"
    assert "--enable-reasoning" not in run_command


@pytest.mark.asyncio
async def test_inspect_state_parses_container_restart_count(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    async def fake_run_command(command: list[str], **_: object) -> str:
        assert command[:3] == ["docker", "inspect", "-f"]
        return '{"Status":"exited","ExitCode":1,"Error":""}|3'

    monkeypatch.setattr(docker_runtime, "run_command", fake_run_command)
    runtime = DockerRuntime(_settings(tmp_path))

    state = await runtime.inspect_state()

    assert state is not None
    assert state.status == "exited"
    assert state.exit_code == 1
    assert state.restart_count == 3
