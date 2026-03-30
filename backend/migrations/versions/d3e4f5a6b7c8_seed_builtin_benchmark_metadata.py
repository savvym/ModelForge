"""seed builtin benchmark metadata from JSON files

Revision ID: d3e4f5a6b7c8
Revises: c2d3e4f5a6b7
Create Date: 2026-03-27 14:02:00.000000
"""

from __future__ import annotations

import json
import os
from collections.abc import Sequence
from uuid import uuid4

from alembic import op
from sqlalchemy import text

# revision identifiers, used by Alembic.
revision: str = "d3e4f5a6b7c8"
down_revision: str = "c2d3e4f5a6b7"
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None

# Path to builtin meta JSON files relative to this migration
_META_DIR = os.path.join(
    os.path.dirname(__file__),
    "..",
    "..",
    "src",
    "nta_backend",
    "eval_catalog",
    "builtin_meta",
)


def _normalize_string_list(value: object) -> list[str]:
    if not isinstance(value, list):
        return []
    return [item.strip() for item in value if isinstance(item, str) and item.strip()]


def _normalize_optional_dict(value: object) -> dict | None:
    return value if isinstance(value, dict) else None


def _load_meta_file(path: str) -> dict | None:
    """Parse a builtin meta JSON file into a dict suitable for DB insert."""
    try:
        with open(path, encoding="utf-8") as f:
            payload = json.load(f)
    except (json.JSONDecodeError, OSError):
        return None

    if not isinstance(payload, dict):
        return None

    raw_meta = payload.get("meta") if isinstance(payload, dict) else None
    meta = raw_meta if isinstance(raw_meta, dict) else {}

    name = os.path.splitext(os.path.basename(path))[0]
    display_name = str(meta.get("pretty_name") or name).strip() or name

    few_shot_num = meta.get("few_shot_num")
    if not isinstance(few_shot_num, int) or isinstance(few_shot_num, bool):
        few_shot_num = None

    return {
        "name": name,
        "display_name": display_name,
        "description": str(meta.get("description") or "").strip(),
        "family_name": str(meta.get("family_name")).strip() if meta.get("family_name") else None,
        "family_display_name": (
            str(meta.get("family_display_name")).strip()
            if meta.get("family_display_name")
            else None
        ),
        "dataset_id": str(meta.get("dataset_id")).strip() if meta.get("dataset_id") else None,
        "category": str(meta.get("category")).strip() if meta.get("category") else None,
        "paper_url": str(meta.get("paper_url")).strip() if meta.get("paper_url") else None,
        "tags": json.dumps(_normalize_string_list(meta.get("tags"))),
        "metric_names": json.dumps(_normalize_string_list(meta.get("metrics"))),
        "few_shot_num": few_shot_num,
        "eval_split": str(meta.get("eval_split")).strip() if meta.get("eval_split") else None,
        "train_split": str(meta.get("train_split")).strip() if meta.get("train_split") else None,
        "subset_list": json.dumps(_normalize_string_list(meta.get("subset_list"))),
        "prompt_template": (
            str(meta.get("prompt_template")).strip() if meta.get("prompt_template") else None
        ),
        "system_prompt": (
            str(meta.get("system_prompt")).strip() if meta.get("system_prompt") else None
        ),
        "few_shot_prompt_template": (
            str(meta.get("few_shot_prompt_template")).strip()
            if meta.get("few_shot_prompt_template")
            else None
        ),
        "sample_example_json": json.dumps(_normalize_optional_dict(payload.get("sample_example"))),
        "statistics_json": json.dumps(_normalize_optional_dict(payload.get("statistics"))),
        "readme_json": json.dumps(_normalize_optional_dict(payload.get("readme"))),
        "source_type": "builtin",
        "is_runnable": False,
    }


