from __future__ import annotations

import asyncio
import logging
import threading
from concurrent.futures import Future
from contextlib import suppress
from datetime import UTC, datetime
from time import monotonic

from nta_infer_agent.config import AgentSettings
from nta_infer_agent.runtime.docker_runtime import DockerRuntime
from nta_infer_agent.runtime.vllm_driver import VllmDriver
from nta_infer_agent.schemas import DeploymentSpec, DeploymentStatus, ErrorDetail
from nta_infer_agent.state import StateStore
from nta_infer_agent.storage.object_store import DownloadProgress, ModelCache, ModelDownloader

logger = logging.getLogger(__name__)

DOWNLOAD_PROGRESS_START = 10
DOWNLOAD_PROGRESS_END = 55
RUNTIME_FAILURE_LOG_TAIL = 120
TERMINAL_CONTAINER_STATES = {"dead", "exited", "removing"}


def _trim_log_excerpt(logs: str, max_chars: int = 1200) -> str:
    lines = [line.strip() for line in logs.splitlines() if line.strip()]
    text = "\n".join(lines[-20:])
    if len(text) <= max_chars:
        return text
    return f"...{text[-max_chars:]}"


class DeploymentReconciler:
    def __init__(self, settings: AgentSettings, state: StateStore) -> None:
        self.settings = settings
        self.state = state
        self.cache = ModelCache(settings.model_cache_root)
        self.downloader = ModelDownloader(self.cache, settings)
        self.docker = DockerRuntime(settings)
        self.vllm = VllmDriver(settings)
        self._kick = asyncio.Event()
        self._task: asyncio.Task[None] | None = None
        self._reported_runtime_restarts: dict[tuple[str, int], int] = {}

    def start(self) -> None:
        if self._task is None:
            self._task = asyncio.create_task(self._run(), name="deployment-reconciler")

    def kick(self) -> None:
        self._kick.set()

    async def _run(self) -> None:
        while True:
            self._kick.clear()
            reconcile_task = asyncio.create_task(
                self.reconcile_once(),
                name="deployment-reconcile-once",
            )
            kick_task = asyncio.create_task(self._kick.wait(), name="deployment-reconcile-kick")
            done, _ = await asyncio.wait(
                {reconcile_task, kick_task},
                return_when=asyncio.FIRST_COMPLETED,
            )
            if kick_task in done and not reconcile_task.done():
                reconcile_task.cancel()
                with suppress(asyncio.CancelledError):
                    await reconcile_task
                self._kick.clear()
                continue

            kick_task.cancel()
            with suppress(asyncio.CancelledError):
                await kick_task
            try:
                await reconcile_task
            except Exception:
                logger.exception("reconcile failed")
            try:
                await asyncio.wait_for(
                    self._kick.wait(),
                    timeout=self.settings.reconcile_interval_seconds,
                )
                self._kick.clear()
            except TimeoutError:
                pass

    async def reconcile_once(self) -> None:
        spec = await self.state.get_desired()
        if spec is None:
            return

        status = await self.state.get_status()
        if status.generation > spec.generation:
            return

        if spec.desired_phase == "stopped":
            if status.phase == "stopped" and status.generation == spec.generation:
                return
            await self._stop(spec)
            return

        if (
            status.phase == "ready"
            and status.generation == spec.generation
            and status.active_model_name == spec.model.served_name
        ):
            return

        if status.phase == "error" and status.generation == spec.generation:
            return

        await self._deploy(spec)

    async def _stop(self, spec: DeploymentSpec) -> None:
        await self._event(spec, "runtime.stopping", "停止当前 vLLM 容器", progress=10)
        await self.docker.stop_current()
        await self._set_status(
            spec,
            phase="stopped",
            progress=100,
            endpoint=None,
            container_id=None,
            last_event="runtime stopped",
            clear_runtime=True,
        )
        await self._event(spec, "runtime.stopped", "当前 vLLM 容器已停止", progress=100)

    async def _deploy(self, spec: DeploymentSpec) -> None:
        runtime_takeover_started = False
        try:
            await self._set_status(
                spec,
                phase="downloading",
                progress=DOWNLOAD_PROGRESS_START,
                last_event="prepare model",
            )
            await self._event(
                spec,
                "artifact.cache_check",
                "检查本地模型缓存",
                progress=DOWNLOAD_PROGRESS_START,
            )
            progress_reporter = _DownloadProgressReporter(self, spec)
            local_path, cache_hit = await self.downloader.ensure_cached(
                spec.model,
                progress=progress_reporter.report,
            )
            await progress_reporter.drain()
            if cache_hit:
                await self._event(
                    spec,
                    "artifact.cache_hit",
                    f"命中本地缓存：{local_path}",
                    progress=35,
                    payload={"local_path": str(local_path)},
                )
            else:
                await self._event(
                    spec,
                    "artifact.download_completed",
                    f"模型已下载到本地缓存：{local_path}",
                    progress=55,
                    payload={"local_path": str(local_path)},
                )

            await self._set_status(
                spec,
                phase="stopping_previous",
                progress=60,
                local_path=str(local_path),
                last_event="stopping previous runtime",
            )
            await self._event(spec, "runtime.stopping_previous", "停止旧 vLLM 容器", progress=60)
            await self.docker.stop_current()
            runtime_takeover_started = True

            await self._set_status(
                spec,
                phase="starting",
                progress=70,
                local_path=str(local_path),
                last_event="starting vllm",
                clear_runtime=True,
            )
            await self._event(spec, "runtime.starting", "启动 vLLM 容器", progress=70)
            container_id = await self.docker.start_vllm(spec, local_path)

            await self._set_status(
                spec,
                phase="warming",
                progress=82,
                local_path=str(local_path),
                container_id=container_id,
                endpoint=self.vllm.endpoint(spec),
                last_event="waiting for vllm health",
            )
            await self._event(spec, "runtime.warming", "等待 vLLM 健康检查通过", progress=82)
            await self.vllm.wait_ready(
                spec,
                before_sleep=lambda: self._guard_runtime_restart_limit(spec),
            )

            await self._set_status(
                spec,
                phase="smoke_testing",
                progress=92,
                local_path=str(local_path),
                container_id=container_id,
                endpoint=self.vllm.endpoint(spec),
                last_event="running smoke test",
                last_health_ok_at=datetime.now(UTC),
            )
            await self._event(
                spec,
                "smoke_test.started",
                "执行 OpenAI-compatible smoke test",
                progress=92,
            )
            await self.vllm.smoke_test(spec)

            await self._set_status(
                spec,
                phase="ready",
                progress=100,
                local_path=str(local_path),
                container_id=container_id,
                endpoint=self.vllm.endpoint(spec),
                active_model_name=spec.model.served_name,
                last_event="deployment ready",
                last_health_ok_at=datetime.now(UTC),
            )
            await self._event(
                spec,
                "deployment.ready",
                f"部署完成，对外访问地址：{self.vllm.endpoint(spec)}",
                progress=100,
                payload={"endpoint": self.vllm.endpoint(spec)},
            )
        except asyncio.CancelledError:
            await self._event(
                spec,
                "deployment.cancelled",
                "检测到新的部署期望，取消当前部署流程",
                level="warning",
                progress=100,
            )
            raise
        except Exception as exc:
            if runtime_takeover_started:
                with suppress(Exception):
                    await self.docker.stop_current()
                await self._event(
                    spec,
                    "runtime.cleaned",
                    "部署失败，已清理 vLLM 容器",
                    level="warning",
                    progress=100,
                )
            error_message = _trim_log_excerpt(str(exc), max_chars=1600) or str(exc)
            await self._set_status(
                spec,
                phase="error",
                progress=100,
                active_model_name=spec.model.served_name,
                last_event=error_message,
                error=ErrorDetail(code=exc.__class__.__name__, message=error_message),
                clear_runtime=runtime_takeover_started,
            )
            await self._event(
                spec,
                "deployment.failed",
                f"部署失败：{error_message}",
                level="error",
                progress=100,
            )

    async def _guard_runtime_restart_limit(self, spec: DeploymentSpec) -> None:
        restart_limit = self.settings.max_runtime_restarts
        if restart_limit <= 0:
            return

        state = await self.docker.inspect_state()
        if state is None:
            return

        restart_key = (spec.deployment_id, spec.generation)
        last_reported = self._reported_runtime_restarts.get(restart_key, 0)
        if state.restart_count > last_reported:
            self._reported_runtime_restarts[restart_key] = state.restart_count
            await self._event(
                spec,
                "runtime.restart_detected",
                f"vLLM 容器已重启 {state.restart_count}/{restart_limit} 次",
                level="warning",
                progress=82,
                payload={
                    "container_status": state.status,
                    "exit_code": state.exit_code,
                    "restart_count": state.restart_count,
                    "restart_limit": restart_limit,
                },
            )

        if state.restart_count < restart_limit or state.status not in TERMINAL_CONTAINER_STATES:
            return

        logs = await self.docker.logs(tail=RUNTIME_FAILURE_LOG_TAIL)
        message = f"vLLM 容器重启 {state.restart_count}/{restart_limit} 次后仍未就绪"
        if state.exit_code is not None:
            message = f"{message}，退出码 {state.exit_code}"
        if state.error:
            message = f"{message}，错误：{state.error}"
        log_excerpt = _trim_log_excerpt(logs)
        if log_excerpt:
            message = f"{message}。\n最近日志：\n{log_excerpt}"
        raise RuntimeError(message)

    async def _set_status(
        self,
        spec: DeploymentSpec,
        *,
        phase: str,
        progress: int,
        endpoint: str | None = None,
        active_model_name: str | None = None,
        local_path: str | None = None,
        container_id: str | None = None,
        last_event: str | None = None,
        error: ErrorDetail | None = None,
        last_health_ok_at: datetime | None = None,
        clear_runtime: bool = False,
    ) -> DeploymentStatus:
        current = await self.state.get_status()
        status = DeploymentStatus(
            deployment_id=spec.deployment_id,
            generation=spec.generation,
            phase=phase,
            progress=progress,
            endpoint=(
                None if clear_runtime else endpoint if endpoint is not None else current.endpoint
            ),
            active_model_name=active_model_name or spec.model.served_name,
            local_path=local_path if local_path is not None else current.local_path,
            container_id=(
                None
                if clear_runtime
                else container_id if container_id is not None else current.container_id
            ),
            last_event=last_event,
            error=error,
            last_health_ok_at=None
            if clear_runtime
            else last_health_ok_at or current.last_health_ok_at,
        )
        return await self.state.set_status(status)

    async def _event(
        self,
        spec: DeploymentSpec,
        event_type: str,
        message: str,
        *,
        level: str = "info",
        progress: int | None = None,
        payload: dict | None = None,
    ) -> None:
        await self.state.add_event(
            event_type=event_type,
            message=message,
            deployment_id=spec.deployment_id,
            generation=spec.generation,
            level=level,
            progress=progress,
            payload=payload,
        )


