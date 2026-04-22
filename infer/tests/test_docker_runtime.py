from pathlib import Path

import pytest

from nta_infer_agent.config import AgentSettings
from nta_infer_agent.runtime import docker_runtime
from nta_infer_agent.runtime.docker_runtime import DockerRuntime
from nta_infer_agent.schemas import DeploymentSpec, EngineSpec, ModelBinding, ModelSource


@pytest.mark.asyncio
async def test_start_vllm_uses_all_gpus(monkeypatch: pytest.MonkeyPatch) -> None:
    commands: list[list[str]] = []

    async def fake_run_command(command: list[str], **_: object) -> str:
        commands.append(command)
        return "container-id"

    monkeypatch.setattr(docker_runtime, "run_command", fake_run_command)
    runtime = DockerRuntime(AgentSettings())
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
            image="vllm/vllm-openai:latest",
            gpu_ids=[0, 1, 2, 3],
            tensor_parallel_size=4,
        ),
    )

    await runtime.start_vllm(spec, Path("/tmp/model"))

    run_command = commands[1]
    gpus_index = run_command.index("--gpus")
    assert run_command[gpus_index + 1] == "all"
    restart_index = run_command.index("--restart")
    assert run_command[restart_index + 1] == "on-failure:3"


@pytest.mark.asyncio
async def test_inspect_state_parses_container_restart_count(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async def fake_run_command(command: list[str], **_: object) -> str:
        assert command[:3] == ["docker", "inspect", "-f"]
        return '{"Status":"exited","ExitCode":1,"Error":""}|3'

    monkeypatch.setattr(docker_runtime, "run_command", fake_run_command)
    runtime = DockerRuntime(AgentSettings())

    state = await runtime.inspect_state()

    assert state is not None
    assert state.status == "exited"
    assert state.exit_code == 1
    assert state.restart_count == 3
