from __future__ import annotations

import asyncio
import json
import threading
from datetime import UTC, datetime
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Any
from uuid import UUID

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from nta_backend.core.auth_context import resolve_current_user
from nta_backend.core.config import get_settings
from nta_backend.core.db import SessionLocal
from nta_backend.core.object_store import (
    create_object_prefix,
    delete_object_prefix,
    get_object_bytes,
    put_object_bytes,
)
from nta_backend.core.project_context import resolve_active_project_id
from nta_backend.evaluation_v2.compiler import compile_run_request
from nta_backend.evaluation_v2.engine_registry import get_engine_adapter
from nta_backend.evaluation_v2.execution import ExecutionCancelledError, ExecutionContext
from nta_backend.models.evaluation_v2 import (
    EvaluationRun,
    EvaluationRunArtifact,
    EvaluationRunEvent,
    EvaluationRunItem,
    EvaluationRunMetric,
    EvaluationRunSample,
    EvalSpec,
    EvalSpecVersion,
    EvalSuite,
    EvalSuiteVersion,
    JudgePolicy,
    TemplateSpec,
    TemplateSpecVersion,
)
from nta_backend.schemas.evaluation_v2 import (
    CompiledRunItemPlan,
    EvaluationRunCancelResponse,
    EvaluationRunCreate,
    EvaluationRunDetail,
    EvaluationRunItemResponse,
    EvaluationRunMetricResponse,
    EvaluationRunSampleResponse,
    EvaluationRunSummary,
)

EVAL_ARTIFACT_BUCKET = get_settings().s3_bucket_eval_artifacts


def _utc_now() -> datetime:
    return datetime.now(UTC)


def _build_s3_uri(bucket: str, object_key: str) -> str:
    return f"s3://{bucket}/{object_key}"


def _run_prefix(project_id: UUID, run_id: UUID) -> str:
    return f"projects/{project_id}/evaluation-runs/{run_id}/"


def _run_item_prefix(project_id: UUID, run_id: UUID, item_id: UUID) -> str:
    return f"{_run_prefix(project_id, run_id)}items/{item_id}/"


def _guess_content_type(path: Path) -> str | None:
    if path.suffix == ".json":
        return "application/json"
    if path.suffix == ".jsonl":
        return "application/x-ndjson"
    if path.suffix == ".log":
        return "text/plain"
    if path.suffix == ".yaml":
        return "application/x-yaml"
    return None


def _progress_percent(done: int | None, total: int | None) -> tuple[int | None, int | None]:
    if total is None or total <= 0:
        return done, total
    normalized_done = min(max(done or 0, 0), total)
    return normalized_done, total


def _is_workflow_not_found_error(exc: Exception) -> bool:
    return "workflow not found" in str(exc).lower()


def _serialize_metric(metric: EvaluationRunMetric) -> EvaluationRunMetricResponse:
    return EvaluationRunMetricResponse(
        metric_name=metric.metric_name,
        metric_value=metric.metric_value,
        metric_scope=metric.metric_scope,
        metric_unit=metric.metric_unit,
        dimension_json=dict(metric.dimension_json or {}),
        extra_json=dict(metric.extra_json or {}),
    )


def _serialize_sample(sample: EvaluationRunSample) -> EvaluationRunSampleResponse:
    return EvaluationRunSampleResponse(
        sample_id=sample.sample_id,
        subset_name=sample.subset_name,
        input_preview=sample.input_preview,
        prediction_text=sample.prediction_text,
        reference_answers_json=list(sample.reference_answers_json or []),
        score=sample.score,
        raw_score=sample.raw_score,
        passed=sample.passed,
        reason=sample.reason,
        error=sample.error,
        latency_ms=sample.latency_ms,
        total_tokens=sample.total_tokens,
        metadata_json=dict(sample.metadata_json or {}),
    )


