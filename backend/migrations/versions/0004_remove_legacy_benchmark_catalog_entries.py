"""remove legacy benchmark catalog entries

Revision ID: 0004
Revises: 0003
Create Date: 2026-03-30
"""

from __future__ import annotations

from collections.abc import Sequence

from alembic import op
from sqlalchemy import text

revision: str = "0004"
down_revision: str = "0003"
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None


def upgrade() -> None:
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
    # Irreversible data cleanup.
    pass
