from __future__ import annotations

from collections import defaultdict
from typing import Any

from nta_backend.eval.canonical import EvalSample
from nta_backend.eval.scoring import aggregate_scored_metrics, get_eval_scorer


def score_eval_samples(
    samples: list[EvalSample],
    predictions: list[dict[str, Any]],
    *,
    force_method: str | None = None,
) -> list[dict[str, Any]]:
    predictions_by_sample = {str(item.get("sample_id")): item for item in predictions}
    grouped: dict[str, list[tuple[EvalSample, dict[str, Any]]]] = defaultdict(list)

    for index, sample in enumerate(samples):
        method = force_method or sample.scoring.method
        prediction = predictions_by_sample.get(sample.sample_id)
        if prediction is None and index < len(predictions):
            prediction = predictions[index]
        grouped[method].append((sample, prediction or {}))

    scored_by_sample_id: dict[str, dict[str, Any]] = {}
    for method, pairs in grouped.items():
        scorer = get_eval_scorer(method)
        batch_samples = [sample for sample, _ in pairs]
        batch_predictions = [prediction for _, prediction in pairs]
        for row in scorer.score_batch(samples=batch_samples, predictions=batch_predictions):
            scored_by_sample_id[str(row["sample_id"])] = row

    return [scored_by_sample_id[sample.sample_id] for sample in samples]


def evaluate_predictions(
    samples: list[EvalSample],
    predictions: list[dict[str, Any]],
    *,
    force_method: str | None = None,
) -> dict[str, Any]:
    scored_samples = score_eval_samples(
        samples,
        predictions,
        force_method=force_method,
    )
    return {
        "scored_samples": scored_samples,
        "metrics": aggregate_scored_metrics(scored_samples),
    }
