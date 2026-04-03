from __future__ import annotations

import json
import time
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import httpx
from evalscope.api.evaluator.cache import ReviewResult
from evalscope.api.messages import ChatMessage
from evalscope.api.model import GenerateConfig, Model, ModelAPI, ModelOutput, ModelUsage
from evalscope.api.model.model import get_model
from evalscope.api.registry import create_evaluator, get_benchmark, register_model_api
from evalscope.config import TaskConfig
from evalscope.utils.io_utils import OutputsStructure, jsonl_to_list
from evalscope.utils.logger import configure_logging

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

_MODEL_API_NAME = "nta_v2_openai_compatible"


def _serialize_chat_message(message: ChatMessage) -> dict[str, str]:
    return {"role": message.role, "content": message.text}


def _normalize_api_format(value: str | None) -> str:
    normalized = (value or "").strip().lower()
    if normalized in {"responses", "openai-responses"}:
        return "responses"
    if normalized in {"google", "google-genai", "google-generativeai"}:
        return "google"
    return "chat-completions"


def _normalize_chat_completions_url(api_url: str) -> str:
    normalized = api_url.strip().rstrip("/")
    if normalized.endswith("/chat/completions"):
        return normalized
    if normalized.endswith("/v1"):
        return f"{normalized}/chat/completions"
    return f"{normalized}/v1/chat/completions"


def _normalize_responses_url(api_url: str) -> str:
    normalized = api_url.strip().rstrip("/")
    if normalized.endswith("/responses"):
        return normalized
    if normalized.endswith("/v1"):
        return f"{normalized}/responses"
    return f"{normalized}/v1/responses"


def _normalize_google_generate_content_url(api_url: str, model_name: str) -> str:
    normalized = api_url.strip().rstrip("/")
    normalized_model_name = model_name.strip().removeprefix("models/")
    if normalized.endswith(":generateContent"):
        return normalized
    if normalized.endswith(f"/models/{normalized_model_name}"):
        return f"{normalized}:generateContent"
    if normalized.endswith("/models"):
        return f"{normalized}/{normalized_model_name}:generateContent"
    return f"{normalized}/models/{normalized_model_name}:generateContent"


def _normalize_request_url(api_url: str, api_format: str, *, model_name: str) -> str:
    if api_format == "responses":
        return _normalize_responses_url(api_url)
    if api_format == "google":
        return _normalize_google_generate_content_url(api_url, model_name)
    return _normalize_chat_completions_url(api_url)


def _responses_input_from_messages(messages: list[dict[str, str]]) -> str:
    parts: list[str] = []
    for message in messages:
        content = message["content"].strip()
        if not content:
            continue
        role = message["role"]
        prefix = "System"
        if role == "user":
            prefix = "User"
        elif role == "assistant":
            prefix = "Assistant"
        parts.append(f"{prefix}: {content}")
    parts.append("Assistant:")
    return "\n\n".join(parts)


def _build_google_payload(
    *,
    messages: list[dict[str, str]],
    temperature: float,
    max_tokens: int | None,
) -> dict[str, Any]:
    system_messages: list[str] = []
    contents: list[dict[str, Any]] = []
    for message in messages:
        content = message["content"].strip()
        if not content:
            continue
        if message["role"] == "system":
            system_messages.append(content)
            continue
        contents.append(
            {
                "role": "model" if message["role"] == "assistant" else "user",
                "parts": [{"text": content}],
            }
        )
    payload: dict[str, Any] = {
        "contents": contents,
        "generationConfig": {"temperature": temperature},
    }
    if max_tokens is not None:
        payload["generationConfig"]["maxOutputTokens"] = max_tokens
    if system_messages:
        payload["systemInstruction"] = {"parts": [{"text": "\n\n".join(system_messages)}]}
    return payload


def _build_request_payload(
    *,
    model_name: str,
    messages: list[dict[str, str]],
    api_format: str,
    temperature: float,
    max_tokens: int | None,
) -> dict[str, Any]:
    if api_format == "responses":
        payload: dict[str, Any] = {
            "model": model_name,
            "input": _responses_input_from_messages(messages),
        }
        if max_tokens is not None:
            payload["max_output_tokens"] = max_tokens
        return payload
    if api_format == "google":
        return _build_google_payload(messages=messages, temperature=temperature, max_tokens=max_tokens)
    payload = {
        "model": model_name,
        "messages": messages,
        "temperature": temperature,
    }
    if max_tokens is not None:
        payload["max_tokens"] = max_tokens
    return payload