def _serialize_item(
    item: EvaluationRunItem,
    *,
    metrics: list[EvaluationRunMetric],
    samples: list[EvaluationRunSample],
) -> EvaluationRunItemResponse:
    return EvaluationRunItemResponse(
        id=item.id,
        item_key=item.item_key,
        display_name=item.display_name,
        group_name=item.group_name,
        weight=item.weight,
        status=item.status,
        engine=item.engine,
        execution_mode=item.execution_mode,
        report_uri=item.report_uri,
        raw_output_prefix_uri=item.raw_output_prefix_uri,
        temporal_workflow_id=item.temporal_workflow_id,
        progress_total=item.progress_total,
        progress_done=item.progress_done,
        error_code=item.error_code,
        error_message=item.error_message,
        started_at=item.started_at,
        finished_at=item.finished_at,
        metrics=[_serialize_metric(metric) for metric in metrics],
        samples=[_serialize_sample(sample) for sample in samples],
    )


def _serialize_run_summary(run: EvaluationRun) -> EvaluationRunSummary:
    done, total = _progress_percent(run.progress_done, run.progress_total)
    return EvaluationRunSummary(
        id=run.id,
        name=run.name,
        description=run.description,
        kind=run.kind,
        status=run.status,
        model_name=run.model_name,
        summary_report_uri=run.summary_report_uri,
        temporal_workflow_id=run.temporal_workflow_id,
        progress_total=total,
        progress_done=done,
        error_code=run.error_code,
        error_message=run.error_message,
        created_at=run.created_at,
        started_at=run.started_at,
        finished_at=run.finished_at,
    )


async def _get_run_or_raise(
    session: AsyncSession,
    *,
    project_id: UUID,
    run_id: UUID,
) -> EvaluationRun:
    row = await session.execute(
        select(EvaluationRun).where(
            EvaluationRun.id == run_id,
            EvaluationRun.project_id == project_id,
        )
    )
    run = row.scalar_one_or_none()
    if run is None:
        raise KeyError(str(run_id))
    return run


async def _is_run_cancel_requested(run_id: UUID) -> bool:
    async with SessionLocal() as session:
        run = await session.get(EvaluationRun, run_id)
        if run is None:
            return False
        return bool(run.cancel_requested or run.status in {"cancelling", "cancelled"})


async def _persist_run_progress(run_id: UUID) -> None:
    async with SessionLocal() as session:
        run = await session.get(EvaluationRun, run_id)
        if run is None:
            return
        rows = await session.execute(
            select(EvaluationRunItem.status).where(EvaluationRunItem.run_id == run_id)
        )
        statuses = [value for value in rows.scalars().all()]
        run.progress_total = len(statuses)
        run.progress_done = sum(
            1 for status in statuses if status in {"completed", "failed", "cancelled"}
        )
        await session.commit()


async def _force_finalize_run_terminal(
    run_id: UUID,
    *,
    item_status: str,
    run_error_message: str | None = None,
    item_error_message: str | None = None,
) -> None:
    terminal_item_statuses = {"completed", "failed", "cancelled"}
    if item_status not in terminal_item_statuses:
        raise ValueError(f"Unsupported terminal item status: {item_status}")

    async with SessionLocal() as session:
        run = await session.get(EvaluationRun, run_id)
        if run is None:
            return
        now = _utc_now()
        item_rows = (
            await session.execute(
                select(EvaluationRunItem)
                .where(EvaluationRunItem.run_id == run_id)
                .order_by(EvaluationRunItem.created_at.asc(), EvaluationRunItem.id.asc())
            )
        ).scalars().all()
        for item in item_rows:
            if item.status in terminal_item_statuses:
                continue
            item.status = item_status
            item.finished_at = item.finished_at or now
            if item_status == "failed":
                item.error_message = (item_error_message or run_error_message or "Temporal workflow not found.")[
                    :500
                ]
        if item_status == "failed":
            run.error_message = (run_error_message or "Temporal workflow not found.")[:500]
        await session.commit()

    await _persist_run_progress(run_id)
    await aggregate_run_summary(run_id=str(run_id))


