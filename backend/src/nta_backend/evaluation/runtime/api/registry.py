from __future__ import annotations

from typing import TYPE_CHECKING

from nta_backend.evaluation.runtime.api.benchmark import BenchmarkMeta

if TYPE_CHECKING:
    from pathlib import Path

    from nta_backend.evaluation.runtime.api.benchmark import DataAdapter
    from nta_backend.evaluation.runtime.api.evaluator import Evaluator
    from nta_backend.evaluation.runtime.api.metric import Aggregator, Metric
    from nta_backend.evaluation.runtime.api.model import ModelAPI
    from nta_backend.evaluation.runtime.config import EvalTaskConfig


BENCHMARK_REGISTRY: dict[str, type[DataAdapter]] = {}
MODEL_REGISTRY: dict[str, type[ModelAPI]] = {}
METRIC_REGISTRY: dict[str, type[Metric]] = {}
AGGREGATOR_REGISTRY: dict[str, type[Aggregator]] = {}
EVALUATOR_REGISTRY: dict[str, type[Evaluator]] = {}


def register_benchmark(metadata: BenchmarkMeta):
    def decorate(cls: type[DataAdapter]) -> type[DataAdapter]:
        if metadata.name in BENCHMARK_REGISTRY:
            raise ValueError(f"Benchmark '{metadata.name}' is already registered.")
        cls.meta = metadata
        BENCHMARK_REGISTRY[metadata.name] = cls
        return cls

    return decorate


def get_benchmark(
    name: str,
    *,
    task_config: EvalTaskConfig | None = None,
    **kwargs: object,
) -> DataAdapter:
    benchmark_cls = BENCHMARK_REGISTRY.get(name)
    if benchmark_cls is None:
        raise ValueError(_missing_name_message("Benchmark", name, BENCHMARK_REGISTRY))
    return benchmark_cls(task_config=task_config, **kwargs)


def get_benchmark_meta(name: str) -> BenchmarkMeta | None:
    benchmark_cls = BENCHMARK_REGISTRY.get(name)
    if benchmark_cls is None:
        return None
    return benchmark_cls.meta.model_copy(deep=True)


def list_benchmark_metas() -> list[BenchmarkMeta]:
    return [
        benchmark_cls.meta.model_copy(deep=True)
        for _, benchmark_cls in sorted(BENCHMARK_REGISTRY.items())
    ]


def register_model(name: str):
    def decorate(cls: type[ModelAPI]) -> type[ModelAPI]:
        if name in MODEL_REGISTRY:
            raise ValueError(f"Model '{name}' is already registered.")
        MODEL_REGISTRY[name] = cls
        return cls

    return decorate


def get_model(name: str, **kwargs: object) -> ModelAPI:
    model_cls = MODEL_REGISTRY.get(name)
    if model_cls is None:
        raise ValueError(_missing_name_message("Model", name, MODEL_REGISTRY))
    return model_cls(**kwargs)


def register_metric(name: str):
    def decorate(cls: type[Metric]) -> type[Metric]:
        if name in METRIC_REGISTRY:
            raise ValueError(f"Metric '{name}' is already registered.")
        cls.name = name
        METRIC_REGISTRY[name] = cls
        return cls

    return decorate


def get_metric(name: str, **kwargs: object) -> Metric:
    metric_cls = METRIC_REGISTRY.get(name)
    if metric_cls is None:
        raise ValueError(_missing_name_message("Metric", name, METRIC_REGISTRY))
    return metric_cls(**kwargs)


def register_aggregator(name: str):
    def decorate(cls: type[Aggregator]) -> type[Aggregator]:
        if name in AGGREGATOR_REGISTRY:
            raise ValueError(f"Aggregator '{name}' is already registered.")
        cls.name = name
        AGGREGATOR_REGISTRY[name] = cls
        return cls

    return decorate


def get_aggregator(name: str, **kwargs: object) -> Aggregator:
    aggregator_cls = AGGREGATOR_REGISTRY.get(name)
    if aggregator_cls is None:
        raise ValueError(_missing_name_message("Aggregator", name, AGGREGATOR_REGISTRY))
    return aggregator_cls(**kwargs)


def register_evaluator(name: str):
    def decorate(cls: type[Evaluator]) -> type[Evaluator]:
        if name in EVALUATOR_REGISTRY:
            raise ValueError(f"Evaluator '{name}' is already registered.")
        EVALUATOR_REGISTRY[name] = cls
        return cls

    return decorate


def get_evaluator(name: str) -> type[Evaluator]:
    evaluator_cls = EVALUATOR_REGISTRY.get(name)
    if evaluator_cls is None:
        raise ValueError(_missing_name_message("Evaluator", name, EVALUATOR_REGISTRY))
    return evaluator_cls


def create_evaluator(
    name: str,
    *,
    benchmark: DataAdapter,
    model: ModelAPI,
    task_config: EvalTaskConfig,
    output_dir: Path | None = None,
    **kwargs: object,
) -> Evaluator:
    evaluator_cls = get_evaluator(name)
    return evaluator_cls(
        benchmark=benchmark,
        model=model,
        task_config=task_config,
        output_dir=output_dir,
        **kwargs,
    )


def _missing_name_message(kind: str, name: str, registry: dict[str, object]) -> str:
    available = ", ".join(sorted(registry))
    return f"{kind} '{name}' is not registered. Available: {available or '(none)'}"
