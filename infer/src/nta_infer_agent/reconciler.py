from __future__ import annotations

import asyncio
import logging
from datetime import UTC, datetime

from nta_infer_agent.config import AgentSettings
from nta_infer_agent.runtime.docker_runtime import DockerRuntime
from nta_infer_agent.runtime.vllm_driver import VllmDriver
from nta_infer_agent.schemas import DeploymentSpec, DeploymentStatus, ErrorDetail
from nta_infer_agent.state import StateStore
from nta_infer_agent.storage.object_store import ModelCache, ModelDownloader

logger = logging.getLogger(__name__)


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

    def start(self) -> None:
        if self._task is None:
            self._task = asyncio.create_task(self._run(), name="deployment-reconciler")

    def kick(self) -> None:
        self._kick.set()

    async def _run(self) -> None:
        while True:
            try:
                await self.reconcile_once()
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
        )
        await self._event(spec, "runtime.stopped", "当前 vLLM 容器已停止", progress=100)

    async def _deploy(self, spec: DeploymentSpec) -> None:
        try:
            await self._set_status(
                spec,
                phase="downloading",
                progress=10,
                last_event="prepare model",
            )
            await self._event(spec, "artifact.cache_check", "检查本地模型缓存", progress=10)
            local_path, cache_hit = await self.downloader.ensure_cached(spec.model)
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

            await self._set_status(
                spec,
                phase="starting",
                progress=70,
                local_path=str(local_path),
                last_event="starting vllm",
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
            await self.vllm.wait_ready(spec)

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
        except Exception as exc:
            await self._set_status(
                spec,
                phase="error",
                progress=100,
                active_model_name=spec.model.served_name,
                last_event=str(exc),
                error=ErrorDetail(code=exc.__class__.__name__, message=str(exc)),
            )
            await self._event(
                spec,
                "deployment.failed",
                f"部署失败：{exc}",
                level="error",
                progress=100,
            )

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
    ) -> DeploymentStatus:
        current = await self.state.get_status()
        status = DeploymentStatus(
            deployment_id=spec.deployment_id,
            generation=spec.generation,
            phase=phase,
            progress=progress,
            endpoint=endpoint if endpoint is not None else current.endpoint,
            active_model_name=active_model_name or spec.model.served_name,
            local_path=local_path if local_path is not None else current.local_path,
            container_id=container_id if container_id is not None else current.container_id,
            last_event=last_event,
            error=error,
            last_health_ok_at=last_health_ok_at or current.last_health_ok_at,
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
