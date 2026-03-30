"""expand dataset schema

Revision ID: d3d1f8a1b4c2
Revises: 6b98732bbb08
Create Date: 2026-03-21 18:05:00.000000
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = "d3d1f8a1b4c2"
down_revision = "6b98732bbb08"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("datasets", sa.Column("use_case", sa.String(length=64), nullable=True))
    op.add_column("datasets", sa.Column("modality", sa.String(length=32), nullable=True))
    op.add_column("datasets", sa.Column("recipe", sa.String(length=64), nullable=True))
    op.add_column(
        "datasets",
        sa.Column(
            "scope",
            sa.String(length=32),
            nullable=False,
            server_default="my-datasets",
        ),
    )
    op.add_column("datasets", sa.Column("source_type", sa.String(length=32), nullable=True))
    op.add_column("datasets", sa.Column("source_uri", sa.Text(), nullable=True))
    op.add_column("datasets", sa.Column("owner_name", sa.String(length=120), nullable=True))
    op.add_column(
        "datasets",
        sa.Column(
            "tags",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default=sa.text("'[]'::jsonb"),
        ),
    )
    op.alter_column("datasets", "scope", server_default=None)
    op.alter_column("datasets", "tags", server_default=None)

    op.add_column("dataset_versions", sa.Column("description", sa.Text(), nullable=True))
    op.add_column("dataset_versions", sa.Column("format", sa.String(length=32), nullable=True))
    op.add_column("dataset_versions", sa.Column("source_uri", sa.Text(), nullable=True))


def downgrade() -> None:
    op.drop_column("dataset_versions", "source_uri")
    op.drop_column("dataset_versions", "format")
    op.drop_column("dataset_versions", "description")

    op.drop_column("datasets", "tags")
    op.drop_column("datasets", "owner_name")
    op.drop_column("datasets", "source_uri")
    op.drop_column("datasets", "source_type")
    op.drop_column("datasets", "scope")
    op.drop_column("datasets", "recipe")
    op.drop_column("datasets", "modality")
    op.drop_column("datasets", "use_case")
