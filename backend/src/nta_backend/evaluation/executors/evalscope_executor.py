from __future__ import annotations

import json
import threading
import time
from datetime import UTC, datetime
from pathlib import Path
from statistics import mean
from typing import Any

import httpx
from evalscope.api.benchmark import BenchmarkMeta
from evalscope.api.benchmark.adapters.default_data_adapter import DefaultDataAdapter
from evalscope.api.dataset import Sample
from evalscope.constants import HubType
from evalscope.api.evaluator.cache import ReviewResult
from evalscope.api.metric import AggScore, SampleScore, Score
from evalscope.api.messages import ChatMessage, ChatMessageUser
from evalscope.api.model import GenerateConfig, Model, ModelAPI, ModelOutput, ModelUsage
from evalscope.api.model.model import get_model
from evalscope.api.registry import get_benchmark, register_benchmark, register_model_api
from evalscope.evaluator.evaluator import DefaultEvaluator
from evalscope.report import Report
from evalscope.utils.io_utils import OutputsStructure, jsonl_to_list
from evalscope.utils.logger import configure_logging

from nta_backend.evaluation.executors.contracts import (
    EvalExecutionCancelledError,
    EvalExecutionRequest,
    EvalExecutionResult,
    EvalExecutor,
    ExecutorModelConfig,
)
from nta_backend.evaluation.executors.sample_mapping import (
    build_evalscope_sample,
    metric_names_for_eval_method,
    primary_metric_name_for_eval_method,
)
from nta_backend.evaluation.runtime.template_utils import build_output_instruction, compile_template

_BENCHMARK_KEY = "nta_generic"
_DEFAULT_JUDGE_TIMEOUT_S = 180.0
_DEFAULT_MODEL_TIMEOUT_S = 180.0
_DEFAULT_MODEL_MAX_TOKENS = 4096
_JUDGE_MAX_TOKENS = 1024

_RUBRIC_PROMPT_TEMPLATE = (
    "You are a strict grader.\n"
    "Score the student response against every rubric item using all-or-nothing grading.\n"
    "If any single rubric item is not fully satisfied, the overall score must be 0.\n"
    "Return only valid JSON.\n\n"
    "Rubrics:\n{rubrics}\n\n"
    "Student Response:\n{student_response}\n\n"
    "Return exactly this JSON schema:\n"
    "{{\n"
    '  "rationale": "string",\n'
    '  "requirement_status": ["yes" | "no"],\n'
    '  "score": 0 or 1\n'
    "}}"
)

_QUALITY_PROMPT_TEMPLATE = (
    "You are an expert evaluator.\n"
    "Evaluate the quality of the following response to the given question.\n"
    "Score from 1 to 5 where:\n"
    "  1 = completely wrong or irrelevant\n"
    "  2 = mostly wrong with minor correct elements\n"
    "  3 = partially correct but incomplete or inaccurate\n"
    "  4 = mostly correct with minor issues\n"
    "  5 = fully correct, complete, and well-articulated\n\n"
    "Question:\n{question}\n\n"
    "Response:\n{student_response}\n\n"
    "Return only valid JSON with exactly this schema:\n"
    "{{\n"
    '  "score": <integer 1-5>,\n'
    '  "reason": "<brief rationale>"\n'
    "}}"
)


def _serialize_chat_message(message: ChatMessage) -> dict[str, str]:
    return {
        "role": message.role,
        "content": message.text,
    }


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


def _normalize_request_url(
    api_url: str,
    api_format: str,
    *,
    model_name: str,
) -> str:
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
        return _build_google_payload(
            messages=messages,
            temperature=temperature,
            max_tokens=max_tokens,
        )

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
        parts = [item["text"] for item in content if isinstance(item, dict) and isinstance(item.get("text"), str)]
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
        content = item.get("content")
        extracted = _extract_text(content)
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


