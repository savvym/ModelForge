"""add evaluation v2 leaderboards

Revision ID: 0004
Revises: 0003
Create Date: 2026-04-03
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0004"
down_revision: str = "0003"
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "evaluation_leaderboards",
        sa.Column("project_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("name", sa.String(length=120), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("target_kind", sa.String(length=16), nullable=False),
        sa.Column("source_spec_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("source_spec_version_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("source_suite_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("source_suite_version_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("score_metric_name", sa.String(length=120), nullable=False, server_default="score"),
        sa.Column("score_metric_scope", sa.String(length=32), nullable=False, server_default="overall"),
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["project_id"], ["projects.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["source_spec_id"], ["eval_specs.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["source_spec_version_id"], ["eval_spec_versions.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["source_suite_id"], ["eval_suites.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["source_suite_version_id"], ["eval_suite_versions.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("project_id", "name"),
    )
    op.create_index("ix_evaluation_leaderboards_project_id", "evaluation_leaderboards", ["project_id"], unique=False)

    op.create_table(
        "evaluation_leaderboard_runs",
        sa.Column("leaderboard_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("run_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["leaderboard_id"], ["evaluation_leaderboards.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["run_id"], ["evaluation_runs.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("leaderboard_id", "run_id"),
    )
    op.create_index("ix_evaluation_leaderboard_runs_leaderboard_id", "evaluation_leaderboard_runs", ["leaderboard_id"], unique=False)
    op.create_index("ix_evaluation_leaderboard_runs_run_id", "evaluation_leaderboard_runs", ["run_id"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_evaluation_leaderboard_runs_run_id", table_name="evaluation_leaderboard_runs")
    op.drop_index("ix_evaluation_leaderboard_runs_leaderboard_id", table_name="evaluation_leaderboard_runs")
    op.drop_table("evaluation_leaderboard_runs")

    op.drop_index("ix_evaluation_leaderboards_project_id", table_name="evaluation_leaderboards")
    op.drop_table("evaluation_leaderboards")
