import asyncio
from pathlib import Path
from uuid import uuid4

from nta_probe_agent.agent import ProbeAgent
from nta_probe_agent.client import ProbeControlPlaneError
from nta_probe_agent.config import ProbeAgentConfig


class FakeClient:
    def __init__(self) -> None:
        self.progress_summaries: list[str | None] = []
        self.completed_payloads: list[dict] = []
        self.failed_messages: list[str] = []

    async def start_task(self, *, task_id: str, auth_token: str, payload) -> None:
        return None

    async def get_task_runtime_config(self, *, task_id: str, auth_token: str):
        raise ProbeControlPlaneError("GET runtime-config returned 404", status_code=404)

    async def report_progress(self, *, task_id: str, auth_token: str, payload) -> None:
        self.progress_summaries.append(payload.summary)
        return None

    async def complete_task(self, *, task_id: str, auth_token: str, payload) -> None:
        self.completed_payloads.append(payload.result_json)
        return None

    async def fail_task(self, *, task_id: str, auth_token: str, payload) -> None:
        self.failed_messages.append(payload.error_message)
        return None


class FakeExecutor:
    def __init__(self) -> None:
        self.models: list[str] = []

    async def execute(self, *, task_id, config, timeout_seconds: int) -> dict:
        self.models.append(config.model)
        return {"task_id": str(task_id), "model": config.model}


def _build_config(tmp_path: Path) -> ProbeAgentConfig:
    return ProbeAgentConfig(
        server_base_url="http://example.com",
        project_id=None,
        registration_token=None,
        probe_name="probe-demo",
        display_name="probe-demo",
        tags=[],
        heartbeat_interval_seconds=30,
        poll_interval_seconds=10,
        state_path=tmp_path / "state.json",
        work_dir=tmp_path / "tasks",
    )


def test_execute_task_falls_back_to_claim_payload_config(tmp_path: Path) -> None:
    agent = ProbeAgent(_build_config(tmp_path))
    fake_client = FakeClient()
    fake_executor = FakeExecutor()
    agent._client = fake_client
    agent._executor = fake_executor
    agent._state.probe_id = "probe-id"
    agent._state.auth_token = "probe-token"

    task_id = uuid4()
    payload_json = {
        "runtime_kind": "evalscope-perf",
        "config": {
            "model": "gpt-5.4",
            "url": "https://example.com/v1/chat/completions",
            "api": "openai",
            "api_key_env": "OPENAI_API_KEY",
        },
    }

    asyncio.run(
        agent._execute_task(
            task_id,
            payload_json,
            timeout_seconds=60,
        )
    )

    assert fake_client.failed_messages == []
    assert fake_executor.models == ["gpt-5.4"]
    assert fake_client.progress_summaries == [
        "Resolving runtime config.",
        "Running evalscope perf.",
    ]
    assert fake_client.completed_payloads == [
        {"task_id": str(task_id), "model": "gpt-5.4"}
    ]
