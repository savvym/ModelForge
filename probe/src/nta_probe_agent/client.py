from __future__ import annotations

from typing import Any

import httpx

from nta_probe_agent.schemas import (
    ProbeHeartbeatRequest,
    ProbeHeartbeatResponse,
    ProbeRegistrationRequest,
    ProbeRegistrationResponse,
    ProbeTaskClaimResponse,
    ProbeTaskCompleteRequest,
    ProbeTaskFailRequest,
    ProbeTaskProgressRequest,
    ProbeTaskStartRequest,
    ProbeTaskTransitionResponse,
)


class ProbeControlPlaneError(RuntimeError):
    pass


class ProbeControlPlaneAuthError(ProbeControlPlaneError):
    pass


class ProbeControlPlaneClient:
    def __init__(
        self,
        *,
        base_url: str,
        project_id: str | None,
        timeout_seconds: float,
    ):
        self._project_id = project_id
        self._client = httpx.AsyncClient(
            base_url=base_url.rstrip("/"),
            timeout=httpx.Timeout(timeout_seconds),
        )

    async def aclose(self) -> None:
        await self._client.aclose()

    async def register(
        self,
        payload: ProbeRegistrationRequest,
        *,
        registration_token: str | None,
    ) -> ProbeRegistrationResponse:
        data = await self._request(
            "POST",
            "/api/v2/probes/register",
            json=payload.model_dump(mode="json"),
            token=registration_token,
        )
        return ProbeRegistrationResponse.model_validate(data)

    async def heartbeat(
        self,
        *,
        probe_id: str,
        auth_token: str,
        payload: ProbeHeartbeatRequest,
    ) -> ProbeHeartbeatResponse:
        data = await self._request(
            "POST",
            f"/api/v2/probes/{probe_id}/heartbeat",
            json=payload.model_dump(mode="json"),
            token=auth_token,
        )
        return ProbeHeartbeatResponse.model_validate(data)

    async def claim_task(
        self,
        *,
        probe_id: str,
        auth_token: str,
    ) -> ProbeTaskClaimResponse:
        data = await self._request(
            "POST",
            f"/api/v2/probes/{probe_id}/tasks/claim",
            json={},
            token=auth_token,
        )
        return ProbeTaskClaimResponse.model_validate(data)

    async def start_task(
        self,
        *,
        task_id: str,
        auth_token: str,
        payload: ProbeTaskStartRequest,
    ) -> ProbeTaskTransitionResponse:
        data = await self._request(
            "POST",
            f"/api/v2/probes/tasks/{task_id}/start",
            json=payload.model_dump(mode="json"),
            token=auth_token,
        )
        return ProbeTaskTransitionResponse.model_validate(data)

    async def report_progress(
        self,
        *,
        task_id: str,
        auth_token: str,
        payload: ProbeTaskProgressRequest,
    ) -> ProbeTaskTransitionResponse:
        data = await self._request(
            "POST",
            f"/api/v2/probes/tasks/{task_id}/progress",
            json=payload.model_dump(mode="json"),
            token=auth_token,
        )
        return ProbeTaskTransitionResponse.model_validate(data)

    async def complete_task(
        self,
        *,
        task_id: str,
        auth_token: str,
        payload: ProbeTaskCompleteRequest,
    ) -> ProbeTaskTransitionResponse:
        data = await self._request(
            "POST",
            f"/api/v2/probes/tasks/{task_id}/complete",
            json=payload.model_dump(mode="json"),
            token=auth_token,
        )
        return ProbeTaskTransitionResponse.model_validate(data)

    async def fail_task(
        self,
        *,
        task_id: str,
        auth_token: str,
        payload: ProbeTaskFailRequest,
    ) -> ProbeTaskTransitionResponse:
        data = await self._request(
            "POST",
            f"/api/v2/probes/tasks/{task_id}/fail",
            json=payload.model_dump(mode="json"),
            token=auth_token,
        )
        return ProbeTaskTransitionResponse.model_validate(data)

    async def _request(
        self,
        method: str,
        path: str,
        *,
        json: dict[str, Any] | None,
        token: str | None,
    ) -> Any:
        headers: dict[str, str] = {}
        if token:
            headers["Authorization"] = f"Bearer {token}"
        if self._project_id:
            headers["X-Project-ID"] = self._project_id
        response = await self._client.request(method, path, json=json, headers=headers)
        if response.status_code in {401, 403}:
            raise ProbeControlPlaneAuthError(response.text.strip() or "Authentication failed.")
        if response.status_code >= 400:
            raise ProbeControlPlaneError(
                f"{method} {path} returned {response.status_code}: {response.text.strip()}"
            )
        if not response.content:
            return None
        return response.json()
