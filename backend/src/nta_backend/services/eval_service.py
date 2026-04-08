from __future__ import annotations

import asyncio
import json
import shutil
import threading
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import UTC, datetime
from mimetypes import guess_type
from pathlib import Path
from tempfile import NamedTemporaryFile
from typing import Any
from uuid import UUID

from sqlalchemy import delete, select

from nta_backend.core.auth_context import resolve_current_user
from nta_backend.core.config import get_settings
from nta_backend.core.db import SessionLocal
from nta_backend.core.object_store import (
    create_object_prefix,
    delete_object,
    delete_object_prefix,
    get_object_bytes,
    put_object_bytes,
)
from nta_backend.core.project_context import resolve_active_project_id
from nta_backend.core.storage_layout import (
    build_eval_job_artifact_key,
    build_eval_job_code,
    build_eval_job_prefix,
)
from nta_backend.evaluation.executors import (
    EvalExecutionCancelledError,
    EvalExecutionRequest,
    EvalScopeExecutor,
    ExecutorModelConfig,
    ExecutorTemplateConfig,
)
from nta_backend.models.jobs import EvalJob, EvalJobMetric
from nta_backend.models.modeling import Model, ModelProvider
from nta_backend.schemas.eval_job import (
    EvalJobCreate,
    EvalJobDetail,
    EvalJobSummary,
    EvalMetric,
    EvalSampleAnalysis,
)
from nta_backend.services.benchmark_catalog_service import (
    get_benchmark_definition_record,
    resolve_benchmark_version_record,
)

REPO_ROOT = Path(__file__).resolve().parents[4]
LOCAL_EVALRUNS_ROOT = REPO_ROOT / "backend" / ".evalruns"
EVAL_ARTIFACT_BUCKET = get_settings().s3_bucket_eval_artifacts
_MODEL_TIMEOUT_S = 180.0
_MODEL_MAX_TOKENS = 4096
_EVAL_EXECUTOR = EvalScopeExecutor()

_STATUS_PROGRESS = {
    "queued": 0,
    "preparing": 20,
    "inferencing": 60,
    "cancelling": 60,
    "scoring": 85,
    "completed": 100,
    "failed": 100,
    "cancelled": 100,
}
_DELETE_BLOCKED_STATUSES = frozenset({"preparing", "inferencing", "scoring"})
_STOPPABLE_STATUSES = frozenset({"queued", "preparing", "inferencing", "scoring", "cancelling"})
_TERMINAL_STATUSES = frozenset({"completed", "failed", "cancelled"})
_TEMPORAL_TO_JOB_STATUS = {
    "failed": "failed",
    "cancelled": "cancelled",
    "terminated": "failed",
    "timed_out": "failed",
}
_RUNNING_PROGRESS_FLOOR = {
    "preparing": 5,
    "inferencing": 5,
    "scoring": 90,
    "cancelling": 5,
}


@dataclass(frozen=True)
class _ResolvedModelConfig:
    model_name: str
    display_name: str
    api_url: str
    api_key: str | None
    api_format: str
    organization: str | None = None
    headers: dict[str, str] = field(default_factory=dict)


@dataclass(frozen=True)
class _ResolvedDatasetInput:
    benchmark_name: str
    dataset_path: str
    source_uri: str | None
    prompt_config: dict[str, Any]
    field_mapping: dict[str, Any]
    eval_method: str
    template_config: ExecutorTemplateConfig | None = None
    template_id: UUID | None = None
    template_version: int | None = None
    template_model_name: str | None = None


def _utc_now() -> datetime:
    return datetime.now(UTC)


def _progress_percent(job: EvalJob) -> int:
    status = job.status
    if not status:
        return 0
    if status == "completed":
        return 100
    total = job.progress_total
    done = job.progress_done or 0
    if isinstance(total, int) and total > 0:
        normalized_done = min(max(done, 0), total)
        progress = round((normalized_done / total) * 100)
        if status in _RUNNING_PROGRESS_FLOOR:
            floor = _RUNNING_PROGRESS_FLOOR[status]
            if normalized_done < total:
                return max(floor, min(progress, 95))
            return 95
        return progress
    return _STATUS_PROGRESS.get(status, 0)


def _created_by(job: EvalJob) -> str | None:
    if job.created_by_name:
        return job.created_by_name
    if job.created_by is not None:
        return str(job.created_by)
    return None


def _to_summary(job: EvalJob) -> EvalJobSummary:
    return EvalJobSummary(
        id=build_eval_job_code(job.created_at, job.id),
        name=job.name,
        description=job.description,
        status=job.status,
        model_name=job.model_name or "-",
        model_source=job.model_source or "model-square",
        created_by=_created_by(job),
        progress_percent=_progress_percent(job),
        progress_done=job.progress_done,
        progress_total=job.progress_total,
        inference_mode=job.inference_mode or "batch",
        eval_method=job.eval_method or "judge-rubric",
        temporal_workflow_id=job.temporal_workflow_id,
        error_message=job.error_message,
        created_at=job.created_at,
        started_at=job.started_at,
        finished_at=job.finished_at,
    )


