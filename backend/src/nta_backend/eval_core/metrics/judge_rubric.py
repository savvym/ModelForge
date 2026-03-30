from __future__ import annotations

import json
from typing import Any

from nta_backend.eval_core.api.dataset import ChatMessage, Sample
from nta_backend.eval_core.api.metric import Metric, SampleScore
from nta_backend.eval_core.api.model import ModelOutput
from nta_backend.eval_core.api.registry import register_metric
from nta_backend.eval_core.models.openai_compatible import call_openai_compatible_chat

_DEFAULT_PROMPT_TEMPLATE = (
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


@register_metric("judge_rubric")
class JudgeRubricMetric(Metric):
    """Rubric-based judge metric: target contains rubrics, judge checks each one."""

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
        rubrics = _rubrics_from_target(sample.target)
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

        judge_output = call_openai_compatible_chat(
            sample_id=sample.id,
            api_url=self.api_url,
            api_key=self.api_key,
            model_name=self.model_name,
            api_format=self.api_format,
            messages=[
                ChatMessage(
                    role="user",
                    content=_build_rubric_prompt(
                        rubrics,
                        output.text,
                        prompt_template=self.prompt_template,
                    ),
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

        overall_score = _normalize_binary_score(
            parsed.get("score") or parsed.get("Overall Score")
        )
        return SampleScore(
            sample_id=sample.id,
            metric=self.name,
            score=float(overall_score),
            passed=bool(overall_score),
            reason=str(parsed.get("rationale") or parsed.get("Grading Rationale") or ""),
            extra={
                "judge_response": parsed,
                "requirement_status": (
                    parsed.get("requirement_status")
                    or parsed.get("List of Requirement Satisfaction Status")
                    or []
                ),
            },
        )


def _rubrics_from_target(target: str | list[str] | None) -> list[str]:
    if target is None:
        return []
    if isinstance(target, str):
        return [target]
    return [item for item in target if isinstance(item, str) and item.strip()]


def _build_rubric_prompt(
    rubrics: list[str],
    student_response: str,
    *,
    prompt_template: str,
) -> str:
    rubric_text = "\n".join(f"{i}. {item}" for i, item in enumerate(rubrics, start=1))
    return prompt_template.replace("{rubrics}", rubric_text).replace(
        "{student_response}", student_response
    )


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


def _normalize_binary_score(value: Any) -> int:
    try:
        numeric = int(value)
    except (TypeError, ValueError):
        return 0
    return 1 if numeric == 1 else 0
