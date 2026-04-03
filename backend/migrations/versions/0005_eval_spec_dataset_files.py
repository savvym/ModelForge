"""add eval spec dataset files

Revision ID: 0005
Revises: 0004
Create Date: 2026-04-03
"""

from __future__ import annotations

from collections.abc import Sequence
from pathlib import PurePosixPath
from uuid import UUID, uuid4

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0005"
down_revision: str = "0004"
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "eval_spec_dataset_files",
        sa.Column("spec_version_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("file_key", sa.String(length=120), nullable=False),
        sa.Column("display_name", sa.String(length=255), nullable=False),
        sa.Column("role", sa.String(length=64), nullable=False, server_default="dataset"),
        sa.Column("position", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("file_name", sa.String(length=255), nullable=True),
        sa.Column("format", sa.String(length=64), nullable=True),
        sa.Column("source_uri", sa.Text(), nullable=True),
        sa.Column("object_key", sa.Text(), nullable=True),
        sa.Column("content_type", sa.String(length=120), nullable=True),
        sa.Column("size_bytes", sa.BigInteger(), nullable=True),
        sa.Column("is_required", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("status", sa.String(length=32), nullable=False, server_default="missing"),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("last_synced_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["spec_version_id"], ["eval_spec_versions.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("spec_version_id", "file_key"),
    )
    op.create_index(
        "ix_eval_spec_dataset_files_spec_version_id",
        "eval_spec_dataset_files",
        ["spec_version_id"],
        unique=False,
    )
    op.create_index(
        "ix_eval_spec_dataset_files_status",
        "eval_spec_dataset_files",
        ["status"],
        unique=False,
    )

    conn = op.get_bind()
    rows = conn.execute(
        sa.text(
            """
            SELECT
              sv.id AS version_id,
              s.name AS spec_name,
              sv.version AS version_name,
              sv.engine_benchmark_name AS benchmark_name,
              sv.dataset_source_uri AS dataset_source_uri
            FROM eval_spec_versions sv
            JOIN eval_specs s ON s.id = sv.spec_id
            """
        )
    ).mappings()

    dataset_files = sa.table(
        "eval_spec_dataset_files",
        sa.column("id", postgresql.UUID(as_uuid=True)),
        sa.column("spec_version_id", postgresql.UUID(as_uuid=True)),
        sa.column("file_key", sa.String),
        sa.column("display_name", sa.String),
        sa.column("role", sa.String),
        sa.column("position", sa.Integer),
        sa.column("file_name", sa.String),
        sa.column("format", sa.String),
        sa.column("source_uri", sa.Text),
        sa.column("object_key", sa.Text),
        sa.column("content_type", sa.String),
        sa.column("size_bytes", sa.BigInteger),
        sa.column("is_required", sa.Boolean),
        sa.column("status", sa.String),
        sa.column("error_message", sa.Text),
        sa.column("last_synced_at", sa.DateTime(timezone=True)),
    )

    insert_rows: list[dict[str, object]] = []
    for row in rows:
        version_id = row["version_id"]
        source_uri = (row["dataset_source_uri"] or "").strip() or None
        benchmark_name = (row["benchmark_name"] or "").strip() or None
        if source_uri:
            insert_rows.append(
                {
                    "id": uuid4(),
                    "spec_version_id": version_id,
                    "file_key": "primary-dataset",
                    "display_name": "主数据集",
                    "role": "dataset",
                    "position": 0,
                    "file_name": _guess_file_name(source_uri, fallback_name="dataset.bin"),
                    "format": _guess_format(source_uri),
                    "source_uri": source_uri,
                    "object_key": None,
                    "content_type": None,
                    "size_bytes": None,
                    "is_required": True,
                    "status": "external" if source_uri.startswith("evalscope://") else "missing",
                    "error_message": None,
                    "last_synced_at": None,
                }
            )
            continue
        if benchmark_name:
            builtin_uri = f"evalscope://builtin/{benchmark_name}"
            insert_rows.append(
                {
                    "id": uuid4(),
                    "spec_version_id": version_id,
                    "file_key": "builtin-dataset",
                    "display_name": "内置数据集",
                    "role": "dataset",
                    "position": 0,
                    "file_name": f"{benchmark_name}.builtin",
                    "format": "evalscope-builtin",
                    "source_uri": builtin_uri,
                    "object_key": None,
                    "content_type": None,
                    "size_bytes": None,
                    "is_required": True,
                    "status": "external",
                    "error_message": None,
                    "last_synced_at": None,
                }
            )
            conn.execute(
                sa.text(
                    "UPDATE eval_spec_versions SET dataset_source_uri = :dataset_source_uri WHERE id = :version_id"
                ),
                {"dataset_source_uri": builtin_uri, "version_id": version_id},
            )

    if insert_rows:
        op.bulk_insert(dataset_files, insert_rows)


def downgrade() -> None:
    conn = op.get_bind()
    conn.execute(
        sa.text(
            """
            UPDATE eval_spec_versions
            SET dataset_source_uri = NULL
            WHERE dataset_source_uri LIKE 'evalscope://builtin/%'
            """
        )
    )
    op.drop_index("ix_eval_spec_dataset_files_status", table_name="eval_spec_dataset_files")
    op.drop_index("ix_eval_spec_dataset_files_spec_version_id", table_name="eval_spec_dataset_files")
    op.drop_table("eval_spec_dataset_files")


def _guess_file_name(source_uri: str, *, fallback_name: str) -> str:
    name = PurePosixPath(source_uri.replace("\\", "/")).name
    return name or fallback_name


def _guess_format(source_uri: str) -> str | None:
    name = _guess_file_name(source_uri, fallback_name="")
    suffix = PurePosixPath(name).suffix.lstrip(".")
    return suffix or None
