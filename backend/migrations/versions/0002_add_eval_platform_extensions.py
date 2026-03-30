"""add eval platform extensions – squashed from 4 migrations

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
        sa.Column(
            "project_id",
            sa.dialects.postgresql.UUID(as_uuid=True),
            sa.ForeignKey("projects.id", ondelete="CASCADE"),
            nullable=True,
            index=True,
        ),
        sa.Column("name", sa.String(120), nullable=False),
        sa.Column("version", sa.Integer, nullable=False, server_default="1"),
        sa.Column("prompt", sa.Text, nullable=False),
        sa.Column("vars", postgresql.JSONB, nullable=False, server_default="[]"),
        sa.Column("template_type", sa.String(64), nullable=False, server_default="llm_numeric"),
        sa.Column("preset_id", sa.String(120), nullable=True),
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

    op.add_column(
        "benchmark_definitions",
        sa.Column(
            "eval_template_id",
            sa.dialects.postgresql.UUID(as_uuid=True),
            sa.ForeignKey("eval_templates.id", ondelete="SET NULL"),
            nullable=True,
        ),
    )
    op.add_column(
        "eval_jobs",
        sa.Column("eval_template_id", sa.dialects.postgresql.UUID(as_uuid=True), nullable=True),
    )
    op.add_column(
        "eval_jobs",
        sa.Column("eval_template_version", sa.Integer, nullable=True),
    )

    op.create_table(
        "benchmark_leaderboards",
        sa.Column("project_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("name", sa.String(length=120), nullable=False),
        sa.Column("benchmark_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("benchmark_version_row_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["benchmark_id"], ["benchmark_definitions.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["benchmark_version_row_id"], ["benchmark_versions.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["project_id"], ["projects.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_benchmark_leaderboards")),
        sa.UniqueConstraint("project_id", "name", name=op.f("uq_benchmark_leaderboards_project_id")),
    )
    op.create_index(
        op.f("ix_benchmark_leaderboards_project_id"),
        "benchmark_leaderboards",
        ["project_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_benchmark_leaderboards_benchmark_id"),
        "benchmark_leaderboards",
        ["benchmark_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_benchmark_leaderboards_benchmark_version_row_id"),
        "benchmark_leaderboards",
        ["benchmark_version_row_id"],
        unique=False,
    )

    op.create_table(
        "benchmark_leaderboard_jobs",
        sa.Column("leaderboard_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("eval_job_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["eval_job_id"], ["eval_jobs.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["leaderboard_id"], ["benchmark_leaderboards.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_benchmark_leaderboard_jobs")),
        sa.UniqueConstraint("leaderboard_id", "eval_job_id", name=op.f("uq_benchmark_leaderboard_jobs_leaderboard_id")),
    )
    op.create_index(
        op.f("ix_benchmark_leaderboard_jobs_leaderboard_id"),
        "benchmark_leaderboard_jobs",
        ["leaderboard_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_benchmark_leaderboard_jobs_eval_job_id"),
        "benchmark_leaderboard_jobs",
        ["eval_job_id"],
        unique=False,
    )

    _seed_builtin_templates()
    _remove_legacy_benchmark_catalog_entries()


def _seed_builtin_templates() -> None:
    conn = op.get_bind()

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
            "template_type": "llm_categorical",
            "preset_id": "rubric-check",
            "output_type": "boolean",
            "output_config": json.dumps(
                {
                    "reasoning_hint": "Explain whether each rubric item is satisfied",
                    "score_hint": "true if all rubric items are satisfied, false otherwise",
                }
            ),
            "description": "Built-in rubric-based grading template. Checks each rubric item and returns pass/fail.",
        },
    )

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
            "template_type": "llm_numeric",
            "preset_id": "quality-score-1-5",
            "output_type": "numeric",
            "output_config": json.dumps(
                {
                    "score_min": 1,
                    "score_max": 5,
                    "pass_threshold": 3,
                    "reasoning_hint": "Explain your reasoning",
                    "score_hint": "Rate 1-5",
                }
            ),
            "description": "Built-in quality scoring template. Rates response quality on a 1-5 scale.",
        },
    )


def _remove_legacy_benchmark_catalog_entries() -> None:
    conn = op.get_bind()
    conn.execute(
        text(
            """
            DELETE FROM benchmark_definitions
            WHERE COALESCE(source_type, 'builtin') <> 'custom'
            """
        )
    )


def downgrade() -> None:
    op.drop_index(op.f("ix_benchmark_leaderboard_jobs_eval_job_id"), table_name="benchmark_leaderboard_jobs")
    op.drop_index(op.f("ix_benchmark_leaderboard_jobs_leaderboard_id"), table_name="benchmark_leaderboard_jobs")
    op.drop_table("benchmark_leaderboard_jobs")

    op.drop_index(op.f("ix_benchmark_leaderboards_benchmark_version_row_id"), table_name="benchmark_leaderboards")
    op.drop_index(op.f("ix_benchmark_leaderboards_benchmark_id"), table_name="benchmark_leaderboards")
    op.drop_index(op.f("ix_benchmark_leaderboards_project_id"), table_name="benchmark_leaderboards")
    op.drop_table("benchmark_leaderboards")

    op.drop_column("eval_jobs", "eval_template_version")
    op.drop_column("eval_jobs", "eval_template_id")
    op.drop_column("benchmark_definitions", "eval_template_id")
    op.drop_index("ix_eval_templates_name", table_name="eval_templates")
    op.drop_table("eval_templates")

    # Builtin benchmark cleanup is intentionally not reversed.
