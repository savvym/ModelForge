import pytest

from nta_infer_agent.config import AgentSettings
from nta_infer_agent.reconciler import DeploymentReconciler, _DownloadProgressReporter
from nta_infer_agent.schemas import (
    DeploymentSpec,
    DeploymentStatus,
    EngineSpec,
    ModelBinding,
    ModelSource,
)
from nta_infer_agent.storage.object_store import DownloadProgress


class _FakeDocker:
    def __init__(self) -> None:
        self.stop_calls = 0

    async def stop_current(self) -> None:
        self.stop_calls += 1


class _StoppedState:
    def __init__(self, spec: DeploymentSpec) -> None:
        self.spec = spec
        self.status = DeploymentStatus(
            deployment_id=spec.deployment_id,
            generation=spec.generation,
            phase="stopped",
            progress=100,
        )
        self.events: list[str] = []

    async def get_desired(self) -> DeploymentSpec:
        return self.spec

    async def get_status(self) -> DeploymentStatus:
        return self.status

    async def add_event(self, *, event_type: str, **_: object) -> None:
        self.events.append(event_type)


class _RecordingState:
    def __init__(self) -> None:
        self.status = DeploymentStatus(phase="pending", progress=0)
        self.statuses: list[DeploymentStatus] = []
        self.events: list[dict[str, object]] = []

    async def get_status(self) -> DeploymentStatus:
        return self.status

    async def set_status(self, status: DeploymentStatus) -> DeploymentStatus:
        self.status = status
        self.statuses.append(status)
        return status

    async def add_event(self, **kwargs: object) -> None:
        self.events.append(kwargs)


def _deployment_spec(**overrides: object) -> DeploymentSpec:
    return DeploymentSpec(
        deployment_id=str(overrides.get("deployment_id", "deployment-id")),
        generation=int(overrides.get("generation", 7)),
        desired_phase=str(overrides.get("desired_phase", "running")),  # type: ignore[arg-type]
        model=ModelBinding(
            model_id="model-id",
            name="Qwen",
            served_name="qwen",
            source=ModelSource(type="local", uri="local:///model"),
        ),
        engine=EngineSpec(image="vllm/vllm-openai:latest"),
    )


@pytest.mark.asyncio
async def test_reconcile_does_not_repeat_stop_when_already_stopped() -> None:
    spec = _deployment_spec(desired_phase="stopped")
    state = _StoppedState(spec)
    reconciler = DeploymentReconciler(AgentSettings(), state)  # type: ignore[arg-type]
    docker = _FakeDocker()
    reconciler.docker = docker  # type: ignore[assignment]

    await reconciler.reconcile_once()

    assert docker.stop_calls == 0
    assert state.events == []


@pytest.mark.asyncio
async def test_download_progress_reporter_updates_status_and_event() -> None:
    spec = _deployment_spec()
    state = _RecordingState()
    reconciler = DeploymentReconciler(AgentSettings(), state)  # type: ignore[arg-type]
    reporter = _DownloadProgressReporter(reconciler, spec)

    reporter.report(
        DownloadProgress(
            completed=50,
            total=100,
            unit="bytes",
            message="正在下载模型文件",
        )
    )
    await reporter.drain()

    assert state.status.phase == "downloading"
    assert state.status.progress > 10
    assert state.status.last_event == "正在下载模型文件（50 B / 100 B）"
    assert state.events[-1]["event_type"] == "artifact.download_progress"
