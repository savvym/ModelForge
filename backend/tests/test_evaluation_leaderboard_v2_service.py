from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest
from sqlalchemy import delete, select

from nta_backend.core.db import SessionLocal, dispose_engine
from nta_backend.core.project_context import resolve_active_project_id
from nta_backend.models.evaluation_v2 import (
    EvalSpec,
    EvalSpecVersion,
    EvalSuite,
    EvalSuiteVersion,
    EvaluationLeaderboard,
    EvaluationRun,
    EvaluationRunMetric,
)
from nta_backend.schemas.evaluation_v2 import (
    EvaluationLeaderboardAddRuns,
    EvaluationLeaderboardCreate,
    EvaluationTargetRef,
)
from nta_backend.services.evaluation_leaderboard_v2_service import EvaluationLeaderboardV2Service

pytestmark = pytest.mark.asyncio(loop_scope="module")


@pytest.fixture(autouse=True)
async def _dispose_db_engine_between_tests():
    yield
    await dispose_engine()


async def _resolve_spec_version_id(name: str, version: str):
    async with SessionLocal() as session:
        project_id = await resolve_active_project_id(session)
        row = await session.execute(
            select(EvalSpecVersion)
            .join(EvalSpec, EvalSpec.id == EvalSpecVersion.spec_id)
            .where(
                EvalSpec.name == name,
                EvalSpecVersion.version == version,
            )
        )
        spec_version = row.scalar_one()
        return project_id, spec_version.id


async def _resolve_suite_version_id(name: str, version: str):
    async with SessionLocal() as session:
        project_id = await resolve_active_project_id(session)
        row = await session.execute(
            select(EvalSuiteVersion)
            .join(EvalSuite, EvalSuite.id == EvalSuiteVersion.suite_id)
            .where(
                EvalSuite.name == name,
                EvalSuiteVersion.version == version,
            )
        )
        suite_version = row.scalar_one()
        return project_id, suite_version.id


async def _create_completed_run(
    *,
    project_id,
    name: str,
    model_name: str,
    score: float,
    created_at: datetime,
    source_spec_version_id=None,
    source_suite_version_id=None,
):
    async with SessionLocal() as session:
        run = EvaluationRun(
            project_id=project_id,
            name=name,
            kind="suite" if source_suite_version_id is not None else "spec",
            status="completed",
            model_name=model_name,
            source_spec_version_id=source_spec_version_id,
            source_suite_version_id=source_suite_version_id,
            progress_total=1,
            progress_done=1,
            created_at=created_at,
            updated_at=created_at,
            started_at=created_at,
            finished_at=created_at + timedelta(minutes=2),
        )
        session.add(run)
        await session.flush()
        session.add(
            EvaluationRunMetric(
                run_id=run.id,
                run_item_id=None,
                metric_name="score",
                metric_value=score,
                metric_scope="overall",
                dimension_json={},
                extra_json={},
                created_at=created_at,
                updated_at=created_at,
            )
        )
        await session.commit()
        return run.id


