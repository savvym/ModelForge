from __future__ import annotations

import csv
import json
import zipfile
from pathlib import Path
from typing import Any

from nta_backend.eval_core.adapters.default_adapter import DefaultDataAdapter
from nta_backend.eval_core.api.dataset import DatasetDict, Sample
from nta_backend.eval_core.config import EvalTaskConfig

try:
    import pyarrow.parquet as pq
except ModuleNotFoundError:  # pragma: no cover
    pq = None

_LETTER_LABELS = ("A", "B", "C", "D", "E", "F")


class MultiChoiceAdapter(DefaultDataAdapter):
    """Adapter for multiple-choice benchmarks (MMLU, CEval, CMMLU, ARC, etc.).

    Supports loading from JSONL, CSV, ZIP, and Parquet formats.  Dispatches
    record parsing by ``self.meta.name`` to handle vendor-specific schemas.
    """

    def __init__(
        self,
        *,
        task_config: EvalTaskConfig | None = None,
        dataset_path: str | None = None,
        **kwargs: object,
    ):
        super().__init__(task_config=task_config, dataset_path=dataset_path, **kwargs)
        # Cache prompt_template from meta for runtime MCQ prompt rendering.
        # This replaces the old runtime call to get_builtin_benchmark_meta().
        self._prompt_template: str | None = (
            self.meta.prompt_config_json.get("prompt_template")
            if self.meta.prompt_config_json
            else None
        )

    # ------------------------------------------------------------------
    # Dataset loading (multi-format)
    # ------------------------------------------------------------------

    def load_dataset(self) -> DatasetDict:
        path = self._require_dataset_path()
        samples = list(self._load_samples(path))
        if not samples:
            benchmark_name = self.meta.display_name or self.meta.name
            raise ValueError(f"{benchmark_name} dataset is empty.")
        return {"default": samples}

    def _load_samples(self, path: Path) -> list[Sample]:
        name = self.meta.name
        pt = self._prompt_template
        suffix = path.suffix.lower()
        if suffix == ".jsonl":
            return _load_jsonl_samples(path, benchmark_name=name, prompt_template=pt)
        if suffix == ".csv":
            return _load_csv_samples(path, benchmark_name=name, prompt_template=pt)
        if suffix == ".zip":
            return _load_zip_samples(path, benchmark_name=name, prompt_template=pt)
        if suffix == ".parquet":
            return _load_parquet_samples(path, benchmark_name=name, prompt_template=pt)
        raise ValueError(
            f"{self.meta.display_name or self.meta.name} does not support dataset file "
            f"format '{suffix or '(none)'}'."
        )

    # ------------------------------------------------------------------
    # record_to_sample — dispatches by benchmark name
    # ------------------------------------------------------------------

    def record_to_sample(self, record: dict[str, Any], line_number: int) -> Sample:
        return _record_to_sample(
            record, line_number,
            benchmark_name=self.meta.name,
            prompt_template=self._prompt_template,
        )


# ======================================================================
# Module-level helpers
# ======================================================================


def _load_jsonl_samples(
    path: Path, *, benchmark_name: str, prompt_template: str | None = None,
) -> list[Sample]:
    samples: list[Sample] = []
    lines = path.read_text(encoding="utf-8").splitlines()
    default_subset = _infer_subset_from_path(path, benchmark_name=benchmark_name)
    for line_number, raw_line in enumerate(lines, start=1):
        line = raw_line.strip()
        if not line:
            continue
        try:
            record = json.loads(line)
        except json.JSONDecodeError as exc:
            raise ValueError(
                f"{benchmark_name} dataset has invalid JSON at line {line_number}."
            ) from exc
        if not isinstance(record, dict):
            raise ValueError(f"{benchmark_name} dataset line {line_number} must be a JSON object.")
        samples.append(
            _record_to_sample(
                record,
                line_number,
                benchmark_name=benchmark_name,
                default_subset=default_subset,
                prompt_template=prompt_template,
            )
        )
    return samples