async def _reconcile_non_terminal_run(run_id: UUID) -> None:
    async with SessionLocal() as session:
        run = await session.get(EvaluationRun, run_id)
        if run is None or run.status in {"completed", "failed", "cancelled"}:
            return
        workflow_id = run.temporal_workflow_id
        cancel_requested = bool(run.cancel_requested or run.status == "cancelling")

    async def _has_non_terminal_items() -> bool:
        async with SessionLocal() as session:
            rows = await session.execute(
                select(EvaluationRunItem.status).where(EvaluationRunItem.run_id == run_id)
            )
            return any(status not in {"completed", "failed", "cancelled"} for status in rows.scalars().all())

    if not workflow_id:
        await _force_finalize_run_terminal(
            run_id,
            item_status="cancelled" if cancel_requested else "failed",
            run_error_message=None if cancel_requested else "Temporal workflow id is missing.",
            item_error_message=None if cancel_requested else "Temporal workflow id is missing.",
        )
        return

    from nta_backend.core.temporal import get_workflow_execution_state

    try:
        state = await get_workflow_execution_state(workflow_id)
    except Exception as exc:  # noqa: BLE001
        if not _is_workflow_not_found_error(exc):
            return
        await _force_finalize_run_terminal(
            run_id,
            item_status="cancelled" if cancel_requested else "failed",
            run_error_message=None if cancel_requested else "Temporal workflow not found.",
            item_error_message=None if cancel_requested else "Temporal workflow not found.",
        )
        return

    if not state.is_terminal:
        return

    if state.status in {"cancelled", "terminated"}:
        await _force_finalize_run_terminal(run_id, item_status="cancelled")
        return
    if state.status in {"failed", "timed_out"}:
        message = state.failure_message or f"Temporal workflow {state.status}."
        await _force_finalize_run_terminal(
            run_id,
            item_status="failed",
            run_error_message=message,
            item_error_message=message,
        )
        return
    if state.status == "completed":
        if await _has_non_terminal_items():
            await _force_finalize_run_terminal(
                run_id,
                item_status="cancelled" if cancel_requested else "failed",
                run_error_message=(
                    "Temporal workflow completed before all evaluation items reached a terminal state."
                ),
                item_error_message=(
                    "Temporal workflow completed before this evaluation item reached a terminal state."
                ),
            )
            return
        await aggregate_run_summary(run_id=str(run_id))


async def _persist_item_progress(item_id: UUID, *, progress_done: int, progress_total: int) -> None:
    async with SessionLocal() as session:
        item = await session.get(EvaluationRunItem, item_id)
        if item is None:
            return
        item.progress_total = max(progress_total, 0)
        item.progress_done = min(max(progress_done, 0), item.progress_total or progress_total)
        await session.commit()
        await _persist_run_progress(item.run_id)


def _upload_item_artifacts(
    *,
    project_id: UUID,
    run_id: UUID,
    item_id: UUID,
    output_dir: Path,
) -> tuple[str | None, str | None, list[dict[str, Any]]]:
    prefix = _run_item_prefix(project_id, run_id, item_id)
    create_object_prefix(EVAL_ARTIFACT_BUCKET, prefix)
    report_uri: str | None = None
    artifact_rows: list[dict[str, Any]] = []
    for artifact_path in sorted(output_dir.rglob("*")):
        if not artifact_path.is_file():
            continue
        relative_path = artifact_path.relative_to(output_dir).as_posix()
        object_key = f"{prefix}{relative_path}"
        put_object_bytes(
            EVAL_ARTIFACT_BUCKET,
            object_key,
            artifact_path.read_bytes(),
            content_type=_guess_content_type(artifact_path),
        )
        uri = _build_s3_uri(EVAL_ARTIFACT_BUCKET, object_key)
        if relative_path == "canonical-report.json":
            report_uri = uri
            artifact_type = "canonical-report"
        else:
            artifact_type = relative_path.split("/", 1)[0] if "/" in relative_path else "raw-output"
        artifact_rows.append(
            {
                "artifact_type": artifact_type,
                "uri": uri,
                "content_type": _guess_content_type(artifact_path),
                "extra_json": {"relative_path": relative_path},
            }
        )
    return report_uri, _build_s3_uri(EVAL_ARTIFACT_BUCKET, prefix), artifact_rows


