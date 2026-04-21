"""add inference machines

Revision ID: 0009
Revises: 0008
Create Date: 2026-04-21
"""

from __future__ import annotations

from collections.abc import Sequence
from uuid import uuid4

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0009"
down_revision: str = "0008"
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "inference_machines",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, default=uuid4),
        sa.Column(
            "project_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("projects.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("name", sa.String(120), nullable=False),
        sa.Column("agent_base_url", sa.Text(), nullable=False),
        sa.Column("agent_token", sa.Text(), nullable=True),
        sa.Column("runtime_public_host", sa.String(255), nullable=True),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("config_json", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("created_by", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("status", sa.String(32), nullable=False, server_default="active"),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
    )
    op.create_index(
        "ix_inference_machines_project_id",
        "inference_machines",
        ["project_id"],
    )
    op.create_index(
        "ix_inference_machines_project_name",
        "inference_machines",
        ["project_id", "name"],
        unique=True,
    )


def downgrade() -> None:
    op.drop_index("ix_inference_machines_project_name", table_name="inference_machines")
    op.drop_index("ix_inference_machines_project_id", table_name="inference_machines")
    op.drop_table("inference_machines")
