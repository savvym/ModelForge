from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from uuid import UUID

from sqlalchemy import or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import selectinload

from nta_backend.core.db import SessionLocal
from nta_backend.core.project_context import resolve_active_project_id
from nta_backend.models.evaluation_v2 import (
    EvalSpec,
    EvalSpecVersion,
    EvalSuite,
    EvalSuiteVersion,
    EvaluationLeaderboard,
    EvaluationLeaderboardRun,
    EvaluationRun,
    EvaluationRunMetric,
)
from nta_backend.schemas.evaluation_v2 import (
    EvaluationLeaderboardAddRuns,
    EvaluationLeaderboardCreate,
    EvaluationLeaderboardDetail,
    EvaluationLeaderboardEntry,
    EvaluationLeaderboardRunCandidate,
    EvaluationLeaderboardSummary,
)


@dataclass(slots=True)
class _MetricValue:
    metric_name: str
    score: float


@dataclass(slots=True)
class _ResolvedTarget:
    kind: str
    spec: EvalSpec | None = None
    spec_version: EvalSpecVersion | None = None
    suite: EvalSuite | None = None
    suite_version: EvalSuiteVersion | None = None

    @property
    def display_name(self) -> str:
        if self.kind == "suite":
            if self.suite is None:
                raise ValueError("Leaderboard target suite is missing.")
            return self.suite.display_name
        if self.spec is None:
            raise ValueError("Leaderboard target spec is missing.")
        return self.spec.display_name

    @property
    def version(self) -> str:
        if self.kind == "suite":
            if self.suite_version is None:
                raise ValueError("Leaderboard target suite version is missing.")
            return self.suite_version.version
        if self.spec_version is None:
            raise ValueError("Leaderboard target spec version is missing.")
        return self.spec_version.version

    @property
    def version_display_name(self) -> str:
        if self.kind == "suite":
            if self.suite_version is None:
                raise ValueError("Leaderboard target suite version is missing.")
            return self.suite_version.display_name
        if self.spec_version is None:
            raise ValueError("Leaderboard target spec version is missing.")
        return self.spec_version.display_name

    @property
    def name(self) -> str:
        if self.kind == "suite":
            if self.suite is None:
                raise ValueError("Leaderboard target suite is missing.")
            return self.suite.name
        if self.spec is None:
            raise ValueError("Leaderboard target spec is missing.")
        return self.spec.name


async def _resolve_target(
    session,
    *,
    project_id: UUID,
    kind: str,
    name: str,
    version: str,
) -> _ResolvedTarget:
    if kind == "spec":
        rows = await session.execute(
            select(EvalSpecVersion)
            .join(EvalSpec, EvalSpec.id == EvalSpecVersion.spec_id)
            .options(selectinload(EvalSpecVersion.spec))
            .where(
                EvalSpec.name == name,
                EvalSpecVersion.version == version,
                or_(EvalSpec.project_id == project_id, EvalSpec.project_id.is_(None)),
            )
        )
        spec_version = rows.scalar_one_or_none()
        if spec_version is None:
            raise KeyError(name)
        return _ResolvedTarget(
            kind="spec",
            spec=spec_version.spec,
            spec_version=spec_version,
        )

    rows = await session.execute(
        select(EvalSuiteVersion)
        .join(EvalSuite, EvalSuite.id == EvalSuiteVersion.suite_id)
        .options(selectinload(EvalSuiteVersion.suite))
        .where(
            EvalSuite.name == name,
            EvalSuiteVersion.version == version,
            or_(EvalSuite.project_id == project_id, EvalSuite.project_id.is_(None)),
        )
    )
    suite_version = rows.scalar_one_or_none()
    if suite_version is None:
        raise KeyError(name)
    return _ResolvedTarget(
        kind="suite",
        suite=suite_version.suite,
        suite_version=suite_version,
    )


