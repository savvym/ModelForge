"""create probe system tables

Revision ID: 0006
Revises: 0005
Create Date: 2026-04-09
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0006"
down_revision: str = "0005"
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "probes",
        sa.Column("project_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("name", sa.String(length=120), nullable=False),
        sa.Column("display_name", sa.String(length=255), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False, server_default="offline"),
        sa.Column("ip_address", sa.String(length=64), nullable=True),
        sa.Column("isp", sa.String(length=120), nullable=True),
        sa.Column("asn", sa.Integer(), nullable=True),
        sa.Column("region", sa.String(length=64), nullable=True),
        sa.Column("country", sa.String(length=8), nullable=True),
        sa.Column("city", sa.String(length=120), nullable=True),
        sa.Column("network_type", sa.String(length=32), nullable=False, server_default="cloud"),
        sa.Column(
            "tags_json",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default=sa.text("'[]'::jsonb"),
        ),
        sa.Column("agent_version", sa.String(length=64), nullable=True),
        sa.Column(
            "device_info_json",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default=sa.text("'{}'::jsonb"),
        ),
        sa.Column(
            "metadata_json",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default=sa.text("'{}'::jsonb"),
        ),
        sa.Column("last_heartbeat", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_error_message", sa.Text(), nullable=True),
        sa.Column("auth_token_hash", sa.String(length=255), nullable=True),
        sa.Column("created_by", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["project_id"], ["projects.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("project_id", "name"),
    )
    op.create_index("ix_probes_project_id", "probes", ["project_id"], unique=False)
    op.create_index("ix_probes_name", "probes", ["name"], unique=False)
    op.create_index("ix_probes_status", "probes", ["status"], unique=False)

    op.create_table(
        "probe_heartbeats",
        sa.Column("probe_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("ip_address", sa.String(length=64), nullable=False),
        sa.Column(
            "network_metrics_json",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default=sa.text("'{}'::jsonb"),
        ),
        sa.Column(
            "agent_status_json",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default=sa.text("'{}'::jsonb"),
        ),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.ForeignKeyConstraint(["probe_id"], ["probes.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_probe_heartbeats_probe_id", "probe_heartbeats", ["probe_id"], unique=False)

    op.create_table(
        "probe_tasks",
        sa.Column("project_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("probe_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("task_type", sa.String(length=64), nullable=False, server_default="evalscope-perf"),
        sa.Column("status", sa.String(length=32), nullable=False, server_default="queued"),
        sa.Column("timeout_seconds", sa.Integer(), nullable=False, server_default="3600"),
        sa.Column("attempt_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column(
            "payload_json",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default=sa.text("'{}'::jsonb"),
        ),
        sa.Column(
            "progress_json",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default=sa.text("'{}'::jsonb"),
        ),
        sa.Column("result_json", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("claimed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("lease_expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_by", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["project_id"], ["projects.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["probe_id"], ["probes.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_probe_tasks_project_id", "probe_tasks", ["project_id"], unique=False)
    op.create_index("ix_probe_tasks_probe_id", "probe_tasks", ["probe_id"], unique=False)
    op.create_index("ix_probe_tasks_status", "probe_tasks", ["status"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_probe_tasks_status", table_name="probe_tasks")
    op.drop_index("ix_probe_tasks_probe_id", table_name="probe_tasks")
    op.drop_index("ix_probe_tasks_project_id", table_name="probe_tasks")
    op.drop_table("probe_tasks")
    op.drop_index("ix_probe_heartbeats_probe_id", table_name="probe_heartbeats")
    op.drop_table("probe_heartbeats")
    op.drop_index("ix_probes_status", table_name="probes")
    op.drop_index("ix_probes_name", table_name="probes")
    op.drop_index("ix_probes_project_id", table_name="probes")
    op.drop_table("probes")
