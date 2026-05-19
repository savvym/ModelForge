"""drop legacy lake/bronze tables and add lake_repos

Revision ID: 0014
Revises: 0013
Create Date: 2026-05-19
"""

from __future__ import annotations

from collections.abc import Sequence
from uuid import uuid4

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0014"
down_revision: str = "0013"
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None


def upgrade() -> None:
    op.drop_index("ix_lake_assets_project_stage", table_name="lake_assets")
    op.drop_index("ix_lake_assets_batch_created", table_name="lake_assets")
    op.drop_table("lake_assets")
    op.drop_table("lake_batches")

    op.create_table(
        "lake_repos",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, default=uuid4),
        sa.Column(
            "project_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("projects.id", ondelete="CASCADE"),
            nullable=False,
            index=True,
        ),
        sa.Column("name", sa.String(64), nullable=False),
        sa.Column("display_name", sa.String(255), nullable=False),
        sa.Column("description", sa.Text, nullable=True),
        sa.Column("gitea_org", sa.String(64), nullable=False),
        sa.Column("gitea_repo", sa.String(64), nullable=False),
        sa.Column("default_branch", sa.String(64), nullable=False, server_default="main"),
        sa.Column("visibility", sa.String(16), nullable=False, server_default="private"),
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
        sa.UniqueConstraint("project_id", "name", name="uq_lake_repos_project_name"),
    )
    op.create_index("ix_lake_repos_gitea", "lake_repos", ["gitea_org", "gitea_repo"])


def downgrade() -> None:
    op.drop_index("ix_lake_repos_gitea", table_name="lake_repos")
    op.drop_table("lake_repos")

    op.create_table(
        "lake_batches",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, default=uuid4),
        sa.Column(
            "project_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("projects.id", ondelete="CASCADE"),
            nullable=False,
            index=True,
        ),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("description", sa.Text, nullable=True),
        sa.Column("source_type", sa.String(64), nullable=False, server_default="upload"),
        sa.Column("resource_type", sa.String(64), nullable=True),
        sa.Column("stage", sa.String(32), nullable=False, server_default="raw"),
        sa.Column("planned_file_count", sa.Integer, nullable=False, server_default="1"),
        sa.Column("completed_file_count", sa.Integer, nullable=False, server_default="0"),
        sa.Column("failed_file_count", sa.Integer, nullable=False, server_default="0"),
        sa.Column("total_size_bytes", sa.BigInteger, nullable=False, server_default="0"),
        sa.Column("tags", postgresql.JSONB, nullable=False, server_default="[]"),
        sa.Column("metadata", postgresql.JSONB, nullable=False, server_default="{}"),
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
    op.create_table(
        "lake_assets",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, default=uuid4),
        sa.Column(
            "project_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("projects.id", ondelete="CASCADE"),
            nullable=False,
            index=True,
        ),
        sa.Column(
            "batch_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("lake_batches.id", ondelete="CASCADE"),
            nullable=False,
            index=True,
        ),
        sa.Column(
            "parent_asset_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("lake_assets.id", ondelete="SET NULL"),
            nullable=True,
            index=True,
        ),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("description", sa.Text, nullable=True),
        sa.Column("stage", sa.String(32), nullable=False, server_default="raw"),
        sa.Column("source_type", sa.String(64), nullable=False, server_default="upload"),
        sa.Column("resource_type", sa.String(64), nullable=True),
        sa.Column("format", sa.String(64), nullable=True),
        sa.Column("mime_type", sa.String(120), nullable=True),
        sa.Column("relative_path", sa.Text, nullable=True),
        sa.Column("object_key", sa.Text, nullable=True),
        sa.Column("source_uri", sa.Text, nullable=True),
        sa.Column("size_bytes", sa.BigInteger, nullable=True),
        sa.Column("etag", sa.String(128), nullable=True),
        sa.Column("checksum", sa.String(128), nullable=True),
        sa.Column("record_count", sa.BigInteger, nullable=True),
        sa.Column("tags", postgresql.JSONB, nullable=False, server_default="[]"),
        sa.Column("metadata", postgresql.JSONB, nullable=False, server_default="{}"),
        sa.Column("error_message", sa.Text, nullable=True),
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
    op.create_index("ix_lake_assets_project_stage", "lake_assets", ["project_id", "stage"])
    op.create_index("ix_lake_assets_batch_created", "lake_assets", ["batch_id", "created_at"])