def _extract_text(value: Any) -> str | None:
    if isinstance(value, str):
        normalized = value.strip()
        return normalized or None
    if isinstance(value, dict):
        for key in ("text", "content", "value"):
            extracted = _extract_text(value.get(key))
            if extracted:
                return extracted
    if isinstance(value, list):
        parts = [part for item in value if (part := _extract_text(item))]
        if parts:
            return "\n".join(parts).strip() or None
    return None


def _extract_chat_completions_text(payload: dict[str, Any]) -> str:
    choices = payload.get("choices")
    if not isinstance(choices, list) or not choices:
        return ""
    message = (choices[0] or {}).get("message") or {}
    content = message.get("content")
    if isinstance(content, str):
        return content.strip()
    if isinstance(content, list):
        parts = [
            item["text"]
            for item in content
            if isinstance(item, dict) and isinstance(item.get("text"), str)
        ]
        return "\n".join(parts).strip()
    return ""


def _extract_responses_text(payload: dict[str, Any]) -> str:
    text = _extract_text(payload.get("output_text"))
    if text:
        return text
    output = payload.get("output")
    if not isinstance(output, list):
        return ""
    parts: list[str] = []
    for item in output:
        if not isinstance(item, dict):
            continue
        extracted = _extract_text(item.get("content"))
        if extracted:
            parts.append(extracted)
    return "\n".join(parts).strip()


def _extract_google_text(payload: dict[str, Any]) -> str:
    candidates = payload.get("candidates")
    if not isinstance(candidates, list) or not candidates:
        return ""
    content = candidates[0].get("content") if isinstance(candidates[0], dict) else None
    if not isinstance(content, dict):
        return ""
    parts = content.get("parts")
    if not isinstance(parts, list):
        return ""
    chunks: list[str] = []
    for part in parts:
        if not isinstance(part, dict):
            continue
        text = _extract_text(part.get("text"))
        if text:
            chunks.append(text)
    return "\n".join(chunks).strip()


def _extract_output_text(payload: dict[str, Any], api_format: str) -> str:
    if api_format == "responses":
        return _extract_responses_text(payload)
    if api_format == "google":
        return _extract_google_text(payload)
    return _extract_chat_completions_text(payload)


def _as_int(value: Any) -> int | None:
    if isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        return int(value)
    return None


def _extract_usage(payload: Any, api_format: str) -> ModelUsage | None:
    if not isinstance(payload, dict):
        return None
    if api_format == "google":
        usage_metadata = payload.get("usageMetadata")
        if not isinstance(usage_metadata, dict):
            return None
        return ModelUsage(
            input_tokens=_as_int(usage_metadata.get("promptTokenCount")) or 0,
            output_tokens=_as_int(usage_metadata.get("candidatesTokenCount")) or 0,
            total_tokens=_as_int(usage_metadata.get("totalTokenCount")) or 0,
        )
    usage = payload.get("usage") if isinstance(payload.get("usage"), dict) else payload
    if not isinstance(usage, dict):
        return None
    input_key = "input_tokens" if api_format == "responses" else "prompt_tokens"
    output_key = "output_tokens" if api_format == "responses" else "completion_tokens"
    return ModelUsage(
        input_tokens=_as_int(usage.get(input_key)) or 0,
        output_tokens=_as_int(usage.get(output_key)) or 0,
        total_tokens=_as_int(usage.get("total_tokens")) or 0,
    )


def _call_model(
    *,
    model_binding: ModelBindingSnapshot,
    messages: list[ChatMessage],
    temperature: float,
    max_tokens: int | None,
    timeout_s: float,
) -> tuple[str, ModelUsage | None, dict[str, Any], str | None, int]:
    api_format = _normalize_api_format(model_binding.api_format)
    payload = _build_request_payload(
        model_name=model_binding.model_name,
        messages=[_serialize_chat_message(message) for message in messages],
        api_format=api_format,
        temperature=temperature,
        max_tokens=max_tokens,
    )
    headers = {
        "Content-Type": "application/json",
        **{str(key): str(value) for key, value in model_binding.headers.items()},
    }
    if model_binding.api_key:
        if api_format == "google":
            headers["x-goog-api-key"] = model_binding.api_key
        else:
            headers["Authorization"] = f"Bearer {model_binding.api_key}"
    if model_binding.organization and api_format != "google":
        headers["OpenAI-Organization"] = model_binding.organization
    started_at = time.perf_counter()
    try:
        response = httpx.post(
            _normalize_request_url(model_binding.api_url, api_format, model_name=model_binding.model_name),
            headers=headers,
            json=payload,
            timeout=timeout_s,
        )
        response.raise_for_status()
        body = response.json()
    except Exception as exc:  # noqa: BLE001
        latency_ms = int((time.perf_counter() - started_at) * 1000)
        return "", None, {}, str(exc), latency_ms
    latency_ms = int((time.perf_counter() - started_at) * 1000)
    return (
        _extract_output_text(body, api_format),
        _extract_usage(body, api_format),
        body,
        None,
        latency_ms,
    )