def _call_openai_compatible_chat(
    *,
    api_url: str,
    api_key: str | None,
    model_name: str,
    messages: list[ChatMessage] | list[dict[str, str]],
    api_format: str = "chat-completions",
    organization: str | None = None,
    headers: dict[str, str] | None = None,
    timeout_s: float = _DEFAULT_MODEL_TIMEOUT_S,
    temperature: float = 0.0,
    max_tokens: int | None = None,
) -> tuple[str, ModelUsage | None, dict[str, Any], str | None, int | None]:
    normalized_api_format = _normalize_api_format(api_format)
    serialized_messages = [
        item if isinstance(item, dict) else _serialize_chat_message(item) for item in messages
    ]
    payload = _build_request_payload(
        model_name=model_name,
        messages=serialized_messages,
        api_format=normalized_api_format,
        temperature=temperature,
        max_tokens=max_tokens,
    )
    headers = {
        "Content-Type": "application/json",
        **{str(key): str(value) for key, value in (headers or {}).items()},
    }
    if api_key:
        if normalized_api_format == "google":
            headers["x-goog-api-key"] = api_key
        else:
            headers["Authorization"] = f"Bearer {api_key}"
    if organization and normalized_api_format != "google":
        headers["OpenAI-Organization"] = organization

    started_at = time.perf_counter()
    try:
        response = httpx.post(
            _normalize_request_url(api_url, normalized_api_format, model_name=model_name),
            headers=headers,
            json=payload,
            timeout=timeout_s,
        )
        response.raise_for_status()
        body = response.json()
    except Exception as exc:
        latency_ms = int((time.perf_counter() - started_at) * 1000)
        return "", None, {}, str(exc), latency_ms

    latency_ms = int((time.perf_counter() - started_at) * 1000)
    return (
        _extract_output_text(body, normalized_api_format),
        _extract_usage(body, normalized_api_format),
        body,
        None,
        latency_ms,
    )


@register_model_api("nta_openai_compatible")
class NTAOpenAICompatibleAPI(ModelAPI):
    def __init__(
        self,
        model_name: str,
        base_url: str | None = None,
        api_key: str | None = None,
        config: GenerateConfig = GenerateConfig(),
        *,
        api_format: str = "chat-completions",
        organization: str | None = None,
        headers: dict[str, str] | None = None,
        timeout_s: float = _DEFAULT_MODEL_TIMEOUT_S,
        **_: Any,
    ) -> None:
        super().__init__(
            model_name=model_name,
            base_url=base_url,
            api_key=api_key,
            config=config,
        )
        self.api_format = api_format
        self.organization = organization
        self.headers = {str(key): str(value) for key, value in (headers or {}).items()}
        self.timeout_s = timeout_s

    def generate(
        self,
        input: list[ChatMessage],
        tools: list[Any],
        tool_choice: Any,
        config: GenerateConfig,
    ) -> ModelOutput:
        del tools, tool_choice
        completion, usage, raw_payload, error, latency_ms = _call_openai_compatible_chat(
            api_url=self.base_url or "",
            api_key=self.api_key,
            model_name=self.model_name,
            messages=input,
            api_format=self.api_format,
            organization=self.organization,
            headers=self.headers,
            timeout_s=config.timeout or self.timeout_s,
            temperature=config.temperature or 0.0,
            max_tokens=config.max_tokens,
        )
        if error:
            return ModelOutput(
                model=self.model_name,
                error=error,
                time=(latency_ms / 1000) if latency_ms is not None else None,
                usage=usage,
            )
        return ModelOutput.from_content(
            model=self.model_name,
            content=completion,
            error=None,
        ).model_copy(
            update={
                "usage": usage,
                "time": (latency_ms / 1000) if latency_ms is not None else None,
                "metadata": raw_payload or None,
            }
        )


