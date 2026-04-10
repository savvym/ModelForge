from __future__ import annotations

import hashlib
import hmac
import secrets
from datetime import UTC, datetime, timedelta
from uuid import UUID

from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from nta_backend.core.auth_context import resolve_current_user
from nta_backend.core.config import get_settings
from nta_backend.core.db import SessionLocal
from nta_backend.core.project_context import resolve_active_project_id
from nta_backend.models.probe import Probe, ProbeHeartbeat, ProbeTask
from nta_backend.schemas.probe import (
    ProbeDetail,
    ProbeHeartbeatRequest,
    ProbeHeartbeatResponse,
    ProbeHeartbeatSummary,
    ProbeRegistrationRequest,
    ProbeRegistrationResponse,
    ProbeSummary,
    ProbeTaskClaim,
    ProbeTaskClaimResponse,
    ProbeTaskCompleteRequest,
    ProbeTaskCreate,
    ProbeTaskDetail,
    ProbeTaskFailRequest,
    ProbeTaskProgressRequest,
    ProbeTaskStartRequest,
    ProbeTaskSummary,
    ProbeTaskTransitionResponse,
)


def _utc_now() -> datetime:
    return datetime.now(UTC)


def _normalize_bearer_token(authorization: str | None) -> str | None:
    if not authorization:
        return None
    prefix = "bearer "
    if authorization.lower().startswith(prefix):
        token = authorization[len(prefix) :].strip()
        return token or None
    return authorization.strip() or None


def _truncate_error(value: str | None) -> str | None:
    if value is None:
        return None
    normalized = " ".join(value.split())
    return normalized[:1000]


def _effective_probe_status(probe: Probe) -> str:
    if probe.status == "disabled":
        return "disabled"
    timeout_seconds = get_settings().probe_heartbeat_timeout_seconds
    if probe.last_heartbeat is None:
        return "offline"
    if _utc_now() - probe.last_heartbeat <= timedelta(seconds=timeout_seconds):
        return "online"
    return "offline"


def _hash_probe_token(token: str) -> str:
    secret = get_settings().secret_key.get_secret_value().encode("utf-8")
    return hmac.new(secret, token.encode("utf-8"), hashlib.sha256).hexdigest()


def _issue_probe_token() -> str:
    return f"ntp_{secrets.token_urlsafe(32)}"


def _serialize_probe(probe: Probe) -> ProbeSummary:
    return ProbeSummary(
        id=probe.id,
        name=probe.name,
        display_name=probe.display_name,
        status=_effective_probe_status(probe),
        ip_address=probe.ip_address,
        isp=probe.isp,
        asn=probe.asn,
        region=probe.region,
        country=probe.country,
        city=probe.city,
        network_type=probe.network_type,
        tags_json=list(probe.tags_json or []),
        agent_version=probe.agent_version,
        device_info_json=dict(probe.device_info_json or {}),
        metadata_json=dict(probe.metadata_json or {}),
        last_heartbeat=probe.last_heartbeat,
        last_error_message=probe.last_error_message,
        created_at=probe.created_at,
        updated_at=probe.updated_at,
    )


def _serialize_task(task: ProbeTask) -> ProbeTaskSummary:
    return ProbeTaskSummary(
        id=task.id,
        probe_id=task.probe_id,
        name=task.name,
        task_type=task.task_type,
        status=task.status,
        timeout_seconds=task.timeout_seconds,
        attempt_count=task.attempt_count,
        payload_json=dict(task.payload_json or {}),
        progress_json=dict(task.progress_json or {}),
        result_json=dict(task.result_json or {}) if task.result_json is not None else None,
        error_message=task.error_message,
        claimed_at=task.claimed_at,
        started_at=task.started_at,
        finished_at=task.finished_at,
        lease_expires_at=task.lease_expires_at,
        created_at=task.created_at,
        updated_at=task.updated_at,
    )


def _serialize_task_claim(task: ProbeTask) -> ProbeTaskClaim:
    return ProbeTaskClaim(
        id=task.id,
        probe_id=task.probe_id,
        name=task.name,
        task_type=task.task_type,
        timeout_seconds=task.timeout_seconds,
        attempt_count=task.attempt_count,
        payload_json=dict(task.payload_json or {}),
        created_at=task.created_at,
        lease_expires_at=task.lease_expires_at,
    )


