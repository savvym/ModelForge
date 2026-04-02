from __future__ import annotations

import json
from uuid import uuid4

from nta_backend.evaluation.runtime.api.benchmark import BenchmarkMeta, DataAdapter
from nta_backend.evaluation.runtime.api.dataset import Sample
from nta_backend.evaluation.runtime.api.metric import Aggregator, AggScore, Metric, SampleScore
from nta_backend.evaluation.runtime.api.model import ModelAPI, ModelOutput
from nta_backend.evaluation.runtime.api.registry import (
    get_aggregator,
    get_metric,
    register_aggregator,
    register_benchmark,
    register_metric,
    register_model,
)
from nta_backend.evaluation.runtime.run import run_task


def test_run_task_executes_default_evaluator_and_writes_report(tmp_path) -> None:
    suffix = uuid4().hex
    benchmark_name = f"benchmark-{suffix}"
    model_name = f"model-{suffix}"
    metric_name = f"metric-{suffix}"
    aggregator_name = f"aggregator-{suffix}"

    @register_metric(metric_name)
    class ExactMetric(Metric):
        def score(self, sample: Sample, output: ModelOutput) -> SampleScore:
            passed = output.text == sample.target
            return SampleScore(
                sample_id=sample.id,
                metric=self.name,
                score=1.0 if passed else 0.0,
                passed=passed,
            )

    @register_aggregator(aggregator_name)
    class MeanAggregator(Aggregator):
        def aggregate(self, scores: list[SampleScore]) -> AggScore:
            total = sum(score.score for score in scores)
            value = total / len(scores) if scores else 0.0
            return AggScore(metric=self.name, value=value)

    @register_model(model_name)
    class EchoModel(ModelAPI):
        def generate(self, sample: Sample) -> ModelOutput:
            return ModelOutput(sample_id=sample.id, text=str(sample.input).upper())

    @register_benchmark(
        BenchmarkMeta(
            name=benchmark_name,
            metric_names=[metric_name],
            aggregator_names=[aggregator_name],
        )
    )
    class UppercaseBenchmark(DataAdapter):
        def load_dataset(self):
            return {
                "default": [
                    Sample(id="s1", input="alpha", target="ALPHA"),
                    Sample(id="s2", input="beta", target="BETA"),
                ]
            }

        def review(self, sample: Sample, output: ModelOutput) -> list[SampleScore]:
            metric = get_metric(metric_name)
            return [metric.score(sample, output)]

        def aggregate(self, sample_scores: list[SampleScore]) -> list[AggScore]:
            aggregator = get_aggregator(aggregator_name)
            return [aggregator.aggregate(sample_scores)]

    report = run_task(
        {
            "benchmark": benchmark_name,
            "model": model_name,
            "output_dir": str(tmp_path),
        }
    )

    assert report.benchmark_name == benchmark_name
    assert report.model_name == model_name
    assert len(report.subset_reports) == 1
    assert report.subset_reports[0].sample_count == 2
    assert report.subset_reports[0].metrics[0].value == 1.0

    report_path = tmp_path / "report.json"
    assert report_path.exists()
    payload = json.loads(report_path.read_text(encoding="utf-8"))
    assert payload["benchmark_name"] == benchmark_name
