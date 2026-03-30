"""add benchmark contract fields

Revision ID: a9b8c7d6e5f4
Revises: f1c2d3e4b5a6
Create Date: 2026-03-26 21:10:00.000000
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = "a9b8c7d6e5f4"
down_revision = "f1c2d3e4b5a6"
branch_labels = None
depends_on = None


CL_BENCH_SAMPLE_SCHEMA = {
    "type": "object",
    "required": ["messages", "rubrics"],
    "properties": {
        "id": {"type": "string"},
        "messages": {
            "type": "array",
            "minItems": 1,
            "items": {
                "type": "object",
                "required": ["role", "content"],
                "properties": {
                    "role": {
                        "type": "string",
                        "enum": ["system", "user", "assistant", "tool"],
                    },
                    "content": {"type": "string"},
                },
            },
        },
        "rubrics": {
            "type": "array",
            "minItems": 1,
            "items": {"type": "string"},
        },
        "metadata": {"type": "object"},
        "group_id": {"type": "string"},
    },
}

CL_BENCH_PROMPT_SCHEMA = {
    "type": "object",
    "properties": {
        "judge_prompt_template": {"type": "string"},
    },
}


def upgrade() -> None:
    op.add_column(
        "benchmark_definitions",
        sa.Column(
            "sample_schema_json",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=True,
        ),
    )
    op.add_column(
        "benchmark_definitions",
        sa.Column(
            "prompt_schema_json",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=True,
        ),
    )
    op.add_column(
        "benchmark_definitions",
        sa.Column(
            "prompt_config_json",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=True,
        ),
    )
    op.add_column(
        "benchmark_versions",
        sa.Column("sample_count", sa.BigInteger(), nullable=True),
    )

    benchmark_table = sa.table(
        "benchmark_definitions",
        sa.column("name", sa.String()),
        sa.column("sample_schema_json", postgresql.JSONB(astext_type=sa.Text())),
        sa.column("prompt_schema_json", postgresql.JSONB(astext_type=sa.Text())),
        sa.column("prompt_config_json", postgresql.JSONB(astext_type=sa.Text())),
    )
    op.execute(
        benchmark_table.update()
        .where(benchmark_table.c.name == "cl_bench")
        .values(
            sample_schema_json=CL_BENCH_SAMPLE_SCHEMA,
            prompt_schema_json=CL_BENCH_PROMPT_SCHEMA,
            prompt_config_json={},
        )
    )

    op.execute("UPDATE benchmark_versions SET sample_count = COALESCE(sample_limit, 0)")

    op.alter_column("benchmark_definitions", "sample_schema_json", nullable=False)
    op.alter_column("benchmark_definitions", "prompt_schema_json", nullable=False)
    op.alter_column("benchmark_definitions", "prompt_config_json", nullable=False)
    op.alter_column("benchmark_versions", "sample_count", nullable=False)

    op.drop_column("benchmark_versions", "aliases_json")
    op.drop_column("benchmark_versions", "sample_limit")


def downgrade() -> None:
    op.add_column(
        "benchmark_versions",
        sa.Column(
            "sample_limit",
            sa.BigInteger(),
            nullable=True,
        ),
    )
    op.add_column(
        "benchmark_versions",
        sa.Column(
            "aliases_json",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=True,
        ),
    )
    op.execute("UPDATE benchmark_versions SET sample_limit = sample_count")

    op.drop_column("benchmark_versions", "sample_count")
    op.drop_column("benchmark_definitions", "prompt_config_json")
    op.drop_column("benchmark_definitions", "prompt_schema_json")
    op.drop_column("benchmark_definitions", "sample_schema_json")
