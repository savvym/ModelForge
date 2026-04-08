from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path, PurePosixPath
from statistics import mean
from typing import Any

from nta_backend.core.config import get_settings
from nta_backend.core.object_store import get_object_bytes
from nta_backend.evaluation.executors import (
    EvalExecutionCancelledError,
    EvalExecutionRequest,
    EvalScopeExecutor,
    ExecutorModelConfig,
    ExecutorTemplateConfig,
)
from nta_backend.evaluation_v2.execution.contracts import (
    CanonicalExecutionResult,
    CanonicalMetric,
    CanonicalSample,
    EvaluationEngineAdapter,
    ExecutionArtifact,
    ExecutionCancelledError,
    ExecutionContext,
)
from nta_backend.schemas.evaluation_v2 import CompiledRunItemPlan, ModelBindingSnapshot

_PRIMARY_DATASET_ROLES = ("dataset", "primary", "questions")
_UNSUPPORTED_JUDGE_STRATEGIES = {"pairwise"}
_EXECUTOR = EvalScopeExecutor()


class EvalScopeDatasetExecutor(EvaluationEngineAdapter):
    def execute(
        self,
        item_plan: CompiledRunItemPlan,
        context: ExecutionContext,
    ) -> CanonicalExecutionResult:
        if context.cancellation_event is not None and context.cancellation_event.is_set():
            raise ExecutionCancelledError("Evaluation item was cancelled before execution started.")

        context.output_dir.mkdir(parents=True, exist_ok=True)
        dataset_files = list(item_plan.engine_config.get("dataset_files") or [])
        materialized_files = _materialize_dataset_files(dataset_files, output_dir=context.output_dir)
        primary_dataset_path = _select_primary_dataset_path(dataset_files, materialized_files)
        eval_method = _resolve_eval_method(item_plan)
        judge_model = _resolve_judge_model_binding(item_plan, eval_method=eval_method)

        try:
            legacy_result = _EXECUTOR.execute(
                EvalExecutionRequest(
                    benchmark_name=item_plan.display_name or item_plan.spec_name,
                    dataset_path=str(primary_dataset_path),
                    output_dir=context.output_dir,
                    eval_method=eval_method,
                    eval_model=_to_executor_model_config(item_plan.model_binding),
                    judge_model=judge_model,
                    field_mapping=dict(item_plan.engine_config.get("field_mapping") or {}),
                    prompt_config=_build_prompt_config(item_plan),
                    template_config=_build_template_config(item_plan),
                    limit=_coerce_limit(item_plan.engine_config.get("limit")),
                    progress_callback=context.progress_callback,
                    cancellation_event=context.cancellation_event,
                )
            )
        except EvalExecutionCancelledError as exc:
            raise ExecutionCancelledError(str(exc)) from exc

        report_payload, metrics, samples = _normalize_legacy_report(
            legacy_report=legacy_result.report_payload,
            item_plan=item_plan,
            dataset_files=dataset_files,
        )
        report_path = context.output_dir / "canonical-report.json"
        report_path.write_text(json.dumps(report_payload, ensure_ascii=False, indent=2), encoding="utf-8")
        artifacts = _collect_artifacts(context.output_dir)
        artifacts.append(
            ExecutionArtifact(
                artifact_type="canonical-report",
                path=report_path,
                content_type="application/json",
            )
        )
        return CanonicalExecutionResult(
            report_payload=report_payload,
            metrics=metrics,
            samples=samples,
            artifacts=artifacts,
        )


def _materialize_dataset_files(
    dataset_files: list[dict[str, Any]],
    *,
    output_dir: Path,
) -> dict[str, Path]:
    inputs_dir = output_dir / "inputs"
    inputs_dir.mkdir(parents=True, exist_ok=True)
    materialized: dict[str, Path] = {}
    for index, dataset_file in enumerate(dataset_files):
        file_key = str(dataset_file.get("file_key") or f"dataset-{index}")
        file_name = PurePosixPath(str(dataset_file.get("file_name") or f"{file_key}.jsonl")).name
        target_path = inputs_dir / f"{index:02d}-{file_name}"
        target_path.write_bytes(_load_dataset_bytes(dataset_file))
        materialized[file_key] = target_path
    return materialized