def _load_csv_samples(
    path: Path, *, benchmark_name: str, prompt_template: str | None = None,
) -> list[Sample]:
    samples: list[Sample] = []
    default_subset = _infer_subset_from_path(path, benchmark_name=benchmark_name)
    with path.open("r", encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        for line_number, row in enumerate(reader, start=1):
            samples.append(
                _record_to_sample(
                    dict(row),
                    line_number,
                    benchmark_name=benchmark_name,
                    default_subset=default_subset,
                    prompt_template=prompt_template,
                )
            )
    return samples


def _load_zip_samples(
    path: Path, *, benchmark_name: str, prompt_template: str | None = None,
) -> list[Sample]:
    if benchmark_name != "cmmlu":
        raise ValueError(f"{benchmark_name} does not support zip dataset sources.")

    samples: list[Sample] = []
    line_number = 0
    with zipfile.ZipFile(path) as archive:
        entry_names = sorted(
            name
            for name in archive.namelist()
            if name.endswith(".csv") and not name.endswith("/")
        )
        if not entry_names:
            raise ValueError("cmmlu zip dataset does not contain any CSV files.")
        for entry_name in entry_names:
            subset_name = Path(entry_name).stem
            with archive.open(entry_name) as handle:
                reader = csv.DictReader(
                    (line.decode("utf-8-sig") for line in handle),
                )
                for row in reader:
                    line_number += 1
                    samples.append(
                        _record_to_sample(
                            dict(row),
                            line_number,
                            benchmark_name=benchmark_name,
                            default_subset=subset_name,
                            prompt_template=prompt_template,
                        )
                    )
    return samples


def _load_parquet_samples(
    path: Path, *, benchmark_name: str, prompt_template: str | None = None,
) -> list[Sample]:
    if pq is None:
        raise ValueError(
            f"{benchmark_name} parquet support requires pyarrow to be installed in backend."
        )

    table = pq.read_table(path)
    rows = table.to_pylist()
    default_subset = _infer_subset_from_path(path, benchmark_name=benchmark_name)
    return [
        _record_to_sample(
            row,
            index,
            benchmark_name=benchmark_name,
            default_subset=default_subset,
            prompt_template=prompt_template,
        )
        for index, row in enumerate(rows, start=1)
    ]


# ------------------------------------------------------------------
# Record → Sample dispatch
# ------------------------------------------------------------------


def _record_to_sample(
    record: dict[str, Any],
    line_number: int,
    *,
    benchmark_name: str,
    default_subset: str | None = None,
    prompt_template: str | None = None,
) -> Sample:
    payload = record.get("data")
    if isinstance(payload, dict):
        raw = payload
    else:
        raw = record

    if _looks_like_standardized_sample(raw):
        return _standardized_record_to_sample(raw, line_number)
    if benchmark_name == "mmlu":
        return _mmlu_record_to_sample(raw, line_number, prompt_template=prompt_template)
    if benchmark_name == "ceval":
        return _ceval_record_to_sample(
            raw, line_number, default_subset=default_subset, prompt_template=prompt_template,
        )
    if benchmark_name == "cmmlu":
        return _cmmlu_record_to_sample(
            raw, line_number, default_subset=default_subset, prompt_template=prompt_template,
        )
    if benchmark_name == "arc":
        return _arc_record_to_sample(
            raw, line_number, default_subset=default_subset, prompt_template=prompt_template,
        )
    raise ValueError(f"Unsupported MCQ benchmark runtime: {benchmark_name}")


def _looks_like_standardized_sample(raw: dict[str, Any]) -> bool:
    return "choices" in raw and (
        ("input" in raw and "target" in raw)
        or ("messages" in raw and "rubrics" in raw)
    )


# ------------------------------------------------------------------
# Standardized format
# ------------------------------------------------------------------


def _standardized_record_to_sample(raw: dict[str, Any], line_number: int) -> Sample:
    prompt = _extract_standardized_prompt(raw, line_number)
    choices = _extract_standardized_choices(raw, line_number)
    target = _extract_standardized_target(raw, line_number, len(choices))
    metadata = _extract_standardized_metadata(raw)
    sample_id = _extract_standardized_sample_id(raw, metadata, line_number)
    return Sample(
        id=sample_id,
        input=prompt,
        choices=choices,
        target=target,
        metadata=metadata,
    )


def _extract_standardized_prompt(raw: dict[str, Any], line_number: int) -> str:
    input_value = raw.get("input")
    if isinstance(input_value, str) and input_value.strip():
        return input_value.strip()
    if isinstance(input_value, list):
        parts: list[str] = []
        for item in input_value:
            if not isinstance(item, dict):
                continue
            content = item.get("content")
            if isinstance(content, str) and content.strip():
                parts.append(content.strip())
        if parts:
            return "\n\n".join(parts)
    raise ValueError(f"MCQ sample at line {line_number} must contain non-empty input.")


def _extract_standardized_choices(raw: dict[str, Any], line_number: int) -> list[str]:
    value = raw.get("choices")
    if not isinstance(value, list):
        raise ValueError(f"MCQ sample at line {line_number} must contain choices.")
    choices = [str(item).strip() for item in value if str(item).strip()]
    if len(choices) < 2:
        raise ValueError(f"MCQ sample at line {line_number} must contain at least 2 choices.")
    return choices


def _extract_standardized_target(
    raw: dict[str, Any],
    line_number: int,
    choice_count: int,
) -> str:
    value = raw.get("target")
    if isinstance(value, int) and not isinstance(value, bool):
        if value < 0 or value >= choice_count:
            raise ValueError(f"MCQ sample at line {line_number} has out-of-range target index.")
        return _LETTER_LABELS[value]
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"MCQ sample at line {line_number} must contain target.")
    normalized = value.strip().upper()
    if normalized.startswith("(") and normalized.endswith(")") and len(normalized) == 3:
        normalized = normalized[1]
    if len(normalized) == 1:
        return normalized
    return normalized[0]


