from __future__ import annotations

import json
from typing import Any, Callable

from nta_backend.eval_core.api.dataset import ChatMessage, Sample
from nta_backend.eval_core.api.metric import Metric, SampleScore
from nta_backend.eval_core.api.model import ModelOutput
from nta_backend.eval_core.api.registry import register_metric
from nta_backend.eval_core.models.openai_compatible import call_openai_compatible_chat


@register_metric("judge_template")
class JudgeTemplateMetric(Metric):
    """Configurable judge metric driven by an EvalTemplate.

    The prompt, output type, and scoring logic are all determined by the
    template configuration rather than hardcoded values.
    """

    def __init__(
        self,
        *,
        api_url: str,
        model_name: str,
        api_key: str | None = None,
        api_format: str = "chat-completions",
        compiled_prompt_fn: Callable[[Sample, ModelOutput], str],
        output_type: str = "numeric",
        output_config: dict[str, Any] | None = None,
        timeout_s: float = 180.0,
    ):
        self.api_url = api_url
        self.api_key = api_key
        self.model_name = model_name
        self.api_format = api_format
        self.compiled_prompt_fn = compiled_prompt_fn
        self.output_type = output_type
        self.output_config = output_config or {}
        self.timeout_s = timeout_s

    def score(self, sample: Sample, output: ModelOutput) -> SampleScore:
        if output.error:
            return SampleScore(
                sample_id=sample.id,
                metric=self.name,
                score=0.0,
                passed=False,
                reason=f"Model generation failed: {output.error}",
            )
        if not output.text.strip():
            return SampleScore(
                sample_id=sample.id,
                metric=self.name,
                score=0.0,
                passed=False,
                reason="Empty model output; scored as 0.",
            )

        prompt = self.compiled_prompt_fn(sample, output)
        judge_output = call_openai_compatible_chat(
            sample_id=sample.id,
            api_url=self.api_url,
            api_key=self.api_key,
            model_name=self.model_name,
            api_format=self.api_format,
            messages=[ChatMessage(role="user", content=prompt)],
            timeout_s=self.timeout_s,
            max_tokens=1024,
        )
        if judge_output.error:
            return SampleScore(
                sample_id=sample.id,
                metric=self.name,
                score=0.0,
                passed=False,
                reason=f"Judge model failed: {judge_output.error}",
            )

        parsed = _extract_json_dict(judge_output.text)
        if not isinstance(parsed, dict):
            return SampleScore(
                sample_id=sample.id,
                metric=self.name,
                score=0.0,
                passed=False,
                reason="Judge response parsing failed.",
                extra={"judge_response": judge_output.text},
            )

        return self._build_score(sample.id, parsed)

    def _build_score(self, sample_id: str, parsed: dict[str, Any]) -> SampleScore:
        reasoning = str(parsed.get("reasoning") or "")
        raw_score = parsed.get("score")

        if self.output_type == "boolean":
            return _score_boolean(sample_id, self.name, raw_score, reasoning, parsed)

        if self.output_type == "categorical":
            return _score_categorical(
                sample_id, self.name, raw_score, reasoning, parsed, self.output_config
            )

        # numeric (default)
        return _score_numeric(
            sample_id, self.name, raw_score, reasoning, parsed, self.output_config
        )


# ---------------------------------------------------------------------------
# Output type scoring
# ---------------------------------------------------------------------------


def _score_numeric(
    sample_id: str,
    metric_name: str,
    raw_score: Any,
    reasoning: str,
    parsed: dict,
    config: dict,
) -> SampleScore:
    score_min = config.get("score_min", 1)
    score_max = config.get("score_max", 5)
    pass_threshold = config.get("pass_threshold", score_min)

    try:
        value = float(raw_score)
    except (TypeError, ValueError):
        return SampleScore(
            sample_id=sample_id,
            metric=metric_name,
            score=0.0,
            passed=False,
            reason=f"Invalid numeric score: {raw_score}",
            extra={"judge_response": parsed},
        )

    clamped = max(score_min, min(score_max, value))
    score_range = score_max - score_min
    normalized = (clamped - score_min) / score_range if score_range > 0 else 0.0

    return SampleScore(
        sample_id=sample_id,
        metric=metric_name,
        score=normalized,
        passed=clamped >= pass_threshold,
        reason=reasoning,
        extra={"judge_response": parsed, "raw_score": clamped},
    )


def _score_boolean(
    sample_id: str,
    metric_name: str,
    raw_score: Any,
    reasoning: str,
    parsed: dict,
) -> SampleScore:
    if isinstance(raw_score, bool):
        passed = raw_score
    elif isinstance(raw_score, (int, float)):
        passed = bool(raw_score)
    elif isinstance(raw_score, str):
        passed = raw_score.lower() in ("true", "1", "yes")
    else:
        passed = False

    return SampleScore(
        sample_id=sample_id,
        metric=metric_name,
        score=1.0 if passed else 0.0,
        passed=passed,
        reason=reasoning,
        extra={"judge_response": parsed},
    )


def _score_categorical(
    sample_id: str,
    metric_name: str,
    raw_score: Any,
    reasoning: str,
    parsed: dict,
    config: dict,
) -> SampleScore:
    value_str = str(raw_score).strip() if raw_score is not None else ""
    label_groups = config.get("label_groups", [])

    if isinstance(label_groups, list):
        for group in label_groups:
            if not isinstance(group, dict):
                continue
            labels = group.get("labels", [])
            if not isinstance(labels, list):
                continue
            if value_str in {str(label).strip() for label in labels}:
                score_policy = str(group.get("score_policy", "pass")).strip().lower()
                passed = score_policy != "fail"
                return SampleScore(
                    sample_id=sample_id,
                    metric=metric_name,
                    score=1.0 if passed else 0.0,
                    passed=passed,
                    reason=reasoning,
                    extra={
                        "judge_response": parsed,
                        "category": value_str,
                        "label_group": group.get("key"),
                    },
                )

    categories = config.get("categories", [])
    normalized = 0.0
    if categories and value_str in categories:
        index = categories.index(value_str)
        normalized = index / (len(categories) - 1) if len(categories) > 1 else 1.0

    return SampleScore(
        sample_id=sample_id,
        metric=metric_name,
        score=normalized,
        passed=normalized > 0,
        reason=reasoning,
        extra={
            "judge_response": parsed,
            "category": value_str,
        },
    )


# ---------------------------------------------------------------------------
# JSON extraction
# ---------------------------------------------------------------------------


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
    if isinstance(parsed, dict):
        return parsed
    return None
