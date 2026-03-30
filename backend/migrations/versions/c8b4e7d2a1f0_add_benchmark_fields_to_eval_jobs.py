"""add benchmark fields to eval jobs

Revision ID: c8b4e7d2a1f0
Revises: ab12cd34ef56
Create Date: 2026-03-26 23:30:00.000000
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = "c8b4e7d2a1f0"
down_revision = "ab12cd34ef56"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("eval_jobs", sa.Column("benchmark_name", sa.String(length=120), nullable=True))
    op.add_column(
        "eval_jobs",
        sa.Column("benchmark_version_id", sa.String(length=120), nullable=True),
    )
    op.add_column(
        "eval_jobs",
        sa.Column(
            "benchmark_config_json",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=True,
        ),
    )

    op.execute(
        """
        UPDATE eval_jobs
        SET
            benchmark_name = split_part(replace(dataset_source_uri, 'benchmark://', ''), '/', 1),
            benchmark_version_id = split_part(
                replace(dataset_source_uri, 'benchmark://', ''),
                '/',
                3
            )
        WHERE dataset_source_uri LIKE 'benchmark://%/%/%'
          AND benchmark_name IS NULL
          AND benchmark_version_id IS NULL
        """
    )
    op.execute(
        """
        UPDATE eval_jobs
        SET dataset_source_type = 'benchmark-version'
        WHERE benchmark_name IS NOT NULL
          AND benchmark_version_id IS NOT NULL
          AND dataset_source_type IN ('benchmark-preset', 'preset-suite')
        """
    )


def downgrade() -> None:
    op.drop_column("eval_jobs", "benchmark_config_json")
    op.drop_column("eval_jobs", "benchmark_version_id")
    op.drop_column("eval_jobs", "benchmark_name")