async def _persist_item_result(
    session: AsyncSession,
    *,
    run: EvaluationRun,
    item: EvaluationRunItem,
    report_payload: dict[str, Any],
    output_dir: Path,
) -> None:
    report_uri, raw_prefix_uri, artifact_rows = _upload_item_artifacts(
        project_id=run.project_id,
        run_id=run.id,
        item_id=item.id,
        output_dir=output_dir,
    )
    item.report_uri = report_uri
    item.raw_output_prefix_uri = raw_prefix_uri
    item.status = "completed"
    item.finished_at = _utc_now()
    item.error_code = None
    item.error_message = None
    await session.execute(delete(EvaluationRunMetric).where(EvaluationRunMetric.run_item_id == item.id))
    await session.execute(delete(EvaluationRunSample).where(EvaluationRunSample.run_item_id == item.id))
    await session.execute(delete(EvaluationRunArtifact).where(EvaluationRunArtifact.run_item_id == item.id))

    for metric in report_payload.get("metrics") or []:
        session.add(
            EvaluationRunMetric(
                run_id=run.id,
                run_item_id=item.id,
                metric_name=str(metric.get("metric_name") or "score"),
                metric_value=float(metric.get("metric_value") or 0.0),
                metric_scope=str(metric.get("metric_scope") or "overall"),
                metric_unit=metric.get("metric_unit"),
                dimension_json=dict(metric.get("dimension") or {}),
                extra_json=dict(metric.get("extra") or {}),
            )
        )
    for sample in report_payload.get("samples") or []:
        session.add(
            EvaluationRunSample(
                run_item_id=item.id,
                sample_id=str(sample.get("sample_id") or ""),
                subset_name=sample.get("subset_name"),
                input_preview=sample.get("input_preview"),
                prediction_text=sample.get("prediction_text"),
                reference_answers_json=list(sample.get("reference_answers") or []),
                score=sample.get("score"),
                raw_score=sample.get("raw_score"),
                passed=bool(sample.get("passed")),
                reason=sample.get("reason"),
                error=sample.get("error"),
                latency_ms=sample.get("latency_ms"),
                total_tokens=sample.get("total_tokens"),
                metadata_json=dict(sample.get("metadata") or {}),
            )
        )
    for artifact in artifact_rows:
        session.add(
            EvaluationRunArtifact(
                run_id=run.id,
                run_item_id=item.id,
                artifact_type=artifact["artifact_type"],
                uri=artifact["uri"],
                content_type=artifact["content_type"],
                extra_json=artifact["extra_json"],
            )
        )
    session.add(
        EvaluationRunEvent(
            run_id=run.id,
            run_item_id=item.id,
            event_type="item.completed",
            level="info",
            message="Evaluation item completed.",
            payload_json={"report_uri": report_uri},
            created_at=_utc_now(),
        )
    )


