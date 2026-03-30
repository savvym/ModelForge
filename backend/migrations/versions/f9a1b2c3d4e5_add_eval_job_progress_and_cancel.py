"""add eval job progress and cancel fields

Revision ID: f9a1b2c3d4e5
Revises: f7a8c9d0e1f2
Create Date: 2026-03-27 00:56:00.000000
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "f9a1b2c3d4e5"
down_revision: str | None = "f7a8c9d0e1f2"
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("eval_jobs", sa.Column("progress_total", sa.BigInteger(), nullable=True))
    op.add_column("eval_jobs", sa.Column("progress_done", sa.BigInteger(), nullable=True))
    op.add_column(
        "eval_jobs",
        sa.Column(
            "cancel_requested",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("false"),
        ),
    )


def downgrade() -> None:
    op.drop_column("eval_jobs", "cancel_requested")
    op.drop_column("eval_jobs", "progress_done")
    op.drop_column("eval_jobs", "progress_total")
