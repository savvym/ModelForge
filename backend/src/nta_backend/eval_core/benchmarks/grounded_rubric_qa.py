from __future__ import annotations

from typing import Any

from nta_backend.eval_catalog.contracts import (
    GROUNDED_RUBRIC_QA_PROMPT_CONFIG,
    GROUNDED_RUBRIC_QA_PROMPT_SCHEMA,
    GROUNDED_RUBRIC_QA_SOURCE_SCHEMA,
)
from nta_backend.eval_core.adapters import JudgeModelAdapter
from nta_backend.eval_core.api.benchmark import BenchmarkMeta
from nta_backend.eval_core.api.dataset import ChatMessage, Sample
from nta_backend.eval_core.api.registry import register_benchmark
from nta_backend.eval_core.config import EvalTaskConfig

_FAMILY_NAME = "grounded_rubric_qa"
_FAMILY_DISPLAY_NAME = "Grounded Rubric QA"
_BENCHMARK_NAMES = ("nta_bench_network",)


class BaseGroundedRubricQABenchmark(JudgeModelAdapter):
    def __init__(
        self,
        *,
        task_config: EvalTaskConfig | None = None,
        dataset_path: str | None = None,
        prompt_config: dict[str, object] | None = None,
        **kwargs: object,
    ):
        merged_config = {
            **GROUNDED_RUBRIC_QA_PROMPT_CONFIG,
            **(prompt_config or {}),
        }
        super().__init__(
            task_config=task_config,
            dataset_path=dataset_path,
            prompt_config=merged_config,
            **kwargs,
        )

    def record_to_sample(self, record: dict[str, Any], line_number: int) -> Sample:
        return _record_to_sample(
            record,
            line_number,
            benchmark_name=self.meta.name,
            prompt_config=self.prompt_config,
        )


# ------------------------------------------------------------------
# Record parsing helpers
# ------------------------------------------------------------------


def _record_to_sample(
    record: dict[str, Any],
    line_number: int,
    *,
    benchmark_name: str,
    prompt_config: dict[str, object],
) -> Sample:
    messages = _messages_from_record(
        record,
        line_number,
        benchmark_name=benchmark_name,
        prompt_config=prompt_config,
    )
    target = _rubrics_from_record(record, line_number, benchmark_name=benchmark_name)
    metadata = record.get("metadata") if isinstance(record.get("metadata"), dict) else {}
    sample_id = str(record.get("id") or metadata.get("task_id") or f"sample-{line_number}")
    return Sample(
        id=sample_id,
        input=messages,
        target=target,
        metadata=metadata,
    )


def _messages_from_record(
    record: dict[str, Any],
    line_number: int,
    *,
    benchmark_name: str,
    prompt_config: dict[str, object],
) -> list[ChatMessage]:
    raw_messages = record.get("messages")
    if raw_messages is None:
        raw_messages = record.get("input")
    if isinstance(raw_messages, list):
        messages = [
            ChatMessage(role=str(item["role"]), content=str(item["content"]))
            for item in raw_messages
            if isinstance(item, dict) and item.get("role") and item.get("content")
        ]
        if messages:
            return messages
        raise ValueError(
            f"{benchmark_name} sample at line {line_number} has no valid messages."
        )

    context = str(record.get("context") or "").strip()
    question = str(record.get("question") or "").strip()
    if not context or not question:
        raise ValueError(
            f"{benchmark_name} sample must contain either messages/input "
            "or both context and question."
        )
    user_prompt_template = _config_text(prompt_config, "user_prompt_template")
    user_content = (
        user_prompt_template.replace("{context}", context).replace("{question}", question)
        if user_prompt_template
        else f"背景信息：\n{context}\n\n问题：{question}"
    )
    system_prompt = _config_text(prompt_config, "system_prompt")
    messages: list[ChatMessage] = []
    if system_prompt:
        messages.append(ChatMessage(role="system", content=system_prompt))
    messages.append(ChatMessage(role="user", content=user_content))
    return messages


def _rubrics_from_record(
    record: dict[str, Any],
    line_number: int,
    *,
    benchmark_name: str,
) -> list[str]:
    raw = record.get("rubrics")
    if raw is None:
        raw = record.get("target")
    if isinstance(raw, str) and raw.strip():
        return [raw.strip()]
    if isinstance(raw, list):
        rubrics = [str(item).strip() for item in raw if str(item).strip()]
        if rubrics:
            return rubrics
    raise ValueError(f"{benchmark_name} sample at line {line_number} must contain rubrics.")


def _config_text(prompt_config: dict[str, object], key: str) -> str | None:
    value = prompt_config.get(key)
    if isinstance(value, str) and value.strip():
        return value.strip()
    return None


# ------------------------------------------------------------------
# Registration
# ------------------------------------------------------------------


def _grounded_rubric_meta(benchmark_name: str) -> BenchmarkMeta:
    # display_name / description / subset_list will be enriched from DB
    # by the startup sync (benchmark_sync.py). Only provide runtime defaults here.
    return BenchmarkMeta(
        name=benchmark_name,
        display_name=benchmark_name,
        family_name=_FAMILY_NAME,
        family_display_name=_FAMILY_DISPLAY_NAME,
        default_eval_method="judge-model",
        requires_judge_model=True,
        supports_custom_dataset=False,
        sample_schema_json=GROUNDED_RUBRIC_QA_SOURCE_SCHEMA,
        prompt_schema_json=GROUNDED_RUBRIC_QA_PROMPT_SCHEMA,
        prompt_config_json=dict(GROUNDED_RUBRIC_QA_PROMPT_CONFIG),
        metric_names=["cl_bench_acc"],
        aggregator_names=["mean"],
        subset_list=["default"],
    )


def _register_grounded_rubric_benchmark(benchmark_name: str) -> None:
    metadata = _grounded_rubric_meta(benchmark_name)

    @register_benchmark(metadata)
    class _ConcreteGroundedRubricQABenchmark(BaseGroundedRubricQABenchmark):
        pass

    _ConcreteGroundedRubricQABenchmark.__name__ = (
        f"{benchmark_name.title().replace('_', '')}Benchmark"
    )


for _benchmark_name in _BENCHMARK_NAMES:
    _register_grounded_rubric_benchmark(_benchmark_name)