def _load_dataset_bytes(dataset_file: dict[str, Any]) -> bytes:
    object_key = str(dataset_file.get("object_key") or "").strip()
    if object_key:
        return get_object_bytes(get_settings().s3_bucket_dataset_raw, object_key).body

    source_uri = str(dataset_file.get("source_uri") or "").strip()
    if source_uri.startswith("s3://"):
        bucket, object_key = _parse_s3_uri(source_uri)
        return get_object_bytes(bucket, object_key).body
    if source_uri.startswith("file://"):
        return Path(source_uri.removeprefix("file://")).read_bytes()
    if source_uri.startswith("/"):
        return Path(source_uri).read_bytes()
    if source_uri.startswith("evalscope://"):
        raise ValueError("EvalScope dataset execution requires a concrete dataset file, not an external builtin dataset.")
    if source_uri:
        candidate = Path(source_uri)
        if candidate.exists():
            return candidate.read_bytes()
    raise ValueError(f"数据集文件 {dataset_file.get('display_name') or dataset_file.get('file_key')} 尚未就绪。")


def _parse_s3_uri(uri: str) -> tuple[str, str]:
    normalized = uri.removeprefix("s3://")
    bucket, _, key = normalized.partition("/")
    if not bucket or not key:
        raise ValueError(f"Invalid S3 URI: {uri}")
    return bucket, key


def _select_primary_dataset_path(
    dataset_files: list[dict[str, Any]],
    materialized_files: dict[str, Path],
) -> Path:
    if not materialized_files:
        raise ValueError("当前评测版本没有可执行的数据集文件。")
    for preferred_role in _PRIMARY_DATASET_ROLES:
        for dataset_file in dataset_files:
            if str(dataset_file.get("role") or "").strip() == preferred_role:
                file_key = str(dataset_file.get("file_key") or "")
                if file_key in materialized_files:
                    return materialized_files[file_key]
    first_key = next(iter(materialized_files))
    return materialized_files[first_key]


def _resolve_eval_method(item_plan: CompiledRunItemPlan) -> str:
    engine_config = dict(item_plan.engine_config or {})
    scoring_config = dict(engine_config.get("scoring_config") or {})
    explicit = (
        str(engine_config.get("eval_method") or "").strip()
        or str(scoring_config.get("eval_method") or "").strip()
    )
    if explicit:
        return explicit
    judge_policy = dict(item_plan.judge_policy_snapshot or {})
    strategy = str(judge_policy.get("strategy") or "").strip().lower()
    if strategy in _UNSUPPORTED_JUDGE_STRATEGIES:
        raise ValueError(f"当前暂不支持 Judge Policy strategy: {strategy}")
    if strategy == "judge-template":
        return "judge-template"
    if strategy == "rubric":
        return "judge-rubric"
    if item_plan.template_snapshot is not None:
        return "judge-template"
    return "auto"


def _resolve_judge_model_binding(
    item_plan: CompiledRunItemPlan,
    *,
    eval_method: str,
) -> ExecutorModelConfig | None:
    if eval_method not in {"auto", "judge-rubric", "judge-model", "judge-quality", "judge-template"}:
        return None
    binding = item_plan.judge_model_binding or item_plan.model_binding
    return _to_executor_model_config(binding)


def _to_executor_model_config(binding: ModelBindingSnapshot) -> ExecutorModelConfig:
    return ExecutorModelConfig(
        model_name=binding.model_name,
        display_name=binding.display_name,
        api_url=binding.api_url,
        api_key=binding.api_key,
        api_format=binding.api_format,
        organization=binding.organization,
        headers=dict(binding.headers),
    )


def _build_prompt_config(item_plan: CompiledRunItemPlan) -> dict[str, Any]:
    prompt_config = dict(item_plan.engine_config.get("prompt_config") or {})
    judge_policy = dict(item_plan.judge_policy_snapshot or {})
    execution_params = dict(judge_policy.get("execution_params") or {})
    judge_prompt_template = execution_params.get("judge_prompt_template")
    if judge_prompt_template and "judge_prompt_template" not in prompt_config:
        prompt_config["judge_prompt_template"] = judge_prompt_template
    return prompt_config


