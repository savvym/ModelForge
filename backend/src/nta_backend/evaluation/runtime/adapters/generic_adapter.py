from __future__ import annotations

import re
from typing import Any

from nta_backend.evaluation.runtime.adapters.default_adapter import DefaultDataAdapter
from nta_backend.evaluation.runtime.api.benchmark import BenchmarkMeta
from nta_backend.evaluation.runtime.api.dataset import ChatMessage, Sample
from nta_backend.evaluation.runtime.api.model import ModelOutput
from nta_backend.evaluation.runtime.api.registry import register_benchmark
from nta_backend.evaluation.runtime.config import EvalTaskConfig

# Default field names matching the standard JSONL format.
_DEFAULT_INPUT_FIELD = "input"
_DEFAULT_TARGET_FIELD = "target"
_DEFAULT_ID_FIELD = "id"

# Regex for parsing path segments: field name, or array index like [0] or [-1]
_PATH_SEGMENT_RE = re.compile(r"([^.\[\]]+)|\[(-?\d+)\]")


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
        prompt_config: dict[str, object] | None = None,
        judge_model_name: str | None = None,
        judge_api_url: str | None = None,
        judge_api_key: str | None = None,
        judge_api_format: str | None = None,
        judge_timeout_s: float = 180.0,
        # Template-driven eval params
        template_prompt: str | None = None,
        template_vars: list[str] | None = None,
        template_output_type: str | None = None,
        template_output_config: dict[str, Any] | None = None,
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
        self._eval_method = eval_method
        self._prompt_config = prompt_config or {}

        # Judge model params (used when eval_method is judge-rubric or judge-quality)
        self._judge_model_name = judge_model_name or self._as_str(task_config, "judge_model_name")
        self._judge_api_url = (
            judge_api_url
            or self._as_str(task_config, "judge_api_url")
            or self._as_str(task_config, "api_url")
        )
        self._judge_api_key = (
            judge_api_key
            or self._as_str(task_config, "judge_api_key")
            or self._as_str(task_config, "api_key")
        )
        self._judge_api_format = (
            judge_api_format
            or self._as_str(task_config, "judge_api_format")
            or self._as_str(task_config, "api_format")
            or "chat-completions"
        )
        self._judge_timeout_s = judge_timeout_s

        # Template-driven eval
        self._template_prompt = template_prompt
        self._template_vars = template_vars or []
        self._template_output_type = template_output_type
        self._template_output_config = template_output_config or {}

    # ------------------------------------------------------------------
    # Judge model support
    # ------------------------------------------------------------------

    def _metric_kwargs(self) -> dict[str, Any]:
        if self._eval_method == "judge-template" and self._template_prompt:
            return self._build_template_metric_kwargs()
        if self._eval_method in ("judge-rubric", "judge-quality", "judge-model"):
            return self._build_judge_metric_kwargs()
        return {}

    def _build_judge_metric_kwargs(self) -> dict[str, Any]:
        if not self._judge_model_name or not self._judge_api_url:
            raise ValueError(
                "Judge-based eval requires judge_model_name and judge_api_url. "
                "Pass them via benchmark_args or model_args."
            )
        prompt_template = self._prompt_config.get("judge_prompt_template")
        if isinstance(prompt_template, str) and not prompt_template.strip():
            prompt_template = None
        return {
            "api_url": self._judge_api_url,
            "api_key": self._judge_api_key,
            "api_format": self._judge_api_format,
            "model_name": self._judge_model_name,
            "prompt_template": prompt_template,
            "timeout_s": self._judge_timeout_s,
        }

    def _build_template_metric_kwargs(self) -> dict[str, Any]:
        if not self._judge_model_name or not self._judge_api_url:
            raise ValueError(
                "Template-based eval requires judge_model_name and judge_api_url."
            )

        from nta_backend.evaluation.runtime.template_utils import (
            build_output_instruction,
            compile_template,
        )

        tmpl_prompt = self._template_prompt
        output_type = self._template_output_type or "numeric"
        output_config = self._template_output_config
        output_instruction = build_output_instruction(output_type, output_config)

        def compiled_prompt_fn(sample: Sample, output: ModelOutput) -> str:
            # Build variable map from sample fields
            variables: dict[str, str] = {}
            if isinstance(sample.input, str):
                variables["input"] = sample.input
            elif isinstance(sample.input, list):
                variables["input"] = "\n".join(
                    f"{m.role}: {m.content}" for m in sample.input
                )
            if sample.target is not None:
                if isinstance(sample.target, list):
                    variables["target"] = "\n".join(
                        f"{i}. {t}" for i, t in enumerate(sample.target, 1)
                    )
                else:
                    variables["target"] = sample.target
            variables["output"] = output.text
            # Include metadata fields
            for key, value in sample.metadata.items():
                if key not in variables:
                    variables[key] = str(value)
            compiled = compile_template(tmpl_prompt, variables)
            return f"{compiled}\n\n{output_instruction}"

        return {
            "api_url": self._judge_api_url,
            "api_key": self._judge_api_key,
            "api_format": self._judge_api_format,
            "model_name": self._judge_model_name,
            "compiled_prompt_fn": compiled_prompt_fn,
            "output_type": output_type,
            "output_config": output_config,
            "timeout_s": self._judge_timeout_s,
        }

    # ------------------------------------------------------------------
    # record_to_sample — config-driven field mapping
    # ------------------------------------------------------------------

    def record_to_sample(self, record: dict[str, Any], line_number: int) -> Sample:
        mapping = self._field_mapping

        # input supports template mode: "背景：{context}\n问题：{question}"
        input_template = mapping.get("input_template")
        if input_template:
            raw_input = _render_template(input_template, record)
        else:
            raw_input = _resolve_field(
                record,
                mapping,
                "input_field",
                "input_selector",
                _DEFAULT_INPUT_FIELD,
            )

        raw_target = _resolve_field(
            record,
            mapping,
            "target_field",
            "target_selector",
            _DEFAULT_TARGET_FIELD,
        )
        raw_id = _resolve_field(record, mapping, "id_field", "id_selector", _DEFAULT_ID_FIELD)

        return Sample(
            id=str(raw_id) if raw_id is not None else f"sample-{line_number}",
            input=_parse_input(raw_input, line_number),
            target=_parse_target(raw_target),
            metadata=_extract_metadata(record, mapping),
        )


