from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field


class BuiltinBenchmarkMetadata(BaseModel):
    name: str
    display_name: str
    family_name: str | None = None
    family_display_name: str | None = None
    description: str = ""
    dataset_id: str | None = None
    category: str | None = None
    paper_url: str | None = None
    tags: list[str] = Field(default_factory=list)
    metric_names: list[str] = Field(default_factory=list)
    few_shot_num: int | None = None
    eval_split: str | None = None
    train_split: str | None = None
    subset_list: list[str] = Field(default_factory=list)
    prompt_template: str | None = None
    system_prompt: str | None = None
    few_shot_prompt_template: str | None = None
    sample_example_json: dict[str, Any] | None = None
    statistics_json: dict[str, Any] | None = None
    readme_json: dict[str, Any] | None = None
    meta_updated_at: str | None = None
    meta_translation_updated_at: str | None = None


def _meta_dir() -> Path:
    return Path(__file__).resolve().parent / "builtin_meta"


def _normalize_string_list(value: object) -> list[str]:
    if not isinstance(value, list):
        return []
    return [item.strip() for item in value if isinstance(item, str) and item.strip()]


def _normalize_optional_dict(value: object) -> dict[str, Any] | None:
    return value if isinstance(value, dict) else None


def _load_meta_file(path: Path) -> BuiltinBenchmarkMetadata:
    payload = json.loads(path.read_text(encoding="utf-8"))
    raw_meta = payload.get("meta") if isinstance(payload, dict) else None
    meta = raw_meta if isinstance(raw_meta, dict) else {}
    few_shot_num = meta.get("few_shot_num")
    if not isinstance(few_shot_num, int) or isinstance(few_shot_num, bool):
        few_shot_num = None

    return BuiltinBenchmarkMetadata(
        name=path.stem,
        display_name=str(meta.get("pretty_name") or path.stem).strip() or path.stem,
        family_name=str(meta.get("family_name")).strip() if meta.get("family_name") else None,
        family_display_name=(
            str(meta.get("family_display_name")).strip()
            if meta.get("family_display_name")
            else None
        ),
        description=str(meta.get("description") or "").strip(),
        dataset_id=str(meta.get("dataset_id")).strip() if meta.get("dataset_id") else None,
        category=str(meta.get("category")).strip() if meta.get("category") else None,
        paper_url=str(meta.get("paper_url")).strip() if meta.get("paper_url") else None,
        tags=_normalize_string_list(meta.get("tags")),
        metric_names=_normalize_string_list(meta.get("metrics")),
        few_shot_num=few_shot_num,
        eval_split=str(meta.get("eval_split")).strip() if meta.get("eval_split") else None,
        train_split=str(meta.get("train_split")).strip() if meta.get("train_split") else None,
        subset_list=_normalize_string_list(meta.get("subset_list")),
        prompt_template=str(meta.get("prompt_template")).strip()
        if meta.get("prompt_template")
        else None,
        system_prompt=str(meta.get("system_prompt")).strip() if meta.get("system_prompt") else None,
        few_shot_prompt_template=str(meta.get("few_shot_prompt_template")).strip()
        if meta.get("few_shot_prompt_template")
        else None,
        sample_example_json=_normalize_optional_dict(payload.get("sample_example")),
        statistics_json=_normalize_optional_dict(payload.get("statistics")),
        readme_json=_normalize_optional_dict(payload.get("readme")),
        meta_updated_at=(
            str(payload.get("updated_at")).strip() if payload.get("updated_at") else None
        ),
        meta_translation_updated_at=str(payload.get("translation_updated_at")).strip()
        if payload.get("translation_updated_at")
        else None,
    )


@lru_cache(maxsize=1)
def _meta_map() -> dict[str, BuiltinBenchmarkMetadata]:
    meta_dir = _meta_dir()
    if not meta_dir.exists():
        return {}
    return {
        path.stem: _load_meta_file(path)
        for path in sorted(meta_dir.glob("*.json"))
    }


def list_builtin_benchmark_metas() -> list[BuiltinBenchmarkMetadata]:
    return [
        metadata.model_copy(deep=True)
        for _, metadata in sorted(_meta_map().items())
    ]


def get_builtin_benchmark_meta(name: str | None) -> BuiltinBenchmarkMetadata | None:
    if not name or not name.strip():
        return None
    metadata = _meta_map().get(name.strip())
    if metadata is None:
        return None
    return metadata.model_copy(deep=True)