@register_benchmark(
    BenchmarkMeta(
        name=_BENCHMARK_KEY,
        dataset_id=".",
        pretty_name="NTA Generic",
        description="NTA generic benchmark adapter backed by EvalScope.",
        subset_list=["default"],
        default_subset="default",
        metric_list=["acc"],
        aggregation="mean",
    )
)
class NTAEvalScopeBenchmarkAdapter(DefaultDataAdapter):
    def __init__(self, benchmark_meta: BenchmarkMeta, task_config) -> None:
        super().__init__(benchmark_meta=benchmark_meta, task_config=task_config)
        config = dict(task_config.dataset_args.get(self.name, {}))
        self.config = config
        self.eval_method = str(config.get("eval_method") or "accuracy").strip()
        self.metric_name = primary_metric_name_for_eval_method(self.eval_method)
        self.field_mapping = dict(config.get("field_mapping") or {})
        self.prompt_config = dict(config.get("prompt_config") or {})
        self.template_config = dict(config.get("template_config") or {})
        self.benchmark_name = str(config.get("benchmark_name") or self.pretty_name or self.name)
        self._benchmark_meta.pretty_name = self.benchmark_name
        self._benchmark_meta.metric_list = [self.metric_name]
        self._judge_model_config = _coerce_model_config(config.get("judge_model"))
        self._judge_model: Model | None = None
        self._judge_model_lock = threading.Lock()

    def load(self):
        with self._temporary_attribute("dataset_hub", HubType.LOCAL):
            return self.load_from_disk(use_local_loader=True)

    def process_sample_input(self, sample: Sample, subset: str) -> str:
        del subset
        if isinstance(sample.input, str):
            return sample.input
        raise TypeError("Expected string input when formatting prompt text.")

    def record_to_sample(self, record: dict[str, Any]) -> Sample:
        return build_evalscope_sample(record, field_mapping=self.field_mapping)

    def sample_to_fewshot(self, sample: Sample) -> str:
        target = sample.target if isinstance(sample.target, str) else "\n".join(sample.target)
        return f"Question: {sample.input}\nAnswer: {target}"

    def calculate_metrics(self, task_state) -> SampleScore:
        prediction_text = task_state.output.completion if task_state.output is not None else ""
        score_details = self._score_task_state(task_state, prediction_text)
        score = Score(
            value={self.metric_name: score_details["score"]},
            prediction=prediction_text,
            extracted_prediction=prediction_text,
            explanation=score_details.get("reason"),
            metadata=score_details,
            main_score_name=self.metric_name,
        )
        return SampleScore(
            score=score,
            sample_id=task_state.sample_id,
            group_id=task_state.group_id,
            sample_metadata=task_state.metadata,
        )

    def aggregate_scores(self, sample_scores: list[SampleScore]) -> list[AggScore]:
        values = [float(sample_score.score.main_value or 0.0) for sample_score in sample_scores]
        passed_count = sum(
            1 for sample_score in sample_scores if bool((sample_score.score.metadata or {}).get("passed"))
        )
        return [
            AggScore(
                score=mean(values) if values else 0.0,
                metric_name=self.metric_name,
                aggregation_name="mean",
                num=len(sample_scores),
                ids=[sample_score.sample_id for sample_score in sample_scores],
                metadata={
                    "passed_count": passed_count,
                    "sample_count": len(sample_scores),
                },
            )
        ]

    def _score_task_state(self, task_state, prediction_text: str) -> dict[str, Any]:
        effective_method = _resolve_eval_method(
            self.eval_method,
            task_state._sample.target,
            has_template=bool(str(self.template_config.get("prompt") or "").strip()),
        )
        references = _normalize_reference_answers(task_state.metadata, task_state._sample.target)
        common = {
            "method": effective_method,
            "metric": self.metric_name,
            "prediction_text": prediction_text,
            "reference_answers": references,
            "input_preview": _truncate_preview(task_state.input_markdown),
            "latency_ms": _latency_ms(task_state.output),
            "total_tokens": _total_tokens(task_state.output),
            "judge_model_name": self._judge_model_config.display_name if self._judge_model_config else None,
        }

        if task_state.output is None or task_state.output.error:
            return {
                **common,
                "score": 0.0,
                "raw_score": 0.0,
                "passed": False,
                "reason": None,
                "error": task_state.output.error if task_state.output is not None else "missing model output",
            }

        if not prediction_text.strip():
            return {
                **common,
                "score": 0.0,
                "raw_score": 0.0,
                "passed": False,
                "reason": "Empty model output; scored as 0.",
                "error": None,
            }

        if effective_method in {"accuracy", "acc", "exact-match"}:
            passed, expected, predicted = _score_accuracy_prediction(
                prediction_text=prediction_text,
                target=task_state._sample.target,
                references=references,
            )
            return {
                **common,
                "score": 1.0 if passed else 0.0,
                "raw_score": 1.0 if passed else 0.0,
                "passed": passed,
                "reason": f"expected={expected or '-'} predicted={predicted or '-'}",
                "error": None,
                "expected_answer": expected,
                "predicted_answer": predicted,
            }

        judge_model = self._require_judge_model()
        if effective_method in {"judge-rubric", "judge-model"}:
            return self._score_with_rubric_judge(
                judge_model=judge_model,
                task_state=task_state,
                prediction_text=prediction_text,
                common=common,
            )
        if effective_method == "judge-quality":
            return self._score_with_quality_judge(
                judge_model=judge_model,
                task_state=task_state,
                prediction_text=prediction_text,
                common=common,
            )
        if effective_method == "judge-template":
            return self._score_with_template_judge(
                judge_model=judge_model,
                task_state=task_state,
                prediction_text=prediction_text,
                common=common,
            )
        raise ValueError(f"Unsupported eval_method: {effective_method}")

    def _score_with_rubric_judge(
        self,
        *,
        judge_model: Model,
        task_state,
        prediction_text: str,
        common: dict[str, Any],
    ) -> dict[str, Any]:
        rubrics = _rubrics_from_target(task_state._sample.target)
        prompt_template = self.prompt_config.get("judge_prompt_template")
        prompt = (prompt_template or _RUBRIC_PROMPT_TEMPLATE).replace(
            "{rubrics}",
            "\n".join(f"{index}. {item}" for index, item in enumerate(rubrics, start=1)),
        ).replace(
            "{student_response}",
            prediction_text,
        )
        judge_output = judge_model.generate([ChatMessageUser(content=prompt)])
        if judge_output.error:
            return {
                **common,
                "score": 0.0,
                "raw_score": 0.0,
                "passed": False,
                "reason": None,
                "error": f"Judge model failed: {judge_output.error}",
            }
        parsed = _extract_json_dict(judge_output.completion)
        if not isinstance(parsed, dict):
            return {
                **common,
                "score": 0.0,
                "raw_score": 0.0,
                "passed": False,
                "reason": "Judge response parsing failed.",
                "error": None,
                "judge_response": judge_output.completion,
            }
        raw_score = _normalize_binary_score(parsed.get("score") or parsed.get("Overall Score"))
        passed = bool(raw_score)
        return {
            **common,
            "score": float(raw_score),
            "raw_score": float(raw_score),
            "passed": passed,
            "reason": str(parsed.get("rationale") or parsed.get("Grading Rationale") or "") or None,
            "error": None,
            "judge_response": parsed,
            "requirement_status": (
                parsed.get("requirement_status")
                or parsed.get("List of Requirement Satisfaction Status")
                or []
            ),
        }

    def _score_with_quality_judge(
        self,
        *,
        judge_model: Model,
        task_state,
        prediction_text: str,
        common: dict[str, Any],
    ) -> dict[str, Any]:
        question = _question_from_task_state(task_state)
        prompt_template = self.prompt_config.get("judge_prompt_template") or _QUALITY_PROMPT_TEMPLATE
        prompt = str(prompt_template).replace("{question}", question).replace(
            "{student_response}",
            prediction_text,
        )
        judge_output = judge_model.generate([ChatMessageUser(content=prompt)])
        if judge_output.error:
            return {
                **common,
                "score": 0.0,
                "raw_score": 0.0,
                "passed": False,
                "reason": None,
                "error": f"Judge model failed: {judge_output.error}",
            }
        parsed = _extract_json_dict(judge_output.completion)
        if not isinstance(parsed, dict):
            return {
                **common,
                "score": 0.0,
                "raw_score": 0.0,
                "passed": False,
                "reason": "Judge response parsing failed.",
                "error": None,
                "judge_response": judge_output.completion,
            }
        raw_score = _clamp_quality_score(parsed.get("score"))
        normalized = raw_score / 5
        return {
            **common,
            "score": normalized,
            "raw_score": raw_score,
            "passed": raw_score >= 3,
            "reason": str(parsed.get("reason") or "") or None,
            "error": None,
            "judge_response": parsed,
        }

    def _score_with_template_judge(
        self,
        *,
        judge_model: Model,
        task_state,
        prediction_text: str,
        common: dict[str, Any],
    ) -> dict[str, Any]:
        template_prompt = str(self.template_config.get("prompt") or "").strip()
        if not template_prompt:
            raise ValueError("Template-based eval requires template prompt.")
        output_type = str(self.template_config.get("output_type") or "numeric")
        output_config = dict(self.template_config.get("output_config") or {})
        variables: dict[str, str] = {
            "output": prediction_text,
        }
        input_value = task_state._sample.input
        if isinstance(input_value, str):
            variables["input"] = input_value
        elif isinstance(input_value, list):
            variables["input"] = "\n".join(f"{message.role}: {message.text}" for message in input_value)
        target = task_state._sample.target
        if isinstance(target, list):
            variables["target"] = "\n".join(f"{index}. {item}" for index, item in enumerate(target, start=1))
        elif isinstance(target, str):
            variables["target"] = target
        for key, value in (task_state.metadata or {}).items():
            variables.setdefault(key, str(value))
        prompt = compile_template(template_prompt, variables)
        prompt = f"{prompt}\n\n{build_output_instruction(output_type, output_config)}"
        judge_output = judge_model.generate([ChatMessageUser(content=prompt)])
        if judge_output.error:
            return {
                **common,
                "score": 0.0,
                "raw_score": 0.0,
                "passed": False,
                "reason": None,
                "error": f"Judge model failed: {judge_output.error}",
            }
        parsed = _extract_json_dict(judge_output.completion)
        if not isinstance(parsed, dict):
            return {
                **common,
                "score": 0.0,
                "raw_score": 0.0,
                "passed": False,
                "reason": "Judge response parsing failed.",
                "error": None,
                "judge_response": judge_output.completion,
            }
        reasoning = str(parsed.get("reasoning") or "") or None
        raw_score = parsed.get("score")
        if output_type == "boolean":
            passed = _coerce_boolean(raw_score)
            return {
                **common,
                "score": 1.0 if passed else 0.0,
                "raw_score": 1.0 if passed else 0.0,
                "passed": passed,
                "reason": reasoning,
                "error": None,
                "judge_response": parsed,
            }
        if output_type == "categorical":
            category = str(raw_score).strip() if raw_score is not None else ""
            label_groups = output_config.get("label_groups", [])
            for group in label_groups if isinstance(label_groups, list) else []:
                if not isinstance(group, dict):
                    continue
                labels = group.get("labels", [])
                if category in {str(label).strip() for label in labels if str(label).strip()}:
                    score_policy = str(group.get("score_policy", "pass")).strip().lower()
                    passed = score_policy != "fail"
                    return {
                        **common,
                        "score": 1.0 if passed else 0.0,
                        "raw_score": category,
                        "passed": passed,
                        "reason": reasoning,
                        "error": None,
                        "judge_response": parsed,
                        "category": category,
                        "label_group": group.get("key"),
                    }
            categories = output_config.get("categories", [])
            normalized = 0.0
            if isinstance(categories, list) and category in categories:
                index = categories.index(category)
                normalized = index / (len(categories) - 1) if len(categories) > 1 else 1.0
            return {
                **common,
                "score": normalized,
                "raw_score": category,
                "passed": normalized > 0,
                "reason": reasoning,
                "error": None,
                "judge_response": parsed,
                "category": category,
            }

        score_min = output_config.get("score_min", 1)
        score_max = output_config.get("score_max", 5)
        pass_threshold = output_config.get("pass_threshold", score_min)
        try:
            numeric_value = float(raw_score)
        except (TypeError, ValueError):
            return {
                **common,
                "score": 0.0,
                "raw_score": raw_score,
                "passed": False,
                "reason": f"Invalid numeric score: {raw_score}",
                "error": None,
                "judge_response": parsed,
            }
        clamped = max(score_min, min(score_max, numeric_value))
        score_range = score_max - score_min
        normalized = (clamped - score_min) / score_range if score_range > 0 else 0.0
        return {
            **common,
            "score": normalized,
            "raw_score": clamped,
            "passed": clamped >= pass_threshold,
            "reason": reasoning,
            "error": None,
            "judge_response": parsed,
        }

    def _require_judge_model(self) -> Model:
        if self._judge_model_config is None:
            raise ValueError(f"{self.eval_method} requires a judge model.")
        if self._judge_model is not None:
            return self._judge_model
        with self._judge_model_lock:
            if self._judge_model is None:
                self._judge_model = _build_evalscope_model(
                    self._judge_model_config,
                    max_tokens=_JUDGE_MAX_TOKENS,
                    timeout_s=_DEFAULT_JUDGE_TIMEOUT_S,
                )
        return self._judge_model