def _build_template_config(item_plan: CompiledRunItemPlan) -> ExecutorTemplateConfig | None:
    snapshot = dict(item_plan.template_snapshot or {})
    prompt = str(snapshot.get("prompt") or "").strip()
    if not prompt:
        return None
    parser_config = dict(snapshot.get("parser_config") or {})
    output_schema = dict(snapshot.get("output_schema") or {})
    output_type = str(
        parser_config.get("output_type")
        or output_schema.get("type")
        or ("categorical" if isinstance(output_schema.get("enum"), list) else "numeric")
    ).strip()
    output_config = dict(parser_config.get("output_config") or {})
    if output_type == "categorical" and "categories" not in output_config:
        categories = output_schema.get("enum")
        if isinstance(categories, list):
            output_config["categories"] = [str(item) for item in categories]
    if output_type == "numeric":
        if "score_min" not in output_config and output_schema.get("minimum") is not None:
            output_config["score_min"] = output_schema.get("minimum")
        if "score_max" not in output_config and output_schema.get("maximum") is not None:
            output_config["score_max"] = output_schema.get("maximum")
    return ExecutorTemplateConfig(
        prompt=prompt,
        vars=[str(item) for item in snapshot.get("vars") or []],
        output_type=output_type,
        output_config=output_config,
    )


def _coerce_limit(value: Any) -> int | None:
    if isinstance(value, bool):
        return None
    if isinstance(value, int):
        return value
    if isinstance(value, str) and value.strip():
        try:
            return int(value.strip())
        except ValueError:
            return None
    return None


