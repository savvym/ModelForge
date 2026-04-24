"""add benchmark targets for evaluation leaderboards

Revision ID: 0011
Revises: 0010
Create Date: 2026-04-24
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0011"
down_revision: str = "0010"
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None


def _add_benchmark_target_columns(table_name: str) -> None:
    op.add_column(
        table_name,
        sa.Column("source_benchmark_id", postgresql.UUID(as_uuid=True), nullable=True),
    )
    op.add_column(
        table_name,
        sa.Column("source_benchmark_version_id", postgresql.UUID(as_uuid=True), nullable=True),
    )


def _add_benchmark_target_constraints(table_name: str) -> None:
    op.execute(
        f"""
        ALTER TABLE {table_name}
        ADD CONSTRAINT fk_{table_name}_source_benchmark_id
        FOREIGN KEY (source_benchmark_id)
        REFERENCES benchmark_definitions (id)
        ON DELETE SET NULL
        NOT VALID
        """
    )
    op.execute(
        f"""
        ALTER TABLE {table_name}
        ADD CONSTRAINT fk_{table_name}_source_benchmark_version_id
        FOREIGN KEY (source_benchmark_version_id)
        REFERENCES benchmark_versions (id)
        ON DELETE SET NULL
        NOT VALID
        """
    )
    op.execute(f"ALTER TABLE {table_name} VALIDATE CONSTRAINT fk_{table_name}_source_benchmark_id")
    op.execute(
        f"ALTER TABLE {table_name} VALIDATE CONSTRAINT "
        f"fk_{table_name}_source_benchmark_version_id"
    )


def _create_benchmark_target_indexes() -> None:
    with op.get_context().autocommit_block():
        op.execute(
            """
            CREATE INDEX CONCURRENTLY ix_evaluation_runs_source_benchmark_id
            ON evaluation_runs (source_benchmark_id)
            """
        )
        op.execute(
            """
            CREATE INDEX CONCURRENTLY ix_evaluation_runs_source_benchmark_version_id
            ON evaluation_runs (source_benchmark_version_id)
            """
        )
        op.execute(
            """
            CREATE INDEX CONCURRENTLY ix_evaluation_leaderboards_source_benchmark_id
            ON evaluation_leaderboards (source_benchmark_id)
            """
        )
        op.execute(
            """
            CREATE INDEX CONCURRENTLY ix_evaluation_leaderboards_source_benchmark_version_id
            ON evaluation_leaderboards (source_benchmark_version_id)
            """
        )


def _drop_benchmark_target_indexes() -> None:
    with op.get_context().autocommit_block():
        op.execute(
            "DROP INDEX CONCURRENTLY IF EXISTS "
            "ix_evaluation_leaderboards_source_benchmark_version_id"
        )
        op.execute(
            "DROP INDEX CONCURRENTLY IF EXISTS "
            "ix_evaluation_leaderboards_source_benchmark_id"
        )
        op.execute(
            "DROP INDEX CONCURRENTLY IF EXISTS "
            "ix_evaluation_runs_source_benchmark_version_id"
        )
        op.execute("DROP INDEX CONCURRENTLY IF EXISTS ix_evaluation_runs_source_benchmark_id")


def upgrade() -> None:
    _add_benchmark_target_columns("evaluation_runs")
    _add_benchmark_target_columns("evaluation_leaderboards")

    op.execute(
        """
        UPDATE evaluation_runs AS run
        SET
            source_benchmark_id = definition.id,
            source_benchmark_version_id = version.id
        FROM benchmark_definitions AS definition
        JOIN benchmark_versions AS version
            ON version.benchmark_id = definition.id
        WHERE
            run.kind = 'benchmark'
            AND run.source_benchmark_version_id IS NULL
            AND run.source_benchmark_id IS NULL
            AND COALESCE(
                run.execution_plan_json #>> '{overrides,benchmark,name}',
                run.execution_plan_json ->> 'target_name'
            ) = definition.name
            AND COALESCE(
                run.execution_plan_json #>> '{overrides,benchmark,version}',
                run.execution_plan_json ->> 'target_version'
            ) = version.version_id
        """
    )

    _add_benchmark_target_constraints("evaluation_runs")
    _add_benchmark_target_constraints("evaluation_leaderboards")
    _create_benchmark_target_indexes()


def downgrade() -> None:
    _drop_benchmark_target_indexes()

    op.drop_constraint(
        "fk_evaluation_leaderboards_source_benchmark_version_id",
        "evaluation_leaderboards",
        type_="foreignkey",
    )
    op.drop_constraint(
        "fk_evaluation_leaderboards_source_benchmark_id",
        "evaluation_leaderboards",
        type_="foreignkey",
    )
    op.drop_column("evaluation_leaderboards", "source_benchmark_version_id")
    op.drop_column("evaluation_leaderboards", "source_benchmark_id")

    op.drop_constraint(
        "fk_evaluation_runs_source_benchmark_version_id",
        "evaluation_runs",
        type_="foreignkey",
    )
    op.drop_constraint(
        "fk_evaluation_runs_source_benchmark_id",
        "evaluation_runs",
        type_="foreignkey",
    )
    op.drop_column("evaluation_runs", "source_benchmark_version_id")
    op.drop_column("evaluation_runs", "source_benchmark_id")
