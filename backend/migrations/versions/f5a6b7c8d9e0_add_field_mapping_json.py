"""add field_mapping_json to benchmark_definitions

Revision ID: f5a6b7c8d9e0
Revises: e4f5a6b7c8d9
Create Date: 2026-03-27 16:00:00.000000
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "f5a6b7c8d9e0"
down_revision: str = "e4f5a6b7c8d9"
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "benchmark_definitions",
        sa.Column("field_mapping_json", postgresql.JSONB(), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("benchmark_definitions", "field_mapping_json")