# ------------------------------------------------------------------
# Helpers
# ------------------------------------------------------------------


def _render_template(template: str, record: dict[str, Any]) -> str:
    """Replace ``{field}`` placeholders in *template* with values from *record*.

    Each placeholder name is looked up as a top-level key in the record.
    Missing keys are replaced with an empty string.
    """

    def _replace(match: re.Match) -> str:
        key = match.group(1)
        value = record.get(key)
        if value is None:
            return ""
        if isinstance(value, str):
            return value
        return str(value)

    return re.sub(r"\{(\w+)\}", _replace, template)


def _resolve_field(
    record: dict[str, Any],
    mapping: dict[str, Any],
    field_key: str,
    selector_key: str,
    default_field: str,
) -> Any:
    """Read a field from the record, optionally applying a path selector.

    ``field_key`` names the mapping entry for the top-level field name
    (e.g. ``"input_field"``).  ``selector_key`` names the optional path
    selector (e.g. ``"input_selector"``).  If a selector is provided, it
    is resolved against the value of the top-level field.
    """
    field_name = mapping.get(field_key, default_field)
    value = record.get(field_name)
    selector = mapping.get(selector_key)
    if selector and value is not None:
        value = _resolve_selector(value, selector)
    return value


def _resolve_selector(value: Any, selector: str) -> Any:
    """Resolve a dot/bracket path against a nested value.

    Supports:
      - Dot notation:   ``field.subfield``
      - Array indexing: ``field[0]``, ``[-1]``
      - Combined:       ``messages[-1].content``

    Returns ``None`` if any segment cannot be resolved.
    """
    current = value
    for match in _PATH_SEGMENT_RE.finditer(selector):
        if current is None:
            return None
        field_name, index_str = match.groups()
        if field_name is not None:
            if isinstance(current, dict):
                current = current.get(field_name)
            else:
                return None
        elif index_str is not None:
            idx = int(index_str)
            if isinstance(current, (list, tuple)) and -len(current) <= idx < len(current):
                current = current[idx]
            else:
                return None
    return current


def _metric_names_for_eval_method(eval_method: str) -> list[str]:
    """Map user-facing eval_method to registered metric name(s)."""
    mapping = {
        "accuracy": ["acc"],
        "acc": ["acc"],
        "judge-rubric": ["judge_rubric"],
        "judge-quality": ["judge_quality"],
        "judge-template": ["judge_template"],
        "judge-model": ["judge_rubric"],  # backward compat
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