class _DownloadProgressReporter:
    def __init__(self, reconciler: DeploymentReconciler, spec: DeploymentSpec) -> None:
        self.reconciler = reconciler
        self.spec = spec
        self.loop = asyncio.get_running_loop()
        self._lock = threading.Lock()
        self._futures: set[Future] = set()
        self._last_progress = DOWNLOAD_PROGRESS_START
        self._last_report_at = 0.0

    def report(self, progress: DownloadProgress) -> None:
        mapped_progress = self._map_progress(progress)
        now = monotonic()
        with self._lock:
            if mapped_progress <= self._last_progress and now - self._last_report_at < 5:
                return
            self._last_progress = max(self._last_progress, mapped_progress)
            self._last_report_at = now
            future = asyncio.run_coroutine_threadsafe(
                self._record(progress, mapped_progress),
                self.loop,
            )
            self._futures.add(future)
            future.add_done_callback(self._discard)

    async def drain(self) -> None:
        while True:
            with self._lock:
                futures = list(self._futures)
            if not futures:
                return
            await asyncio.gather(
                *(asyncio.wrap_future(future) for future in futures),
                return_exceptions=True,
            )

    def _discard(self, future: Future) -> None:
        with self._lock:
            self._futures.discard(future)

    def _map_progress(self, progress: DownloadProgress) -> int:
        if progress.total and progress.total > 0:
            fraction = min(1.0, max(0.0, progress.completed / progress.total))
            return round(
                DOWNLOAD_PROGRESS_START
                + fraction * (DOWNLOAD_PROGRESS_END - DOWNLOAD_PROGRESS_START)
            )
        return min(DOWNLOAD_PROGRESS_END - 1, self._last_progress + 1)

    async def _record(self, progress: DownloadProgress, mapped_progress: int) -> None:
        message = self._format_message(progress)
        await self.reconciler._set_status(
            self.spec,
            phase="downloading",
            progress=mapped_progress,
            last_event=message,
        )
        await self.reconciler._event(
            self.spec,
            "artifact.download_progress",
            message,
            progress=mapped_progress,
            payload={
                "completed": progress.completed,
                "total": progress.total,
                "unit": progress.unit,
            },
        )

    def _format_message(self, progress: DownloadProgress) -> str:
        if not progress.message:
            return self._format_progress(progress)
        if progress.unit != "bytes":
            return progress.message
        detail = self._format_progress(progress).removeprefix("下载模型文件 ")
        return f"{progress.message}（{detail}）"

    def _format_progress(self, progress: DownloadProgress) -> str:
        if progress.unit == "bytes":
            completed = _format_bytes(progress.completed)
            if progress.total:
                return f"下载模型文件 {completed} / {_format_bytes(progress.total)}"
            return f"下载模型文件 {completed}"
        if progress.total:
            return f"下载模型文件 {progress.completed} / {progress.total} {progress.unit}"
        return f"下载模型文件 {progress.completed} {progress.unit}"


def _format_bytes(value: int) -> str:
    units = ["B", "KB", "MB", "GB", "TB"]
    size = float(max(value, 0))
    for unit in units:
        if size < 1024 or unit == units[-1]:
            if unit == "B":
                return f"{int(size)} {unit}"
            return f"{size:.1f} {unit}"
        size /= 1024