def upgrade() -> None:
    meta_dir = os.path.normpath(_META_DIR)
    if not os.path.isdir(meta_dir):
        return

    conn = op.get_bind()

    for filename in sorted(os.listdir(meta_dir)):
        if not filename.endswith(".json"):
            continue
        filepath = os.path.join(meta_dir, filename)
        row = _load_meta_file(filepath)
        if row is None:
            continue

        # Check if benchmark already exists (e.g., seeded by a prior migration)
        exists = conn.execute(
            text("SELECT id FROM benchmark_definitions WHERE name = :name"),
            {"name": row["name"]},
        ).fetchone()

        if exists:
            # UPDATE new columns only (don't overwrite runtime-seeded fields)
            conn.execute(
                text("""
                    UPDATE benchmark_definitions SET
                        family_name = COALESCE(family_name, :family_name),
                        family_display_name = COALESCE(family_display_name, :family_display_name),
                        dataset_id = COALESCE(dataset_id, :dataset_id),
                        category = COALESCE(category, :category),
                        paper_url = COALESCE(paper_url, :paper_url),
                        tags = COALESCE(tags, CAST(:tags AS jsonb)),
                        metric_names = COALESCE(metric_names, CAST(:metric_names AS jsonb)),
                        subset_list = COALESCE(subset_list, CAST(:subset_list AS jsonb)),
                        prompt_template = COALESCE(prompt_template, :prompt_template),
                        system_prompt = COALESCE(system_prompt, :system_prompt),
                        few_shot_prompt_template = COALESCE(few_shot_prompt_template, :few_shot_prompt_template),
                        few_shot_num = COALESCE(few_shot_num, :few_shot_num),
                        eval_split = COALESCE(eval_split, :eval_split),
                        train_split = COALESCE(train_split, :train_split),
                        sample_example_json = COALESCE(sample_example_json, CAST(:sample_example_json AS jsonb)),
                        statistics_json = COALESCE(statistics_json, CAST(:statistics_json AS jsonb)),
                        readme_json = COALESCE(readme_json, CAST(:readme_json AS jsonb)),
                        source_type = COALESCE(source_type, :source_type)
                    WHERE name = :name
                """),
                row,
            )
        else:
            # INSERT new benchmark definition
            row["id"] = str(uuid4())
            row["default_eval_method"] = "not-implemented"
            row["sample_schema_json"] = json.dumps({"type": "object"})
            row["prompt_schema_json"] = json.dumps({"type": "object"})
            row["prompt_config_json"] = json.dumps({})
            row["aggregator_names"] = json.dumps([])
            conn.execute(
                text("""
                    INSERT INTO benchmark_definitions (
                        id, name, display_name, description, default_eval_method,
                        sample_schema_json, prompt_schema_json, prompt_config_json,
                        requires_judge_model, supports_custom_dataset,
                        family_name, family_display_name, dataset_id, category, paper_url,
                        tags, metric_names, aggregator_names, subset_list,
                        prompt_template, system_prompt, few_shot_prompt_template,
                        few_shot_num, eval_split, train_split,
                        sample_example_json, statistics_json, readme_json,
                        source_type, is_runnable
                    ) VALUES (
                        :id, :name, :display_name, :description, :default_eval_method,
                        CAST(:sample_schema_json AS jsonb), CAST(:prompt_schema_json AS jsonb), CAST(:prompt_config_json AS jsonb),
                        false, false,
                        :family_name, :family_display_name, :dataset_id, :category, :paper_url,
                        CAST(:tags AS jsonb), CAST(:metric_names AS jsonb), CAST(:aggregator_names AS jsonb), CAST(:subset_list AS jsonb),
                        :prompt_template, :system_prompt, :few_shot_prompt_template,
                        :few_shot_num, :eval_split, :train_split,
                        CAST(:sample_example_json AS jsonb), CAST(:statistics_json AS jsonb), CAST(:readme_json AS jsonb),
                        :source_type, :is_runnable
                    )
                """),
                row,
            )


def downgrade() -> None:
    # Remove rows that were inserted by this migration (source_type='builtin' + is_runnable=false)
    # We only delete rows that have no versions (untouched by users)
    conn = op.get_bind()
    conn.execute(
        text("""
            DELETE FROM benchmark_definitions
            WHERE source_type = 'builtin'
              AND is_runnable = false
              AND id NOT IN (SELECT DISTINCT benchmark_id FROM benchmark_versions)
        """)
    )