def _build_s3_uri(bucket: str, object_key: str) -> str:
    return f"s3://{bucket}/{object_key}"


def _truncate_error_message(value: str) -> str:
    normalized = " ".join(value.split())
    return normalized[:500]


def _parse_s3_uri(value: str | None) -> tuple[str, str] | None:
    if not value or not value.startswith("s3://"):
        return None

    stripped = value.removeprefix("s3://")
    if "/" not in stripped:
        return None

    bucket, object_key = stripped.split("/", 1)
    if not bucket or not object_key:
        return None
    return bucket, object_key


def _eval_method_requires_judge_model(eval_method: str | None) -> bool:
    return (eval_method or "").strip() in {
        "judge-rubric",
        "judge-quality",
        "judge-template",
        "judge-model",
    }


def _artifact_local_path(value: str | None) -> Path | None:
    if not value or not value.startswith("/"):
        return None

    path = Path(value)
    try:
        path.relative_to(LOCAL_EVALRUNS_ROOT)
    except ValueError:
        return None
    return path


def _cleanup_local_eval_artifacts(paths: set[Path]) -> None:
    for path in sorted(paths, key=lambda item: len(item.parts), reverse=True):
        if not path.exists():
            continue
        if path.is_dir():
            shutil.rmtree(path, ignore_errors=True)
            continue
        path.unlink(missing_ok=True)


def _collect_eval_artifact_cleanup(
    job: EvalJob,
) -> tuple[set[Path], set[tuple[str, str]], set[tuple[str, str]]]:
    local_paths: set[Path] = set()
    s3_prefixes: set[tuple[str, str]] = set()
    s3_objects: set[tuple[str, str]] = set()

    for candidate in (
        job.artifact_prefix_uri,
        job.results_prefix_uri,
        job.samples_prefix_uri,
        job.report_object_uri,
    ):
        local_path = _artifact_local_path(candidate)
        if local_path is not None:
            local_paths.add(local_path)

    for candidate in (job.artifact_prefix_uri, job.results_prefix_uri, job.samples_prefix_uri):
        parsed = _parse_s3_uri(candidate)
        if parsed is None:
            continue
        bucket, object_key = parsed
        if object_key:
            s3_prefixes.add((bucket, object_key))

    parsed_report = _parse_s3_uri(job.report_object_uri)
    if parsed_report is not None:
        s3_objects.add(parsed_report)

    return local_paths, s3_prefixes, s3_objects


def _eval_output_dir(job: EvalJob) -> Path:
    return LOCAL_EVALRUNS_ROOT / build_eval_job_code(job.created_at, job.id)


def _guess_artifact_content_type(file_name: str) -> str:
    lower_name = file_name.lower()
    if lower_name.endswith(".jsonl"):
        return "application/x-ndjson"
    if lower_name.endswith(".json"):
        return "application/json"
    if lower_name.endswith(".xlsx"):
        return "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    if lower_name.endswith(".xls"):
        return "application/vnd.ms-excel"

    guessed, _ = guess_type(file_name)
    return guessed or "application/octet-stream"


def _upload_eval_artifacts(job: EvalJob, output_dir: Path) -> tuple[str, str, str, str]:
    artifact_prefix = build_eval_job_prefix(job.project_id, job.id, job.created_at)
    create_object_prefix(EVAL_ARTIFACT_BUCKET, artifact_prefix)

    report_uri: str | None = None
    for artifact_path in sorted(output_dir.rglob("*")):
        if not artifact_path.is_file():
            continue

        relative_path = artifact_path.relative_to(output_dir).as_posix()
        object_key = build_eval_job_artifact_key(
            job.project_id,
            job.id,
            job.created_at,
            relative_path,
        )
        put_object_bytes(
            EVAL_ARTIFACT_BUCKET,
            object_key,
            artifact_path.read_bytes(),
            content_type=_guess_artifact_content_type(artifact_path.name),
        )
        if relative_path == "report.json":
            report_uri = _build_s3_uri(EVAL_ARTIFACT_BUCKET, object_key)

    if report_uri is None:
        raise FileNotFoundError("report.json")

    prefix_uri = _build_s3_uri(EVAL_ARTIFACT_BUCKET, artifact_prefix)
    return prefix_uri, prefix_uri, prefix_uri, report_uri


def _payload_version_id(payload: EvalJobCreate) -> str | None:
    if payload.benchmark_version_id and payload.benchmark_version_id.strip():
        return payload.benchmark_version_id.strip()
    return None


