"""add eval_templates table and FK columns

Revision ID: 0002
Revises: 0001
Create Date: 2026-03-30
"""

from __future__ import annotations

import json
from collections.abc import Sequence
from uuid import uuid4

import sqlalchemy as sa
from alembic import op
from sqlalchemy import text
from sqlalchemy.dialects import postgresql

revision: str = "0002"
down_revision: str = "0001"
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "eval_templates",
        sa.Column("id", sa.dialects.postgresql.UUID(as_uuid=True), primary_key=True, default=uuid4),
        sa.Column("project_id", sa.dialects.postgresql.UUID(as_uuid=True), sa.ForeignKey("projects.id", ondelete="CASCADE"), nullable=True, index=True),
        sa.Column("name", sa.String(120), nullable=False),
        sa.Column("version", sa.Integer, nullable=False, server_default="1"),
        sa.Column("prompt", sa.Text, nullable=False),
        sa.Column("vars", postgresql.JSONB, nullable=False, server_default="[]"),
        sa.Column("output_type", sa.String(32), nullable=False, server_default="numeric"),
        sa.Column("output_config", postgresql.JSONB, nullable=False, server_default="{}"),
        sa.Column("model", sa.String(255), nullable=True),
        sa.Column("provider", sa.String(120), nullable=True),
        sa.Column("model_params", postgresql.JSONB, nullable=True),
        sa.Column("description", sa.Text, nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.UniqueConstraint("project_id", "name", "version"),
    )
    op.create_index("ix_eval_templates_name", "eval_templates", ["name"])

    # benchmark_definitions: add eval_template_id
    op.add_column(
        "benchmark_definitions",
        sa.Column(
            "eval_template_id",
            sa.dialects.postgresql.UUID(as_uuid=True),
            sa.ForeignKey("eval_templates.id", ondelete="SET NULL"),
            nullable=True,
        ),
    )

    # eval_jobs: add template tracking columns
    op.add_column(
        "eval_jobs",
        sa.Column("eval_template_id", sa.dialects.postgresql.UUID(as_uuid=True), nullable=True),
    )
    op.add_column(
        "eval_jobs",
        sa.Column("eval_template_version", sa.Integer, nullable=True),
    )

    # Seed builtin templates (project_id = NULL = global)
    _seed_builtin_templates()


def _seed_builtin_templates() -> None:
    conn = op.get_bind()

    rubric_id = str(uuid4())
    conn.execute(
        text("""
            INSERT INTO eval_templates (id, project_id, name, version, prompt, vars, output_type, output_config, description)
            VALUES (
                :id, NULL, :name, 1, :prompt,
                CAST(:vars AS jsonb), :output_type, CAST(:output_config AS jsonb), :description
            )
        """),
        {
            "id": rubric_id,
            "name": "rubric-grading",
            "prompt": (
                "You are a strict grader.\n"
                "Score the response against every rubric item using all-or-nothing grading.\n"
                "If any single rubric item is not fully satisfied, the overall score must be false.\n"
                "Return only valid JSON.\n\n"
                "Rubrics:\n{{target}}\n\n"
                "Response:\n{{output}}\n\n"
                "Return exactly this JSON schema:\n"
                '{"reasoning": "string", "score": true or false}'
            ),
            "vars": json.dumps(["target", "output"]),
            "output_type": "boolean",
            "output_config": json.dumps({
                "reasoning_hint": "Explain whether each rubric item is satisfied",
                "score_hint": "true if all rubric items are satisfied, false otherwise",
            }),
            "description": "Built-in rubric-based grading template. Checks each rubric item and returns pass/fail.",
        },
    )

    quality_id = str(uuid4())
    conn.execute(
        text("""
            INSERT INTO eval_templates (id, project_id, name, version, prompt, vars, output_type, output_config, description)
            VALUES (
                :id, NULL, :name, 1, :prompt,
                CAST(:vars AS jsonb), :output_type, CAST(:output_config AS jsonb), :description
            )
        """),
        {
            "id": quality_id,
            "name": "quality-scoring",
            "prompt": (
                "You are an expert evaluator.\n"
                "Evaluate the quality of the following response to the given question.\n"
                "Score from 1 to 5 where:\n"
                "  1 = completely wrong or irrelevant\n"
                "  2 = mostly wrong with minor correct elements\n"
                "  3 = partially correct but incomplete\n"
                "  4 = mostly correct with minor issues\n"
                "  5 = fully correct, complete, and well-articulated\n\n"
                "Question:\n{{input}}\n\n"
                "Response:\n{{output}}\n\n"
                "Return only valid JSON:\n"
                '{"reasoning": "string", "score": <integer 1-5>}'
            ),
            "vars": json.dumps(["input", "output"]),
            "output_type": "numeric",
            "output_config": json.dumps({
                "score_min": 1,
                "score_max": 5,
                "pass_threshold": 3,
                "reasoning_hint": "Explain your reasoning",
                "score_hint": "Rate 1-5",
            }),
            "description": "Built-in quality scoring template. Rates response quality on a 1-5 scale.",
        },
    )


def downgrade() -> None:
    op.drop_column("eval_jobs", "eval_template_version")
    op.drop_column("eval_jobs", "eval_template_id")
    op.drop_column("benchmark_definitions", "eval_template_id")
    op.drop_index("ix_eval_templates_name", table_name="eval_templates")
    op.drop_table("eval_templates")