@register_model_api(_MODEL_API_NAME)
class NTAV2OpenAICompatibleModelAPI(ModelAPI):
    def __init__(
        self,
        model_name: str,
        base_url: str | None = None,
        api_key: str | None = None,
        config: GenerateConfig = GenerateConfig(),
        *,
        api_format: str = "chat-completions",
        timeout_s: float = 180.0,
        organization: str | None = None,
        headers: dict[str, str] | None = None,
        **_: Any,
    ) -> None:
        super().__init__(model_name=model_name, base_url=base_url, api_key=api_key, config=config)
        self.api_format = api_format
        self.timeout_s = timeout_s
        self.organization = organization
        self.headers = headers or {}

    def generate(
        self,
        input: list[ChatMessage],
        tools: list[Any],
        tool_choice: Any,
        config: GenerateConfig,
    ) -> ModelOutput:
        del tools, tool_choice
        binding = ModelBindingSnapshot(
            model_name=self.model_name,
            display_name=self.model_name,
            api_url=self.base_url or "",
            api_format=self.api_format,
            api_key=self.api_key,
            organization=self.organization,
            headers=self.headers,
            model_params={},
        )
        completion, usage, raw_payload, error, latency_ms = _call_model(
            model_binding=binding,
            messages=input,
            temperature=config.temperature or 0.0,
            max_tokens=config.max_tokens,
            timeout_s=config.timeout or self.timeout_s,
        )
        if error:
            raise RuntimeError(error)
        return ModelOutput.from_content(model=self.model_name, content=completion, error=None).model_copy(
            update={
                "usage": usage,
                "time": latency_ms / 1000,
                "metadata": raw_payload or None,
            }
        )