def _extract_standardized_metadata(raw: dict[str, Any]) -> dict[str, Any]:
    metadata = raw.get("metadata")
    normalized = metadata.copy() if isinstance(metadata, dict) else {}
    if raw.get("subset_key") is not None:
        normalized.setdefault("subset_key", str(raw["subset_key"]))
    if raw.get("group_id") is not None:
        normalized.setdefault("group_id", raw["group_id"])
    return normalized


def _extract_standardized_sample_id(
    raw: dict[str, Any],
    metadata: dict[str, Any],
    line_number: int,
) -> str:
    if raw.get("id") is not None:
        return str(raw["id"])
    if metadata.get("id") is not None:
        return str(metadata["id"])
    return f"sample-{line_number}"


# ------------------------------------------------------------------
# MMLU
# ------------------------------------------------------------------


def _mmlu_record_to_sample(
    raw: dict[str, Any], line_number: int, *, prompt_template: str | None = None,
) -> Sample:
    question = _required_string(raw, "question", line_number, "mmlu")
    subject = _required_string(raw, "subject", line_number, "mmlu")
    choices = _extract_choice_list(raw.get("choices"), line_number, "mmlu")
    answer_value = raw.get("answer")
    if not isinstance(answer_value, int):
        raise ValueError(f"mmlu sample at line {line_number} must contain integer answer.")
    if answer_value < 0 or answer_value >= len(choices):
        raise ValueError(f"mmlu sample at line {line_number} has out-of-range answer index.")
    prompt = _render_mcq_prompt(
        question=question, choices=choices, subject=subject, prompt_template=prompt_template,
    )
    metadata = {"subject": subject, "subset_key": subject}
    sample_id = str(raw.get("id") or f"{subject}-{line_number}")
    return Sample(
        id=sample_id,
        input=prompt,
        choices=choices,
        target=_LETTER_LABELS[answer_value],
        metadata=metadata,
    )


# ------------------------------------------------------------------
# CEval
# ------------------------------------------------------------------


def _ceval_record_to_sample(
    raw: dict[str, Any],
    line_number: int,
    *,
    default_subset: str | None,
    prompt_template: str | None = None,
) -> Sample:
    question = _required_string(raw, "question", line_number, "ceval")
    choices = [_required_string(raw, label, line_number, "ceval") for label in _LETTER_LABELS[:4]]
    target = _normalize_answer_letter(raw.get("answer"), line_number, "ceval")
    subject = _resolve_subject(raw, default_subset=default_subset)
    prompt = _render_mcq_prompt(
        question=question, choices=choices, subject=subject, prompt_template=prompt_template,
    )
    metadata: dict[str, Any] = {"subject": subject, "subset_key": subject}
    explanation = raw.get("explanation")
    if isinstance(explanation, str) and explanation.strip():
        metadata["explanation"] = explanation.strip()
    sample_id = str(raw.get("id") or f"{subject}-{line_number}")
    return Sample(
        id=sample_id,
        input=prompt,
        choices=choices,
        target=target,
        metadata=metadata,
    )


# ------------------------------------------------------------------
# CMMLU
# ------------------------------------------------------------------


def _cmmlu_record_to_sample(
    raw: dict[str, Any],
    line_number: int,
    *,
    default_subset: str | None,
    prompt_template: str | None = None,
) -> Sample:
    question = _required_string(raw, "Question", line_number, "cmmlu")
    choices = [_required_string(raw, label, line_number, "cmmlu") for label in _LETTER_LABELS[:4]]
    target = _normalize_answer_letter(raw.get("Answer"), line_number, "cmmlu")
    subject = _resolve_subject(raw, default_subset=default_subset)
    prompt = _render_mcq_prompt(
        question=question, choices=choices, subject=subject, prompt_template=prompt_template,
    )
    metadata = {"subject": subject, "subset_key": subject}
    raw_id = raw.get("Unnamed: 0")
    sample_id = str(raw.get("id") or raw_id or f"{subject}-{line_number}")
    return Sample(
        id=sample_id,
        input=prompt,
        choices=choices,
        target=target,
        metadata=metadata,
    )


# ------------------------------------------------------------------
# ARC
# ------------------------------------------------------------------