class NTAEvalScopeEvaluator(DefaultEvaluator):
    def __init__(
        self,
        *,
        benchmark,
        model,
        outputs,
        task_config,
        progress_callback,
        cancellation_event,
    ) -> None:
        super().__init__(
            benchmark=benchmark,
            model=model,
            outputs=outputs,
            task_config=task_config,
        )
        self.progress_callback = progress_callback
        self.cancellation_event = cancellation_event
        self._progress_done = 0
        self._progress_total = 0
        self._progress_lock = threading.RLock()

    def eval(self) -> Report:
        self._raise_if_cancelled()
        dataset_dict = {key: value for key, value in self.benchmark.load_dataset().items() if len(value) > 0}
        if not dataset_dict:
            self._publish_progress(0, 0)
            self.finalize()
            return {}
        context = self._collect_work_items(dataset_dict)
        self._publish_progress(context.total_cached, context.grand_total)
        results_by_subset = self._run_pool(context)
        self._raise_if_cancelled()
        agg_score_dict = self._aggregate_scores(dataset_dict, context, results_by_subset)
        if not agg_score_dict:
            report = {}
        else:
            report = self.get_report(agg_score_dict)
        self.finalize()
        return report

    def _process_work_item(self, item, model_prediction_dir):
        self._raise_if_cancelled()
        result = super()._process_work_item(item, model_prediction_dir)
        self._raise_if_cancelled()
        return result

    def _review_task_state(self, task_state):
        self._raise_if_cancelled()
        result = super()._review_task_state(task_state)
        self._raise_if_cancelled()
        return result

    def _persist_result(self, item, task_state, sample_score):
        super()._persist_result(item, task_state, sample_score)
        with self._progress_lock:
            self._progress_done += 1
            self._publish_progress(self._progress_done, self._progress_total)

    def _publish_progress(self, progress_done: int, progress_total: int) -> None:
        with self._progress_lock:
            self._progress_done = progress_done
            self._progress_total = progress_total
        if self.progress_callback is not None:
            self.progress_callback(progress_done, progress_total)

    def _raise_if_cancelled(self) -> None:
        if self.cancellation_event is not None and self.cancellation_event.is_set():
            raise EvalExecutionCancelledError("Eval job was cancelled.")


