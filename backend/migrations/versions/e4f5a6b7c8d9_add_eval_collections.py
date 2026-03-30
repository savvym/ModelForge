"""add eval collections table and collection_id to eval_jobs

Revision ID: e4f5a6b7c8d9
Revises: d3e4f5a6b7c8
Create Date: 2026-03-27 15:00:00.000000
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "e4f5a6b7c8d9"
down_revision: str = "d3e4f5a6b7c8"
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "eval_collections",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("project_id", sa.Uuid(), nullable=False),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("schema_json", postgresql.JSONB(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_eval_collections")),
        sa.ForeignKeyConstraint(
            ["project_id"],
            ["projects.id"],
            name=op.f("fk_eval_collections_project_id_projects"),
            ondelete="CASCADE",
        ),
    )
    op.create_index(
        op.f("ix_eval_collections_project_id"),
        "eval_collections",
        ["project_id"],
    )

    op.add_column(
        "eval_jobs",
        sa.Column("collection_id", sa.Uuid(), nullable=True),
    )
    op.create_foreign_key(
        op.f("fk_eval_jobs_collection_id_eval_collections"),
        "eval_jobs",
        "eval_collections",
        ["collection_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.create_index(
        op.f("ix_eval_jobs_collection_id"),
        "eval_jobs",
        ["collection_id"],
    )


def downgrade() -> None:
    op.drop_index(op.f("ix_eval_jobs_collection_id"), table_name="eval_jobs")
    op.drop_constraint(
        op.f("fk_eval_jobs_collection_id_eval_collections"),
        "eval_jobs",
        type_="foreignkey",
    )
    op.drop_column("eval_jobs", "collection_id")
    op.drop_index(
        op.f("ix_eval_collections_project_id"),
        table_name="eval_collections",
    )
    op.drop_table("eval_collections")