def _arc_record_to_sample(
    raw: dict[str, Any],
    line_number: int,
    *,
    default_subset: str | None,
    prompt_template: str | None = None,
) -> Sample:
    question_value = raw.get("question")
    question = _extract_arc_question(question_value, line_number)
    choices = _extract_arc_choices(raw.get("choices"), line_number)
    target = _normalize_answer_letter(raw.get("answerKey"), line_number, "arc")
    subset = _resolve_subject(raw, default_subset=default_subset)
    prompt = _render_mcq_prompt(
        question=question, choices=choices, subject=subset, prompt_template=prompt_template,
    )
    metadata = {"subject": subset, "subset_key": subset}
    sample_id = str(raw.get("id") or f"{subset}-{line_number}")
    return Sample(
        id=sample_id,
        input=prompt,
        choices=choices,
        target=target,
        metadata=metadata,
    )


# ------------------------------------------------------------------
# Shared MCQ utilities
# ------------------------------------------------------------------


def _required_string(
    raw: dict[str, Any],
    field_name: str,
    line_number: int,
    benchmark_name: str,
) -> str:
    value = raw.get(field_name)
    if not isinstance(value, str) or not value.strip():
        raise ValueError(
            f"{benchmark_name} sample at line {line_number} must contain {field_name}."
        )
    return value.strip()


def _extract_choice_list(value: object, line_number: int, benchmark_name: str) -> list[str]:
    if not isinstance(value, list):
        raise ValueError(f"{benchmark_name} sample at line {line_number} must contain choices.")
    choices = [str(item).strip() for item in value if str(item).strip()]
    if len(choices) < 2:
        raise ValueError(f"{benchmark_name} sample at line {line_number} must contain 2+ choices.")
    return choices


def _normalize_answer_letter(value: object, line_number: int, benchmark_name: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{benchmark_name} sample at line {line_number} must contain answer.")
    normalized = value.strip().upper()
    if len(normalized) != 1 or normalized not in _LETTER_LABELS:
        raise ValueError(f"{benchmark_name} sample at line {line_number} has invalid answer.")
    return normalized


def _resolve_subject(raw: dict[str, Any], *, default_subset: str | None) -> str:
    for key in ("subject", "subset_key"):
        value = raw.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()
    metadata = raw.get("metadata")
    if isinstance(metadata, dict):
        for key in ("subject", "subset_key"):
            value = metadata.get(key)
            if isinstance(value, str) and value.strip():
                return value.strip()
    return default_subset or "default"


def _extract_arc_question(value: object, line_number: int) -> str:
    if isinstance(value, str) and value.strip():
        return value.strip()
    if isinstance(value, dict):
        for key in ("stem", "text", "question"):
            raw_text = value.get(key)
            if isinstance(raw_text, str) and raw_text.strip():
                return raw_text.strip()
    raise ValueError(f"arc sample at line {line_number} must contain question.")


def _extract_arc_choices(value: object, line_number: int) -> list[str]:
    pairs: list[tuple[str, str]] = []
    if isinstance(value, dict):
        labels = value.get("label")
        texts = value.get("text")
        if isinstance(labels, list) and isinstance(texts, list) and len(labels) == len(texts):
            pairs = [
                (str(label).strip().upper(), str(text).strip())
                for label, text in zip(labels, texts, strict=True)
                if str(text).strip()
            ]
    elif isinstance(value, list):
        for item in value:
            if isinstance(item, dict):
                label = item.get("label") or item.get("id") or item.get("key")
                text = item.get("text") or item.get("content")
                if label is not None and text is not None and str(text).strip():
                    pairs.append((str(label).strip().upper(), str(text).strip()))
    if not pairs:
        raise ValueError(f"arc sample at line {line_number} must contain valid choices.")
    ordered = sorted(
        pairs,
        key=lambda item: _LETTER_LABELS.index(item[0]) if item[0] in _LETTER_LABELS else 99,
    )
    return [text for _, text in ordered]


def _render_mcq_prompt(
    *,
    question: str,
    choices: list[str],
    subject: str | None,
    prompt_template: str | None = None,
) -> str:
    labels = _LETTER_LABELS[: len(choices)]
    choice_block = "\n".join(
        f"{label}. {choice}" for label, choice in zip(labels, choices, strict=True)
    )
    if prompt_template:
        try:
            return prompt_template.format(
                subject=subject or "general",
                question=question.strip(),
                choices=choice_block,
                letters=",".join(labels),
            ).strip()
        except KeyError:
            pass
    return (
        f"{question.strip()}\n\nChoices:\n{choice_block}\n\n"
        "Answer with the option letter only."
    )


def _infer_subset_from_path(path: Path, *, benchmark_name: str) -> str | None:
    if benchmark_name == "mmlu":
        return path.parent.name if path.parent.name and path.parent.name != path.anchor else None
    if benchmark_name == "ceval":
        return path.parent.name if path.parent.name else path.stem
    if benchmark_name == "cmmlu":
        return path.stem
    if benchmark_name == "arc":
        return path.parent.name if path.parent.name else path.stem
    return None
