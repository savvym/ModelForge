"""add benchmark metadata columns for unified catalog

Revision ID: c2d3e4f5a6b7
Revises: b1c2d3e4f5a6
Create Date: 2026-03-27 14:01:00.000000
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "c2d3e4f5a6b7"
down_revision: str = "b1c2d3e4f5a6"
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None


def upgrade() -> None:
    # -- From BuiltinBenchmarkMetadata --
    op.add_column("benchmark_definitions", sa.Column("family_name", sa.String(120), nullable=True))
    op.add_column(
        "benchmark_definitions", sa.Column("family_display_name", sa.String(255), nullable=True)
    )
    op.add_column("benchmark_definitions", sa.Column("dataset_id", sa.String(255), nullable=True))
    op.add_column("benchmark_definitions", sa.Column("category", sa.String(64), nullable=True))
    op.add_column("benchmark_definitions", sa.Column("paper_url", sa.Text(), nullable=True))
    op.add_column(
        "benchmark_definitions",
        sa.Column("tags", postgresql.JSONB(), nullable=True, server_default="[]"),
    )
    op.add_column(
        "benchmark_definitions",
        sa.Column("metric_names", postgresql.JSONB(), nullable=True, server_default="[]"),
    )
    op.add_column(
        "benchmark_definitions",
        sa.Column("aggregator_names", postgresql.JSONB(), nullable=True, server_default="[]"),
    )
    op.add_column(
        "benchmark_definitions",
        sa.Column(
            "subset_list", postgresql.JSONB(), nullable=True, server_default='["default"]'
        ),
    )
    op.add_column(
        "benchmark_definitions", sa.Column("prompt_template", sa.Text(), nullable=True)
    )
    op.add_column(
        "benchmark_definitions", sa.Column("system_prompt", sa.Text(), nullable=True)
    )
    op.add_column(
        "benchmark_definitions", sa.Column("few_shot_prompt_template", sa.Text(), nullable=True)
    )
    op.add_column(
        "benchmark_definitions", sa.Column("few_shot_num", sa.Integer(), nullable=True)
    )
    op.add_column(
        "benchmark_definitions", sa.Column("eval_split", sa.String(64), nullable=True)
    )
    op.add_column(
        "benchmark_definitions", sa.Column("train_split", sa.String(64), nullable=True)
    )
    op.add_column(
        "benchmark_definitions",
        sa.Column("sample_example_json", postgresql.JSONB(), nullable=True),
    )
    op.add_column(
        "benchmark_definitions",
        sa.Column("statistics_json", postgresql.JSONB(), nullable=True),
    )
    op.add_column(
        "benchmark_definitions",
        sa.Column("readme_json", postgresql.JSONB(), nullable=True),
    )

    # -- New operational columns --
    op.add_column(
        "benchmark_definitions",
        sa.Column("adapter_class", sa.String(255), nullable=True),
    )
    op.add_column(
        "benchmark_definitions",
        sa.Column(
            "source_type", sa.String(32), nullable=True, server_default="builtin"
        ),
    )
    op.add_column(
        "benchmark_definitions",
        sa.Column("is_runnable", sa.Boolean(), nullable=True, server_default=sa.text("false")),
    )


def downgrade() -> None:
    op.drop_column("benchmark_definitions", "is_runnable")
    op.drop_column("benchmark_definitions", "source_type")
    op.drop_column("benchmark_definitions", "adapter_class")
    op.drop_column("benchmark_definitions", "readme_json")
    op.drop_column("benchmark_definitions", "statistics_json")
    op.drop_column("benchmark_definitions", "sample_example_json")
    op.drop_column("benchmark_definitions", "train_split")
    op.drop_column("benchmark_definitions", "eval_split")
    op.drop_column("benchmark_definitions", "few_shot_num")
    op.drop_column("benchmark_definitions", "few_shot_prompt_template")
    op.drop_column("benchmark_definitions", "system_prompt")
    op.drop_column("benchmark_definitions", "prompt_template")
    op.drop_column("benchmark_definitions", "subset_list")
    op.drop_column("benchmark_definitions", "aggregator_names")
    op.drop_column("benchmark_definitions", "metric_names")
    op.drop_column("benchmark_definitions", "tags")
    op.drop_column("benchmark_definitions", "paper_url")
    op.drop_column("benchmark_definitions", "category")
    op.drop_column("benchmark_definitions", "dataset_id")
    op.drop_column("benchmark_definitions", "family_display_name")
    op.drop_column("benchmark_definitions", "family_name")