def _parse_benchmark_source_uri(value: str | None) -> tuple[str | None, str | None]:
    if not value or not value.startswith("benchmark://"):
        return None, None

    normalized = value.removeprefix("benchmark://")
    parts = normalized.split("/", 2)
    if len(parts) != 3:
        return None, None

    benchmark_name, collection_name, version_id = parts
    if collection_name not in {"versions", "presets"}:
        return None, None
    if not benchmark_name or not version_id:
        return None, None
    return benchmark_name, version_id


async def _get_job_or_raise(session, job_id: UUID) -> EvalJob:
    job = await session.get(EvalJob, job_id)
    if job is None:
        raise KeyError(str(job_id))
    return job


async def _get_job_by_identifier_or_raise(
    session,
    *,
    project_id: UUID,
    job_identifier: str,
) -> EvalJob:
    try:
        job_id = UUID(job_identifier)
    except ValueError:
        job_id = None

    if job_id is not None:
        job = await session.get(EvalJob, job_id)
        if job is not None and job.project_id == project_id:
            return job

    rows = await session.execute(
        select(EvalJob)
        .where(EvalJob.project_id == project_id)
        .order_by(EvalJob.created_at.desc(), EvalJob.id.desc())
    )
    for job in rows.scalars().all():
        if build_eval_job_code(job.created_at, job.id) == job_identifier:
            return job
    raise KeyError(job_identifier)


async def _persist_eval_job_progress(
    job_id: UUID,
    *,
    progress_done: int,
    progress_total: int,
) -> None:
    async with SessionLocal() as session:
        job = await session.get(EvalJob, job_id)
        if job is None:
            return
        if job.status in {"completed", "failed", "cancelled"}:
            return
        job.progress_total = max(progress_total, 0)
        job.progress_done = min(max(progress_done, 0), job.progress_total or progress_total)
        await session.commit()


async def _mark_eval_job_cancelled(
    job_id: UUID,
    *,
    finished_at: datetime | None = None,
) -> None:
    async with SessionLocal() as session:
        job = await session.get(EvalJob, job_id)
        if job is None:
            return
        if job.status == "cancelled":
            return
        job.cancel_requested = True
        job.status = "cancelled"
        job.finished_at = finished_at or _utc_now()
        await session.commit()


async def _is_eval_job_cancel_requested(job_id: UUID) -> bool:
    async with SessionLocal() as session:
        job = await session.get(EvalJob, job_id)
        if job is None:
            return True
        return job.cancel_requested or job.status == "cancelled"


async def _get_eval_job_status(job_id: UUID) -> str:
    async with SessionLocal() as session:
        job = await session.get(EvalJob, job_id)
        if job is None:
            return "missing"
        return job.status


def _raise_if_cancel_requested(cancel_event: threading.Event) -> None:
    if cancel_event.is_set():
        raise EvalCancelledError("Eval job was cancelled.")


async def _resolve_model_config(
    session,
    *,
    model_id: UUID | None,
    fallback_name: str | None = None,
) -> _ResolvedModelConfig:
    model: Model | None = None
    if model_id is not None:
        model = await session.get(Model, model_id)
    if model is None and fallback_name:
        row = await session.execute(
            select(Model).where(
                (Model.name == fallback_name) | (Model.model_code == fallback_name),
            )
        )
        model = row.scalar_one_or_none()
    if model is None:
        raise ValueError("评测模型不存在或未同步到模型注册表。")

    if model.provider_id is None:
        raise ValueError(f"模型 {model.name} 未绑定 Provider。")

    provider = await session.get(ModelProvider, model.provider_id)
    if provider is None:
        raise ValueError(f"模型 {model.name} 绑定的 Provider 不存在。")
    if not provider.base_url.strip():
        raise ValueError(f"Provider {provider.name} 缺少 base_url。")

    return _ResolvedModelConfig(
        model_name=(model.model_code or model.name).strip(),
        display_name=model.name,
        api_url=provider.base_url.strip(),
        api_key=provider.api_key,
        api_format=(model.api_format or provider.api_format or "chat-completions").strip(),
        organization=provider.organization,
        headers={str(key): str(value) for key, value in (provider.headers_json or {}).items()},
    )


