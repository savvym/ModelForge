from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import selectinload

from nta_backend.core.db import SessionLocal
from nta_backend.core.project_context import resolve_active_project_id
from nta_backend.core.storage_layout import build_eval_job_code
from nta_backend.models.benchmark_leaderboard import (
    BenchmarkLeaderboard,
    BenchmarkLeaderboardJob,
)
from nta_backend.models.jobs import EvalJob, EvalJobMetric
from nta_backend.schemas.benchmark_leaderboard import (
    BenchmarkLeaderboardAddJobs,
    BenchmarkLeaderboardCreate,
    BenchmarkLeaderboardDetail,
    BenchmarkLeaderboardEntry,
    BenchmarkLeaderboardJobCandidate,
    BenchmarkLeaderboardSummary,
)
from nta_backend.services.benchmark_catalog_service import (
    get_benchmark_definition_record,
    resolve_benchmark_version_record,
)


@dataclass(frozen=True)
class _MetricValue:
    metric_name: str
    score: float


def _normalize_required_text(value: str | None, field_name: str) -> str:
    normalized = (value or "").strip()
    if not normalized:
        raise ValueError(f"{field_name} 不能为空。")
    return normalized


async def _load_single_leaderboard(
    session,
    *,
    project_id: UUID,
    leaderboard_id: UUID,
) -> BenchmarkLeaderboard | None:
    row = await session.execute(
        select(BenchmarkLeaderboard)
        .options(
            selectinload(BenchmarkLeaderboard.benchmark),
            selectinload(BenchmarkLeaderboard.benchmark_version),
            selectinload(BenchmarkLeaderboard.jobs).selectinload(BenchmarkLeaderboardJob.eval_job),
        )
        .where(
            BenchmarkLeaderboard.project_id == project_id,
            BenchmarkLeaderboard.id == leaderboard_id,
        )
    )
    return row.scalar_one_or_none()


async def _load_metric_map_for_jobs(
    session,
    *,
    job_ids: list[UUID],
    preferred_metric_names: list[str],
) -> dict[UUID, _MetricValue]:
    if not job_ids:
        return {}

    rows = await session.execute(
        select(EvalJobMetric)
        .where(EvalJobMetric.eval_job_id.in_(job_ids))
        .order_by(EvalJobMetric.created_at.asc(), EvalJobMetric.id.asc())
    )

    preferred = set(preferred_metric_names)
    selected: dict[UUID, _MetricValue] = {}
    fallback: dict[UUID, _MetricValue] = {}
    for row in rows.scalars().all():
        metric = _MetricValue(metric_name=row.metric_name, score=row.metric_value)
        fallback.setdefault(row.eval_job_id, metric)
        if preferred and row.metric_name in preferred and row.eval_job_id not in selected:
            selected[row.eval_job_id] = metric

    for job_id, metric in fallback.items():
        selected.setdefault(job_id, metric)
    return selected


async def _list_eligible_jobs(
    session,
    *,
    project_id: UUID,
    benchmark_name: str,
    benchmark_version_id: str,
    preferred_metric_names: list[str],
    exclude_job_ids: set[UUID] | None = None,
) -> list[BenchmarkLeaderboardJobCandidate]:
    rows = await session.execute(
        select(EvalJob)
        .where(
            EvalJob.project_id == project_id,
            EvalJob.benchmark_name == benchmark_name,
            EvalJob.benchmark_version_id == benchmark_version_id,
            EvalJob.status == "completed",
        )
        .order_by(EvalJob.created_at.desc(), EvalJob.id.desc())
    )
    jobs = list(rows.scalars().all())
    if exclude_job_ids:
        jobs = [job for job in jobs if job.id not in exclude_job_ids]

    metric_map = await _load_metric_map_for_jobs(
        session,
        job_ids=[job.id for job in jobs],
        preferred_metric_names=preferred_metric_names,
    )

    candidates: list[BenchmarkLeaderboardJobCandidate] = []
    for job in jobs:
        metric = metric_map.get(job.id)
        if metric is None:
            continue
        candidates.append(
            BenchmarkLeaderboardJobCandidate(
                eval_job_id=build_eval_job_code(job.created_at, job.id),
                eval_job_name=job.name,
                model_name=job.model_name or "-",
                model_source=job.model_source,
                score=metric.score,
                metric_name=metric.metric_name,
                created_at=job.created_at,
                finished_at=job.finished_at,
                judge_model_name=job.judge_model_name,
            )
        )
    return candidates


