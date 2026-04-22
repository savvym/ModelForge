"""drop legacy eval job tables

Revision ID: 0010
Revises: 0009
Create Date: 2026-04-22
"""

from __future__ import annotations

from collections.abc import Sequence

from alembic import op

revision: str = "0010"
down_revision: str = "0009"
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None


def upgrade() -> None:
    op.execute("DROP TABLE IF EXISTS benchmark_leaderboard_jobs CASCADE")
    op.execute("DROP TABLE IF EXISTS benchmark_leaderboards CASCADE")
    op.execute("DROP TABLE IF EXISTS eval_job_metrics CASCADE")
    op.execute("DROP TABLE IF EXISTS eval_jobs CASCADE")


def downgrade() -> None:
    raise NotImplementedError("Legacy Eval Job tables cannot be restored by downgrade.")