async def _resolve_dataset_input(
    session,
    payload: EvalJobCreate,
) -> _ResolvedDatasetInput:
    benchmark_name = payload.benchmark_name.strip() if payload.benchmark_name else None
    benchmark_definition, version = await resolve_benchmark_version_record(
        session,
        benchmark_name=benchmark_name,
        version_id=_payload_version_id(payload),
    )

    if payload.dataset_source_type not in (
        "benchmark-version",
        "benchmark-preset",
        "preset-suite",
    ):
        raise ValueError("当前系统仅支持通过 Benchmark Version 创建评测任务。")
    if benchmark_definition is None:
        raise ValueError("请选择可用 Benchmark。")
    if version is None:
        raise ValueError("请选择可用 Benchmark Version。")
    dataset_path = _materialize_benchmark_version_dataset(
        dataset_source_uri=version.dataset_source_uri,
        dataset_path=version.dataset_path,
    )
    field_mapping = dict(benchmark_definition.field_mapping_json or {})
    prompt_config = dict(benchmark_definition.prompt_config_json or {})
    if payload.benchmark_config:
        prompt_config.update(payload.benchmark_config)
    if payload.judge_prompt:
        prompt_config["judge_prompt_template"] = payload.judge_prompt

    eval_method = (benchmark_definition.default_eval_method or payload.eval_method or "accuracy").strip()
    template_config: ExecutorTemplateConfig | None = None
    template_id: UUID | None = None
    template_version: int | None = None
    template_model_name: str | None = None
    if benchmark_definition.eval_template_id:
        from nta_backend.models.eval_template import EvalTemplate

        template = await session.get(EvalTemplate, benchmark_definition.eval_template_id)
        if template is not None:
            template_config = ExecutorTemplateConfig(
                prompt=template.prompt,
                vars=list(template.vars or []),
                output_type=template.output_type,
                output_config=dict(template.output_config or {}),
            )
            eval_method = "judge-template"
            template_id = template.id
            template_version = template.version
            template_model_name = (template.model or "").strip() or None

    return _ResolvedDatasetInput(
        benchmark_name=benchmark_definition.name,
        dataset_path=str(dataset_path),
        source_uri=f"benchmark://{benchmark_definition.name}/versions/{version.version_id}",
        prompt_config=prompt_config,
        field_mapping=field_mapping,
        eval_method=eval_method,
        template_config=template_config,
        template_id=template_id,
        template_version=template_version,
        template_model_name=template_model_name,
    )


def _materialize_benchmark_version_dataset(
    *,
    dataset_source_uri: str | None,
    dataset_path: str | None,
) -> Path:
    if dataset_path:
        local_path = Path(dataset_path)
        if local_path.exists():
            return local_path

    if dataset_source_uri and dataset_source_uri.startswith("file://"):
        local_path = Path(dataset_source_uri.removeprefix("file://"))
        if local_path.exists():
            return local_path
        raise FileNotFoundError(str(local_path))

    if dataset_source_uri and dataset_source_uri.startswith("/"):
        local_path = Path(dataset_source_uri)
        if local_path.exists():
            return local_path
        raise FileNotFoundError(str(local_path))

    parsed = _parse_s3_uri(dataset_source_uri)
    if parsed is None:
        raise FileNotFoundError(str(dataset_source_uri or dataset_path))

    bucket, object_key = parsed
    payload = get_object_bytes(bucket, object_key)
    suffix = Path(object_key).suffix or ".jsonl"
    with NamedTemporaryFile(
        mode="wb",
        suffix=suffix,
        prefix="benchmark-version-",
        delete=False,
    ) as handle:
        handle.write(payload.body)
        return Path(handle.name)


def _persist_eval_metrics(session, job_id: UUID, report_payload: dict[str, Any]) -> None:
    subset_reports = report_payload.get("subset_reports")
    if not isinstance(subset_reports, list):
        return

    for subset in subset_reports:
        if not isinstance(subset, dict):
            continue
        subset_name = subset.get("subset")
        metrics = subset.get("metrics")
        if not isinstance(metrics, list):
            continue
        for metric in metrics:
            if not isinstance(metric, dict):
                continue
            extra = metric.get("extra")
            session.add(
                EvalJobMetric(
                    eval_job_id=job_id,
                    metric_name=str(metric.get("metric") or "-"),
                    metric_value=float(metric.get("value") or 0.0),
                    metric_unit=None,
                    extra_json=(
                        {
                            "subset": subset_name,
                            **extra,
                        }
                        if isinstance(extra, dict)
                        else ({"subset": subset_name} if subset_name else None)
                    ),
                )
            )


def _load_eval_report_payload(job: EvalJob) -> dict[str, Any] | None:
    report_uri = job.report_object_uri
    if not report_uri:
        return None

    path = Path(report_uri)
    if path.exists():
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return None

    parsed = _parse_s3_uri(report_uri)
    if parsed is None:
        return None

    bucket, object_key = parsed
    try:
        payload = get_object_bytes(bucket, object_key)
    except FileNotFoundError:
        return None
    try:
        return json.loads(payload.body.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError):
        return None


def _report_metrics_from_payload(payload: dict[str, Any]) -> list[EvalMetric]:
    subset_reports = payload.get("subset_reports")
    if not isinstance(subset_reports, list):
        return []

    metrics: list[EvalMetric] = []
    for subset in subset_reports:
        if not isinstance(subset, dict):
            continue
        subset_metrics = subset.get("metrics")
        if not isinstance(subset_metrics, list):
            continue
        for metric in subset_metrics:
            if not isinstance(metric, dict):
                continue
            metrics.append(
                EvalMetric(
                    metric_name=str(metric.get("metric") or "-"),
                    metric_value=float(metric.get("value") or 0.0),
                    metric_unit=None,
                )
            )
    return metrics


