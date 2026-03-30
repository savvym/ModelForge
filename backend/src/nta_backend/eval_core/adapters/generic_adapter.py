from __future__ import annotations

from typing import Any

from nta_backend.eval_core.adapters.default_adapter import DefaultDataAdapter
from nta_backend.eval_core.api.benchmark import BenchmarkMeta
from nta_backend.eval_core.api.dataset import ChatMessage, Sample
from nta_backend.eval_core.api.registry import register_benchmark
from nta_backend.eval_core.config import EvalTaskConfig

# Default field names matching the standard JSONL format.
_DEFAULT_INPUT_FIELD = "input"
_DEFAULT_TARGET_FIELD = "target"
_DEFAULT_CHOICES_FIELD = "choices"
_DEFAULT_ID_FIELD = "id"


@register_benchmark(
    BenchmarkMeta(
        name="_generic",
        display_name="Generic Benchmark",
        description="Config-driven benchmark adapter. Supports any JSONL format via field mapping.",
        default_eval_method="accuracy",
        supports_custom_dataset=True,
        metric_names=["acc"],
        aggregator_names=["mean"],
    )
)
class GenericBenchmark(DefaultDataAdapter):
    """Config-driven benchmark adapter that requires no custom Python code.

    Field mapping and eval method are read from ``benchmark_args`` at
    construction time, allowing the same adapter class to serve any
    benchmark whose scoring logic is covered by a registered metric.
    """

    def __init__(
        self,
        *,
        task_config: EvalTaskConfig | None = None,
        dataset_path: str | None = None,
        field_mapping: dict[str, Any] | None = None,
        eval_method: str | None = None,
        **kwargs: object,
    ):
        # Override meta dynamically if eval_method / metric_names are provided.
        if eval_method:
            metric_names = _metric_names_for_eval_method(eval_method)
        else:
            metric_names = None

        super().__init__(task_config=task_config, dataset_path=dataset_path, **kwargs)

        if metric_names:
            # Patch meta.metric_names so DefaultDataAdapter._build_metrics()
            # picks up the right metric from the registry.
            self.meta = self.meta.model_copy(update={"metric_names": metric_names})

        self._field_mapping = field_mapping or {}

    # ------------------------------------------------------------------
    # record_to_sample — config-driven field mapping
    # ------------------------------------------------------------------

    def record_to_sample(self, record: dict[str, Any], line_number: int) -> Sample:
        mapping = self._field_mapping

        input_field = mapping.get("input_field", _DEFAULT_INPUT_FIELD)
        target_field = mapping.get("target_field", _DEFAULT_TARGET_FIELD)
        choices_field = mapping.get("choices_field", _DEFAULT_CHOICES_FIELD)
        id_field = mapping.get("id_field", _DEFAULT_ID_FIELD)

        raw_input = record.get(input_field)
        raw_target = record.get(target_field)
        raw_choices = record.get(choices_field)
        raw_id = record.get(id_field)

        return Sample(
            id=str(raw_id) if raw_id is not None else f"sample-{line_number}",
            input=_parse_input(raw_input, line_number),
            target=_parse_target(raw_target),
            choices=_parse_choices(raw_choices),
            metadata=_extract_metadata(record, mapping),
        )


# ------------------------------------------------------------------
# Helpers
# ------------------------------------------------------------------


def _metric_names_for_eval_method(eval_method: str) -> list[str]:
    """Map user-facing eval_method to registered metric name(s)."""
    mapping = {
        "accuracy": ["acc"],
        "acc": ["acc"],
        "judge-model": ["cl_bench_acc"],
    }
    return mapping.get(eval_method, [eval_method])


def _parse_input(value: Any, line_number: int) -> str | list[ChatMessage]:
    """Convert raw input value to str or list[ChatMessage]."""
    if isinstance(value, str):
        if not value.strip():
            raise ValueError(f"Sample at line {line_number}: input is empty.")
        return value.strip()

    if isinstance(value, list):
        # Try to interpret as ChatMessage list
        messages: list[ChatMessage] = []
        for item in value:
            if isinstance(item, dict) and item.get("role") and item.get("content"):
                messages.append(
                    ChatMessage(role=str(item["role"]), content=str(item["content"]))
                )
        if messages:
            return messages
        # Fallback: join string items
        parts = [str(item).strip() for item in value if str(item).strip()]
        if parts:
            return "\n\n".join(parts)

    if value is not None:
        text = str(value).strip()
        if text:
            return text

    raise ValueError(f"Sample at line {line_number}: input is missing or empty.")


def _parse_target(value: Any) -> str | list[str] | None:
    """Convert raw target value to str, list[str], or None."""
    if value is None:
        return None
    if isinstance(value, str):
        return value.strip() or None
    if isinstance(value, list):
        items = [str(item).strip() for item in value if str(item).strip()]
        return items if items else None
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        return str(value)
    return str(value).strip() or None


def _parse_choices(value: Any) -> list[str] | None:
    """Convert raw choices value to list[str] or None."""
    if value is None:
        return None
    if not isinstance(value, list):
        return None
    choices = [str(item).strip() for item in value if str(item).strip()]
    return choices if len(choices) >= 2 else None


def _extract_metadata(
    record: dict[str, Any],
    mapping: dict[str, Any],
) -> dict[str, Any]:
    """Extract metadata fields from the raw record."""
    metadata: dict[str, Any] = {}

    # Copy explicitly listed metadata fields
    for field_name in mapping.get("metadata_fields", []):
        if field_name in record:
            metadata[field_name] = record[field_name]

    # Also include any "metadata" field from the record itself
    raw_metadata = record.get("metadata")
    if isinstance(raw_metadata, dict):
        for key, value in raw_metadata.items():
            metadata.setdefault(key, value)

    return metadata
