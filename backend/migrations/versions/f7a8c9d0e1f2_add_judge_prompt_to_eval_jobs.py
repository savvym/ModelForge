"""add judge prompt to eval jobs

Revision ID: f7a8c9d0e1f2
Revises: e4f6c9a1d2b3
Create Date: 2026-03-23 16:40:00.000000
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "f7a8c9d0e1f2"
down_revision = "e4f6c9a1d2b3"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("eval_jobs", sa.Column("judge_prompt_text", sa.Text(), nullable=True))


def downgrade() -> None:
    op.drop_column("eval_jobs", "judge_prompt_text")