async def test_evaluation_leaderboard_v2_crud_and_ranking_for_spec() -> None:
    service = EvaluationLeaderboardV2Service()
    project_id, spec_version_id = await _resolve_spec_version_id("gsm8k", "builtin-v1")

    leaderboard_id = None
    run_ids = []

    try:
        base_time = datetime.now(UTC)
        high_run_id = await _create_completed_run(
            project_id=project_id,
            name="High Score Run",
            model_name="GPT-5.4",
            score=0.92,
            created_at=base_time,
            source_spec_version_id=spec_version_id,
        )
        run_ids.append(high_run_id)
        low_run_id = await _create_completed_run(
            project_id=project_id,
            name="Low Score Run",
            model_name="Qwen3-32B",
            score=0.41,
            created_at=base_time + timedelta(minutes=5),
            source_spec_version_id=spec_version_id,
        )
        run_ids.append(low_run_id)
        mid_run_id = await _create_completed_run(
            project_id=project_id,
            name="Mid Score Run",
            model_name="DeepSeek-V3",
            score=0.63,
            created_at=base_time + timedelta(minutes=10),
            source_spec_version_id=spec_version_id,
        )
        run_ids.append(mid_run_id)

        created = await service.create_leaderboard(
            EvaluationLeaderboardCreate(
                name=f"spec-leaderboard-{uuid4().hex[:8]}",
                target=EvaluationTargetRef(kind="spec", name="gsm8k", version="builtin-v1"),
                run_ids=[low_run_id, high_run_id],
            )
        )
        leaderboard_id = created.id
        assert created.target_kind == "spec"
        assert created.target_name == "gsm8k"
        assert created.target_version == "builtin-v1"
        assert created.run_count == 2
        assert created.score_metric_name == "score"

        detail = await service.get_leaderboard(created.id)
        assert [entry.run_name for entry in detail.entries] == [
            "High Score Run",
            "Low Score Run",
        ]
        assert [entry.rank for entry in detail.entries] == [1, 2]

        available_runs = await service.list_available_runs(
            kind="spec",
            name="gsm8k",
            version="builtin-v1",
            exclude_leaderboard_id=created.id,
        )
        assert [candidate.run_name for candidate in available_runs] == ["Mid Score Run"]

        updated = await service.add_runs(
            created.id,
            EvaluationLeaderboardAddRuns(run_ids=[mid_run_id]),
        )
        assert [entry.run_name for entry in updated.entries] == [
            "High Score Run",
            "Mid Score Run",
            "Low Score Run",
        ]

        await service.remove_run(created.id, low_run_id)
        detail_after_remove = await service.get_leaderboard(created.id)
        assert [entry.run_name for entry in detail_after_remove.entries] == [
            "High Score Run",
            "Mid Score Run",
        ]

        summaries = await service.list_leaderboards()
        created_summary = next(summary for summary in summaries if summary.id == created.id)
        assert created_summary.run_count == 2

        await service.delete_leaderboard(created.id)
        leaderboard_id = None
        remaining = await service.list_leaderboards()
        assert all(summary.id != created.id for summary in remaining)
    finally:
        async with SessionLocal() as session:
            if leaderboard_id is not None:
                await session.execute(
                    delete(EvaluationLeaderboard).where(EvaluationLeaderboard.id == leaderboard_id)
                )
            if run_ids:
                await session.execute(
                    delete(EvaluationRunMetric).where(EvaluationRunMetric.run_id.in_(run_ids))
                )
                await session.execute(delete(EvaluationRun).where(EvaluationRun.id.in_(run_ids)))
            await session.commit()


async def test_suite_leaderboard_lists_completed_suite_runs() -> None:
    service = EvaluationLeaderboardV2Service()
    project_id, suite_version_id = await _resolve_suite_version_id("baseline-general", "v1")
    run_ids = []
    leaderboard_id = None

    try:
        base_time = datetime.now(UTC)
        suite_a = await _create_completed_run(
            project_id=project_id,
            name="Suite Run A",
            model_name="GPT-5.4",
            score=0.78,
            created_at=base_time,
            source_suite_version_id=suite_version_id,
        )
        run_ids.append(suite_a)
        suite_b = await _create_completed_run(
            project_id=project_id,
            name="Suite Run B",
            model_name="Qwen3-32B",
            score=0.67,
            created_at=base_time + timedelta(minutes=3),
            source_suite_version_id=suite_version_id,
        )
        run_ids.append(suite_b)

        candidates = await service.list_available_runs(
            kind="suite",
            name="baseline-general",
            version="v1",
        )
        candidate_names = {candidate.run_name for candidate in candidates}
        assert {"Suite Run A", "Suite Run B"} <= candidate_names

        created = await service.create_leaderboard(
            EvaluationLeaderboardCreate(
                name=f"suite-leaderboard-{uuid4().hex[:8]}",
                target=EvaluationTargetRef(kind="suite", name="baseline-general", version="v1"),
                run_ids=[suite_a, suite_b],
            )
        )
        leaderboard_id = created.id
        assert created.target_kind == "suite"
        assert created.target_name == "baseline-general"

        detail = await service.get_leaderboard(created.id)
        assert [entry.run_name for entry in detail.entries] == ["Suite Run A", "Suite Run B"]
    finally:
        async with SessionLocal() as session:
            if leaderboard_id is not None:
                await session.execute(
                    delete(EvaluationLeaderboard).where(EvaluationLeaderboard.id == leaderboard_id)
                )
            if run_ids:
                await session.execute(
                    delete(EvaluationRunMetric).where(EvaluationRunMetric.run_id.in_(run_ids))
                )
                await session.execute(delete(EvaluationRun).where(EvaluationRun.id.in_(run_ids)))
            await session.commit()
