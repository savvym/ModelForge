from __future__ import annotations

import re
from abc import ABC, abstractmethod
from typing import Any

from nta_backend.evaluation.canonical import EvalSample

_SCORER_REGISTRY: dict[str, type[EvalScorer]] = {}


class EvalScorer(ABC):
    method: str

    @abstractmethod
    def score_sample(
        self,
        *,
        sample: EvalSample,
        prediction: dict[str, Any],
    ) -> dict[str, Any]:
        raise NotImplementedError

    def score_batch(
        self,
        *,
        samples: list[EvalSample],
        predictions: list[dict[str, Any]],
    ) -> list[dict[str, Any]]:
        indexed_predictions = {
            str(item.get("sample_id")): item
            for item in predictions
            if item.get("sample_id") is not None
        }
        return [
            self.score_sample(
                sample=sample,
                prediction=indexed_predictions.get(
                    sample.sample_id,
                    _prediction_by_index(predictions, index),
                ),
            )
            for index, sample in enumerate(samples)
        ]


def register_eval_scorer(method: str):
    def decorate(cls: type[EvalScorer]) -> type[EvalScorer]:
        if method in _SCORER_REGISTRY:
            raise ValueError(f"Eval scorer '{method}' is already registered.")
        cls.method = method
        _SCORER_REGISTRY[method] = cls
        return cls

    return decorate


def get_eval_scorer(method: str) -> EvalScorer:
    scorer_cls = _SCORER_REGISTRY.get(method)
    if scorer_cls is None:
        available = ", ".join(sorted(_SCORER_REGISTRY))
        raise ValueError(f"未知评测方法：{method}。当前支持：{available}")
    return scorer_cls()