def _sample_analysis_from_report(job: EvalJob, payload: dict[str, Any]) -> list[EvalSampleAnalysis]:
    subset_reports = payload.get("subset_reports")
    if not isinstance(subset_reports, list):
        return []

    analyses: list[EvalSampleAnalysis] = []
    for subset in subset_reports:
        if not isinstance(subset, dict):
            continue
        sample_scores = subset.get("sample_scores")
        if not isinstance(sample_scores, list):
            continue
        for sample_score in sample_scores:
            if not isinstance(sample_score, dict):
                continue
            numeric_score = sample_score.get("score")
            score = float(numeric_score) if isinstance(numeric_score, (int, float)) else None
            references = sample_score.get("reference_answers")
            analyses.append(
                EvalSampleAnalysis(
                    sample_id=str(sample_score.get("sample_id") or "-"),
                    method=str(sample_score.get("metric") or job.eval_method or "-"),
                    input_preview=str(sample_score.get("input_preview") or "") or None,
                    prediction_text=str(sample_score.get("prediction_text") or "") or None,
                    reference_answers=(
                        [str(item) for item in references if str(item).strip()]
                        if isinstance(references, list)
                        else []
                    ),
                    score=score,
                    raw_score=(
                        float(sample_score.get("raw_score"))
                        if isinstance(sample_score.get("raw_score"), (int, float))
                        else score
                    ),
                    passed=bool(sample_score.get("passed")),
                    reason=str(sample_score.get("reason") or "") or None,
                    error=str(sample_score.get("error") or "") or None,
                    latency_ms=(
                        int(sample_score.get("latency_ms"))
                        if isinstance(sample_score.get("latency_ms"), (int, float))
                        else None
                    ),
                    total_tokens=(
                        int(sample_score.get("total_tokens"))
                        if isinstance(sample_score.get("total_tokens"), (int, float))
                        else None
                    ),
                    judge_model_name=(
                        str(sample_score.get("judge_model_name") or "") or job.judge_model_name
                    ),
                )
            )
    return analyses


def _to_metric_rows(rows: list[EvalJobMetric]) -> list[EvalMetric]:
    return [
        EvalMetric(
            metric_name=row.metric_name,
            metric_value=row.metric_value,
            metric_unit=row.metric_unit,
        )
        for row in rows
    ]


def _to_detail(
    job: EvalJob,
    *,
    metrics: list[EvalMetric],
    sample_analysis: list[EvalSampleAnalysis],
    benchmark_version_name: str | None = None,
) -> EvalJobDetail:
    benchmark_name = job.benchmark_name
    benchmark_version_id = job.benchmark_version_id
    if benchmark_name is None or benchmark_version_id is None:
        parsed_name, parsed_version_id = _parse_benchmark_source_uri(job.dataset_source_uri)
        benchmark_name = benchmark_name or parsed_name
        benchmark_version_id = benchmark_version_id or parsed_version_id

    return EvalJobDetail(
        **_to_summary(job).model_dump(),
        benchmark_name=benchmark_name,
        benchmark_version_id=benchmark_version_id,
        benchmark_version_name=benchmark_version_name or job.dataset_name or benchmark_version_id,
        access_source=job.access_source or "nta",
        dataset_source_type=job.dataset_source_type or "benchmark-version",
        dataset_version_id=job.dataset_version_id,
        dataset_name=job.dataset_name or "-",
        dataset_source_uri=job.dataset_source_uri,
        artifact_prefix_uri=job.artifact_prefix_uri,
        source_object_uri=job.source_object_uri,
        results_prefix_uri=job.results_prefix_uri,
        samples_prefix_uri=job.samples_prefix_uri,
        report_object_uri=job.report_object_uri,
        task_type=job.task_type or "single-turn",
        eval_mode=job.eval_mode or "infer-auto",
        endpoint_name=job.endpoint_name,
        judge_model_name=job.judge_model_name,
        judge_prompt=job.judge_prompt_text,
        rubric=job.criteria_text,
        batch_job_id=job.batch_job_id,
        metrics=metrics,
        sample_analysis=sample_analysis,
    )