def _latest_eval_at(record: BenchmarkLeaderboard) -> datetime | None:
    latest: datetime | None = None
    for link in record.jobs:
        job = link.eval_job
        if job is None:
            continue
        candidate = job.finished_at or job.created_at
        if latest is None or candidate > latest:
            latest = candidate
    return latest


def _score_metric_name(
    record: BenchmarkLeaderboard,
    *,
    entries: list[BenchmarkLeaderboardEntry] | None = None,
) -> str | None:
    benchmark = record.benchmark
    metric_names = list(benchmark.metric_names or []) if benchmark is not None else []
    if metric_names:
        return metric_names[0]
    if entries:
        return entries[0].metric_name
    return None


def _serialize_summary(
    record: BenchmarkLeaderboard,
    *,
    entries: list[BenchmarkLeaderboardEntry] | None = None,
) -> BenchmarkLeaderboardSummary:
    benchmark = record.benchmark
    version = record.benchmark_version
    if benchmark is None or version is None:
        raise ValueError("排行榜缺少 Benchmark 或 Version 关联。")

    return BenchmarkLeaderboardSummary(
        id=record.id,
        name=record.name,
        benchmark_name=benchmark.name,
        benchmark_display_name=benchmark.display_name,
        benchmark_version_id=version.version_id,
        benchmark_version_display_name=version.display_name,
        score_metric_name=_score_metric_name(record, entries=entries),
        job_count=len(record.jobs),
        latest_eval_at=_latest_eval_at(record),
        created_at=record.created_at,
        updated_at=record.updated_at,
    )


async def _build_entries(
    session,
    *,
    record: BenchmarkLeaderboard,
) -> list[BenchmarkLeaderboardEntry]:
    benchmark = record.benchmark
    metric_names = list(benchmark.metric_names or []) if benchmark is not None else []
    jobs = [link.eval_job for link in record.jobs if link.eval_job is not None]
    metric_map = await _load_metric_map_for_jobs(
        session,
        job_ids=[job.id for job in jobs],
        preferred_metric_names=metric_names,
    )

    scored_rows = []
    for job in jobs:
        metric = metric_map.get(job.id)
        if metric is None:
            continue
        scored_rows.append((job, metric))

    scored_rows.sort(
        key=lambda item: (
            -item[1].score,
            -(item[0].finished_at or item[0].created_at).timestamp(),
            item[0].name,
        )
    )

    entries: list[BenchmarkLeaderboardEntry] = []
    for index, (job, metric) in enumerate(scored_rows, start=1):
        entries.append(
            BenchmarkLeaderboardEntry(
                rank=index,
                eval_job_id=build_eval_job_code(job.created_at, job.id),
                eval_job_name=job.name,
                model_name=job.model_name or "-",
                model_source=job.model_source,
                score=metric.score,
                metric_name=metric.metric_name,
                created_at=job.created_at,
                finished_at=job.finished_at,
                judge_model_name=job.judge_model_name,
            )
        )
    return entries