class EvalScopeExecutor(EvalExecutor):
    def execute(self, request: EvalExecutionRequest) -> EvalExecutionResult:
        request.output_dir.mkdir(parents=True, exist_ok=True)
        outputs = OutputsStructure(outputs_dir=str(request.output_dir))
        configure_logging(False, str(Path(outputs.logs_dir) / "eval_log.log"))

        task_config = _build_task_config(request)
        task_config.dump_yaml(outputs.configs_dir)

        benchmark = get_benchmark(_BENCHMARK_KEY, task_config)
        model = _build_evalscope_model(
            request.eval_model,
            max_tokens=_DEFAULT_MODEL_MAX_TOKENS,
            timeout_s=_DEFAULT_MODEL_TIMEOUT_S,
        )
        evaluator = NTAEvalScopeEvaluator(
            benchmark=benchmark,
            model=model,
            outputs=outputs,
            task_config=task_config,
            progress_callback=request.progress_callback,
            cancellation_event=request.cancellation_event,
        )
        evaluator.eval()
        report_payload = _build_normalized_report(
            output_dir=request.output_dir,
            benchmark_name=request.benchmark_name,
            model_name=request.eval_model.display_name,
        )
        (request.output_dir / "report.json").write_text(
            json.dumps(report_payload, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        return EvalExecutionResult(report_payload=report_payload)


def _build_task_config(request: EvalExecutionRequest):
    from evalscope.config import TaskConfig

    return TaskConfig(
        model=request.eval_model.model_name,
        model_id=request.eval_model.model_name,
        datasets=[_BENCHMARK_KEY],
        dataset_args={
            _BENCHMARK_KEY: {
                "local_path": request.dataset_path,
                "benchmark_name": request.benchmark_name,
                "field_mapping": request.field_mapping,
                "eval_method": request.eval_method,
                "prompt_config": request.prompt_config,
                "template_config": (
                    {
                        "prompt": request.template_config.prompt,
                        "vars": request.template_config.vars,
                        "output_type": request.template_config.output_type,
                        "output_config": request.template_config.output_config,
                    }
                    if request.template_config is not None
                    else {}
                ),
                "judge_model": (
                    {
                        "model_name": request.judge_model.model_name,
                        "display_name": request.judge_model.display_name,
                        "api_url": request.judge_model.api_url,
                        "api_key": request.judge_model.api_key,
                        "api_format": request.judge_model.api_format,
                        "organization": request.judge_model.organization,
                        "headers": dict(request.judge_model.headers),
                    }
                    if request.judge_model is not None
                    else None
                ),
            }
        },
        eval_type="nta_openai_compatible",
        api_url=request.eval_model.api_url,
        api_key=request.eval_model.api_key or "EMPTY",
        model_args={
            "api_format": request.eval_model.api_format,
            "organization": request.eval_model.organization,
            "headers": dict(request.eval_model.headers),
            "timeout_s": _DEFAULT_MODEL_TIMEOUT_S,
        },
        generation_config=GenerateConfig(
            max_tokens=_DEFAULT_MODEL_MAX_TOKENS,
            temperature=0.0,
            timeout=_DEFAULT_MODEL_TIMEOUT_S,
        ),
        limit=request.limit,
        eval_batch_size=1,
        work_dir=str(request.output_dir),
        no_timestamp=True,
        use_cache=None,
        analysis_report=False,
        debug=False,
        seed=42,
    )


def _coerce_model_config(value: Any) -> ExecutorModelConfig | None:
    if not isinstance(value, dict):
        return None
    model_name = str(value.get("model_name") or "").strip()
    api_url = str(value.get("api_url") or "").strip()
    api_format = str(value.get("api_format") or "chat-completions").strip()
    if not model_name or not api_url:
        return None
    return ExecutorModelConfig(
        model_name=model_name,
        display_name=str(value.get("display_name") or model_name),
        api_url=api_url,
        api_key=str(value.get("api_key")) if value.get("api_key") is not None else None,
        api_format=api_format,
        organization=(
            str(value.get("organization")) if value.get("organization") is not None else None
        ),
        headers=(
            {str(key): str(item) for key, item in value["headers"].items()}
            if isinstance(value.get("headers"), dict)
            else {}
        ),
    )


def _build_evalscope_model(
    config: ExecutorModelConfig,
    *,
    max_tokens: int,
    timeout_s: float,
) -> Model:
    return get_model(
        model=config.model_name,
        eval_type="nta_openai_compatible",
        base_url=config.api_url,
        api_key=config.api_key,
        config=GenerateConfig(
            max_tokens=max_tokens,
            temperature=0.0,
            timeout=timeout_s,
        ),
        model_args={
            "api_format": config.api_format,
            "organization": config.organization,
            "headers": dict(config.headers),
            "timeout_s": timeout_s,
        },
        memoize=False,
    )


def _normalize_reference_answers(metadata: dict[str, Any] | None, target: Any) -> list[str]:
    source = None
    if metadata:
        source = metadata.get("reference_answers")
    if isinstance(source, list):
        return [str(item) for item in source if str(item).strip()]
    if isinstance(target, list):
        return [str(item) for item in target if str(item).strip()]
    if isinstance(target, str) and target.strip():
        return [target.strip()]
    return []


def _resolve_eval_method(
    configured_method: str | None,
    target: Any,
    *,
    has_template: bool = False,
) -> str:
    normalized = (configured_method or "auto").strip()
    if normalized != "auto":
        return normalized
    if has_template:
        return "judge-template"
    if isinstance(target, list):
        return "judge-rubric"
    return "accuracy"


def _normalize_text_match(value: str) -> str:
    return " ".join(value.strip().lower().split())


def _score_accuracy_prediction(
    *,
    prediction_text: str,
    target: Any,
    references: list[str],
) -> tuple[bool, str | None, str | None]:
    expected_choice = _normalize_target_choice(target)
    predicted_choice = _extract_choice_letter(prediction_text)
    if expected_choice and predicted_choice:
        return expected_choice == predicted_choice, expected_choice, predicted_choice

    normalized_prediction = _normalize_text_match(prediction_text)
    if not normalized_prediction:
        return False, references[0] if references else None, None

    for reference in references:
        normalized_reference = _normalize_text_match(reference)
        if normalized_reference and normalized_reference == normalized_prediction:
            return True, reference, prediction_text.strip() or None

    return False, references[0] if references else None, prediction_text.strip() or None


def _truncate_preview(value: str, *, limit: int = 500) -> str:
    normalized = value.strip()
    if len(normalized) <= limit:
        return normalized
    return normalized[:limit].rstrip() + "..."


def _latency_ms(output: ModelOutput | None) -> int | None:
    if output is None or output.time is None:
        return None
    return int(output.time * 1000)


def _total_tokens(output: ModelOutput | None) -> int | None:
    if output is None or output.usage is None:
        return None
    return output.usage.total_tokens


def _question_from_task_state(task_state) -> str:
    input_value = task_state._sample.input
    if isinstance(input_value, str):
        return input_value
    return "\n\n".join(message.text for message in input_value if getattr(message, "role", None) == "user")


def _rubrics_from_target(target: str | list[str] | None) -> list[str]:
    if target is None:
        return []
    if isinstance(target, str):
        return [target]
    return [item for item in target if isinstance(item, str) and item.strip()]


def _extract_json_dict(raw_text: str) -> dict[str, Any] | None:
    text = raw_text.strip()
    if not text:
        return None
    try:
        parsed = json.loads(text)
    except json.JSONDecodeError:
        start = text.find("{")
        end = text.rfind("}")
        if start < 0 or end < 0 or end <= start:
            return None
        try:
            parsed = json.loads(text[start : end + 1])
        except json.JSONDecodeError:
            return None
    return parsed if isinstance(parsed, dict) else None


def _normalize_binary_score(value: Any) -> int:
    try:
        numeric = int(value)
    except (TypeError, ValueError):
        return 0
    return 1 if numeric == 1 else 0


def _clamp_quality_score(value: Any) -> int:
    try:
        numeric = int(value)
    except (TypeError, ValueError):
        return 1
    return max(1, min(5, numeric))


def _coerce_boolean(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        return bool(value)
    if isinstance(value, str):
        return value.lower() in {"true", "1", "yes"}
    return False


def _normalize_target_choice(target: Any) -> str | None:
    if isinstance(target, list):
        if not target:
            return None
        target = target[0]
    if not isinstance(target, str):
        return None
    normalized = target.strip().upper()
    return normalized[0] if normalized else None


def _extract_choice_letter(text: str) -> str | None:
    import re
    import string

    answer_patterns = (
        re.compile(r"(?:ANSWER|答案)\s*[:：]\s*\(?([A-Z])\)?", re.IGNORECASE),
        re.compile(r"(?:FINAL ANSWER|最终答案)\s*[:：]\s*\(?([A-Z])\)?", re.IGNORECASE),
    )
    valid_letters = set(string.ascii_uppercase)
    normalized = text.strip()
    if not normalized:
        return None
    for pattern in answer_patterns:
        matches = pattern.findall(normalized)
        for match in reversed(matches):
            letter = match.upper()
            if letter in valid_letters:
                return letter
    for line in reversed([item.strip() for item in normalized.splitlines() if item.strip()]):
        candidate = line.strip().upper().strip(" .,:;!?'\"()[]{}")
        if candidate in valid_letters:
            return candidate
        match = re.fullmatch(r"(?:OPTION|CHOICE|答案|ANSWER)?\s*[:：]?\s*([A-Z])", candidate)
        if match:
            letter = match.group(1)
            if letter in valid_letters:
                return letter
    return None


def _build_normalized_report(
    *,
    output_dir: Path,
    benchmark_name: str,
    model_name: str,
) -> dict[str, Any]:
    review_root = output_dir / "reviews"
    subset_reports: list[dict[str, Any]] = []
    if review_root.exists():
        for review_file in sorted(review_root.rglob("*.jsonl")):
            subset_reports.append(_build_subset_report(review_file))
    if not subset_reports:
        raise ValueError("EvalScope produced no review results.")
    return {
        "engine": "evalscope",
        "benchmark_name": benchmark_name,
        "model_name": model_name,
        "generated_at": datetime.now(UTC).isoformat(),
        "subset_reports": subset_reports,
    }


def _build_subset_report(review_file: Path) -> dict[str, Any]:
    rows = [ReviewResult.model_validate(item) for item in jsonl_to_list(str(review_file))]
    sample_scores: list[dict[str, Any]] = []
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
        sample_scores.append(
            {
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
                "judge_model_name": metadata.get("judge_model_name"),
            }
        )

    subset_name = review_file.stem
    if subset_name.startswith(f"{_BENCHMARK_KEY}_"):
        subset_name = subset_name.removeprefix(f"{_BENCHMARK_KEY}_")

    return {
        "subset": subset_name,
        "sample_count": len(sample_scores),
        "metrics": [
            {
                "metric": metric_name,
                "value": mean(numeric_values) if numeric_values else 0.0,
                "extra": {
                    "aggregation": "mean",
                    "sample_count": len(sample_scores),
                },
            }
        ],
        "sample_scores": sample_scores,
    }