async def aggregate_run_summary(*, run_id: str) -> None:
    async with SessionLocal() as session:
        run = await session.get(EvaluationRun, UUID(run_id))
        if run is None:
            return
        items = (
            await session.execute(
                select(EvaluationRunItem).where(EvaluationRunItem.run_id == run.id).order_by(EvaluationRunItem.id.asc())
            )
        ).scalars().all()
        if not items:
            run.status = "failed"
            run.error_message = "Run contains no evaluation items."
            run.finished_at = _utc_now()
            await session.commit()
            return

        await session.execute(
            delete(EvaluationRunMetric).where(
                EvaluationRunMetric.run_id == run.id,
                EvaluationRunMetric.run_item_id.is_(None),
            )
        )

        item_metrics = (
            await session.execute(
                select(EvaluationRunMetric).where(EvaluationRunMetric.run_id == run.id)
            )
        ).scalars().all()

        overall_item_metrics = [
            metric for metric in item_metrics if metric.run_item_id is not None and metric.metric_scope == "overall"
        ]
        grouped_scores: dict[str, list[tuple[float, float]]] = {}
        overall_scores: list[tuple[float, float]] = []
        item_payloads: list[dict[str, Any]] = []

        for item in items:
            item_payloads.append(
                {
                    "item_id": str(item.id),
                    "item_key": item.item_key,
                    "display_name": item.display_name,
                    "group_name": item.group_name,
                    "weight": item.weight,
                    "status": item.status,
                    "report_uri": item.report_uri,
                }
            )
            metric = next((row for row in overall_item_metrics if row.run_item_id == item.id), None)
            if metric is None:
                continue
            overall_scores.append((metric.metric_value, item.weight))
            if item.group_name:
                grouped_scores.setdefault(item.group_name, []).append((metric.metric_value, item.weight))

        terminal_statuses = {"completed", "failed", "cancelled"}
        if any(item.status == "failed" for item in items):
            run.status = "failed"
        elif any(item.status == "cancelled" for item in items):
            run.status = "cancelled"
        elif any(item.status in {"queued", "running"} for item in items):
            run.status = "cancelling" if run.cancel_requested else "running"
        else:
            run.status = "completed"
        run.finished_at = _utc_now() if run.status in terminal_statuses else None
        run.progress_total = len(items)
        run.progress_done = sum(1 for item in items if item.status in terminal_statuses)

        run_metrics: list[dict[str, Any]] = []
        if overall_scores:
            total_weight = sum(weight for _, weight in overall_scores) or 1.0
            overall_score = sum(score * weight for score, weight in overall_scores) / total_weight
            run_metrics.append({"metric_name": "score", "metric_value": overall_score, "metric_scope": "overall"})
            session.add(
                EvaluationRunMetric(
                    run_id=run.id,
                    run_item_id=None,
                    metric_name="score",
                    metric_value=overall_score,
                    metric_scope="overall",
                    dimension_json={},
                    extra_json={"aggregation": "weighted_mean"},
                )
            )
        for group_name, values in grouped_scores.items():
            total_weight = sum(weight for _, weight in values) or 1.0
            group_score = sum(score * weight for score, weight in values) / total_weight
            run_metrics.append(
                {
                    "metric_name": "score",
                    "metric_value": group_score,
                    "metric_scope": "group",
                    "dimension": {"group_name": group_name},
                }
            )
            session.add(
                EvaluationRunMetric(
                    run_id=run.id,
                    run_item_id=None,
                    metric_name="score",
                    metric_value=group_score,
                    metric_scope="group",
                    dimension_json={"group_name": group_name},
                    extra_json={"aggregation": "weighted_mean"},
                )
            )

        summary_payload = {
            "run_id": str(run.id),
            "kind": run.kind,
            "status": run.status,
            "generated_at": _utc_now().isoformat(),
            "metrics": run_metrics,
            "items": item_payloads,
        }
        object_key = f"{_run_prefix(run.project_id, run.id)}summary-report.json"
        put_object_bytes(
            EVAL_ARTIFACT_BUCKET,
            object_key,
            json.dumps(summary_payload, ensure_ascii=False, indent=2).encode("utf-8"),
            content_type="application/json",
        )
        run.summary_report_uri = _build_s3_uri(EVAL_ARTIFACT_BUCKET, object_key)
        session.add(
            EvaluationRunArtifact(
                run_id=run.id,
                run_item_id=None,
                artifact_type="summary-report",
                uri=run.summary_report_uri,
                content_type="application/json",
                extra_json={},
            )
        )
        session.add(
            EvaluationRunEvent(
                run_id=run.id,
                run_item_id=None,
                event_type="run.completed",
                level="info",
                message="Evaluation run aggregated.",
                payload_json={"status": run.status},
                created_at=_utc_now(),
            )
        )
        await session.commit()


async def list_evaluation_run_item_ids(*, run_id: str) -> list[str]:
    async with SessionLocal() as session:
        rows = await session.execute(
            select(EvaluationRunItem.id)
            .where(EvaluationRunItem.run_id == UUID(run_id))
            .order_by(EvaluationRunItem.created_at.asc(), EvaluationRunItem.id.asc())
        )
        return [str(item_id) for item_id in rows.scalars().all()]


