from datetime import datetime, timezone
from uuid import uuid4

import pytest
from sqlalchemy import delete

from nta_backend.core.config import get_settings
from nta_backend.core.db import SessionLocal, dispose_engine
from nta_backend.core.object_store import delete_object, put_object_bytes
from nta_backend.core.project_context import resolve_active_project_id
from nta_backend.core.storage_layout import build_eval_job_code
from nta_backend.models.benchmark_catalog import (
    BenchmarkDefinition as BenchmarkDefinitionRecord,
    BenchmarkVersion as BenchmarkVersionRecord,
)
from nta_backend.models.benchmark_leaderboard import (
    BenchmarkLeaderboard,
    BenchmarkLeaderboardJob,
)
from nta_backend.models.eval_template import EvalTemplate
from nta_backend.models.jobs import EvalJob, EvalJobMetric
from nta_backend.schemas.benchmark_catalog import (
    BenchmarkDefinitionCreate,
    BenchmarkVersionCreate,
)
from nta_backend.schemas.benchmark_leaderboard import (
    BenchmarkLeaderboardAddJobs,
    BenchmarkLeaderboardCreate,
)
from nta_backend.services.benchmark_catalog_service import BenchmarkCatalogService
from nta_backend.services.benchmark_leaderboard_service import BenchmarkLeaderboardService


@pytest.fixture(autouse=True)
async def _dispose_db_engine_between_tests():
    yield
    await dispose_engine()


