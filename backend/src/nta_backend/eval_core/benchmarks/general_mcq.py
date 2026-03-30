from __future__ import annotations

from typing import Any

from nta_backend.eval_catalog.contracts import (
    ARC_SOURCE_SCHEMA,
    CEVAL_SOURCE_SCHEMA,
    CMMLU_SOURCE_SCHEMA,
    GENERAL_MCQ_PROMPT_CONFIG,
    GENERAL_MCQ_PROMPT_SCHEMA,
    MMLU_SOURCE_SCHEMA,
)
from nta_backend.eval_core.adapters import MultiChoiceAdapter
from nta_backend.eval_core.api.benchmark import BenchmarkMeta
from nta_backend.eval_core.api.registry import register_benchmark

_MCQ_BENCHMARK_NAMES = ("mmlu", "cmmlu", "ceval", "arc")


def _mcq_source_schema(name: str) -> dict[str, Any]:
    if name == "mmlu":
        return MMLU_SOURCE_SCHEMA
    if name == "ceval":
        return CEVAL_SOURCE_SCHEMA
    if name == "cmmlu":
        return CMMLU_SOURCE_SCHEMA
    if name == "arc":
        return ARC_SOURCE_SCHEMA
    return {"type": "object"}


def _mcq_meta(name: str) -> BenchmarkMeta:
    # display_name / description / subset_list will be enriched from DB
    # by the startup sync (benchmark_sync.py). Only provide runtime defaults here.
    return BenchmarkMeta(
        name=name,
        display_name=name,
        default_eval_method="acc",
        requires_judge_model=False,
        supports_custom_dataset=False,
        sample_schema_json=_mcq_source_schema(name),
        prompt_schema_json=GENERAL_MCQ_PROMPT_SCHEMA,
        prompt_config_json=GENERAL_MCQ_PROMPT_CONFIG,
        metric_names=["acc"],
        aggregator_names=["mean"],
        subset_list=["default"],
    )


def _register_mcq_benchmark(name: str) -> None:
    metadata = _mcq_meta(name)

    @register_benchmark(metadata)
    class _ConcreteGeneralMCQBenchmark(MultiChoiceAdapter):
        pass

    _ConcreteGeneralMCQBenchmark.__name__ = f"{name.title().replace('_', '')}Benchmark"


for _benchmark_name in _MCQ_BENCHMARK_NAMES:
    _register_mcq_benchmark(_benchmark_name)