async def activity_execute_evaluation_run_item(
    *,
    run_id: str,
    item_id: str,
    cancel_event: threading.Event,
) -> dict[str, str]:
    run_uuid = UUID(run_id)
    item_uuid = UUID(item_id)
    try:
        if await _is_run_cancel_requested(run_uuid):
            raise ExecutionCancelledError("Evaluation run was cancelled.")
        async with SessionLocal() as session:
            run = await session.get(EvaluationRun, run_uuid)
            item = await session.get(EvaluationRunItem, item_uuid)
            if run is None or item is None:
                return {"run_id": run_id, "item_id": item_id, "status": "missing"}
            run.status = "running"
            run.started_at = run.started_at or _utc_now()
            item.status = "running"
            item.started_at = item.started_at or _utc_now()
            if item.progress_total is None:
                item.progress_total = int(item.plan_json.get("expected_sample_count") or 0)
            await session.commit()

            item_plan = CompiledRunItemPlan.model_validate(item.plan_json)

        loop = asyncio.get_running_loop()

        def _progress_callback(progress_done: int, progress_total: int) -> None:
            asyncio.run_coroutine_threadsafe(
                _persist_item_progress(item_uuid, progress_done=progress_done, progress_total=progress_total),
                loop,
            )

        adapter = get_engine_adapter(
            engine=item_plan.engine,
            execution_mode=item_plan.execution_mode,
        )
        with TemporaryDirectory(prefix=f"nta-evalrun-v2-{run_id[:8]}-{item_id[:8]}-") as scratch_dir:
            output_dir = Path(scratch_dir)
            result = await asyncio.to_thread(
                adapter.execute,
                item_plan=item_plan,
                context=ExecutionContext(
                    output_dir=output_dir,
                    progress_callback=_progress_callback,
                    cancellation_event=cancel_event,
                ),
            )
            async with SessionLocal() as session:
                run = await session.get(EvaluationRun, run_uuid)
                item = await session.get(EvaluationRunItem, item_uuid)
                if run is None or item is None:
                    return {"run_id": run_id, "item_id": item_id, "status": "missing"}
                await _persist_item_result(
                    session,
                    run=run,
                    item=item,
                    report_payload=result.report_payload,
                    output_dir=output_dir,
                )
                await session.commit()
        await _persist_run_progress(run_uuid)
        return {"run_id": run_id, "item_id": item_id, "status": "completed"}
    except ExecutionCancelledError:
        async with SessionLocal() as session:
            item = await session.get(EvaluationRunItem, item_uuid)
            if item is not None:
                item.status = "cancelled"
                item.finished_at = _utc_now()
                await session.commit()
        await _persist_run_progress(run_uuid)
        return {"run_id": run_id, "item_id": item_id, "status": "cancelled"}
    except Exception as exc:  # noqa: BLE001
        async with SessionLocal() as session:
            item = await session.get(EvaluationRunItem, item_uuid)
            if item is not None:
                item.status = "failed"
                item.error_message = str(exc)[:500]
                item.finished_at = _utc_now()
                await session.commit()
        await _persist_run_progress(run_uuid)
        raise