async def test_benchmark_leaderboard_service_crud_and_ranking() -> None:
    benchmark_service = BenchmarkCatalogService()
    leaderboard_service = BenchmarkLeaderboardService()

    benchmark_name = f"leaderboard_benchmark_{uuid4().hex[:8]}"
    template_name = f"leaderboard_template_{uuid4().hex[:8]}"
    bucket = get_settings().s3_bucket_dataset_raw
    object_key = f"manual-evals/{benchmark_name}.jsonl"

    template_uuid = None
    version_id: str | None = None
    leaderboard_id = None
    high_job_id = None
    low_job_id = None
    mid_job_id = None

    try:
        async with SessionLocal() as session:
            template = EvalTemplate(
                name=template_name,
                version=1,
                prompt="Question: {{input}}\nReference: {{target}}\nAnswer: {{output}}",
                vars=["input", "target", "output"],
                template_type="llm_categorical",
                preset_id="rubric-check",
                output_type="categorical",
                output_config={
                    "label_groups": [
                        {"key": "pass", "label": "Pass", "labels": ["Pass"], "score_policy": "pass"},
                        {"key": "fail", "label": "Fail", "labels": ["Fail"], "score_policy": "fail"},
                    ]
                },
                model="GPT-5.4",
            )
            session.add(template)
            await session.commit()
            await session.refresh(template)
            template_uuid = template.id

        created = await benchmark_service.create_benchmark_definition(
            BenchmarkDefinitionCreate(
                name=benchmark_name,
                display_name="Leaderboard Benchmark",
                description="benchmark for leaderboard tests",
                category="llm",
                field_mapping={
                    "input_field": "input",
                    "target_field": "target",
                    "id_field": "id",
                },
                eval_template_id=str(template_uuid),
            )
        )

        put_object_bytes(
            bucket,
            object_key,
            b'{"id":"sample-1","input":"hello","target":"world"}\n',
            content_type="application/x-ndjson",
        )
        version = await benchmark_service.create_benchmark_version(
            created.name,
            BenchmarkVersionCreate(
                display_name="Leaderboard Version",
                dataset_source_uri=f"s3://{bucket}/{object_key}",
            ),
        )
        version_id = version.id

        async with SessionLocal() as session:
            project_id = await resolve_active_project_id(session)
            now = datetime.now(timezone.utc)
            high_job = EvalJob(
                project_id=project_id,
                name="High Score Eval",
                status="completed",
                model_name="GPT-5.4",
                model_source="model-square",
                benchmark_name=created.name,
                benchmark_version_id=version.id,
                dataset_name=version.display_name,
                finished_at=now,
            )
            low_job = EvalJob(
                project_id=project_id,
                name="Low Score Eval",
                status="completed",
                model_name="Qwen3-32B",
                model_source="model-square",
                benchmark_name=created.name,
                benchmark_version_id=version.id,
                dataset_name=version.display_name,
                finished_at=now,
            )
            mid_job = EvalJob(
                project_id=project_id,
                name="Mid Score Eval",
                status="completed",
                model_name="DeepSeek-V3",
                model_source="model-square",
                benchmark_name=created.name,
                benchmark_version_id=version.id,
                dataset_name=version.display_name,
                finished_at=now,
            )
            session.add_all([high_job, low_job, mid_job])
            await session.flush()
            session.add_all(
                [
                    EvalJobMetric(
                        eval_job_id=high_job.id,
                        metric_name="judge_template",
                        metric_value=0.92,
                    ),
                    EvalJobMetric(
                        eval_job_id=low_job.id,
                        metric_name="judge_template",
                        metric_value=0.41,
                    ),
                    EvalJobMetric(
                        eval_job_id=mid_job.id,
                        metric_name="judge_template",
                        metric_value=0.63,
                    ),
                ]
            )
            await session.commit()
            high_job_id = high_job.id
            low_job_id = low_job.id
            mid_job_id = mid_job.id
            high_code = build_eval_job_code(high_job.created_at, high_job.id)
            low_code = build_eval_job_code(low_job.created_at, low_job.id)
            mid_code = build_eval_job_code(mid_job.created_at, mid_job.id)

        created_leaderboard = await leaderboard_service.create_leaderboard(
            BenchmarkLeaderboardCreate(
                name="网络问答排行榜",
                benchmark_name=created.name,
                benchmark_version_id=version.id,
                eval_job_ids=[low_code, high_code],
            )
        )
        leaderboard_id = created_leaderboard.id
        assert created_leaderboard.job_count == 2
        assert created_leaderboard.benchmark_name == created.name
        assert created_leaderboard.benchmark_version_id == version.id
        assert created_leaderboard.score_metric_name == "judge_template"

        detail = await leaderboard_service.get_leaderboard(created_leaderboard.id)
        assert [entry.eval_job_name for entry in detail.entries] == [
            "High Score Eval",
            "Low Score Eval",
        ]
        assert [entry.rank for entry in detail.entries] == [1, 2]

        available_jobs = await leaderboard_service.list_available_jobs(
            benchmark_name=created.name,
            benchmark_version_id=version.id,
            exclude_leaderboard_id=created_leaderboard.id,
        )
        assert [job.eval_job_name for job in available_jobs] == ["Mid Score Eval"]

        updated_detail = await leaderboard_service.add_jobs(
            created_leaderboard.id,
            BenchmarkLeaderboardAddJobs(eval_job_ids=[mid_code]),
        )
        assert [entry.eval_job_name for entry in updated_detail.entries] == [
            "High Score Eval",
            "Mid Score Eval",
            "Low Score Eval",
        ]

        await leaderboard_service.remove_job(created_leaderboard.id, low_code)
        detail_after_remove = await leaderboard_service.get_leaderboard(created_leaderboard.id)
        assert [entry.eval_job_name for entry in detail_after_remove.entries] == [
            "High Score Eval",
            "Mid Score Eval",
        ]

        summaries = await leaderboard_service.list_leaderboards()
        created_summary = next(
            summary for summary in summaries if summary.id == created_leaderboard.id
        )
        assert created_summary.job_count == 2

        await leaderboard_service.delete_leaderboard(created_leaderboard.id)
        remaining_summaries = await leaderboard_service.list_leaderboards()
        assert all(summary.id != created_leaderboard.id for summary in remaining_summaries)
    finally:
        async with SessionLocal() as session:
            if leaderboard_id is not None:
                await session.execute(
                    delete(BenchmarkLeaderboardJob).where(
                        BenchmarkLeaderboardJob.leaderboard_id == leaderboard_id
                    )
                )
                await session.execute(
                    delete(BenchmarkLeaderboard).where(
                        BenchmarkLeaderboard.id == leaderboard_id
                    )
                )
            for job_id in [high_job_id, low_job_id, mid_job_id]:
                if job_id is not None:
                    await session.execute(
                        delete(EvalJobMetric).where(EvalJobMetric.eval_job_id == job_id)
                    )
                    await session.execute(delete(EvalJob).where(EvalJob.id == job_id))
            if version_id is not None:
                await session.execute(
                    delete(BenchmarkVersionRecord).where(
                        BenchmarkVersionRecord.version_id == version_id
                    )
                )
            await session.execute(
                delete(BenchmarkDefinitionRecord).where(
                    BenchmarkDefinitionRecord.name == benchmark_name
                )
            )
            if template_uuid is not None:
                await session.execute(delete(EvalTemplate).where(EvalTemplate.id == template_uuid))
            await session.commit()
        delete_object(bucket, object_key)
