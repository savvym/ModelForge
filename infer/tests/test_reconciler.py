import asyncio
from pathlib import Path

import pytest

from nta_infer_agent.config import AgentSettings
from nta_infer_agent.reconciler import DeploymentReconciler, _DownloadProgressReporter
from nta_infer_agent.runtime.docker_runtime import ContainerState
from nta_infer_agent.schemas import (
    DeploymentSpec,
    DeploymentStatus,
    EngineSpec,
    ModelBinding,
    ModelSource,
)
from nta_infer_agent.storage.object_store import DownloadProgress


def _settings() -> AgentSettings:
    return AgentSettings(INFER_AGENT_TOKEN="test-token", _env_file=None)


class _FakeDocker:
    def __init__(self) -> None:
        self.stop_calls = 0

    async def stop_current(self) -> None:
        self.stop_calls += 1


class _RestartLimitDocker:
    def __init__(self) -> None:
        self.stop_calls = 0
        self.start_calls = 0

    async def stop_current(self) -> None:
        self.stop_calls += 1

    async def start_vllm(self, spec: DeploymentSpec, model_path: Path) -> str:
        self.start_calls += 1
        return "container-id"

    async def inspect_state(self) -> ContainerState:
        return ContainerState(status="exited", restart_count=3, exit_code=1)

    async def logs(self, tail: int = 200) -> str:
        return "vllm failed to start"


class _ReadyCache:
    async def ensure_cached(self, model: ModelBinding, **_: object) -> tuple[Path, bool]:
        return Path("/tmp/model"), True


class _BlockingCache:
    def __init__(self) -> None:
        self.started = asyncio.Event()
        self.cancel_event = None

    async def ensure_cached(self, model: ModelBinding, **kwargs: object) -> tuple[Path, bool]:
        self.cancel_event = kwargs.get("cancel_event")
        self.started.set()
        while True:
            await asyncio.sleep(0.1)


class _FailingVllm:
    async def wait_ready(self, spec: DeploymentSpec, before_sleep=None) -> None:
        assert before_sleep is not None
        await before_sleep()

    def endpoint(self, spec: DeploymentSpec) -> str:
        return "http://127.0.0.1:8000/v1"


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
        engine=EngineSpec(api_key="runtime-token", image="vllm/vllm-openai:latest"),
    )


@pytest.mark.asyncio
async def test_reconcile_does_not_repeat_stop_when_already_stopped() -> None:
    spec = _deployment_spec(desired_phase="stopped")
    state = _StoppedState(spec)
    reconciler = DeploymentReconciler(_settings(), state)  # type: ignore[arg-type]
    docker = _FakeDocker()
    reconciler.docker = docker  # type: ignore[assignment]

    await reconciler.reconcile_once()

    assert docker.stop_calls == 0
    assert state.events == []


@pytest.mark.asyncio
async def test_download_progress_reporter_updates_status_and_event() -> None:
    spec = _deployment_spec()
    state = _RecordingState()
    reconciler = DeploymentReconciler(_settings(), state)  # type: ignore[arg-type]
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


@pytest.mark.asyncio
async def test_deploy_sets_download_cancel_event_when_cancelled() -> None:
    spec = _deployment_spec()
    state = _RecordingState()
    reconciler = DeploymentReconciler(_settings(), state)  # type: ignore[arg-type]
    cache = _BlockingCache()
    reconciler.downloader = cache  # type: ignore[assignment]

    task = asyncio.create_task(reconciler._deploy(spec))
    await asyncio.wait_for(cache.started.wait(), timeout=1.0)

    task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await task

    assert cache.cancel_event is not None
    assert cache.cancel_event.is_set()
    assert [event["event_type"] for event in state.events][-2:] == [
        "artifact.download_cancelled",
        "deployment.cancelled",
    ]


@pytest.mark.asyncio
async def test_deploy_marks_error_and_cleans_container_after_restart_limit() -> None:
    spec = _deployment_spec()
    state = _RecordingState()
    reconciler = DeploymentReconciler(_settings(), state)  # type: ignore[arg-type]
    docker = _RestartLimitDocker()
    reconciler.docker = docker  # type: ignore[assignment]
    reconciler.downloader = _ReadyCache()  # type: ignore[assignment]
    reconciler.vllm = _FailingVllm()  # type: ignore[assignment]

    await reconciler._deploy(spec)

    assert docker.start_calls == 1
    assert docker.stop_calls == 2
    assert state.status.phase == "error"
    assert state.status.container_id is None
    assert state.status.endpoint is None
    assert "重启 3/3 次后仍未就绪" in (state.status.error.message if state.status.error else "")
    assert [event["event_type"] for event in state.events][-3:] == [
        "runtime.restart_detected",
        "runtime.cleaned",
        "deployment.failed",
    ]
