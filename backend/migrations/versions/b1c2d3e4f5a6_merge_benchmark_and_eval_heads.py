"""merge benchmark and eval heads

Revision ID: b1c2d3e4f5a6
Revises: a9b8c7d6e5f4, f9a1b2c3d4e5
Create Date: 2026-03-27 14:00:00.000000
"""

from collections.abc import Sequence

# revision identifiers, used by Alembic.
revision: str = "b1c2d3e4f5a6"
down_revision: tuple[str, str] = ("a9b8c7d6e5f4", "f9a1b2c3d4e5")
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
