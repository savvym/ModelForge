"""add benchmark leaderboards

Revision ID: 0005
Revises: 0004
Create Date: 2026-03-30
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0005"
down_revision: str = "0004"
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None


def upgrade() -> None:
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


def downgrade() -> None:
    op.drop_index(op.f("ix_benchmark_leaderboard_jobs_eval_job_id"), table_name="benchmark_leaderboard_jobs")
    op.drop_index(op.f("ix_benchmark_leaderboard_jobs_leaderboard_id"), table_name="benchmark_leaderboard_jobs")
    op.drop_table("benchmark_leaderboard_jobs")

    op.drop_index(op.f("ix_benchmark_leaderboards_benchmark_version_row_id"), table_name="benchmark_leaderboards")
    op.drop_index(op.f("ix_benchmark_leaderboards_benchmark_id"), table_name="benchmark_leaderboards")
    op.drop_index(op.f("ix_benchmark_leaderboards_project_id"), table_name="benchmark_leaderboards")
    op.drop_table("benchmark_leaderboards")
