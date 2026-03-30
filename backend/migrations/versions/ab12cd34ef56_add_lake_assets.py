"""add lake assets

Revision ID: ab12cd34ef56
Revises: f7a8c9d0e1f2
Create Date: 2026-03-26 22:40:00.000000
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = "ab12cd34ef56"
down_revision = "f7a8c9d0e1f2"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "lake_batches",
        sa.Column("project_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("source_type", sa.String(length=64), nullable=False, server_default="upload"),
        sa.Column("resource_type", sa.String(length=64), nullable=True),
        sa.Column("stage", sa.String(length=32), nullable=False, server_default="raw"),
        sa.Column("planned_file_count", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("completed_file_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("failed_file_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("total_size_bytes", sa.BigInteger(), nullable=False, server_default="0"),
        sa.Column(
            "tags",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default=sa.text("'[]'::jsonb"),
        ),
        sa.Column(
            "metadata",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default=sa.text("'{}'::jsonb"),
        ),
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("created_by", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("status", sa.String(length=32), nullable=False, server_default="uploading"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["project_id"], ["projects.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_lake_batches")),
    )
    op.create_index(op.f("ix_lake_batches_project_id"), "lake_batches", ["project_id"], unique=False)
    op.alter_column("lake_batches", "source_type", server_default=None)
    op.alter_column("lake_batches", "stage", server_default=None)
    op.alter_column("lake_batches", "planned_file_count", server_default=None)
    op.alter_column("lake_batches", "completed_file_count", server_default=None)
    op.alter_column("lake_batches", "failed_file_count", server_default=None)
    op.alter_column("lake_batches", "total_size_bytes", server_default=None)
    op.alter_column("lake_batches", "tags", server_default=None)
    op.alter_column("lake_batches", "metadata", server_default=None)
    op.alter_column("lake_batches", "status", server_default=None)

    op.create_table(
        "lake_assets",
        sa.Column("project_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("batch_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("parent_asset_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("stage", sa.String(length=32), nullable=False, server_default="raw"),
        sa.Column("source_type", sa.String(length=64), nullable=False, server_default="upload"),
        sa.Column("resource_type", sa.String(length=64), nullable=True),
        sa.Column("format", sa.String(length=64), nullable=True),
        sa.Column("mime_type", sa.String(length=120), nullable=True),
        sa.Column("relative_path", sa.Text(), nullable=True),
        sa.Column("object_key", sa.Text(), nullable=True),
        sa.Column("source_uri", sa.Text(), nullable=True),
        sa.Column("size_bytes", sa.BigInteger(), nullable=True),
        sa.Column("etag", sa.String(length=128), nullable=True),
        sa.Column("checksum", sa.String(length=128), nullable=True),
        sa.Column("record_count", sa.BigInteger(), nullable=True),
        sa.Column(
            "tags",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default=sa.text("'[]'::jsonb"),
        ),
        sa.Column(
            "metadata",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default=sa.text("'{}'::jsonb"),
        ),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("created_by", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("status", sa.String(length=32), nullable=False, server_default="uploading"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["batch_id"], ["lake_batches.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["parent_asset_id"], ["lake_assets.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["project_id"], ["projects.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_lake_assets")),
    )
    op.create_index(op.f("ix_lake_assets_batch_id"), "lake_assets", ["batch_id"], unique=False)
    op.create_index(op.f("ix_lake_assets_parent_asset_id"), "lake_assets", ["parent_asset_id"], unique=False)
    op.create_index(op.f("ix_lake_assets_project_id"), "lake_assets", ["project_id"], unique=False)
    op.create_index("ix_lake_assets_project_stage", "lake_assets", ["project_id", "stage"], unique=False)
    op.create_index("ix_lake_assets_batch_created", "lake_assets", ["batch_id", "created_at"], unique=False)
    op.alter_column("lake_assets", "stage", server_default=None)
    op.alter_column("lake_assets", "source_type", server_default=None)
    op.alter_column("lake_assets", "tags", server_default=None)
    op.alter_column("lake_assets", "metadata", server_default=None)
    op.alter_column("lake_assets", "status", server_default=None)


def downgrade() -> None:
    op.drop_index("ix_lake_assets_batch_created", table_name="lake_assets")
    op.drop_index("ix_lake_assets_project_stage", table_name="lake_assets")
    op.drop_index(op.f("ix_lake_assets_project_id"), table_name="lake_assets")
    op.drop_index(op.f("ix_lake_assets_parent_asset_id"), table_name="lake_assets")
    op.drop_index(op.f("ix_lake_assets_batch_id"), table_name="lake_assets")
    op.drop_table("lake_assets")

    op.drop_index(op.f("ix_lake_batches_project_id"), table_name="lake_batches")
    op.drop_table("lake_batches")