def _normalize_legacy_report(
    *,
    legacy_report: dict[str, Any],
    item_plan: CompiledRunItemPlan,
    dataset_files: list[dict[str, Any]],
) -> tuple[dict[str, Any], list[CanonicalMetric], list[CanonicalSample]]:
    subset_reports = list(legacy_report.get("subset_reports") or [])
    metrics: list[CanonicalMetric] = []
    samples: list[CanonicalSample] = []
    subset_payloads: list[dict[str, Any]] = []

    for subset_report in subset_reports:
        subset_name = str(subset_report.get("subset") or subset_report.get("subset_name") or "default")
        subset_metrics = list(subset_report.get("metrics") or [])
        subset_samples = list(subset_report.get("sample_scores") or [])
        normalized_metric_name = "score"
        for metric in subset_metrics:
            normalized_metric_name = str(metric.get("metric") or metric.get("metric_name") or "score")
            metric_value = float(metric.get("value") or metric.get("metric_value") or 0.0)
            metrics.append(
                CanonicalMetric(
                    metric_name=normalized_metric_name,
                    metric_value=metric_value,
                    metric_scope="subset",
                    dimension={"subset": subset_name},
                    extra=dict(metric.get("extra") or {"sample_count": len(subset_samples)}),
                )
            )
        sample_payloads: list[dict[str, Any]] = []
        for sample in subset_samples:
            sample_id = str(sample.get("sample_id") or "")
            sample_score = sample.get("score")
            numeric_score = float(sample_score) if isinstance(sample_score, (int, float)) else None
            sample_payload = {
                "sample_id": sample_id,
                "metric": str(sample.get("metric") or normalized_metric_name),
                "score": numeric_score,
                "raw_score": sample.get("raw_score", sample_score),
                "passed": bool(sample.get("passed")),
                "reason": sample.get("reason"),
                "error": sample.get("error"),
                "prediction_text": sample.get("prediction_text"),
                "reference_answers": list(sample.get("reference_answers") or []),
                "input_preview": sample.get("input_preview"),
                "latency_ms": sample.get("latency_ms"),
                "total_tokens": sample.get("total_tokens"),
                "judge_model_name": sample.get("judge_model_name"),
            }
            sample_payloads.append(sample_payload)
            samples.append(
                CanonicalSample(
                    sample_id=sample_id,
                    subset_name=subset_name,
                    input_preview=sample_payload["input_preview"],
                    prediction_text=sample_payload["prediction_text"],
                    reference_answers=list(sample_payload["reference_answers"]),
                    score=numeric_score,
                    raw_score=sample_payload["raw_score"],
                    passed=sample_payload["passed"],
                    reason=sample_payload["reason"],
                    error=sample_payload["error"],
                    latency_ms=sample_payload["latency_ms"],
                    total_tokens=sample_payload["total_tokens"],
                    metadata={
                        "metric": sample_payload["metric"],
                        "judge_model_name": sample_payload["judge_model_name"],
                    },
                )
            )
        subset_payloads.append(
            {
                "subset_name": subset_name,
                "metric_name": normalized_metric_name,
                "score": mean(
                    [
                        float(item["score"])
                        for item in sample_payloads
                        if isinstance(item.get("score"), (int, float))
                    ]
                )
                if any(isinstance(item.get("score"), (int, float)) for item in sample_payloads)
                else 0.0,
                "sample_count": len(sample_payloads),
                "sample_scores": sample_payloads,
            }
        )

    subset_metric_values = [metric.metric_value for metric in metrics if metric.metric_scope == "subset"]
    if subset_metric_values:
        metrics.insert(
            0,
            CanonicalMetric(
                metric_name=metrics[0].metric_name if metrics else "score",
                metric_value=sum(subset_metric_values) / len(subset_metric_values),
                metric_scope="overall",
            )
        )

    report_payload = {
        "engine": "evalscope",
        "engine_mode": "dataset",
        "spec": {
            "name": item_plan.spec_name,
            "version": item_plan.spec_version,
        },
        "benchmark_name": item_plan.display_name or item_plan.spec_name,
        "model_name": item_plan.model_binding.display_name,
        "generated_at": legacy_report.get("generated_at") or datetime.now(UTC).isoformat(),
        "dataset_files": [
            {
                "file_key": dataset_file.get("file_key"),
                "display_name": dataset_file.get("display_name"),
                "role": dataset_file.get("role"),
                "file_name": dataset_file.get("file_name"),
                "status": dataset_file.get("status"),
            }
            for dataset_file in dataset_files
        ],
        "metrics": [
            {
                "metric_name": metric.metric_name,
                "metric_value": metric.metric_value,
                "metric_scope": metric.metric_scope,
                "metric_unit": metric.metric_unit,
                "dimension": metric.dimension,
                "extra": metric.extra,
            }
            for metric in metrics
        ],
        "subset_reports": subset_payloads,
        "samples": [
            {
                "sample_id": sample.sample_id,
                "subset_name": sample.subset_name,
                "input_preview": sample.input_preview,
                "prediction_text": sample.prediction_text,
                "reference_answers": sample.reference_answers,
                "score": sample.score,
                "raw_score": sample.raw_score,
                "passed": sample.passed,
                "reason": sample.reason,
                "error": sample.error,
                "latency_ms": sample.latency_ms,
                "total_tokens": sample.total_tokens,
                "metadata": sample.metadata,
            }
            for sample in samples
        ],
    }
    return report_payload, metrics, samples


def _collect_artifacts(output_dir: Path) -> list[ExecutionArtifact]:
    artifacts: list[ExecutionArtifact] = []
    for artifact_path in sorted(output_dir.rglob("*")):
        if not artifact_path.is_file():
            continue
        relative_path = artifact_path.relative_to(output_dir).as_posix()
        if relative_path == "canonical-report.json":
            continue
        artifact_type = relative_path.split("/", 1)[0] if "/" in relative_path else "raw-output"
        content_type = None
        if artifact_path.suffix == ".json":
            content_type = "application/json"
        elif artifact_path.suffix == ".jsonl":
            content_type = "application/x-ndjson"
        elif artifact_path.suffix == ".log":
            content_type = "text/plain"
        artifacts.append(
            ExecutionArtifact(
                artifact_type=artifact_type,
                path=artifact_path,
                content_type=content_type,
                extra={"relative_path": relative_path},
            )
        )
    return artifacts