async def _run_eval_job(
    job_id: UUID,
    payload: EvalJobCreate,
    *,
    cancel_event: threading.Event,
    progress_listener: Callable[[int, int], None] | None = None,
) -> None:
    async with SessionLocal() as session:
        output_dir: Path | None = None
        try:
            job = await _get_job_or_raise(session, job_id)
            if job.status == "cancelled":
                return
            if job.cancel_requested:
                job.status = "cancelled"
                job.finished_at = job.finished_at or _utc_now()
                await session.commit()
                return
            output_dir = _eval_output_dir(job)
            output_dir.mkdir(parents=True, exist_ok=True)

            job.status = "preparing"
            job.started_at = _utc_now()
            job.finished_at = None
            job.error_message = None
            await session.commit()
            _raise_if_cancel_requested(cancel_event)

            eval_model = await _resolve_model_config(
                session,
                model_id=payload.model_id,
                fallback_name=payload.model_name,
            )
            dataset_input = await _resolve_dataset_input(session, payload=payload)
            judge_model: _ResolvedModelConfig | None = None
            if _eval_method_requires_judge_model(dataset_input.eval_method):
                judge_model = await _resolve_model_config(
                    session,
                    model_id=payload.judge_model_id or payload.model_id,
                    fallback_name=(
                        dataset_input.template_model_name
                        or payload.judge_model_name
                        or payload.model_name
                    ),
                )

            job.model_name = eval_model.display_name
            job.judge_model_name = judge_model.display_name if judge_model is not None else None
            job.eval_method = dataset_input.eval_method
            job.source_object_uri = dataset_input.source_uri
            job.eval_template_id = dataset_input.template_id
            job.eval_template_version = dataset_input.template_version
            await session.commit()
            _raise_if_cancel_requested(cancel_event)

            job.status = "inferencing"
            await session.commit()
            loop = asyncio.get_running_loop()

            def _progress_callback(progress_done: int, progress_total: int) -> None:
                asyncio.run_coroutine_threadsafe(
                    _persist_eval_job_progress(
                        job_id,
                        progress_done=progress_done,
                        progress_total=progress_total,
                    ),
                    loop,
                )
                if progress_listener is not None:
                    loop.call_soon_threadsafe(progress_listener, progress_done, progress_total)

            execution_request = EvalExecutionRequest(
                benchmark_name=dataset_input.benchmark_name,
                dataset_path=dataset_input.dataset_path,
                output_dir=output_dir,
                eval_method=dataset_input.eval_method,
                eval_model=ExecutorModelConfig(
                    model_name=eval_model.model_name,
                    display_name=eval_model.display_name,
                    api_url=eval_model.api_url,
                    api_key=eval_model.api_key,
                    api_format=eval_model.api_format,
                    organization=eval_model.organization,
                    headers=dict(eval_model.headers),
                ),
                judge_model=(
                    ExecutorModelConfig(
                        model_name=judge_model.model_name,
                        display_name=judge_model.display_name,
                        api_url=judge_model.api_url,
                        api_key=judge_model.api_key,
                        api_format=judge_model.api_format,
                        organization=judge_model.organization,
                        headers=dict(judge_model.headers),
                    )
                    if judge_model is not None
                    else None
                ),
                field_mapping=dataset_input.field_mapping,
                prompt_config=dataset_input.prompt_config,
                template_config=dataset_input.template_config,
                progress_callback=_progress_callback,
                cancellation_event=cancel_event,
            )
            execution_result = await asyncio.to_thread(_EVAL_EXECUTOR.execute, execution_request)
            _raise_if_cancel_requested(cancel_event)

            job.status = "scoring"
            await session.commit()

            (
                artifact_prefix_uri,
                results_prefix_uri,
                samples_prefix_uri,
                report_object_uri,
            ) = await asyncio.to_thread(_upload_eval_artifacts, job, output_dir)
            job.artifact_prefix_uri = artifact_prefix_uri
            job.report_object_uri = report_object_uri
            job.results_prefix_uri = results_prefix_uri
            job.samples_prefix_uri = samples_prefix_uri

            await session.execute(delete(EvalJobMetric).where(EvalJobMetric.eval_job_id == job.id))
            _persist_eval_metrics(session, job.id, execution_result.report_payload)

            job.status = "completed"
            job.cancel_requested = False
            job.finished_at = _utc_now()
            job.error_message = None
            await session.commit()
        except EvalExecutionCancelledError:
            await session.rollback()
            await _mark_eval_job_cancelled(job_id)
        except asyncio.CancelledError:
            await session.rollback()
            await _mark_eval_job_cancelled(job_id)
        except KeyError:
            await session.rollback()
            return
        except Exception as exc:
            await session.rollback()
            try:
                job = await _get_job_or_raise(session, job_id)
            except KeyError:
                return
            job.status = "failed"
            job.finished_at = _utc_now()
            job.error_message = _truncate_error_message(str(exc) or exc.__class__.__name__)
            await session.commit()
        finally:
            if output_dir is not None:
                _cleanup_local_eval_artifacts({output_dir})


async def activity_is_eval_job_cancel_requested(*, job_id: str) -> bool:
    return await _is_eval_job_cancel_requested(UUID(job_id))