class ProbeService:
    async def list_probes(self) -> list[ProbeSummary]:
        async with SessionLocal() as session:
            project_id = await resolve_active_project_id(session)
            rows = await session.execute(
                select(Probe)
                .where(Probe.project_id == project_id)
                .order_by(Probe.updated_at.desc(), Probe.created_at.desc())
            )
            return [_serialize_probe(probe) for probe in rows.scalars().all()]

    async def get_probe(self, probe_id: str) -> ProbeDetail:
        async with SessionLocal() as session:
            project_id = await resolve_active_project_id(session)
            probe = await self._get_probe_or_raise(
                session,
                project_id=project_id,
                probe_id=UUID(probe_id),
            )
            heartbeat_rows = await session.execute(
                select(ProbeHeartbeat)
                .where(ProbeHeartbeat.probe_id == probe.id)
                .order_by(ProbeHeartbeat.created_at.desc())
                .limit(20)
            )
            summary = _serialize_probe(probe)
            return ProbeDetail(
                **summary.model_dump(),
                heartbeats=[
                    ProbeHeartbeatSummary(
                        ip_address=heartbeat.ip_address,
                        network_metrics_json=dict(heartbeat.network_metrics_json or {}),
                        agent_status_json=dict(heartbeat.agent_status_json or {}),
                        created_at=heartbeat.created_at,
                    )
                    for heartbeat in heartbeat_rows.scalars().all()
                ],
            )

    async def delete_probe(self, probe_id: str) -> None:
        async with SessionLocal() as session:
            project_id = await resolve_active_project_id(session)
            probe = await self._get_probe_or_raise(
                session,
                project_id=project_id,
                probe_id=UUID(probe_id),
            )
            if _effective_probe_status(probe) == "online":
                raise ValueError("Only offline probes can be deleted.")
            await session.delete(probe)
            await session.commit()

    async def create_task(self, payload: ProbeTaskCreate) -> ProbeTaskDetail:
        async with SessionLocal() as session:
            project_id = await resolve_active_project_id(session)
            user = await resolve_current_user(session)
            probe = await self._get_probe_or_raise(
                session,
                project_id=project_id,
                probe_id=payload.probe_id,
            )
            task = ProbeTask(
                project_id=project_id,
                probe_id=probe.id,
                name=(payload.name or f"{payload.runtime_kind}:{probe.name}").strip(),
                task_type=payload.runtime_kind,
                status="queued",
                timeout_seconds=payload.timeout_seconds,
                attempt_count=0,
                payload_json={
                    "runtime_kind": payload.runtime_kind,
                    "timeout_seconds": payload.timeout_seconds,
                    "config": payload.config.model_dump(mode="json"),
                },
                progress_json={},
                created_by=user.id,
            )
            session.add(task)
            await session.commit()
            await session.refresh(task)
            return ProbeTaskDetail(**_serialize_task(task).model_dump())

    async def list_tasks(
        self,
        *,
        probe_id: str | None = None,
        status: str | None = None,
    ) -> list[ProbeTaskSummary]:
        async with SessionLocal() as session:
            project_id = await resolve_active_project_id(session)
            query = select(ProbeTask).where(ProbeTask.project_id == project_id)
            if probe_id:
                query = query.where(ProbeTask.probe_id == UUID(probe_id))
            if status:
                query = query.where(ProbeTask.status == status)
            rows = await session.execute(
                query.order_by(ProbeTask.created_at.desc(), ProbeTask.id.desc())
            )
            return [_serialize_task(task) for task in rows.scalars().all()]

    async def get_task(self, task_id: str) -> ProbeTaskDetail:
        async with SessionLocal() as session:
            project_id = await resolve_active_project_id(session)
            task = await self._get_task_or_raise(
                session,
                project_id=project_id,
                task_id=UUID(task_id),
            )
            return ProbeTaskDetail(**_serialize_task(task).model_dump())

    async def register_probe(
        self,
        payload: ProbeRegistrationRequest,
        *,
        authorization: str | None,
        client_ip: str | None,
    ) -> ProbeRegistrationResponse:
        self._validate_registration_token(authorization)
        async with SessionLocal() as session:
            project_id = await resolve_active_project_id(session)
            user = await resolve_current_user(session)
            now = _utc_now()
            rows = await session.execute(
                select(Probe).where(
                    Probe.project_id == project_id,
                    Probe.name == payload.name.strip(),
                )
            )
            probe = rows.scalar_one_or_none()
            auth_token = _issue_probe_token()
            if probe is None:
                probe = Probe(
                    project_id=project_id,
                    name=payload.name.strip(),
                    display_name=(payload.display_name or payload.name).strip(),
                    status="online",
                    ip_address=client_ip,
                    isp=payload.isp,
                    asn=payload.asn,
                    region=payload.region,
                    country=payload.country,
                    city=payload.city,
                    network_type=payload.network_type,
                    tags_json=list(payload.tags),
                    agent_version=payload.agent_version,
                    device_info_json=payload.device_info,
                    metadata_json=payload.metadata,
                    last_heartbeat=now,
                    auth_token_hash=_hash_probe_token(auth_token),
                    created_by=user.id,
                )
                session.add(probe)
            else:
                if probe.status == "disabled":
                    raise ValueError("Probe is disabled and cannot re-register.")
                probe.display_name = (payload.display_name or payload.name).strip()
                probe.status = "online"
                probe.ip_address = client_ip or probe.ip_address
                probe.isp = payload.isp
                probe.asn = payload.asn
                probe.region = payload.region
                probe.country = payload.country
                probe.city = payload.city
                probe.network_type = payload.network_type
                probe.tags_json = list(payload.tags)
                probe.agent_version = payload.agent_version
                probe.device_info_json = payload.device_info
                probe.metadata_json = payload.metadata
                probe.last_heartbeat = now
                probe.last_error_message = None
                probe.auth_token_hash = _hash_probe_token(auth_token)
            await session.commit()
            await session.refresh(probe)
            settings = get_settings()
            return ProbeRegistrationResponse(
                probe_id=probe.id,
                name=probe.name,
                display_name=probe.display_name,
                status=_effective_probe_status(probe),
                auth_token=auth_token,
                heartbeat_interval_seconds=settings.probe_heartbeat_timeout_seconds // 3 or 30,
                claim_ttl_seconds=settings.probe_task_claim_ttl_seconds,
            )

    async def heartbeat(
        self,
        probe_id: str,
        payload: ProbeHeartbeatRequest,
        *,
        authorization: str | None,
        client_ip: str | None,
    ) -> ProbeHeartbeatResponse:
        async with SessionLocal() as session:
            probe = await self._authenticate_probe(
                session,
                probe_id=UUID(probe_id),
                authorization=authorization,
            )
            now = _utc_now()
            probe.last_heartbeat = now
            probe.status = "online"
            if client_ip:
                probe.ip_address = client_ip
            session.add(
                ProbeHeartbeat(
                    probe_id=probe.id,
                    ip_address=client_ip or probe.ip_address or "unknown",
                    network_metrics_json=dict(payload.network_metrics or {}),
                    agent_status_json=dict(payload.agent_status or {}),
                    created_at=now,
                )
            )
            await session.commit()
            return ProbeHeartbeatResponse(status="ok", server_time=now)

    async def claim_task(
        self,
        probe_id: str,
        *,
        authorization: str | None,
    ) -> ProbeTaskClaimResponse:
        async with SessionLocal() as session:
            probe = await self._authenticate_probe(
                session,
                probe_id=UUID(probe_id),
                authorization=authorization,
            )
            now = _utc_now()
            lease_deadline = now + timedelta(seconds=get_settings().probe_task_claim_ttl_seconds)
            row = await session.execute(
                select(ProbeTask)
                .where(
                    ProbeTask.project_id == probe.project_id,
                    ProbeTask.probe_id == probe.id,
                    or_(
                        ProbeTask.status == "queued",
                        (ProbeTask.status == "claimed") & (ProbeTask.lease_expires_at < now),
                        (ProbeTask.status == "running") & (ProbeTask.lease_expires_at < now),
                    ),
                )
                .order_by(ProbeTask.created_at.asc(), ProbeTask.id.asc())
                .with_for_update(skip_locked=True)
            )
            task = row.scalars().first()
            if task is None:
                return ProbeTaskClaimResponse(task=None)
            was_running = task.status == "running"
            task.status = "claimed"
            task.claimed_at = now
            task.lease_expires_at = lease_deadline
            if was_running:
                task.started_at = None
            task.attempt_count = int(task.attempt_count or 0) + 1
            task.error_message = None
            await session.commit()
            await session.refresh(task)
            return ProbeTaskClaimResponse(task=_serialize_task_claim(task))

    async def start_task(
        self,
        task_id: str,
        payload: ProbeTaskStartRequest,
        *,
        authorization: str | None,
    ) -> ProbeTaskTransitionResponse:
        async with SessionLocal() as session:
            task = await self._authenticate_task(
                session,
                task_id=UUID(task_id),
                authorization=authorization,
            )
            if task.status not in {"claimed", "running"}:
                raise ValueError(
                    f"Task {task.id} is not claimable for start in status {task.status}."
                )
            now = _utc_now()
            task.status = "running"
            task.started_at = task.started_at or now
            task.lease_expires_at = now + timedelta(
                seconds=get_settings().probe_task_claim_ttl_seconds
            )
            task.progress_json = {
                **dict(task.progress_json or {}),
                "summary": payload.summary or "Task started.",
                "started_at": now.isoformat(),
            }
            await session.commit()
            return ProbeTaskTransitionResponse(task_id=task.id, status=task.status)

    async def report_progress(
        self,
        task_id: str,
        payload: ProbeTaskProgressRequest,
        *,
        authorization: str | None,
    ) -> ProbeTaskTransitionResponse:
        async with SessionLocal() as session:
            task = await self._authenticate_task(
                session,
                task_id=UUID(task_id),
                authorization=authorization,
            )
            if task.status not in {"claimed", "running"}:
                raise ValueError(
                    f"Task {task.id} cannot report progress in status {task.status}."
                )
            now = _utc_now()
            task.status = "running"
            task.lease_expires_at = now + timedelta(
                seconds=get_settings().probe_task_claim_ttl_seconds
            )
            progress = dict(task.progress_json or {})
            if payload.summary is not None:
                progress["summary"] = payload.summary
            if payload.step is not None:
                progress["step"] = payload.step
            if payload.total is not None:
                progress["total"] = payload.total
            progress.update(payload.payload or {})
            progress["updated_at"] = now.isoformat()
            task.progress_json = progress
            await session.commit()
            return ProbeTaskTransitionResponse(task_id=task.id, status=task.status)

    async def complete_task(
        self,
        task_id: str,
        payload: ProbeTaskCompleteRequest,
        *,
        authorization: str | None,
    ) -> ProbeTaskTransitionResponse:
        async with SessionLocal() as session:
            task = await self._authenticate_task(
                session,
                task_id=UUID(task_id),
                authorization=authorization,
            )
            now = _utc_now()
            task.status = "completed"
            task.finished_at = now
            task.lease_expires_at = None
            task.result_json = dict(payload.result_json or {})
            task.error_message = None
            task.progress_json = {
                **dict(task.progress_json or {}),
                "summary": "Task completed.",
                "step": 1,
                "total": 1,
                "updated_at": now.isoformat(),
            }
            await session.commit()
            return ProbeTaskTransitionResponse(task_id=task.id, status=task.status)

    async def fail_task(
        self,
        task_id: str,
        payload: ProbeTaskFailRequest,
        *,
        authorization: str | None,
    ) -> ProbeTaskTransitionResponse:
        async with SessionLocal() as session:
            task = await self._authenticate_task(
                session,
                task_id=UUID(task_id),
                authorization=authorization,
            )
            now = _utc_now()
            task.status = "failed"
            task.finished_at = now
            task.lease_expires_at = None
            task.error_message = _truncate_error(payload.error_message)
            task.result_json = (
                dict(payload.result_json or {}) if payload.result_json is not None else None
            )
            task.progress_json = {
                **dict(task.progress_json or {}),
                "summary": "Task failed.",
                "updated_at": now.isoformat(),
            }
            probe = await session.get(Probe, task.probe_id)
            if probe is not None:
                probe.last_error_message = task.error_message
            await session.commit()
            return ProbeTaskTransitionResponse(task_id=task.id, status=task.status)

    async def _get_probe_or_raise(
        self,
        session: AsyncSession,
        *,
        project_id: UUID,
        probe_id: UUID,
    ) -> Probe:
        row = await session.execute(
            select(Probe).where(
                Probe.id == probe_id,
                Probe.project_id == project_id,
            )
        )
        probe = row.scalar_one_or_none()
        if probe is None:
            raise KeyError(str(probe_id))
        return probe

    async def _get_task_or_raise(
        self,
        session: AsyncSession,
        *,
        project_id: UUID,
        task_id: UUID,
    ) -> ProbeTask:
        row = await session.execute(
            select(ProbeTask).where(
                ProbeTask.id == task_id,
                ProbeTask.project_id == project_id,
            )
        )
        task = row.scalar_one_or_none()
        if task is None:
            raise KeyError(str(task_id))
        return task

    async def _authenticate_probe(
        self,
        session: AsyncSession,
        *,
        probe_id: UUID,
        authorization: str | None,
    ) -> Probe:
        token = _normalize_bearer_token(authorization)
        if token is None:
            raise PermissionError("Missing probe token.")
        row = await session.execute(select(Probe).where(Probe.id == probe_id))
        probe = row.scalar_one_or_none()
        if probe is None:
            raise KeyError(str(probe_id))
        if not probe.auth_token_hash:
            raise PermissionError("Probe token is not configured.")
        if not secrets.compare_digest(probe.auth_token_hash, _hash_probe_token(token)):
            raise PermissionError("Invalid probe token.")
        return probe

    async def _authenticate_task(
        self,
        session: AsyncSession,
        *,
        task_id: UUID,
        authorization: str | None,
    ) -> ProbeTask:
        row = await session.execute(select(ProbeTask).where(ProbeTask.id == task_id))
        task = row.scalar_one_or_none()
        if task is None:
            raise KeyError(str(task_id))
        await self._authenticate_probe(session, probe_id=task.probe_id, authorization=authorization)
        return task

    def _validate_registration_token(self, authorization: str | None) -> None:
        expected = get_settings().probe_registration_token
        if expected is None:
            return
        token = _normalize_bearer_token(authorization)
        secret = expected.get_secret_value()
        if token is None or not secrets.compare_digest(token, secret):
            raise PermissionError("Invalid probe registration token.")