async def _load_metric_map_for_runs(
    session,
    *,
    run_ids: list[UUID],
    preferred_metric_names: list[str],
) -> dict[UUID, _MetricValue]:
    if not run_ids:
        return {}

    rows = await session.execute(
        select(EvaluationRunMetric)
        .where(
            EvaluationRunMetric.run_id.in_(run_ids),
            EvaluationRunMetric.run_item_id.is_(None),
            EvaluationRunMetric.metric_scope == "overall",
        )
        .order_by(EvaluationRunMetric.created_at.asc(), EvaluationRunMetric.id.asc())
    )

    preferred = set(preferred_metric_names)
    selected: dict[UUID, _MetricValue] = {}
    fallback: dict[UUID, _MetricValue] = {}
    for row in rows.scalars().all():
        metric = _MetricValue(metric_name=row.metric_name, score=row.metric_value)
        fallback.setdefault(row.run_id, metric)
        if preferred and row.metric_name in preferred and row.run_id not in selected:
            selected[row.run_id] = metric

    for run_id, metric in fallback.items():
        selected.setdefault(run_id, metric)
    return selected


async def _list_eligible_runs(
    session,
    *,
    project_id: UUID,
    target: _ResolvedTarget,
    preferred_metric_names: list[str],
    exclude_run_ids: set[UUID] | None = None,
) -> list[EvaluationLeaderboardRunCandidate]:
    query = select(EvaluationRun).where(
        EvaluationRun.project_id == project_id,
        EvaluationRun.status == "completed",
    )
    if target.kind == "suite":
        query = query.where(EvaluationRun.source_suite_version_id == target.suite_version.id)
    else:
        query = query.where(EvaluationRun.source_spec_version_id == target.spec_version.id)
    query = query.order_by(EvaluationRun.finished_at.desc(), EvaluationRun.created_at.desc(), EvaluationRun.id.desc())

    rows = await session.execute(query)
    runs = list(rows.scalars().all())
    if exclude_run_ids:
        runs = [run for run in runs if run.id not in exclude_run_ids]

    metric_map = await _load_metric_map_for_runs(
        session,
        run_ids=[run.id for run in runs],
        preferred_metric_names=preferred_metric_names,
    )

    candidates: list[EvaluationLeaderboardRunCandidate] = []
    for run in runs:
        metric = metric_map.get(run.id)
        if metric is None:
            continue
        candidates.append(
            EvaluationLeaderboardRunCandidate(
                run_id=run.id,
                run_name=run.name,
                model_name=run.model_name or "-",
                score=metric.score,
                metric_name=metric.metric_name,
                created_at=run.created_at,
                finished_at=run.finished_at,
            )
        )
    return candidates


async def _load_leaderboard(
    session,
    *,
    project_id: UUID,
    leaderboard_id: UUID,
) -> EvaluationLeaderboard | None:
    rows = await session.execute(
        select(EvaluationLeaderboard)
        .options(
            selectinload(EvaluationLeaderboard.source_spec),
            selectinload(EvaluationLeaderboard.source_spec_version),
            selectinload(EvaluationLeaderboard.source_suite),
            selectinload(EvaluationLeaderboard.source_suite_version),
            selectinload(EvaluationLeaderboard.runs).selectinload(EvaluationLeaderboardRun.run),
        )
        .where(
            EvaluationLeaderboard.project_id == project_id,
            EvaluationLeaderboard.id == leaderboard_id,
        )
    )
    return rows.scalar_one_or_none()


def _latest_run_at(record: EvaluationLeaderboard) -> datetime | None:
    latest: datetime | None = None
    for link in record.runs:
        run = link.run
        if run is None:
            continue
        candidate = run.finished_at or run.created_at
        if latest is None or candidate > latest:
            latest = candidate
    return latest


def _serialize_summary(record: EvaluationLeaderboard) -> EvaluationLeaderboardSummary:
    if record.target_kind == "suite":
        if record.source_suite is None or record.source_suite_version is None:
            raise ValueError("Leaderboard suite target is missing.")
        target_name = record.source_suite.name
        target_display_name = record.source_suite.display_name
        target_version = record.source_suite_version.version
        target_version_display_name = record.source_suite_version.display_name
    else:
        if record.source_spec is None or record.source_spec_version is None:
            raise ValueError("Leaderboard spec target is missing.")
        target_name = record.source_spec.name
        target_display_name = record.source_spec.display_name
        target_version = record.source_spec_version.version
        target_version_display_name = record.source_spec_version.display_name

    return EvaluationLeaderboardSummary(
        id=record.id,
        name=record.name,
        description=record.description,
        target_kind=record.target_kind,
        target_name=target_name,
        target_display_name=target_display_name,
        target_version=target_version,
        target_version_display_name=target_version_display_name,
        score_metric_name=record.score_metric_name,
        run_count=len(record.runs),
        latest_run_at=_latest_run_at(record),
        created_at=record.created_at,
        updated_at=record.updated_at,
    )


