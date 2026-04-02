from __future__ import annotations

from uuid import uuid4

from nta_backend.evaluation.runtime.api.benchmark import BenchmarkMeta, DataAdapter
from nta_backend.evaluation.runtime.api.dataset import Sample
from nta_backend.evaluation.runtime.api.metric import Aggregator, AggScore, Metric, SampleScore
from nta_backend.evaluation.runtime.api.model import ModelAPI, ModelOutput
from nta_backend.evaluation.runtime.api.registry import (
    get_aggregator,
    get_benchmark,
    get_metric,
    get_model,
    register_aggregator,
    register_benchmark,
    register_metric,
    register_model,
)
from nta_backend.evaluation.runtime.config import EvalTaskConfig


def test_registry_registers_and_creates_components() -> None:
    suffix = uuid4().hex
    benchmark_name = f"benchmark-{suffix}"
    model_name = f"model-{suffix}"
    metric_name = f"metric-{suffix}"
    aggregator_name = f"aggregator-{suffix}"

    @register_metric(metric_name)
    class TestMetric(Metric):
        def score(self, sample: Sample, output: ModelOutput) -> SampleScore:
            return SampleScore(sample_id=sample.id, metric=self.name, score=1.0)

    @register_aggregator(aggregator_name)
    class TestAggregator(Aggregator):
        def aggregate(self, scores: list[SampleScore]) -> AggScore:
            return AggScore(metric=self.name, value=float(len(scores)))

    @register_model(model_name)
    class TestModel(ModelAPI):
        def generate(self, sample: Sample) -> ModelOutput:
            return ModelOutput(sample_id=sample.id, text=str(sample.input))

    @register_benchmark(
        BenchmarkMeta(
            name=benchmark_name,
            metric_names=[metric_name],
            aggregator_names=[aggregator_name],
        )
    )
    class TestBenchmark(DataAdapter):
        def load_dataset(self):
            return {"default": [Sample(id="s1", input="hello", target="hello")]}

        def review(self, sample: Sample, output: ModelOutput) -> list[SampleScore]:
            metric = get_metric(metric_name)
            return [metric.score(sample, output)]

        def aggregate(self, sample_scores: list[SampleScore]) -> list[AggScore]:
            aggregator = get_aggregator(aggregator_name)
            return [aggregator.aggregate(sample_scores)]

    benchmark = get_benchmark(
        benchmark_name,
        task_config=EvalTaskConfig(benchmark=benchmark_name, model=model_name),
    )
    model = get_model(model_name, model_id=model_name)
    metric = get_metric(metric_name)
    aggregator = get_aggregator(aggregator_name)

    assert benchmark.meta.name == benchmark_name
    assert model.model_id == model_name
    assert metric.name == metric_name
    assert aggregator.name == aggregator_name
