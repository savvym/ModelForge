from datetime import UTC, datetime, timedelta
from uuid import UUID, uuid4

import pytest
from sqlalchemy import delete

from nta_backend.core.db import SessionLocal
from nta_backend.models.modeling import ModelProvider
from nta_backend.models.probe import Probe, ProbeHeartbeat, ProbeTask
from nta_backend.schemas.model_registry import ModelProviderCreate
from nta_backend.schemas.probe import (
    EvalScopePerfTaskConfig,
    ProbeHeartbeatRequest,
    ProbeRegistrationRequest,
    ProbeTaskCompleteRequest,
    ProbeTaskCreate,
    ProbeTaskStartRequest,
)
from nta_backend.services.model_registry_service import ModelRegistryService
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


async def test_probe_reclaims_expired_running_task() -> None:
    service = ProbeService()
    probe_id: UUID | None = None
    task_id: UUID | None = None
    probe_name = f"pytest-probe-{uuid4().hex[:8]}"

    try:
        registration = await service.register_probe(
            ProbeRegistrationRequest(
                name=probe_name,
                display_name="Pytest Probe Retry",
                tags=["pytest"],
            ),
            authorization=None,
            client_ip="127.0.0.1",
        )
        probe_id = registration.probe_id
        auth_header = f"Bearer {registration.auth_token}"

        created_task = await service.create_task(
            ProbeTaskCreate(
                probe_id=probe_id,
                name="pytest retry",
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

        async with SessionLocal() as session:
            stored_task = await session.get(ProbeTask, task_id)
            assert stored_task is not None
            stored_task.lease_expires_at = datetime.now(UTC) - timedelta(seconds=5)
            await session.commit()

        reclaimed = await service.claim_task(str(probe_id), authorization=auth_header)
        assert reclaimed.task is not None
        assert reclaimed.task.id == task_id
        assert reclaimed.task.attempt_count == 2

        stored_task = await service.get_task(str(task_id))
        assert stored_task.status == "claimed"
        assert stored_task.started_at is None
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


async def test_probe_delete_requires_offline_status() -> None:
    service = ProbeService()
    probe_id: UUID | None = None
    probe_name = f"pytest-probe-{uuid4().hex[:8]}"

    try:
        registration = await service.register_probe(
            ProbeRegistrationRequest(
                name=probe_name,
                display_name="Pytest Probe Delete",
                tags=["pytest"],
            ),
            authorization=None,
            client_ip="127.0.0.1",
        )
        probe_id = registration.probe_id

        with pytest.raises(ValueError, match="Only offline probes can be deleted."):
            await service.delete_probe(str(probe_id))

        async with SessionLocal() as session:
            probe = await session.get(Probe, probe_id)
            assert probe is not None
            probe.last_heartbeat = datetime.now(UTC) - timedelta(days=1)
            await session.commit()

        await service.delete_probe(str(probe_id))

        async with SessionLocal() as session:
            deleted_probe = await session.get(Probe, probe_id)
            assert deleted_probe is None
    finally:
        async with SessionLocal() as session:
            if probe_id is not None:
                await session.execute(
                    delete(ProbeTask).where(ProbeTask.probe_id == probe_id)
                )
                await session.execute(
                    delete(ProbeHeartbeat).where(ProbeHeartbeat.probe_id == probe_id)
                )
                await session.execute(delete(Probe).where(Probe.id == probe_id))
            await session.commit()


async def test_probe_runtime_config_resolves_provider_credentials() -> None:
    service = ProbeService()
    registry_service = ModelRegistryService()
    probe_id: UUID | None = None
    task_id: UUID | None = None
    provider_id: UUID | None = None
    probe_name = f"pytest-probe-{uuid4().hex[:8]}"
    provider_name = f"pytest-provider-{uuid4().hex[:8]}"

    try:
        registration = await service.register_probe(
            ProbeRegistrationRequest(
                name=probe_name,
                display_name="Pytest Probe Provider",
                tags=["pytest"],
            ),
            authorization=None,
            client_ip="127.0.0.1",
        )
        probe_id = registration.probe_id
        auth_header = f"Bearer {registration.auth_token}"

        provider = await registry_service.create_provider(
            ModelProviderCreate(
                name=provider_name,
                api_format="chat-completions",
                base_url="https://example.com/v1",
                api_key="provider-secret",
                description="pytest",
            )
        )
        provider_id = UUID(str(provider.id))

        created_task = await service.create_task(
            ProbeTaskCreate(
                probe_id=probe_id,
                name="pytest provider perf",
                config=EvalScopePerfTaskConfig(
                    model="demo-model",
                    provider_id=provider_id,
                    prompt="hello",
                    number=2,
                    parallel=1,
                ),
            )
        )
        task_id = created_task.id

        stored_config = created_task.payload_json["config"]
        assert stored_config["provider_id"] == str(provider_id)
        assert stored_config["provider_name"] == provider_name
        assert "api_key" not in stored_config
        assert "api_key_env" not in stored_config
        assert "url" not in stored_config

        claimed = await service.claim_task(str(probe_id), authorization=auth_header)
        assert claimed.task is not None
        assert claimed.task.id == task_id

        runtime_config = await service.get_task_runtime_config(
            str(task_id),
            authorization=auth_header,
        )

        assert runtime_config.task_id == task_id
        assert runtime_config.config.provider_id == provider_id
        assert runtime_config.config.provider_name == provider_name
        assert runtime_config.config.url == "https://example.com/v1/chat/completions"
        assert runtime_config.config.api == "openai"
        assert runtime_config.config.api_key == "provider-secret"
        assert runtime_config.config.api_key_env is None
    finally:
        async with SessionLocal() as session:
            if task_id is not None:
                await session.execute(delete(ProbeTask).where(ProbeTask.id == task_id))
            if probe_id is not None:
                await session.execute(
                    delete(ProbeHeartbeat).where(ProbeHeartbeat.probe_id == probe_id)
                )
                await session.execute(delete(Probe).where(Probe.id == probe_id))
            if provider_id is not None:
                await session.execute(delete(ModelProvider).where(ModelProvider.id == provider_id))
            await session.commit()