async def _build_entries(
    session,
    *,
    record: EvaluationLeaderboard,
) -> list[EvaluationLeaderboardEntry]:
    runs = [link.run for link in record.runs if link.run is not None]
    metric_map = await _load_metric_map_for_runs(
        session,
        run_ids=[run.id for run in runs],
        preferred_metric_names=[record.score_metric_name],
    )
    scored_rows: list[tuple[EvaluationRun, _MetricValue]] = []
    for run in runs:
        metric = metric_map.get(run.id)
        if metric is None:
            continue
        scored_rows.append((run, metric))

    scored_rows.sort(
        key=lambda item: (
            -item[1].score,
            -((item[0].finished_at or item[0].created_at).timestamp()),
            item[0].name,
        )
    )

    entries: list[EvaluationLeaderboardEntry] = []
    for index, (run, metric) in enumerate(scored_rows, start=1):
        entries.append(
            EvaluationLeaderboardEntry(
                rank=index,
                run_id=run.id,
                run_name=run.name,
                model_name=run.model_name or "-",
                score=metric.score,
                metric_name=metric.metric_name,
                created_at=run.created_at,
                finished_at=run.finished_at,
            )
        )
    return entries


class EvaluationLeaderboardV2Service:
    async def list_leaderboards(self) -> list[EvaluationLeaderboardSummary]:
        async with SessionLocal() as session:
            project_id = await resolve_active_project_id(session)
            rows = await session.execute(
                select(EvaluationLeaderboard)
                .options(
                    selectinload(EvaluationLeaderboard.source_spec),
                    selectinload(EvaluationLeaderboard.source_spec_version),
                    selectinload(EvaluationLeaderboard.source_suite),
                    selectinload(EvaluationLeaderboard.source_suite_version),
                    selectinload(EvaluationLeaderboard.runs).selectinload(EvaluationLeaderboardRun.run),
                )
                .where(EvaluationLeaderboard.project_id == project_id)
                .order_by(EvaluationLeaderboard.created_at.desc(), EvaluationLeaderboard.id.desc())
            )
            return [_serialize_summary(record) for record in rows.scalars().all()]

    async def get_leaderboard(self, leaderboard_id: UUID) -> EvaluationLeaderboardDetail:
        async with SessionLocal() as session:
            project_id = await resolve_active_project_id(session)
            record = await _load_leaderboard(session, project_id=project_id, leaderboard_id=leaderboard_id)
            if record is None:
                raise KeyError(str(leaderboard_id))
            entries = await _build_entries(session, record=record)
            return EvaluationLeaderboardDetail(
                **_serialize_summary(record).model_dump(),
                entries=entries,
            )

    async def list_available_runs(
        self,
        *,
        kind: str,
        name: str,
        version: str,
        exclude_leaderboard_id: UUID | None = None,
    ) -> list[EvaluationLeaderboardRunCandidate]:
        async with SessionLocal() as session:
            project_id = await resolve_active_project_id(session)
            target = await _resolve_target(
                session,
                project_id=project_id,
                kind=kind,
                name=name,
                version=version,
            )
            excluded_run_ids: set[UUID] = set()
            if exclude_leaderboard_id is not None:
                leaderboard = await _load_leaderboard(
                    session,
                    project_id=project_id,
                    leaderboard_id=exclude_leaderboard_id,
                )
                if leaderboard is None:
                    raise KeyError(str(exclude_leaderboard_id))
                excluded_run_ids = {
                    link.run_id
                    for link in leaderboard.runs
                }
            return await _list_eligible_runs(
                session,
                project_id=project_id,
                target=target,
                preferred_metric_names=["score"],
                exclude_run_ids=excluded_run_ids,
            )

    async def create_leaderboard(
        self,
        payload: EvaluationLeaderboardCreate,
    ) -> EvaluationLeaderboardSummary:
        async with SessionLocal() as session:
            project_id = await resolve_active_project_id(session)
            name = payload.name.strip()
            if not name:
                raise ValueError("排行榜名称不能为空。")
            target = await _resolve_target(
                session,
                project_id=project_id,
                kind=payload.target.kind,
                name=payload.target.name,
                version=payload.target.version,
            )
            eligible_runs = await _list_eligible_runs(
                session,
                project_id=project_id,
                target=target,
                preferred_metric_names=[payload.score_metric_name],
            )
            eligible_map = {candidate.run_id: candidate for candidate in eligible_runs}
            requested_run_ids = list(dict.fromkeys(payload.run_ids))
            missing_run_ids = [run_id for run_id in requested_run_ids if run_id not in eligible_map]
            if missing_run_ids:
                raise ValueError("存在不可加入排行榜的评测任务。")

            record = EvaluationLeaderboard(
                project_id=project_id,
                name=name,
                description=payload.description,
                target_kind=payload.target.kind,
                source_spec_id=target.spec.id if target.spec is not None else None,
                source_spec_version_id=target.spec_version.id if target.spec_version is not None else None,
                source_suite_id=target.suite.id if target.suite is not None else None,
                source_suite_version_id=target.suite_version.id if target.suite_version is not None else None,
                score_metric_name=payload.score_metric_name,
                score_metric_scope="overall",
            )
            session.add(record)
            await session.flush()
            for run_id in requested_run_ids:
                session.add(
                    EvaluationLeaderboardRun(
                        leaderboard_id=record.id,
                        run_id=run_id,
                    )
                )
            try:
                await session.commit()
            except IntegrityError as exc:
                await session.rollback()
                raise ValueError("排行榜创建失败，名称可能已存在。") from exc

            reloaded = await _load_leaderboard(session, project_id=project_id, leaderboard_id=record.id)
            if reloaded is None:
                raise ValueError("排行榜创建失败。")
            return _serialize_summary(reloaded)

    async def add_runs(
        self,
        leaderboard_id: UUID,
        payload: EvaluationLeaderboardAddRuns,
    ) -> EvaluationLeaderboardDetail:
        async with SessionLocal() as session:
            project_id = await resolve_active_project_id(session)
            record = await _load_leaderboard(session, project_id=project_id, leaderboard_id=leaderboard_id)
            if record is None:
                raise KeyError(str(leaderboard_id))

            target = _ResolvedTarget(
                kind=record.target_kind,
                spec=record.source_spec,
                spec_version=record.source_spec_version,
                suite=record.source_suite,
                suite_version=record.source_suite_version,
            )
            existing_run_ids = {link.run_id for link in record.runs}
            eligible_runs = await _list_eligible_runs(
                session,
                project_id=project_id,
                target=target,
                preferred_metric_names=[record.score_metric_name],
                exclude_run_ids=existing_run_ids,
            )
            eligible_map = {candidate.run_id: candidate for candidate in eligible_runs}
            requested_run_ids = list(dict.fromkeys(payload.run_ids))
            missing_run_ids = [run_id for run_id in requested_run_ids if run_id not in eligible_map]
            if missing_run_ids:
                raise ValueError("存在不可加入排行榜的评测任务。")

            for run_id in requested_run_ids:
                session.add(
                    EvaluationLeaderboardRun(
                        leaderboard_id=record.id,
                        run_id=run_id,
                    )
                )
            await session.commit()
        return await self.get_leaderboard(leaderboard_id)

    async def remove_run(self, leaderboard_id: UUID, run_id: UUID) -> None:
        async with SessionLocal() as session:
            project_id = await resolve_active_project_id(session)
            record = await _load_leaderboard(session, project_id=project_id, leaderboard_id=leaderboard_id)
            if record is None:
                raise KeyError(str(leaderboard_id))
            target = next((link for link in record.runs if link.run_id == run_id), None)
            if target is None:
                raise KeyError(str(run_id))
            await session.delete(target)
            await session.commit()

    async def delete_leaderboard(self, leaderboard_id: UUID) -> None:
        async with SessionLocal() as session:
            project_id = await resolve_active_project_id(session)
            record = await _load_leaderboard(session, project_id=project_id, leaderboard_id=leaderboard_id)
            if record is None:
                raise KeyError(str(leaderboard_id))
            await session.delete(record)
            await session.commit()
