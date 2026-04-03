from __future__ import annotations

import re
from pathlib import Path
from typing import Any

from evalscope.api.dataset import Sample
from evalscope.api.dataset.loader import LocalDataLoader
from evalscope.api.messages import ChatMessage, dict_to_chat_message

_DEFAULT_INPUT_FIELD = "input"
_DEFAULT_TARGET_FIELD = "target"
_DEFAULT_ID_FIELD = "id"
_PATH_SEGMENT_RE = re.compile(r"([^.\[\]]+)|\[(-?\d+)\]")


def primary_metric_name_for_eval_method(eval_method: str | None) -> str:
    return metric_names_for_eval_method(eval_method)[0]


def metric_names_for_eval_method(eval_method: str | None) -> list[str]:
    mapping = {
        "accuracy": ["acc"],
        "acc": ["acc"],
        "judge-rubric": ["judge_rubric"],
        "judge-quality": ["judge_quality"],
        "judge-template": ["judge_template"],
        "judge-model": ["judge_rubric"],
    }
    normalized = (eval_method or "accuracy").strip()
    return mapping.get(normalized, [normalized])


def count_local_dataset_samples(
    dataset_path: str | Path,
    *,
    field_mapping: dict[str, Any] | None = None,
    limit: int | None = None,
) -> int:
    loader = LocalDataLoader(
        data_id_or_path=str(dataset_path),
        split="default",
        subset="default",
        sample_fields=lambda record: build_evalscope_sample(
            record,
            field_mapping=field_mapping,
        ),
        limit=limit,
    )
    dataset = loader.load()
    return len(dataset)


def build_evalscope_sample(
    record: dict[str, Any],
    *,
    field_mapping: dict[str, Any] | None = None,
    line_number: int | None = None,
) -> Sample:
    mapping = field_mapping or {}
    input_template = mapping.get("input_template")
    if isinstance(input_template, str) and input_template.strip():
        raw_input = render_template(input_template, record)
    else:
        raw_input = resolve_field(
            record,
            mapping,
            "input_field",
            "input_selector",
            _DEFAULT_INPUT_FIELD,
        )

    raw_target = resolve_field(
        record,
        mapping,
        "target_field",
        "target_selector",
        _DEFAULT_TARGET_FIELD,
    )
    raw_id = resolve_field(
        record,
        mapping,
        "id_field",
        "id_selector",
        _DEFAULT_ID_FIELD,
    )

    metadata = extract_metadata(record, mapping)
    if raw_id is not None:
        metadata.setdefault("source_sample_id", str(raw_id))

    input_value = parse_input_value(raw_input, line_number=line_number)
    target_value = parse_target_value(raw_target)

    normalized_input: str | list[ChatMessage]
    if isinstance(input_value, list):
        normalized_input = [
            item if not isinstance(item, dict) else dict_to_chat_message(item)
            for item in input_value
        ]
    else:
        normalized_input = input_value

    return Sample(
        id=None,
        input=normalized_input,
        target=target_value or "",
        metadata=metadata,
    )


def render_template(template: str, record: dict[str, Any]) -> str:
    def replace(match: re.Match[str]) -> str:
        key = match.group(1)
        value = record.get(key)
        if value is None:
            return ""
        return value if isinstance(value, str) else str(value)

    return re.sub(r"\{(\w+)\}", replace, template)


def resolve_field(
    record: dict[str, Any],
    mapping: dict[str, Any],
    field_key: str,
    selector_key: str,
    default_field: str,
) -> Any:
    field_name = mapping.get(field_key, default_field)
    value = record.get(field_name)
    selector = mapping.get(selector_key)
    if selector and value is not None:
        value = resolve_selector(value, str(selector))
    return value


def resolve_selector(value: Any, selector: str) -> Any:
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
            index = int(index_str)
            if isinstance(current, (list, tuple)) and -len(current) <= index < len(current):
                current = current[index]
            else:
                return None
    return current


def parse_input_value(
    value: Any,
    *,
    line_number: int | None = None,
) -> str | list[dict[str, str]]:
    if isinstance(value, str):
        normalized = value.strip()
        if normalized:
            return normalized
        raise _missing_input_error(line_number)

    if isinstance(value, list):
        messages: list[dict[str, str]] = []
        for item in value:
            if isinstance(item, dict) and item.get("role") and item.get("content"):
                messages.append(
                    {
                        "role": str(item["role"]),
                        "content": str(item["content"]),
                    }
                )
        if messages:
            return messages

        parts = [str(item).strip() for item in value if str(item).strip()]
        if parts:
            return "\n\n".join(parts)

    if value is not None:
        normalized = str(value).strip()
        if normalized:
            return normalized

    raise _missing_input_error(line_number)


def parse_target_value(value: Any) -> str | list[str] | None:
    if value is None:
        return None
    if isinstance(value, str):
        normalized = value.strip()
        return normalized or None
    if isinstance(value, list):
        items = [str(item).strip() for item in value if str(item).strip()]
        return items or None
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        return str(value)
    normalized = str(value).strip()
    return normalized or None


def extract_metadata(
    record: dict[str, Any],
    mapping: dict[str, Any],
) -> dict[str, Any]:
    metadata: dict[str, Any] = {}
    for field_name in mapping.get("metadata_fields", []):
        if field_name in record:
            metadata[field_name] = record[field_name]

    raw_metadata = record.get("metadata")
    if isinstance(raw_metadata, dict):
        for key, value in raw_metadata.items():
            metadata.setdefault(key, value)
    return metadata


def _missing_input_error(line_number: int | None) -> ValueError:
    if line_number is None:
        return ValueError("Sample input is missing or empty.")
    return ValueError(f"Sample at line {line_number}: input is missing or empty.")
