from datetime import UTC, datetime
from pathlib import Path
from uuid import UUID, uuid4

import pytest
from sqlalchemy import func, select

from nta_backend.core.db import SessionLocal
from nta_backend.core.project_context import resolve_active_project_id
from nta_backend.models.jobs import EvalJob, EvalJobMetric
from nta_backend.services import eval_service
from nta_backend.services.eval_service import LOCAL_EVALRUNS_ROOT, EvalJobService

pytestmark = pytest.mark.asyncio(loop_scope="module")

async def test_delete_eval_job_removes_metrics_and_local_artifacts() -> None:
    service = EvalJobService()
    job_uuid: UUID | None = None
    artifact_dir = None

    try:
        async with SessionLocal() as session:
            project_id = await resolve_active_project_id(session)
            job = EvalJob(
                project_id=project_id,
                name=f"tmp-eval-delete-{uuid4().hex[:8]}",
                status="completed",
                model_source="model-square",
                model_name="test-model",
                inference_mode="batch",
                eval_method="judge-model",
                dataset_name="test-dataset",
            )
            session.add(job)
            await session.flush()

            artifact_dir = LOCAL_EVALRUNS_ROOT / f"pytest-delete-{job.id}"
            artifact_dir.mkdir(parents=True, exist_ok=True)
            report_path = artifact_dir / "report.json"
            report_path.write_text("{}", encoding="utf-8")

            job.artifact_prefix_uri = str(artifact_dir)
            job.results_prefix_uri = str(artifact_dir)
            job.report_object_uri = str(report_path)
            session.add(
                EvalJobMetric(
                    eval_job_id=job.id,
                    metric_name="full_score_rate",
                    metric_value=1.0,
                )
            )
            await session.commit()
            job_uuid = job.id

        assert job_uuid is not None
        await service.delete_eval_job(str(job_uuid))

        async with SessionLocal() as session:
            assert await session.get(EvalJob, job_uuid) is None
            metric_count = (
                await session.execute(
                    select(func.count())
                    .select_from(EvalJobMetric)
                    .where(EvalJobMetric.eval_job_id == job_uuid)
                )
            ).scalar_one()
            assert metric_count == 0

        assert artifact_dir is not None
        assert artifact_dir.exists() is False
    finally:
        if artifact_dir is not None and artifact_dir.exists():
            report_path = artifact_dir / "report.json"
            if report_path.exists():
                report_path.unlink()
            artifact_dir.rmdir()
        if job_uuid is not None:
            async with SessionLocal() as session:
                job = await session.get(EvalJob, job_uuid)
                if job is not None:
                    await session.delete(job)
                    await session.commit()


async def test_delete_eval_job_rejects_running_job() -> None:
    service = EvalJobService()

    async with SessionLocal() as session:
        project_id = await resolve_active_project_id(session)
        job = EvalJob(
            project_id=project_id,
            name=f"tmp-eval-running-{uuid4().hex[:8]}",
            status="inferencing",
            model_source="model-square",
            model_name="test-model",
            inference_mode="batch",
            eval_method="judge-model",
            dataset_name="test-dataset",
        )
        session.add(job)
        await session.commit()
        job_uuid = job.id

    try:
        with pytest.raises(ValueError, match="运行中的评测任务暂不支持删除"):
            await service.delete_eval_job(str(job_uuid))

        async with SessionLocal() as session:
            assert await session.get(EvalJob, job_uuid) is not None
    finally:
        async with SessionLocal() as session:
            job = await session.get(EvalJob, job_uuid)
            if job is not None:
                await session.delete(job)
                await session.commit()


async def test_stop_eval_job_rejects_stale_running_job_without_temporal_workflow() -> None:
    service = EvalJobService()

    async with SessionLocal() as session:
        project_id = await resolve_active_project_id(session)
        job = EvalJob(
            project_id=project_id,
            name=f"tmp-eval-stop-{uuid4().hex[:8]}",
            status="inferencing",
            model_source="model-square",
            model_name="test-model",
            inference_mode="batch",
            eval_method="judge-model",
            dataset_name="test-dataset",
            progress_total=10,
            progress_done=4,
        )
        session.add(job)
        await session.commit()
        job_uuid = job.id

    try:
        with pytest.raises(ValueError, match="未绑定 Temporal workflow"):
            await service.stop_eval_job(str(job_uuid))
    finally:
        async with SessionLocal() as session:
            job = await session.get(EvalJob, job_uuid)
            if job is not None:
                await session.delete(job)
                await session.commit()


async def test_stop_eval_job_rejects_missing_temporal_workflow_id() -> None:
    service = EvalJobService()

    async with SessionLocal() as session:
        project_id = await resolve_active_project_id(session)
        job = EvalJob(
            project_id=project_id,
            name=f"tmp-eval-missing-workflow-{uuid4().hex[:8]}",
            status="inferencing",
            model_source="model-square",
            model_name="test-model",
            inference_mode="batch",
            eval_method="judge-model",
            dataset_name="test-dataset",
        )
        session.add(job)
        await session.commit()
        job_uuid = job.id

    try:
        with pytest.raises(ValueError, match="未绑定 Temporal workflow"):
            await service.stop_eval_job(str(job_uuid))
    finally:
        async with SessionLocal() as session:
            job = await session.get(EvalJob, job_uuid)
            if job is not None:
                await session.delete(job)
                await session.commit()