async def activity_run_eval_job(
    *,
    job_id: str,
    payload_data: dict[str, object],
    cancel_event: threading.Event,
    progress_listener: Callable[[int, int], None] | None = None,
) -> dict[str, str]:
    payload = EvalJobCreate.model_validate(payload_data)
    job_uuid = UUID(job_id)
    await _run_eval_job(
        job_uuid,
        payload,
        cancel_event=cancel_event,
        progress_listener=progress_listener,
    )
    return {"job_id": job_id, "status": await _get_eval_job_status(job_uuid)}


async def _get_eval_job_workflow_state(workflow_id: str):
    from nta_backend.core.temporal import get_workflow_execution_state

    return await get_workflow_execution_state(workflow_id)


async def _cancel_eval_job_workflow(workflow_id: str) -> None:
    from nta_backend.core.temporal import cancel_workflow_execution

    await cancel_workflow_execution(workflow_id)


async def _sync_eval_job_with_temporal_state(session, job: EvalJob) -> bool:
    if not job.temporal_workflow_id or job.status in _TERMINAL_STATUSES:
        return False
    try:
        workflow_state = await _get_eval_job_workflow_state(job.temporal_workflow_id)
    except Exception:
        return False
    target_status = _TEMPORAL_TO_JOB_STATUS.get(workflow_state.status)
    if target_status is None or target_status == job.status:
        return False
    job.status = target_status
    job.finished_at = job.finished_at or _utc_now()
    if target_status == "cancelled":
        job.cancel_requested = True
    if target_status == "failed":
        job.error_message = _truncate_error_message(
            workflow_state.failure_message or "Temporal workflow failed."
        )
    return True


