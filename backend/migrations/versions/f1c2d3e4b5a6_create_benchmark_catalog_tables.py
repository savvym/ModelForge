"""create benchmark catalog tables

Revision ID: f1c2d3e4b5a6
Revises: c8b4e7d2a1f0
Create Date: 2026-03-26 19:45:00.000000
"""

from __future__ import annotations

from pathlib import Path
from uuid import uuid4

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = "f1c2d3e4b5a6"
down_revision = "c8b4e7d2a1f0"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "benchmark_definitions",
        sa.Column("name", sa.String(length=120), nullable=False),
        sa.Column("display_name", sa.String(length=255), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("default_eval_method", sa.String(length=64), nullable=False),
        sa.Column("requires_judge_model", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column(
            "supports_custom_dataset",
            sa.Boolean(),
            nullable=False,
            server_default=sa.false(),
        ),
        sa.Column("id", sa.UUID(), nullable=False),
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
        sa.PrimaryKeyConstraint("id", name=op.f("pk_benchmark_definitions")),
        sa.UniqueConstraint("name", name=op.f("uq_benchmark_definitions_name")),
    )
    op.create_index(
        op.f("ix_benchmark_definitions_name"),
        "benchmark_definitions",
        ["name"],
        unique=False,
    )

    op.create_table(
        "benchmark_versions",
        sa.Column("benchmark_id", sa.UUID(), nullable=False),
        sa.Column("version_id", sa.String(length=120), nullable=False),
        sa.Column("display_name", sa.String(length=255), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("dataset_path", sa.Text(), nullable=True),
        sa.Column("dataset_source_uri", sa.Text(), nullable=True),
        sa.Column("sample_limit", sa.BigInteger(), nullable=True),
        sa.Column("enabled", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("aliases_json", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("id", sa.UUID(), nullable=False),
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
            ["benchmark_id"],
            ["benchmark_definitions.id"],
            name=op.f("fk_benchmark_versions_benchmark_id_benchmark_definitions"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_benchmark_versions")),
        sa.UniqueConstraint(
            "benchmark_id",
            "version_id",
            name=op.f("uq_benchmark_versions_benchmark_id"),
        ),
    )
    op.create_index(
        op.f("ix_benchmark_versions_benchmark_id"),
        "benchmark_versions",
        ["benchmark_id"],
        unique=False,
    )

    repo_root = Path(__file__).resolve().parents[3]
    benchmark_id = uuid4()
    smoke_1_id = uuid4()
    smoke_10_id = uuid4()
    benchmark_table = sa.table(
        "benchmark_definitions",
        sa.column("id", sa.UUID()),
        sa.column("name", sa.String()),
        sa.column("display_name", sa.String()),
        sa.column("description", sa.Text()),
        sa.column("default_eval_method", sa.String()),
        sa.column("requires_judge_model", sa.Boolean()),
        sa.column("supports_custom_dataset", sa.Boolean()),
    )
    version_table = sa.table(
        "benchmark_versions",
        sa.column("id", sa.UUID()),
        sa.column("benchmark_id", sa.UUID()),
        sa.column("version_id", sa.String()),
        sa.column("display_name", sa.String()),
        sa.column("description", sa.Text()),
        sa.column("dataset_path", sa.Text()),
        sa.column("dataset_source_uri", sa.Text()),
        sa.column("sample_limit", sa.BigInteger()),
        sa.column("enabled", sa.Boolean()),
        sa.column("aliases_json", postgresql.JSONB(astext_type=sa.Text())),
    )
    op.bulk_insert(
        benchmark_table,
        [
            {
                "id": benchmark_id,
                "name": "cl_bench",
                "display_name": "CL-bench",
                "description": (
                    "评测模型是否能从长上下文中学习新规则、新知识，并严格基于上下文作答。"
                ),
                "default_eval_method": "judge-model",
                "requires_judge_model": True,
                "supports_custom_dataset": False,
            }
        ],
    )
    op.bulk_insert(
        version_table,
        [
            {
                "id": smoke_1_id,
                "benchmark_id": benchmark_id,
                "version_id": "cl_bench_smoke_1",
                "display_name": "CL-bench Smoke (1条)",
                "description": "内置 1 条样本，用于快速验证评测链路是否可用。",
                "dataset_path": str(
                    repo_root / "backend" / ".datasets" / "cl_bench" / "CL-bench-1.jsonl"
                ),
                "dataset_source_uri": None,
                "sample_limit": 1,
                "enabled": True,
                "aliases_json": ["e2d0f6a7-3a96-4b9b-b1ce-3ea08f3d4e01"],
            },
            {
                "id": smoke_10_id,
                "benchmark_id": benchmark_id,
                "version_id": "cl_bench_smoke_10",
                "display_name": "CL-bench Smoke (10条)",
                "description": "内置 10 条样本，用于验证真实生成与 judge 的完整回路。",
                "dataset_path": str(
                    repo_root / "backend" / ".datasets" / "cl_bench" / "CL-bench-10.jsonl"
                ),
                "dataset_source_uri": None,
                "sample_limit": 10,
                "enabled": True,
                "aliases_json": ["6d0d3855-92ec-48f4-af6d-a1d00c32b602"],
            },
        ],
    )


def downgrade() -> None:
    op.drop_index(op.f("ix_benchmark_versions_benchmark_id"), table_name="benchmark_versions")
    op.drop_table("benchmark_versions")
    op.drop_index(op.f("ix_benchmark_definitions_name"), table_name="benchmark_definitions")
    op.drop_table("benchmark_definitions")
