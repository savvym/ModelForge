from __future__ import annotations

import json
from typing import Any

from nta_backend.evaluation.runtime.api.dataset import ChatMessage, Sample
from nta_backend.evaluation.runtime.api.metric import Metric, SampleScore
from nta_backend.evaluation.runtime.api.model import ModelOutput
from nta_backend.evaluation.runtime.api.registry import register_metric
from nta_backend.evaluation.runtime.models.openai_compatible import call_openai_compatible_chat

_MAX_SCORE = 5

_DEFAULT_PROMPT_TEMPLATE = (
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


@register_metric("judge_quality")
class JudgeQualityMetric(Metric):
    """No-rubric judge metric: evaluates output quality on a 1-5 scale."""

    def __init__(
        self,
        *,
        api_url: str,
        model_name: str,
        api_key: str | None = None,
        api_format: str = "chat-completions",
        prompt_template: str | None = None,
        timeout_s: float = 180.0,
    ):
        self.api_url = api_url
        self.api_key = api_key
        self.model_name = model_name
        self.api_format = api_format
        self.prompt_template = prompt_template or _DEFAULT_PROMPT_TEMPLATE
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

        question = _question_from_sample(sample)
        judge_output = call_openai_compatible_chat(
            sample_id=sample.id,
            api_url=self.api_url,
            api_key=self.api_key,
            model_name=self.model_name,
            api_format=self.api_format,
            messages=[
                ChatMessage(
                    role="user",
                    content=self.prompt_template.replace(
                        "{question}", question
                    ).replace("{student_response}", output.text),
                )
            ],
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

        raw_score = _clamp_score(parsed.get("score"))
        normalized = raw_score / _MAX_SCORE
        return SampleScore(
            sample_id=sample.id,
            metric=self.name,
            score=normalized,
            passed=raw_score >= 3,
            reason=str(parsed.get("reason") or ""),
            extra={
                "judge_response": parsed,
                "raw_score": raw_score,
            },
        )


def _question_from_sample(sample: Sample) -> str:
    if isinstance(sample.input, str):
        return sample.input
    # ChatMessage list — concatenate user messages
    parts = [msg.content for msg in sample.input if msg.role == "user"]
    return "\n\n".join(parts) if parts else str(sample.input)


def _clamp_score(value: Any) -> int:
    try:
        numeric = int(value)
    except (TypeError, ValueError):
        return 1
    return max(1, min(_MAX_SCORE, numeric))


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