async def test_stop_eval_job_marks_temporal_backed_running_job_cancelling(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    service = EvalJobService()

    async def _noop_cancel(_workflow_id: str) -> None:
        return None

    monkeypatch.setattr(eval_service, "_cancel_eval_job_workflow", _noop_cancel)

    async with SessionLocal() as session:
        project_id = await resolve_active_project_id(session)
        job = EvalJob(
            project_id=project_id,
            name=f"tmp-eval-temporal-stop-{uuid4().hex[:8]}",
            status="inferencing",
            model_source="model-square",
            model_name="test-model",
            inference_mode="batch",
            eval_method="judge-model",
            dataset_name="test-dataset",
            progress_total=12,
            progress_done=3,
            temporal_workflow_id=f"eval-job-{uuid4()}",
        )
        session.add(job)
        await session.commit()
        job_uuid = job.id

    try:
        summary = await service.stop_eval_job(str(job_uuid))
        assert summary.status == "cancelling"
        assert summary.progress_done == 3
        assert summary.progress_total == 12
        assert summary.progress_percent == 25

        async with SessionLocal() as session:
            persisted = await session.get(EvalJob, job_uuid)
            assert persisted is not None
            assert persisted.status == "cancelling"
            assert persisted.cancel_requested is True
            assert persisted.finished_at is None
    finally:
        async with SessionLocal() as session:
            job = await session.get(EvalJob, job_uuid)
            if job is not None:
                await session.delete(job)
                await session.commit()


async def test_list_eval_jobs_syncs_failed_temporal_workflow(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    service = EvalJobService()

    class _WorkflowState:
        status = "failed"
        is_terminal = True
        failure_message = "temporal worker mismatch"

    async def _failed_state(_workflow_id: str) -> _WorkflowState:
        return _WorkflowState()

    monkeypatch.setattr(eval_service, "_get_eval_job_workflow_state", _failed_state)

    async with SessionLocal() as session:
        project_id = await resolve_active_project_id(session)
        job = EvalJob(
            project_id=project_id,
            name=f"tmp-eval-sync-failed-{uuid4().hex[:8]}",
            status="queued",
            model_source="model-square",
            model_name="test-model",
            inference_mode="batch",
            eval_method="judge-model",
            dataset_name="test-dataset",
            temporal_workflow_id=f"eval-job-{uuid4()}",
        )
        session.add(job)
        await session.commit()
        job_uuid = job.id

    try:
        rows = await service.list_eval_jobs()
        matched = next(row for row in rows if row.name == job.name)
        assert matched.status == "failed"
        assert matched.error_message == "temporal worker mismatch"

        async with SessionLocal() as session:
            persisted = await session.get(EvalJob, job_uuid)
            assert persisted is not None
            assert persisted.status == "failed"
            assert persisted.error_message == "temporal worker mismatch"
            assert persisted.finished_at is not None
    finally:
        async with SessionLocal() as session:
            job = await session.get(EvalJob, job_uuid)
            if job is not None:
                await session.delete(job)
                await session.commit()


async def test_upload_eval_artifacts_persists_report_to_s3_prefix(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    uploaded: dict[str, bytes] = {}
    created_prefixes: list[str] = []

    def _fake_create_object_prefix(bucket: str, prefix: str) -> None:
        assert bucket == eval_service.EVAL_ARTIFACT_BUCKET
        created_prefixes.append(prefix)

    def _fake_put_object_bytes(
        bucket: str, object_key: str, body: bytes, content_type: str | None = None
    ) -> None:
        assert bucket == eval_service.EVAL_ARTIFACT_BUCKET
        uploaded[object_key] = body

    monkeypatch.setattr(eval_service, "create_object_prefix", _fake_create_object_prefix)
    monkeypatch.setattr(eval_service, "put_object_bytes", _fake_put_object_bytes)

    job = EvalJob(
        id=uuid4(),
        project_id=uuid4(),
        name="job",
        status="completed",
        model_source="model-square",
        model_name="test-model",
        inference_mode="batch",
        eval_method="judge-model",
        dataset_name="test-dataset",
        created_at=datetime.now(UTC),
    )
    report_path = tmp_path / "report.json"
    report_body = b'{"ok":true}'
    report_path.write_bytes(report_body)

    artifact_prefix_uri, results_prefix_uri, samples_prefix_uri, report_object_uri = (
        eval_service._upload_eval_artifacts(job, tmp_path)
    )

    expected_prefix = eval_service.build_eval_job_prefix(job.project_id, job.id, job.created_at)
    expected_report_key = eval_service.build_eval_job_artifact_key(
        job.project_id,
        job.id,
        job.created_at,
        "report.json",
    )

    assert created_prefixes == [expected_prefix]
    assert uploaded[expected_report_key] == report_body
    assert artifact_prefix_uri == f"s3://{eval_service.EVAL_ARTIFACT_BUCKET}/{expected_prefix}"
    assert results_prefix_uri == artifact_prefix_uri
    assert samples_prefix_uri == artifact_prefix_uri
    assert report_object_uri == f"s3://{eval_service.EVAL_ARTIFACT_BUCKET}/{expected_report_key}"