class EvalScopeBuiltinExecutor(EvaluationEngineAdapter):
    def execute(
        self,
        item_plan: CompiledRunItemPlan,
        context: ExecutionContext,
    ) -> CanonicalExecutionResult:
        if context.cancellation_event is not None and context.cancellation_event.is_set():
            raise ExecutionCancelledError("Evaluation item was cancelled before execution started.")

        benchmark_name = str(
            item_plan.engine_config.get("engine_benchmark_name") or item_plan.spec_name
        ).strip()
        if not benchmark_name:
            raise ValueError("Missing EvalScope builtin benchmark name.")

        context.output_dir.mkdir(parents=True, exist_ok=True)
        outputs = OutputsStructure(outputs_dir=str(context.output_dir))
        configure_logging(False, str(Path(outputs.logs_dir) / "eval_log.log"))

        task_config = TaskConfig(
            model=item_plan.model_binding.model_name,
            model_id=item_plan.model_binding.model_name,
            datasets=[benchmark_name],
            dataset_args={
                benchmark_name: dict(item_plan.engine_config.get("dataset_args") or {}),
            },
            generation_config=GenerateConfig(
                max_tokens=int(item_plan.model_binding.model_params.get("max_tokens", 4096)),
                temperature=float(item_plan.model_binding.model_params.get("temperature", 0.0)),
                timeout=float(item_plan.model_binding.model_params.get("timeout", 180.0)),
            ),
            eval_type=_MODEL_API_NAME,
            work_dir=str(context.output_dir),
            limit=item_plan.engine_config.get("limit"),
        )

        benchmark = get_benchmark(benchmark_name, task_config)
        model = _build_model(item_plan.model_binding, task_config.generation_config)
        evaluator = create_evaluator(
            benchmark=benchmark,
            model=model,
            outputs=outputs,
            task_config=task_config,
        )
        task_config.dataset_args[benchmark_name] = benchmark.to_dict()
        task_config.dump_yaml(outputs.configs_dir)
        evaluator.eval()

        if context.progress_callback is not None:
            total = item_plan.expected_sample_count or 1
            context.progress_callback(total, total)

        report_payload, metrics, samples = _build_normalized_report(
            output_dir=context.output_dir,
            item_plan=item_plan,
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


def _build_model(model_binding: ModelBindingSnapshot, config: GenerateConfig) -> Model:
    return get_model(
        model=model_binding.model_name,
        eval_type=_MODEL_API_NAME,
        base_url=model_binding.api_url,
        api_key=model_binding.api_key,
        config=config,
        model_args={
            "api_format": model_binding.api_format,
            "timeout_s": config.timeout or 180.0,
            "organization": model_binding.organization,
            "headers": dict(model_binding.headers),
        },
        memoize=False,
    )


def _build_normalized_report(
    *,
    output_dir: Path,
    item_plan: CompiledRunItemPlan,
) -> tuple[dict[str, Any], list[CanonicalMetric], list[CanonicalSample]]:
    subset_reports: list[dict[str, Any]] = []
    metrics: list[CanonicalMetric] = []
    samples: list[CanonicalSample] = []
    review_root = output_dir / "reviews"
    if not review_root.exists():
        raise ValueError("EvalScope produced no review outputs.")

    for review_file in sorted(review_root.rglob("*.jsonl")):
        subset_report, subset_metrics, subset_samples = _build_subset_report(review_file)
        subset_reports.append(subset_report)
        metrics.extend(subset_metrics)
        samples.extend(subset_samples)

    overall_metric_name = metrics[0].metric_name if metrics else "score"
    overall_values = [metric.metric_value for metric in metrics if metric.metric_scope == "subset"]
    if overall_values:
        metrics.insert(
            0,
            CanonicalMetric(
                metric_name=overall_metric_name,
                metric_value=sum(overall_values) / len(overall_values),
                metric_scope="overall",
            ),
        )

    report_payload = {
        "engine": "evalscope",
        "engine_mode": "builtin",
        "spec": {
            "name": item_plan.spec_name,
            "version": item_plan.spec_version,
        },
        "benchmark_name": item_plan.engine_config.get("engine_benchmark_name") or item_plan.spec_name,
        "model_name": item_plan.model_binding.display_name,
        "generated_at": datetime.now(UTC).isoformat(),
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
        "subset_reports": subset_reports,
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


def _build_subset_report(
    review_file: Path,
) -> tuple[dict[str, Any], list[CanonicalMetric], list[CanonicalSample]]:
    rows = [ReviewResult.model_validate(item) for item in jsonl_to_list(str(review_file))]
    subset_name = review_file.stem
    sample_scores: list[dict[str, Any]] = []
    metrics: list[CanonicalMetric] = []
    samples: list[CanonicalSample] = []
    numeric_values: list[float] = []
    metric_name = "score"

    for row in rows:
        score = row.sample_score.score
        metric_name = score.main_score_name or next(iter(score.value), metric_name)
        metric_value = score.value.get(metric_name)
        numeric_score = float(metric_value) if isinstance(metric_value, (int, float)) else None
        metadata = dict(score.metadata or {})
        sample_metadata = dict(row.sample_score.sample_metadata or {})
        sample_id = sample_metadata.get("source_sample_id") or row.sample_score.sample_id or row.index
        if numeric_score is not None:
            numeric_values.append(numeric_score)
        sample_payload = {
            "sample_id": str(sample_id),
            "metric": str(metadata.get("metric") or metric_name),
            "score": numeric_score,
            "raw_score": metadata.get("raw_score", numeric_score),
            "passed": bool(metadata.get("passed")),
            "reason": metadata.get("reason"),
            "error": metadata.get("error"),
            "prediction_text": metadata.get("prediction_text"),
            "reference_answers": metadata.get("reference_answers") or [],
            "input_preview": metadata.get("input_preview"),
            "latency_ms": metadata.get("latency_ms"),
            "total_tokens": metadata.get("total_tokens"),
        }
        sample_scores.append(sample_payload)
        samples.append(
            CanonicalSample(
                sample_id=str(sample_id),
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
                metadata={"metric": sample_payload["metric"]},
            )
        )

    subset_score = (sum(numeric_values) / len(numeric_values)) if numeric_values else 0.0
    metrics.append(
        CanonicalMetric(
            metric_name=metric_name,
            metric_value=subset_score,
            metric_scope="subset",
            dimension={"subset": subset_name},
            extra={"sample_count": len(rows)},
        )
    )
    return (
        {
            "subset_name": subset_name,
            "metric_name": metric_name,
            "score": subset_score,
            "sample_count": len(rows),
            "sample_scores": sample_scores,
        },
        metrics,
        samples,
    )


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
