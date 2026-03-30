from __future__ import annotations

import re
import string

from nta_backend.eval_core.api.dataset import Sample
from nta_backend.eval_core.api.metric import Metric, SampleScore
from nta_backend.eval_core.api.model import ModelOutput
from nta_backend.eval_core.api.registry import register_metric

_ANSWER_PATTERNS = (
    re.compile(r"(?:ANSWER|答案)\s*[:：]\s*\(?([A-Z])\)?", re.IGNORECASE),
    re.compile(r"(?:FINAL ANSWER|最终答案)\s*[:：]\s*\(?([A-Z])\)?", re.IGNORECASE),
)


@register_metric("acc")
class MCQAccuracyMetric(Metric):
    def score(self, sample: Sample, output: ModelOutput) -> SampleScore:
        expected = _normalize_target(sample.target)
        predicted = _extract_choice_letter(output.text, sample.choices or [])
        passed = bool(expected and predicted and expected == predicted)
        reason = (
            f"expected={expected or '-'} predicted={predicted or '-'}"
            if output.error is None
            else output.error
        )
        return SampleScore(
            sample_id=sample.id,
            metric=self.name,
            score=1.0 if passed else 0.0,
            passed=passed,
            reason=reason,
            extra={
                "expected_answer": expected,
                "predicted_answer": predicted,
            },
        )


def _normalize_target(value: str | list[str] | None) -> str | None:
    if isinstance(value, list):
        if not value:
            return None
        value = value[0]
    if not isinstance(value, str):
        return None
    normalized = value.strip().upper()
    if not normalized:
        return None
    return normalized[0]


def _extract_choice_letter(text: str, choices: list[str]) -> str | None:
    normalized = text.strip()
    if not normalized:
        return None

    valid_letters = set(string.ascii_uppercase[: len(choices)])
    for pattern in _ANSWER_PATTERNS:
        matches = pattern.findall(normalized)
        for match in reversed(matches):
            letter = match.upper()
            if letter in valid_letters:
                return letter

    for line in reversed([item.strip() for item in normalized.splitlines() if item.strip()]):
        letter = _extract_standalone_letter(line, valid_letters)
        if letter:
            return letter

    lowered_text = normalized.casefold()
    matches: list[str] = []
    for index, choice in enumerate(choices):
        normalized_choice = choice.strip().casefold()
        if normalized_choice and normalized_choice in lowered_text:
            matches.append(string.ascii_uppercase[index])
    if len(matches) == 1:
        return matches[0]
    return None


def _extract_standalone_letter(value: str, valid_letters: set[str]) -> str | None:
    candidate = value.strip().upper().strip(" .,:;!?'\"()[]{}")
    if candidate in valid_letters:
        return candidate
    match = re.fullmatch(r"(?:OPTION|CHOICE|答案|ANSWER)?\s*[:：]?\s*([A-Z])", candidate)
    if match:
        letter = match.group(1)
        if letter in valid_letters:
            return letter
    return None
