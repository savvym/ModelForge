from uuid import UUID, uuid4

import pytest
from sqlalchemy import delete

from nta_backend.core.db import SessionLocal
from nta_backend.models.probe import Probe, ProbeHeartbeat, ProbeTask
from nta_backend.schemas.probe import (
    EvalScopePerfTaskConfig,
    ProbeHeartbeatRequest,
    ProbeRegistrationRequest,
    ProbeTaskCompleteRequest,
    ProbeTaskCreate,
    ProbeTaskStartRequest,
)
from nta_backend.services.probe_service import ProbeService

pytestmark = pytest.mark.asyncio(loop_scope="module")


async def test_probe_register_claim_and_complete_roundtrip() -> None:
    service = ProbeService()
    probe_id: UUID | None = None
    task_id: UUID | None = None
    probe_name = f"pytest-probe-{uuid4().hex[:8]}"

    try:
        registration = await service.register_probe(
            ProbeRegistrationRequest(
                name=probe_name,
                display_name="Pytest Probe",
                tags=["pytest"],
                metadata={"source": "test"},
            ),
            authorization=None,
            client_ip="127.0.0.1",
        )
        probe_id = registration.probe_id
        auth_header = f"Bearer {registration.auth_token}"

        heartbeat = await service.heartbeat(
            str(probe_id),
            ProbeHeartbeatRequest(
                network_metrics={"local_ip": "127.0.0.1"},
                agent_status={"active_tasks": 0},
            ),
            authorization=auth_header,
            client_ip="127.0.0.1",
        )
        assert heartbeat.status == "ok"

        created_task = await service.create_task(
            ProbeTaskCreate(
                probe_id=probe_id,
                name="pytest perf",
                config=EvalScopePerfTaskConfig(
                    model="demo-model",
                    url="https://example.com/v1/chat/completions",
                    api_key_env="OPENAI_API_KEY",
                    prompt="hello",
                    number=2,
                    parallel=1,
                ),
            )
        )
        task_id = created_task.id

        claimed = await service.claim_task(str(probe_id), authorization=auth_header)
        assert claimed.task is not None
        assert claimed.task.id == task_id

        started = await service.start_task(
            str(task_id),
            ProbeTaskStartRequest(summary="running"),
            authorization=auth_header,
        )
        assert started.status == "running"

        completed = await service.complete_task(
            str(task_id),
            ProbeTaskCompleteRequest(result_json={"ok": True}),
            authorization=auth_header,
        )
        assert completed.status == "completed"

        stored_task = await service.get_task(str(task_id))
        assert stored_task.status == "completed"
        assert stored_task.result_json == {"ok": True}
    finally:
        async with SessionLocal() as session:
            if task_id is not None:
                await session.execute(delete(ProbeTask).where(ProbeTask.id == task_id))
            if probe_id is not None:
                await session.execute(
                    delete(ProbeHeartbeat).where(ProbeHeartbeat.probe_id == probe_id)
                )
                await session.execute(delete(Probe).where(Probe.id == probe_id))
            await session.commit()
