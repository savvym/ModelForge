"""add template_type and preset_id to eval_templates

Revision ID: 0003
Revises: 0002
Create Date: 2026-03-30
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy import text

revision: str = "0003"
down_revision: str = "0002"
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "eval_templates",
        sa.Column("template_type", sa.String(length=64), nullable=False, server_default="llm_numeric"),
    )
    op.add_column(
        "eval_templates",
        sa.Column("preset_id", sa.String(length=120), nullable=True),
    )

    conn = op.get_bind()
    conn.execute(
        text(
            """
            UPDATE eval_templates
            SET
                template_type = CASE
                    WHEN name = 'quality-scoring' THEN 'llm_numeric'
                    WHEN name IN ('rubric-grading', 'relevance-check', 'correctness-category') THEN 'llm_categorical'
                    WHEN output_type = 'numeric' THEN 'llm_numeric'
                    WHEN output_type IN ('boolean', 'categorical') THEN 'llm_categorical'
                    ELSE 'llm_numeric'
                END,
                preset_id = CASE
                    WHEN name = 'quality-scoring' THEN 'quality-score-1-5'
                    WHEN name = 'rubric-grading' THEN 'rubric-check'
                    WHEN name = 'relevance-check' THEN 'relevance-check'
                    WHEN name = 'correctness-category' THEN 'correctness-category'
                    ELSE preset_id
                END
            """
        )
    )

    op.alter_column("eval_templates", "template_type", server_default=None)


def downgrade() -> None:
    op.drop_column("eval_templates", "preset_id")
    op.drop_column("eval_templates", "template_type")
