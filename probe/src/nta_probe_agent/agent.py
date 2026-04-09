from __future__ import annotations

import asyncio
import importlib.metadata
import os
import platform
import socket
from typing import Any
from uuid import UUID

from nta_probe_agent import __version__
from nta_probe_agent.client import ProbeControlPlaneAuthError, ProbeControlPlaneClient
from nta_probe_agent.config import ProbeAgentConfig
from nta_probe_agent.executor import EvalScopePerfExecutionError, EvalScopePerfExecutor
from nta_probe_agent.schemas import (
    EvalScopePerfTaskConfig,
    ProbeHeartbeatRequest,
    ProbeRegistrationRequest,
    ProbeTaskCompleteRequest,
    ProbeTaskFailRequest,
    ProbeTaskProgressRequest,
    ProbeTaskStartRequest,
)
from nta_probe_agent.state import ProbeAgentState, ProbeAgentStateStore


class ProbeAgent:
    def __init__(self, config: ProbeAgentConfig):
        self._config = config
        self._state_store = ProbeAgentStateStore(config.state_path)
        self._state = self._state_store.load()
        self._client = ProbeControlPlaneClient(
            base_url=config.server_base_url,
            project_id=config.project_id,
            timeout_seconds=config.request_timeout_seconds,
        )
        self._executor = EvalScopePerfExecutor(
            work_dir=config.work_dir,
            evalscope_bin=config.evalscope_bin,
            stdout_tail_chars=config.stdout_tail_chars,
        )
        self._running_task_id: str | None = None

    async def aclose(self) -> None:
        await self._client.aclose()

    async def run_forever(self) -> None:
        await self.ensure_registered(
            force=not bool(self._state.probe_id and self._state.auth_token)
        )
        async with asyncio.TaskGroup() as tg:
            tg.create_task(self._heartbeat_loop())
            tg.create_task(self._poll_loop())

    async def ensure_registered(self, *, force: bool = False) -> None:
        if self._state.probe_id and self._state.auth_token and not force:
            return
        payload = ProbeRegistrationRequest(
            name=self._state.probe_name or self._config.probe_name,
            display_name=self._config.display_name,
            tags=self._config.tags,
            agent_version=__version__,
            device_info=self._collect_device_info(),
            metadata={"pid": os.getpid()},
        )
        response = await self._client.register(
            payload,
            registration_token=self._config.registration_token,
        )
        self._state = ProbeAgentState(
            probe_id=str(response.probe_id),
            auth_token=response.auth_token,
            probe_name=response.name,
        )
        self._state_store.save(self._state)

    async def _heartbeat_loop(self) -> None:
        while True:
            try:
                await self._send_heartbeat()
            except ProbeControlPlaneAuthError:
                await self.ensure_registered(force=True)
            await asyncio.sleep(max(5, self._config.heartbeat_interval_seconds))

    async def _poll_loop(self) -> None:
        while True:
            try:
                claimed = await self._client.claim_task(
                    probe_id=self.probe_id,
                    auth_token=self.auth_token,
                )
            except ProbeControlPlaneAuthError:
                await self.ensure_registered(force=True)
                await asyncio.sleep(1)
                continue

            task = claimed.task
            if task is None:
                await asyncio.sleep(max(2, self._config.poll_interval_seconds))
                continue
            await self._execute_task(
                task.id,
                task.payload_json,
                timeout_seconds=task.timeout_seconds,
            )

    async def _execute_task(
        self,
        task_id: UUID,
        payload_json: dict[str, Any],
        *,
        timeout_seconds: int,
    ) -> None:
        self._running_task_id = str(task_id)
        await self._client.start_task(
            task_id=str(task_id),
            auth_token=self.auth_token,
            payload=ProbeTaskStartRequest(summary="Probe accepted task."),
        )
        await self._client.report_progress(
            task_id=str(task_id),
            auth_token=self.auth_token,
            payload=ProbeTaskProgressRequest(
                summary="Running evalscope perf.",
                step=0,
                total=1,
            ),
        )
        try:
            runtime_kind = str(payload_json.get("runtime_kind") or "").strip()
            if runtime_kind != "evalscope-perf":
                raise EvalScopePerfExecutionError(
                    f"Unsupported runtime kind: {runtime_kind or 'unknown'}"
                )
            config = EvalScopePerfTaskConfig.model_validate(payload_json.get("config") or {})
            result = await self._executor.execute(
                task_id=task_id,
                config=config,
                timeout_seconds=timeout_seconds,
            )
            await self._client.complete_task(
                task_id=str(task_id),
                auth_token=self.auth_token,
                payload=ProbeTaskCompleteRequest(result_json=result),
            )
        except Exception as exc:
            await self._client.fail_task(
                task_id=str(task_id),
                auth_token=self.auth_token,
                payload=ProbeTaskFailRequest(
                    error_message=str(exc),
                    result_json={"running_task_id": str(task_id)},
                ),
            )
        finally:
            self._running_task_id = None

    async def _send_heartbeat(self) -> None:
        await self._client.heartbeat(
            probe_id=self.probe_id,
            auth_token=self.auth_token,
            payload=ProbeHeartbeatRequest(
                network_metrics=self._collect_network_metrics(),
                agent_status=self._collect_agent_status(),
            ),
        )

    def _collect_device_info(self) -> dict[str, Any]:
        try:
            evalscope_version = importlib.metadata.version("evalscope")
        except importlib.metadata.PackageNotFoundError:
            evalscope_version = None
        return {
            "hostname": socket.gethostname(),
            "platform": platform.platform(),
            "python_version": platform.python_version(),
            "evalscope_version": evalscope_version,
        }

    def _collect_agent_status(self) -> dict[str, Any]:
        return {
            "pid": os.getpid(),
            "hostname": socket.gethostname(),
            "active_tasks": 1 if self._running_task_id else 0,
            "current_task_id": self._running_task_id,
            "work_dir": str(self._config.work_dir),
        }

    def _collect_network_metrics(self) -> dict[str, Any]:
        try:
            with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sock:
                sock.connect(("8.8.8.8", 80))
                local_ip = sock.getsockname()[0]
        except OSError:
            local_ip = None
        return {
            "local_ip": local_ip,
            "server_base_url": self._config.server_base_url,
        }

    @property
    def probe_id(self) -> str:
        if not self._state.probe_id:
            raise RuntimeError("Probe is not registered.")
        return self._state.probe_id

    @property
    def auth_token(self) -> str:
        if not self._state.auth_token:
            raise RuntimeError("Probe auth token is missing.")
        return self._state.auth_token
