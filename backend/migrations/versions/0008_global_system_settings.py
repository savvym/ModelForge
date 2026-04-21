"""add global system settings

Revision ID: 0008
Revises: 0007
Create Date: 2026-04-21
"""

from __future__ import annotations

import json
from collections.abc import Sequence
from uuid import uuid4

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0008"
down_revision: str = "0007"
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None


def _table_exists(table_name: str) -> bool:
    bind = op.get_bind()
    return table_name in sa.inspect(bind).get_table_names()


def _column_exists(table_name: str, column_name: str) -> bool:
    bind = op.get_bind()
    return column_name in {column["name"] for column in sa.inspect(bind).get_columns(table_name)}


def _create_system_settings_table() -> None:
    if _table_exists("system_settings"):
        return

    op.create_table(
        "system_settings",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, default=uuid4),
        sa.Column("key", sa.String(120), nullable=False),
        sa.Column(
            "value_json",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default=sa.text("'{}'::jsonb"),
        ),
        sa.Column("updated_by", postgresql.UUID(as_uuid=True), nullable=True),
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
    op.create_index("ix_system_settings_key", "system_settings", ["key"], unique=True)


def _migrate_project_huggingface_config() -> None:
    if not _column_exists("projects", "integration_config_json"):
        return

    bind = op.get_bind()
    row = (
        bind.execute(
            sa.text(
                """
            SELECT integration_config_json -> 'huggingface' AS value
            FROM projects
            WHERE integration_config_json ? 'huggingface'
            ORDER BY updated_at DESC
            LIMIT 1
            """
            )
        )
        .mappings()
        .first()
    )
    if row is None or row["value"] is None:
        return

    value = row["value"]
    if isinstance(value, str):
        value = json.loads(value)
    if not isinstance(value, dict) or not value:
        return

    bind.execute(
        sa.text(
            """
            INSERT INTO system_settings (id, key, value_json, created_at, updated_at)
            VALUES (:id, 'huggingface', CAST(:value_json AS jsonb), now(), now())
            ON CONFLICT (key)
            DO UPDATE SET value_json = EXCLUDED.value_json, updated_at = now()
            """
        ),
        {"id": str(uuid4()), "value_json": json.dumps(value)},
    )


def upgrade() -> None:
    _create_system_settings_table()
    _migrate_project_huggingface_config()
    if _column_exists("projects", "integration_config_json"):
        op.drop_column("projects", "integration_config_json")


def downgrade() -> None:
    if not _column_exists("projects", "integration_config_json"):
        op.add_column(
            "projects",
            sa.Column(
                "integration_config_json",
                postgresql.JSONB(astext_type=sa.Text()),
                nullable=True,
            ),
        )
    op.execute("DROP TABLE IF EXISTS system_settings")
