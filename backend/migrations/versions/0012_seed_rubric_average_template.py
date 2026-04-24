"""seed rubric average eval template

Revision ID: 0012
Revises: 0011
Create Date: 2026-04-25
"""

from __future__ import annotations

import json
from collections.abc import Sequence
from uuid import uuid4

from alembic import op
from sqlalchemy import text

revision: str = "0012"
down_revision: str = "0011"
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None

_TEMPLATE_NAME = "rubric-average"
_PRESET_ID = "rubric-average"

_PROMPT = (
    "You are a strict but fair rubric grader.\n"
    "Score each rubric item independently using the configured numeric score range.\n"
    "Treat the minimum score as not satisfied and the maximum score as fully satisfied.\n"
    "Use the average of all rubric item scores as the final score. "
    "The final score may be a decimal.\n\n"
    "Rubric items:\n{{target}}\n\n"
    "Question or context:\n{{input}}\n\n"
    "Response:\n{{output}}"
)

_OUTPUT_CONFIG = {
    "mode": "llm",
    "numeric_range": {"min": 1, "max": 5, "pass_threshold": 3},
    "score_min": 1,
    "score_max": 5,
    "pass_threshold": 3,
    "score_scale": "raw",
    "reasoning_hint": "Explain the per-rubric scores and the final average",
    "score_hint": "Return the raw average score within the configured range; decimals are allowed",
}


def upgrade() -> None:
    conn = op.get_bind()
    exists = conn.execute(
        text(
            """
            SELECT 1
            FROM eval_templates
            WHERE project_id IS NULL AND name = :name
            LIMIT 1
            """
        ),
        {"name": _TEMPLATE_NAME},
    ).first()
    if exists:
        return

    conn.execute(
        text(
            """
            INSERT INTO eval_templates (
                id, project_id, name, version, prompt, vars, template_type,
                preset_id, output_type, output_config, description
            )
            VALUES (
                :id, NULL, :name, 1, :prompt,
                CAST(:vars AS jsonb), :template_type, :preset_id,
                :output_type, CAST(:output_config AS jsonb), :description
            )
            """
        ),
        {
            "id": str(uuid4()),
            "name": _TEMPLATE_NAME,
            "prompt": _PROMPT,
            "vars": json.dumps(["target", "input", "output"]),
            "template_type": "llm_numeric",
            "preset_id": _PRESET_ID,
            "output_type": "numeric",
            "output_config": json.dumps(_OUTPUT_CONFIG),
            "description": (
                "Built-in rubric average scoring template. Scores each rubric item "
                "within the configured range and reports the average as the final score."
            ),
        },
    )


def downgrade() -> None:
    conn = op.get_bind()
    conn.execute(
        text(
            """
            DELETE FROM eval_templates
            WHERE project_id IS NULL
                AND name = :name
                AND preset_id = :preset_id
            """
        ),
        {"name": _TEMPLATE_NAME, "preset_id": _PRESET_ID},
    )
