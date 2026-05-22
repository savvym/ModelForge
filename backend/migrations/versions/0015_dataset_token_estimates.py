"""add dataset token estimates

Revision ID: 0015
Revises: 0014
Create Date: 2026-05-21
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0015"
down_revision: str = "0014"
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("dataset_versions", sa.Column("token_count", sa.BigInteger(), nullable=True))
    op.add_column("dataset_versions", sa.Column("tokenizer_name", sa.String(64), nullable=True))


def downgrade() -> None:
    op.drop_column("dataset_versions", "tokenizer_name")
    op.drop_column("dataset_versions", "token_count")
