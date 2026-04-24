from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable
from datetime import UTC, datetime, timedelta
from time import perf_counter

import httpx

from nta_infer_agent.config import AgentSettings
from nta_infer_agent.schemas import DeploymentSpec


class VllmDriver:
    def __init__(self, settings: AgentSettings) -> None:
        self.settings = settings

    def endpoint(self, spec: DeploymentSpec) -> str:
        host = self.settings.runtime_public_host or "127.0.0.1"
        return f"http://{host}:{spec.engine.listen_port}/v1"

    def local_base_url(self, spec: DeploymentSpec) -> str:
        return f"http://127.0.0.1:{spec.engine.listen_port}"

    async def wait_ready(
        self,
        spec: DeploymentSpec,
        before_sleep: Callable[[], Awaitable[None]] | None = None,
    ) -> None:
        deadline = datetime.now(UTC) + timedelta(seconds=self.settings.health_timeout_seconds)
        headers = self._headers(spec)
        async with httpx.AsyncClient(timeout=5.0) as client:
            while datetime.now(UTC) < deadline:
                try:
                    response = await client.get(
                        f"{self.local_base_url(spec)}/health",
                        headers=headers,
                    )
                    if response.status_code < 500:
                        models = await client.get(
                            f"{self.local_base_url(spec)}/v1/models",
                            headers=headers,
                        )
                        if models.status_code < 500:
                            return
                except httpx.HTTPError:
                    pass
                if before_sleep is not None:
                    await before_sleep()
                await asyncio.sleep(self.settings.health_poll_interval_seconds)
        raise TimeoutError("vLLM did not become healthy before timeout")

    async def smoke_test(self, spec: DeploymentSpec) -> None:
        if spec.smoke_test is None or not spec.smoke_test.enabled:
            return
        headers = {"Content-Type": "application/json", **self._headers(spec)}
        payload = {
            "model": spec.model.served_name,
            "messages": [{"role": "user", "content": spec.smoke_test.prompt}],
            "max_tokens": 8,
            "temperature": 0,
        }
        async with httpx.AsyncClient(timeout=spec.smoke_test.timeout_seconds) as client:
            response = await client.post(
                f"{self.local_base_url(spec)}/v1/chat/completions",
                headers=headers,
                json=payload,
            )
            response.raise_for_status()

    async def fetch_metrics(self, spec: DeploymentSpec) -> tuple[str, int]:
        started_at = perf_counter()
        async with httpx.AsyncClient(timeout=8.0) as client:
            response = await client.get(
                f"{self.local_base_url(spec)}/metrics",
                headers=self._headers(spec),
            )
            response.raise_for_status()
            return response.text, int((perf_counter() - started_at) * 1000)

    def _headers(self, spec: DeploymentSpec) -> dict[str, str]:
        return {"Authorization": f"Bearer {spec.engine.api_key.get_secret_value()}"}