class EvalJobService:
    async def list_eval_jobs(self) -> list[EvalJobSummary]:
        async with SessionLocal() as session:
            project_id = await resolve_active_project_id(session)
            rows = await session.execute(
                select(EvalJob)
                .where(EvalJob.project_id == project_id)
                .order_by(EvalJob.created_at.desc(), EvalJob.id.desc())
            )
            jobs = rows.scalars().all()
            changed = False
            for job in jobs:
                changed = await _sync_eval_job_with_temporal_state(session, job) or changed
            if changed:
                await session.commit()
                for job in jobs:
                    await session.refresh(job)
            return [_to_summary(job) for job in jobs]

    async def get_eval_job(self, job_id: str) -> EvalJobDetail:
        async with SessionLocal() as session:
            project_id = await resolve_active_project_id(session)
            job = await _get_job_by_identifier_or_raise(
                session,
                project_id=project_id,
                job_identifier=job_id,
            )
            if await _sync_eval_job_with_temporal_state(session, job):
                await session.commit()
                await session.refresh(job)
            metric_rows = (
                await session.execute(
                    select(EvalJobMetric)
                    .where(EvalJobMetric.eval_job_id == job.id)
                    .order_by(EvalJobMetric.created_at.asc(), EvalJobMetric.id.asc())
                )
            ).scalars().all()

            report_payload = _load_eval_report_payload(job)
            metrics = _to_metric_rows(metric_rows)
            if not metrics and report_payload is not None:
                metrics = _report_metrics_from_payload(report_payload)
            sample_analysis = []
            if report_payload is not None:
                sample_analysis = _sample_analysis_from_report(job, report_payload)
            _, benchmark_version = await resolve_benchmark_version_record(
                session,
                benchmark_name=job.benchmark_name,
                version_id=job.benchmark_version_id,
            )
            return _to_detail(
                job,
                metrics=metrics,
                sample_analysis=sample_analysis,
                benchmark_version_name=(
                    benchmark_version.display_name if benchmark_version is not None else None
                ),
            )

    async def create_eval_job(self, payload: EvalJobCreate) -> EvalJobSummary:
        async with SessionLocal() as session:
            project_id = await resolve_active_project_id(session)
            user = await resolve_current_user(session)

            benchmark_name = payload.benchmark_name.strip() if payload.benchmark_name else None
            benchmark_definition, version = await resolve_benchmark_version_record(
                session,
                benchmark_name=benchmark_name,
                version_id=_payload_version_id(payload),
            )
            if benchmark_name and (
                await get_benchmark_definition_record(session, benchmark_name) is None
            ):
                raise ValueError("所选 Benchmark 不存在。")
            if benchmark_definition is None or version is None:
                raise ValueError("所选 Benchmark Version 不存在。")
            benchmark_name = benchmark_definition.name

            dataset_name = version.display_name
            dataset_version_id = None
            dataset_source_type = "benchmark-version"
            dataset_source_uri = f"benchmark://{benchmark_name}/versions/{version.version_id}"
            resolved_eval_method = (
                "judge-template"
                if benchmark_definition.eval_template_id is not None
                else (benchmark_definition.default_eval_method or payload.eval_method)
            )

            job = EvalJob(
                project_id=project_id,
                name=payload.name.strip(),
                description=payload.description,
                created_by=user.id,
                created_by_name=user.name,
                status="queued",
                model_source=payload.model_source,
                model_name=payload.model_name,
                model_id=payload.model_id,
                access_source=payload.access_source,
                benchmark_name=benchmark_name,
                benchmark_version_id=version.version_id,
                benchmark_config_json=payload.benchmark_config,
                inference_mode=payload.inference_mode,
                task_type=payload.task_type,
                eval_mode=payload.eval_mode,
                eval_method=resolved_eval_method,
                criteria_text=payload.rubric,
                endpoint_name=payload.endpoint_name,
                judge_model_name=payload.judge_model_name,
                judge_prompt_text=payload.judge_prompt,
                dataset_version_id=dataset_version_id,
                dataset_source_type=dataset_source_type,
                dataset_name=dataset_name,
                dataset_source_uri=dataset_source_uri,
                auto_progress=True,
                progress_total=version.sample_count,
                progress_done=0,
                cancel_requested=False,
            )
            session.add(job)
            await session.flush()

            artifact_prefix = build_eval_job_prefix(project_id, job.id, job.created_at)
            artifact_prefix_uri = _build_s3_uri(EVAL_ARTIFACT_BUCKET, artifact_prefix)
            job.artifact_prefix_uri = artifact_prefix_uri
            job.results_prefix_uri = artifact_prefix_uri
            job.samples_prefix_uri = artifact_prefix_uri
            job.temporal_workflow_id = f"eval-job-{job.id}"
            await session.commit()
            await session.refresh(job)

        from nta_backend.core.temporal import start_eval_job_workflow
        from nta_backend.workflows.eval_job import EvalJobWorkflowInput

        workflow_input = EvalJobWorkflowInput(
            job_id=str(job.id),
            payload=payload.model_dump(mode="json"),
        )

        try:
            await start_eval_job_workflow(
                workflow_input,
                workflow_id=job.temporal_workflow_id,
            )
        except Exception as exc:
            async with SessionLocal() as session:
                persisted = await session.get(EvalJob, job.id)
                if persisted is not None and persisted.status == "queued":
                    persisted.status = "failed"
                    persisted.finished_at = _utc_now()
                    persisted.error_message = _truncate_error_message(
                        f"Failed to start eval workflow: {exc}"
                    )
                    await session.commit()
            raise RuntimeError("启动评测工作流失败。") from exc
        return _to_summary(job)

    async def stop_eval_job(self, job_id: str) -> EvalJobSummary:
        async with SessionLocal() as session:
            project_id = await resolve_active_project_id(session)
            job = await _get_job_by_identifier_or_raise(
                session,
                project_id=project_id,
                job_identifier=job_id,
            )
            if await _sync_eval_job_with_temporal_state(session, job):
                await session.commit()
                await session.refresh(job)
            if job.status not in _STOPPABLE_STATUSES:
                raise ValueError("当前任务状态不支持停止。")
            if not job.temporal_workflow_id:
                raise ValueError("评测任务未绑定 Temporal workflow，无法停止。")

            job.cancel_requested = True
            if job.status != "cancelling":
                job.status = "cancelling"
            await session.commit()
            await session.refresh(job)
            workflow_id = job.temporal_workflow_id
            summary = _to_summary(job)

        try:
            await _cancel_eval_job_workflow(workflow_id)
        except Exception as exc:
            async with SessionLocal() as session:
                project_id = await resolve_active_project_id(session)
                persisted = await _get_job_by_identifier_or_raise(
                    session,
                    project_id=project_id,
                    job_identifier=job_id,
                )
                if await _sync_eval_job_with_temporal_state(session, persisted):
                    await session.commit()
                    await session.refresh(persisted)
                    return _to_summary(persisted)
            raise RuntimeError("取消评测工作流失败。") from exc
        return summary

    async def delete_eval_job(self, job_id: str) -> None:
        async with SessionLocal() as session:
            project_id = await resolve_active_project_id(session)
            job = await _get_job_by_identifier_or_raise(
                session,
                project_id=project_id,
                job_identifier=job_id,
            )
            if job.status in _DELETE_BLOCKED_STATUSES:
                raise ValueError("运行中的评测任务暂不支持删除，请等待任务完成后再删除。")

            local_paths, s3_prefixes, s3_objects = _collect_eval_artifact_cleanup(job)
            await session.delete(job)
            await session.commit()

        try:
            _cleanup_local_eval_artifacts(local_paths)
        except OSError:
            pass
        for bucket, object_key in s3_objects:
            try:
                delete_object(bucket, object_key)
            except Exception:
                continue
        for bucket, prefix in s3_prefixes:
            try:
                delete_object_prefix(bucket, prefix)
            except Exception:
                continue
