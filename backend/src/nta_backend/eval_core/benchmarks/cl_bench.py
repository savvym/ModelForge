from __future__ import annotations

from typing import Any

from nta_backend.eval_catalog.contracts import (
    CL_BENCH_PROMPT_CONFIG,
    CL_BENCH_PROMPT_SCHEMA,
    CL_BENCH_SAMPLE_SCHEMA,
)
from nta_backend.eval_core.adapters import JudgeModelAdapter
from nta_backend.eval_core.api.benchmark import BenchmarkMeta
from nta_backend.eval_core.api.dataset import ChatMessage, Sample
from nta_backend.eval_core.api.registry import register_benchmark

CL_BENCH_DESCRIPTION = (
    "CL-bench evaluates whether a model can learn new rules and knowledge from context "
    "and answer strictly based on that context."
)


@register_benchmark(
    BenchmarkMeta(
        name="cl_bench",
        display_name="CL-bench",
        description=CL_BENCH_DESCRIPTION,
        default_eval_method="judge-model",
        requires_judge_model=True,
        supports_custom_dataset=False,
        sample_schema_json=CL_BENCH_SAMPLE_SCHEMA,
        prompt_schema_json=CL_BENCH_PROMPT_SCHEMA,
        prompt_config_json=CL_BENCH_PROMPT_CONFIG,
        metric_names=["cl_bench_acc"],
        aggregator_names=["mean"],
    )
)
class CLBenchBenchmark(JudgeModelAdapter):
    def record_to_sample(self, record: dict[str, Any], line_number: int) -> Sample:
        return _record_to_sample(record, line_number)


def _record_to_sample(record: dict[str, Any], line_number: int) -> Sample:
    raw_messages = record.get("messages")
    if not isinstance(raw_messages, list):
        raw_messages = record.get("input")
    if not isinstance(raw_messages, list) or not raw_messages:
        raise ValueError(f"CL-bench sample at line {line_number} must contain messages/input.")

    messages = [
        ChatMessage(role=str(item["role"]), content=str(item["content"]))
        for item in raw_messages
        if isinstance(item, dict) and item.get("role") and item.get("content")
    ]
    if not messages:
        raise ValueError(f"CL-bench sample at line {line_number} has no valid messages.")

    target = record.get("rubrics")
    if target is None:
        target = record.get("target")
    if isinstance(target, str):
        normalized_target: str | list[str] | None = target
    elif isinstance(target, list):
        normalized_target = [str(item) for item in target if str(item).strip()]
    else:
        normalized_target = None

    metadata = record.get("metadata") or record.get("meta_data") or {}
    if not isinstance(metadata, dict):
        metadata = {}
    if record.get("group_id") is not None:
        metadata.setdefault("group_id", record["group_id"])

    sample_id = str(record.get("id") or metadata.get("task_id") or f"sample-{line_number}")
    return Sample(
        id=sample_id,
        input=messages,
        target=normalized_target,
        metadata=metadata,
    )
