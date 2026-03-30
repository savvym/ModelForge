from __future__ import annotations

from nta_backend.eval_core.api.metric import Aggregator, AggScore, SampleScore
from nta_backend.eval_core.api.registry import register_aggregator


@register_aggregator("mean")
class MeanAggregator(Aggregator):
    def aggregate(self, scores: list[SampleScore]) -> AggScore:
        metric_name = scores[0].metric if scores else "mean"
        value = sum(score.score for score in scores) / len(scores) if scores else 0.0
        return AggScore(metric=metric_name, value=value)