def score_accuracy_samples(
    samples: list[EvalSample],
    predictions: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    return get_eval_scorer("accuracy").score_batch(
        samples=samples,
        predictions=predictions,
    )


def score_exact_match_samples(
    samples: list[EvalSample],
    predictions: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    return get_eval_scorer("exact-match").score_batch(
        samples=samples,
        predictions=predictions,
    )


def score_rule_based_samples(
    samples: list[EvalSample],
    predictions: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    return get_eval_scorer("rule-based").score_batch(
        samples=samples,
        predictions=predictions,
    )


def aggregate_scored_metrics(scored_rows: list[dict[str, Any]]) -> dict[str, float]:
    if not scored_rows:
        return {
            "full_score_rate": 0.0,
            "availability_rate": 0.0,
            "consistency_score": 0.0,
        }

    total_weight = sum(_result_weight(row) for row in scored_rows)
    if total_weight <= 0:
        return {
            "full_score_rate": 0.0,
            "availability_rate": 0.0,
            "consistency_score": 0.0,
        }

    available_weight = sum(_result_weight(row) for row in scored_rows if not row.get("error"))
    score_total = sum(float(row.get("score") or 0.0) * _result_weight(row) for row in scored_rows)
    passed_total = sum(_result_weight(row) for row in scored_rows if row.get("passed"))

    return {
        "full_score_rate": round(score_total / total_weight * 100, 1),
        "availability_rate": round(available_weight / total_weight * 100, 1),
        "consistency_score": round(passed_total / total_weight * 100, 1),
    }


@register_eval_scorer("accuracy")
class AccuracyScorer(EvalScorer):
    def score_sample(
        self,
        *,
        sample: EvalSample,
        prediction: dict[str, Any],
    ) -> dict[str, Any]:
        return _score_exact_like_sample(
            sample=sample,
            prediction=prediction,
            method=self.method,
            option_aware=True,
        )


@register_eval_scorer("exact-match")
class ExactMatchScorer(EvalScorer):
    def score_sample(
        self,
        *,
        sample: EvalSample,
        prediction: dict[str, Any],
    ) -> dict[str, Any]:
        return _score_exact_like_sample(
            sample=sample,
            prediction=prediction,
            method=self.method,
            option_aware=False,
        )


@register_eval_scorer("rule-based")
class RuleBasedScorer(EvalScorer):
    def score_sample(
        self,
        *,
        sample: EvalSample,
        prediction: dict[str, Any],
    ) -> dict[str, Any]:
        output_text = _prediction_text(prediction)
        haystack = _normalize_free_text(output_text)
        reference_answers = _reference_answers(sample)
        normalized_keywords = [_normalize_free_text(item) for item in reference_answers]
        matched_keywords = [
            keyword for keyword in normalized_keywords if keyword and keyword in haystack
        ]
        passed = bool(output_text) and bool(matched_keywords)
        score = 1.0 if passed else 0.0
        reason = (
            f"命中关键词：{', '.join(matched_keywords)}。"
            if matched_keywords
            else "未命中参考关键词。"
        )
        if not output_text:
            reason = "模型未返回有效输出。"

        return _build_score_row(
            sample=sample,
            prediction=prediction,
            method=self.method,
            prediction_text=output_text,
            reference_answers=reference_answers,
            score=score,
            passed=passed,
            reason=reason,
            extra={"matched_keywords": matched_keywords},
        )


@register_eval_scorer("judge-model")
class JudgeModelScorer(EvalScorer):
    def score_sample(
        self,
        *,
        sample: EvalSample,
        prediction: dict[str, Any],
    ) -> dict[str, Any]:
        raise NotImplementedError("judge-model scorer 还未接入真实裁判模型执行器。")


def _score_exact_like_sample(
    *,
    sample: EvalSample,
    prediction: dict[str, Any],
    method: str,
    option_aware: bool,
) -> dict[str, Any]:
    output_text = _prediction_text(prediction)
    answers = _reference_answers(sample)
    normalized_prediction = _normalize_prediction(output_text, answers, option_aware=option_aware)
    normalized_answers = {
        _normalize_reference(answer, answers, option_aware=option_aware) for answer in answers
    }
    passed = bool(normalized_prediction) and normalized_prediction in normalized_answers
    score = 1.0 if passed else 0.0
    reason = "命中参考答案。" if passed else "未命中参考答案。"
    if not output_text:
        reason = "模型未返回有效输出。"
    elif not answers:
        reason = "样本缺少参考答案。"

    return _build_score_row(
        sample=sample,
        prediction=prediction,
        method=method,
        prediction_text=output_text,
        reference_answers=answers,
        score=score,
        passed=passed,
        reason=reason,
    )


def _build_score_row(
    *,
    sample: EvalSample,
    prediction: dict[str, Any],
    method: str,
    prediction_text: str,
    reference_answers: list[str],
    score: float,
    passed: bool,
    reason: str,
    extra: dict[str, Any] | None = None,
) -> dict[str, Any]:
    row = {
        "sample_id": sample.sample_id,
        "method": method,
        "weight": sample.scoring.weight,
        "prediction_text": prediction_text,
        "reference_answers": reference_answers,
        "score": score,
        "passed": passed,
        "reason": reason,
        "request_id": prediction.get("request_id"),
        "input_tokens": prediction.get("input_tokens"),
        "output_tokens": prediction.get("output_tokens"),
        "total_tokens": prediction.get("total_tokens"),
        "latency_ms": prediction.get("latency_ms"),
        "error": prediction.get("error"),
    }
    if extra:
        row.update(extra)
    return row


def _result_weight(row: dict[str, Any]) -> float:
    weight = row.get("weight")
    if isinstance(weight, (int, float)) and weight > 0:
        return float(weight)
    return 1.0


def _prediction_by_index(predictions: list[dict[str, Any]], index: int) -> dict[str, Any]:
    if index < len(predictions):
        return predictions[index]
    return {}


def _reference_answers(sample: EvalSample) -> list[str]:
    answers: list[str] = []
    if sample.reference.answer:
        answers.append(sample.reference.answer)
    if sample.reference.answers:
        answers.extend(sample.reference.answers)
    if sample.reference.label:
        answers.append(sample.reference.label)
    if sample.reference.reference_text:
        answers.append(sample.reference.reference_text)
    return [item.strip() for item in answers if item and item.strip()]


def _prediction_text(prediction: dict[str, Any]) -> str:
    for key in ("output_text", "response", "prediction_text"):
        value = prediction.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()
    return ""


def _normalize_prediction(prediction: str, answers: list[str], *, option_aware: bool) -> str:
    if not prediction:
        return ""
    if option_aware and _looks_like_option_answers(answers):
        match = re.search(r"\b([A-Z])\b", prediction.upper())
        if match:
            return match.group(1)
    return _normalize_free_text(prediction)


def _normalize_reference(answer: str, answers: list[str], *, option_aware: bool) -> str:
    if option_aware and _looks_like_option_answers(answers):
        return answer.strip().upper()
    return _normalize_free_text(answer)


def _looks_like_option_answers(answers: list[str]) -> bool:
    return bool(answers) and all(
        len(answer.strip()) == 1 and answer.strip().isalpha() for answer in answers
    )


def _normalize_free_text(text: str) -> str:
    return re.sub(r"\s+", " ", text.strip().lower())