class EvaluationRunV2Service:
    async def list_runs(self) -> list[EvaluationRunSummary]:
        async with SessionLocal() as session:
            project_id = await resolve_active_project_id(session)
            rows = await session.execute(
                select(EvaluationRun)
                .where(EvaluationRun.project_id == project_id)
                .order_by(EvaluationRun.created_at.desc(), EvaluationRun.id.desc())
            )
            runs = rows.scalars().all()
            for run in runs:
                if run.status not in {"completed", "failed", "cancelled"}:
                    await _reconcile_non_terminal_run(run.id)
            session.expire_all()
            rows = await session.execute(
                select(EvaluationRun)
                .where(EvaluationRun.project_id == project_id)
                .order_by(EvaluationRun.created_at.desc(), EvaluationRun.id.desc())
            )
            return [_serialize_run_summary(run) for run in rows.scalars().all()]

    async def get_run(self, run_id: str) -> EvaluationRunDetail:
        async with SessionLocal() as session:
            project_id = await resolve_active_project_id(session)
            run = await _get_run_or_raise(session, project_id=project_id, run_id=UUID(run_id))
            if run.status not in {"completed", "failed", "cancelled"}:
                await _reconcile_non_terminal_run(run.id)
                await session.refresh(run)
            metric_rows = (
                await session.execute(
                    select(EvaluationRunMetric)
                    .where(EvaluationRunMetric.run_id == run.id, EvaluationRunMetric.run_item_id.is_(None))
                    .order_by(EvaluationRunMetric.created_at.asc(), EvaluationRunMetric.id.asc())
                )
            ).scalars().all()
            item_rows = (
                await session.execute(
                    select(EvaluationRunItem)
                    .where(EvaluationRunItem.run_id == run.id)
                    .order_by(EvaluationRunItem.created_at.asc(), EvaluationRunItem.id.asc())
                )
            ).scalars().all()
            item_ids = [item.id for item in item_rows]
            item_metrics_rows = []
            item_samples_rows = []
            if item_ids:
                item_metrics_rows = (
                    await session.execute(
                        select(EvaluationRunMetric)
                        .where(EvaluationRunMetric.run_item_id.in_(item_ids))
                        .order_by(EvaluationRunMetric.created_at.asc(), EvaluationRunMetric.id.asc())
                    )
                ).scalars().all()
                item_samples_rows = (
                    await session.execute(
                        select(EvaluationRunSample)
                        .where(EvaluationRunSample.run_item_id.in_(item_ids))
                        .order_by(EvaluationRunSample.created_at.asc(), EvaluationRunSample.id.asc())
                    )
                ).scalars().all()
            metrics_by_item: dict[UUID, list[EvaluationRunMetric]] = {}
            for metric in item_metrics_rows:
                if metric.run_item_id is not None:
                    metrics_by_item.setdefault(metric.run_item_id, []).append(metric)
            samples_by_item: dict[UUID, list[EvaluationRunSample]] = {}
            for sample in item_samples_rows:
                samples_by_item.setdefault(sample.run_item_id, []).append(sample)
            return EvaluationRunDetail(
                **_serialize_run_summary(run).model_dump(),
                source_spec_id=run.source_spec_id,
                source_spec_version_id=run.source_spec_version_id,
                source_suite_id=run.source_suite_id,
                source_suite_version_id=run.source_suite_version_id,
                judge_policy_id=run.judge_policy_id,
                execution_plan_json=dict(run.execution_plan_json or {}),
                metrics=[_serialize_metric(metric) for metric in metric_rows],
                items=[
                    _serialize_item(
                        item,
                        metrics=metrics_by_item.get(item.id, []),
                        samples=samples_by_item.get(item.id, []),
                    )
                    for item in item_rows
                ],
            )

    async def create_run(self, payload: EvaluationRunCreate) -> EvaluationRunSummary:
        async with SessionLocal() as session:
            project_id = await resolve_active_project_id(session)
            current_user = await resolve_current_user(session)
            compiled = await compile_run_request(session, project_id=project_id, payload=payload)
            target_display = f"{compiled.plan.target_name}@{compiled.plan.target_version}"
            run = EvaluationRun(
                project_id=project_id,
                created_by=current_user.id if current_user is not None else None,
                name=(payload.name or f"{target_display} · {compiled.plan.model_binding.display_name}").strip(),
                description=payload.description,
                kind=compiled.plan.kind,
                status="queued",
                model_id=compiled.plan.model_binding.model_id,
                model_name=compiled.plan.model_binding.display_name,
                source_spec_id=compiled.source_spec_id,
                source_spec_version_id=compiled.source_spec_version_id,
                source_suite_id=compiled.source_suite_id,
                source_suite_version_id=compiled.source_suite_version_id,
                judge_policy_id=compiled.judge_policy_id,
                execution_plan_json=compiled.plan.model_dump(mode="json"),
                progress_total=len(compiled.plan.items),
                progress_done=0,
            )
            session.add(run)
            await session.flush()
            for plan_item in compiled.plan.items:
                item = EvaluationRunItem(
                    run_id=run.id,
                    item_key=plan_item.item_key,
                    display_name=plan_item.display_name,
                    group_name=plan_item.group_name,
                    weight=plan_item.weight,
                    status="queued",
                    spec_id=plan_item.spec_id,
                    spec_version_id=plan_item.spec_version_id,
                    engine=plan_item.engine,
                    execution_mode=plan_item.execution_mode,
                    model_binding_json=plan_item.model_binding.model_dump(mode="json"),
                    judge_policy_snapshot_json=plan_item.judge_policy_snapshot,
                    template_snapshot_json=plan_item.template_snapshot,
                    plan_json=plan_item.model_dump(mode="json"),
                    progress_total=plan_item.expected_sample_count,
                    progress_done=0,
                )
                session.add(
                    item
                )
                await session.flush()
                item.temporal_workflow_id = f"evaluation-run-item-{item.id}"
            await session.flush()
            run.temporal_workflow_id = f"evaluation-run-{run.id}"
            await session.commit()

        from nta_backend.core.temporal import start_evaluation_run_workflow
        from nta_backend.workflows.evaluation_run import EvaluationRunWorkflowInput

        workflow_input = EvaluationRunWorkflowInput(run_id=str(run.id))
        try:
            await start_evaluation_run_workflow(
                workflow_input,
                workflow_id=run.temporal_workflow_id,
            )
        except Exception as exc:  # noqa: BLE001
            async with SessionLocal() as session:
                failed_run = await session.get(EvaluationRun, run.id)
                if failed_run is not None:
                    failed_run.status = "failed"
                    failed_run.error_message = f"Failed to start evaluation run workflow: {exc}"[:500]
                    failed_run.finished_at = _utc_now()
                    await session.commit()
            raise
        return _serialize_run_summary(run)

    async def cancel_run(self, run_id: str) -> EvaluationRunCancelResponse:
        run_uuid = UUID(run_id)
        async with SessionLocal() as session:
            project_id = await resolve_active_project_id(session)
            run = await _get_run_or_raise(session, project_id=project_id, run_id=run_uuid)
            if run.status in {"completed", "failed", "cancelled"}:
                raise ValueError("当前任务已结束，无法取消。")
            workflow_id = run.temporal_workflow_id
            run.cancel_requested = True
            run.status = "cancelling"
            session.add(
                EvaluationRunEvent(
                    run_id=run.id,
                    run_item_id=None,
                    event_type="run.cancelling",
                    level="info",
                    message="Evaluation run cancellation requested.",
                    payload_json={},
                    created_at=_utc_now(),
                )
            )
            await session.commit()

        status = "cancelling"
        if workflow_id:
            from nta_backend.core.temporal import cancel_workflow_execution

            try:
                await cancel_workflow_execution(workflow_id)
            except Exception as exc:  # noqa: BLE001
                if _is_workflow_not_found_error(exc):
                    await _force_finalize_run_terminal(run_uuid, item_status="cancelled")
                    status = "cancelled"
        else:
            await _force_finalize_run_terminal(run_uuid, item_status="cancelled")
            status = "cancelled"

        if status == "cancelling":
            await _reconcile_non_terminal_run(run_uuid)
            async with SessionLocal() as session:
                latest = await session.get(EvaluationRun, run_uuid)
                if latest is not None and latest.status in {"completed", "failed", "cancelled"}:
                    status = latest.status
        return EvaluationRunCancelResponse(run_id=run_uuid, status=status)

    async def delete_run(self, run_id: str) -> None:
        async with SessionLocal() as session:
            project_id = await resolve_active_project_id(session)
            run = await _get_run_or_raise(session, project_id=project_id, run_id=UUID(run_id))
            if run.status not in {"completed", "failed", "cancelled"}:
                raise ValueError("仅可删除已结束的任务。")
            await session.delete(run)
            await session.commit()
        delete_object_prefix(EVAL_ARTIFACT_BUCKET, _run_prefix(project_id, UUID(run_id)))
