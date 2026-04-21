"""reserve revision 0007

Revision ID: 0007
Revises: 0006
Create Date: 2026-04-21
"""

from __future__ import annotations

from collections.abc import Sequence

revision: str = "0007"
down_revision: str = "0006"
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
