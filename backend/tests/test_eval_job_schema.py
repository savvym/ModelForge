from datetime import UTC, datetime
from uuid import uuid4

from nta_backend.models.jobs import EvalJob
from nta_backend.schemas.eval_job import EvalJobCreate
from nta_backend.services.eval_service import _to_detail, _to_summary


def test_eval_job_create_accepts_legacy_benchmark_preset_alias() -> None:
    payload = EvalJobCreate.model_validate(
        {
            "name": "compat",
            "benchmark_name": "cl_bench",
            "benchmark_preset_id": "cl_bench_smoke_1",
        }
    )

    assert payload.benchmark_version_id == "cl_bench_smoke_1"


def test_eval_job_detail_prefers_persisted_benchmark_fields() -> None:
    job = EvalJob(
        id=uuid4(),
        project_id=uuid4(),
        name="job",
        status="completed",
        benchmark_name="cl_bench",
        benchmark_version_id="cl_bench_smoke_1",
        dataset_name="legacy-name",
        dataset_source_uri="benchmark://wrong/versions/wrong",
        model_name="GPT-5.4",
        model_source="model-square",
        inference_mode="batch",
        eval_method="judge-model",
        access_source="nta",
        task_type="single-turn",
        eval_mode="infer-auto",
        created_at=datetime.now(UTC),
    )

    detail = _to_detail(
        job,
        metrics=[],
        sample_analysis=[],
        benchmark_version_name="CL-bench Smoke (1条)",
    )

    assert detail.benchmark_name == "cl_bench"
    assert detail.benchmark_version_id == "cl_bench_smoke_1"
    assert detail.benchmark_version_name == "CL-bench Smoke (1条)"


def test_eval_job_summary_uses_sample_progress_when_available() -> None:
    job = EvalJob(
        id=uuid4(),
        project_id=uuid4(),
        name="job",
        status="inferencing",
        progress_done=3,
        progress_total=12,
        model_name="GPT-5.4",
        model_source="model-square",
        inference_mode="batch",
        eval_method="judge-model",
        created_at=datetime.now(UTC),
    )

    summary = _to_summary(job)

    assert summary.progress_done == 3
    assert summary.progress_total == 12
    assert summary.progress_percent == 25


def test_eval_job_summary_running_progress_has_non_zero_floor() -> None:
    job = EvalJob(
        id=uuid4(),
        project_id=uuid4(),
        name="job",
        status="inferencing",
        progress_done=0,
        progress_total=1,
        model_name="GPT-5.4",
        model_source="model-square",
        inference_mode="batch",
        eval_method="judge-model",
        created_at=datetime.now(UTC),
    )

    summary = _to_summary(job)

    assert summary.progress_done == 0
    assert summary.progress_total == 1
    assert summary.progress_percent == 5
