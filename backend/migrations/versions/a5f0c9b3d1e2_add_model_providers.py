"""add model providers

Revision ID: a5f0c9b3d1e2
Revises: d3d1f8a1b4c2
Create Date: 2026-03-21 18:45:00.000000
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = "a5f0c9b3d1e2"
down_revision = "d3d1f8a1b4c2"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "model_providers",
        sa.Column("project_id", sa.UUID(), nullable=False),
        sa.Column("name", sa.String(length=120), nullable=False),
        sa.Column("provider_type", sa.String(length=64), nullable=False),
        sa.Column("adapter", sa.String(length=32), nullable=False),
        sa.Column("api_format", sa.String(length=32), nullable=False),
        sa.Column("base_url", sa.Text(), nullable=False),
        sa.Column("api_key", sa.Text(), nullable=True),
        sa.Column("organization", sa.String(length=120), nullable=True),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("headers_json", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("last_synced_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("created_by", sa.UUID(), nullable=True),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["project_id"],
            ["projects.id"],
            name=op.f("fk_model_providers_project_id_projects"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_model_providers")),
    )
    op.create_index(op.f("ix_model_providers_project_id"), "model_providers", ["project_id"], unique=False)
    op.create_index(
        "ix_model_providers_project_name",
        "model_providers",
        ["project_id", "name"],
        unique=True,
    )

    op.add_column("models", sa.Column("provider_id", sa.UUID(), nullable=True))
    op.add_column("models", sa.Column("model_code", sa.String(length=160), nullable=True))
    op.add_column("models", sa.Column("api_format", sa.String(length=32), nullable=True))
    op.add_column("models", sa.Column("capabilities_json", postgresql.JSONB(astext_type=sa.Text()), nullable=True))
    op.add_column(
        "models",
        sa.Column(
            "is_provider_managed",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("false"),
        ),
    )
    op.add_column("models", sa.Column("last_synced_at", sa.DateTime(timezone=True), nullable=True))
    op.alter_column("models", "is_provider_managed", server_default=None)
    op.create_foreign_key(
        op.f("fk_models_provider_id_model_providers"),
        "models",
        "model_providers",
        ["provider_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.create_index(
        "ix_models_provider_model_code",
        "models",
        ["provider_id", "model_code"],
        unique=True,
    )


def downgrade() -> None:
    op.drop_index("ix_models_provider_model_code", table_name="models")
    op.drop_constraint(op.f("fk_models_provider_id_model_providers"), "models", type_="foreignkey")
    op.drop_column("models", "last_synced_at")
    op.drop_column("models", "is_provider_managed")
    op.drop_column("models", "capabilities_json")
    op.drop_column("models", "api_format")
    op.drop_column("models", "model_code")
    op.drop_column("models", "provider_id")

    op.drop_index("ix_model_providers_project_name", table_name="model_providers")
    op.drop_index(op.f("ix_model_providers_project_id"), table_name="model_providers")
    op.drop_table("model_providers")