class BenchmarkLeaderboardService:
    async def list_leaderboards(self) -> list[BenchmarkLeaderboardSummary]:
        async with SessionLocal() as session:
            project_id = await resolve_active_project_id(session)
            rows = await session.execute(
                select(BenchmarkLeaderboard)
                .options(
                    selectinload(BenchmarkLeaderboard.benchmark),
                    selectinload(BenchmarkLeaderboard.benchmark_version),
                    selectinload(BenchmarkLeaderboard.jobs).selectinload(
                        BenchmarkLeaderboardJob.eval_job
                    ),
                )
                .where(BenchmarkLeaderboard.project_id == project_id)
                .order_by(BenchmarkLeaderboard.created_at.desc(), BenchmarkLeaderboard.id.desc())
            )
            return [_serialize_summary(record) for record in rows.scalars().all()]

    async def get_leaderboard(self, leaderboard_id: UUID) -> BenchmarkLeaderboardDetail:
        async with SessionLocal() as session:
            project_id = await resolve_active_project_id(session)
            record = await _load_single_leaderboard(
                session,
                project_id=project_id,
                leaderboard_id=leaderboard_id,
            )
            if record is None:
                raise KeyError(str(leaderboard_id))

            entries = await _build_entries(session, record=record)
            summary = _serialize_summary(record, entries=entries)
            return BenchmarkLeaderboardDetail(**summary.model_dump(), entries=entries)

    async def list_available_jobs(
        self,
        *,
        benchmark_name: str,
        benchmark_version_id: str,
        exclude_leaderboard_id: UUID | None = None,
    ) -> list[BenchmarkLeaderboardJobCandidate]:
        async with SessionLocal() as session:
            project_id = await resolve_active_project_id(session)
            definition = await get_benchmark_definition_record(session, benchmark_name)
            if definition is None:
                raise KeyError(benchmark_name)
            _, version = await resolve_benchmark_version_record(
                session,
                benchmark_name=benchmark_name,
                version_id=benchmark_version_id,
            )
            if version is None:
                raise KeyError(benchmark_version_id)

            excluded_job_ids: set[UUID] = set()
            if exclude_leaderboard_id is not None:
                leaderboard = await _load_single_leaderboard(
                    session,
                    project_id=project_id,
                    leaderboard_id=exclude_leaderboard_id,
                )
                if leaderboard is None:
                    raise KeyError(str(exclude_leaderboard_id))
                excluded_job_ids = {
                    link.eval_job_id
                    for link in leaderboard.jobs
                }

            return await _list_eligible_jobs(
                session,
                project_id=project_id,
                benchmark_name=definition.name,
                benchmark_version_id=version.version_id,
                preferred_metric_names=list(definition.metric_names or []),
                exclude_job_ids=excluded_job_ids,
            )

    async def create_leaderboard(
        self,
        payload: BenchmarkLeaderboardCreate,
    ) -> BenchmarkLeaderboardSummary:
        async with SessionLocal() as session:
            project_id = await resolve_active_project_id(session)
            name = _normalize_required_text(payload.name, "name")

            definition = await get_benchmark_definition_record(session, payload.benchmark_name)
            if definition is None:
                raise ValueError("所选 Benchmark 不存在。")
            _, version = await resolve_benchmark_version_record(
                session,
                benchmark_name=definition.name,
                version_id=payload.benchmark_version_id,
            )
            if version is None:
                raise ValueError("所选 Benchmark Version 不存在。")

            eligible_jobs = await _list_eligible_jobs(
                session,
                project_id=project_id,
                benchmark_name=definition.name,
                benchmark_version_id=version.version_id,
                preferred_metric_names=list(definition.metric_names or []),
            )
            eligible_map = {job.eval_job_id: job for job in eligible_jobs}
            rows = await session.execute(
                select(EvalJob)
                .where(
                    EvalJob.project_id == project_id,
                    EvalJob.benchmark_name == definition.name,
                    EvalJob.benchmark_version_id == version.version_id,
                    EvalJob.status == "completed",
                )
                .order_by(EvalJob.created_at.desc(), EvalJob.id.desc())
            )
            job_map = {
                build_eval_job_code(job.created_at, job.id): job
                for job in rows.scalars().all()
            }

            requested_job_ids = list(dict.fromkeys(payload.eval_job_ids))
            invalid_job_ids = [job_id for job_id in requested_job_ids if job_id not in eligible_map]
            if invalid_job_ids:
                raise ValueError(
                    "所选评测任务必须属于当前 Benchmark Version，且任务已完成并产生得分。"
                )

            record = BenchmarkLeaderboard(
                project_id=project_id,
                name=name,
                benchmark_id=definition.id,
                benchmark_version_row_id=version.id,
            )
            session.add(record)
            await session.flush()

            for job_id in requested_job_ids:
                matched_job = job_map.get(job_id)
                if matched_job is None:
                    raise ValueError(f"评测任务 {job_id} 不存在。")
                session.add(
                    BenchmarkLeaderboardJob(
                        leaderboard_id=record.id,
                        eval_job_id=matched_job.id,
                    )
                )

            try:
                await session.commit()
            except IntegrityError as exc:
                await session.rollback()
                raise ValueError("排行榜创建失败，名称可能已存在。") from exc

            record = await _load_single_leaderboard(
                session,
                project_id=project_id,
                leaderboard_id=record.id,
            )
            if record is None:
                raise ValueError("排行榜创建失败。")
            return _serialize_summary(record)

    async def add_jobs(
        self,
        leaderboard_id: UUID,
        payload: BenchmarkLeaderboardAddJobs,
    ) -> BenchmarkLeaderboardDetail:
        async with SessionLocal() as session:
            project_id = await resolve_active_project_id(session)
            record = await _load_single_leaderboard(
                session,
                project_id=project_id,
                leaderboard_id=leaderboard_id,
            )
            if record is None:
                raise KeyError(str(leaderboard_id))

            benchmark = record.benchmark
            version = record.benchmark_version
            if benchmark is None or version is None:
                raise ValueError("排行榜缺少 Benchmark 或 Version 关联。")

            excluded_job_ids = {link.eval_job_id for link in record.jobs}
            eligible_jobs = await _list_eligible_jobs(
                session,
                project_id=project_id,
                benchmark_name=benchmark.name,
                benchmark_version_id=version.version_id,
                preferred_metric_names=list(benchmark.metric_names or []),
                exclude_job_ids=excluded_job_ids,
            )
            eligible_map = {job.eval_job_id: job for job in eligible_jobs}
            requested_job_ids = list(dict.fromkeys(payload.eval_job_ids))
            invalid_job_ids = [job_id for job_id in requested_job_ids if job_id not in eligible_map]
            if invalid_job_ids:
                raise ValueError("存在不可加入排行榜的评测任务。")

            rows = await session.execute(
                select(EvalJob)
                .where(
                    EvalJob.project_id == project_id,
                    EvalJob.benchmark_name == benchmark.name,
                    EvalJob.benchmark_version_id == version.version_id,
                    EvalJob.status == "completed",
                )
                .order_by(EvalJob.created_at.desc(), EvalJob.id.desc())
            )
            job_map = {
                build_eval_job_code(job.created_at, job.id): job
                for job in rows.scalars().all()
            }

            for job_id in requested_job_ids:
                job = job_map.get(job_id)
                if job is None:
                    raise ValueError(f"评测任务 {job_id} 不存在。")
                session.add(
                    BenchmarkLeaderboardJob(
                        leaderboard_id=record.id,
                        eval_job_id=job.id,
                    )
                )

            try:
                await session.commit()
            except IntegrityError as exc:
                await session.rollback()
                raise ValueError("添加评测任务失败。") from exc

        return await self.get_leaderboard(leaderboard_id)

    async def remove_job(
        self,
        leaderboard_id: UUID,
        eval_job_identifier: str,
    ) -> None:
        async with SessionLocal() as session:
            project_id = await resolve_active_project_id(session)
            record = await _load_single_leaderboard(
                session,
                project_id=project_id,
                leaderboard_id=leaderboard_id,
            )
            if record is None:
                raise KeyError(str(leaderboard_id))

            target = next(
                (
                    link
                    for link in record.jobs
                    if link.eval_job is not None
                    and build_eval_job_code(link.eval_job.created_at, link.eval_job.id)
                    == eval_job_identifier
                ),
                None,
            )
            if target is None:
                raise KeyError(eval_job_identifier)

            await session.delete(target)
            await session.commit()

    async def delete_leaderboard(self, leaderboard_id: UUID) -> None:
        async with SessionLocal() as session:
            project_id = await resolve_active_project_id(session)
            record = await _load_single_leaderboard(
                session,
                project_id=project_id,
                leaderboard_id=leaderboard_id,
            )
            if record is None:
                raise KeyError(str(leaderboard_id))
            await session.delete(record)
            await session.commit()
