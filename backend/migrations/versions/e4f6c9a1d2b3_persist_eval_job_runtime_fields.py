"""persist eval job runtime fields

Revision ID: e4f6c9a1d2b3
Revises: c4f2b6a7e9d1
Create Date: 2026-03-23 11:12:00.000000
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "e4f6c9a1d2b3"
down_revision = "c4f2b6a7e9d1"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("eval_jobs", sa.Column("created_by_name", sa.String(length=120), nullable=True))
    op.add_column("eval_jobs", sa.Column("model_name", sa.String(length=255), nullable=True))
    op.add_column("eval_jobs", sa.Column("access_source", sa.String(length=32), nullable=True))
    op.add_column("eval_jobs", sa.Column("task_type", sa.String(length=64), nullable=True))
    op.add_column("eval_jobs", sa.Column("eval_mode", sa.String(length=64), nullable=True))
    op.add_column("eval_jobs", sa.Column("endpoint_name", sa.String(length=120), nullable=True))
    op.add_column("eval_jobs", sa.Column("judge_model_name", sa.String(length=255), nullable=True))
    op.add_column("eval_jobs", sa.Column("dataset_source_type", sa.String(length=32), nullable=True))
    op.add_column("eval_jobs", sa.Column("dataset_name", sa.String(length=255), nullable=True))
    op.add_column("eval_jobs", sa.Column("dataset_source_uri", sa.Text(), nullable=True))
    op.add_column("eval_jobs", sa.Column("artifact_prefix_uri", sa.Text(), nullable=True))
    op.add_column("eval_jobs", sa.Column("source_object_uri", sa.Text(), nullable=True))
    op.add_column("eval_jobs", sa.Column("results_prefix_uri", sa.Text(), nullable=True))
    op.add_column("eval_jobs", sa.Column("samples_prefix_uri", sa.Text(), nullable=True))
    op.add_column("eval_jobs", sa.Column("report_object_uri", sa.Text(), nullable=True))
    op.add_column("eval_jobs", sa.Column("auto_progress", sa.Boolean(), nullable=False, server_default=sa.false()))

    op.alter_column(
        "eval_jobs",
        "batch_job_id",
        existing_type=sa.UUID(),
        type_=sa.String(length=128),
        existing_nullable=True,
        postgresql_using="batch_job_id::text",
    )

    op.execute("UPDATE eval_jobs SET created_by_name = 'zhanghaodong' WHERE created_by_name IS NULL")
    op.execute("UPDATE eval_jobs SET access_source = 'nta' WHERE access_source IS NULL")
    op.execute(
        "UPDATE eval_jobs SET dataset_source_type = 'managed-dataset' WHERE dataset_source_type IS NULL"
    )
    op.execute("UPDATE eval_jobs SET task_type = 'single-turn' WHERE task_type IS NULL")
    op.execute("UPDATE eval_jobs SET eval_mode = 'infer-auto' WHERE eval_mode IS NULL")
    op.execute("UPDATE eval_jobs SET model_name = name WHERE model_name IS NULL")
    op.execute("UPDATE eval_jobs SET dataset_name = name WHERE dataset_name IS NULL")
    op.execute(
        "UPDATE eval_jobs SET judge_model_name = criteria_text WHERE judge_model_name IS NULL AND criteria_text IS NOT NULL"
    )

    op.alter_column("eval_jobs", "auto_progress", server_default=None)


def downgrade() -> None:
    op.alter_column(
        "eval_jobs",
        "batch_job_id",
        existing_type=sa.String(length=128),
        type_=sa.UUID(),
        existing_nullable=True,
        postgresql_using="NULLIF(batch_job_id, '')::uuid",
    )

    op.drop_column("eval_jobs", "auto_progress")
    op.drop_column("eval_jobs", "report_object_uri")
    op.drop_column("eval_jobs", "samples_prefix_uri")
    op.drop_column("eval_jobs", "results_prefix_uri")
    op.drop_column("eval_jobs", "source_object_uri")
    op.drop_column("eval_jobs", "artifact_prefix_uri")
    op.drop_column("eval_jobs", "dataset_source_uri")
    op.drop_column("eval_jobs", "dataset_name")
    op.drop_column("eval_jobs", "dataset_source_type")
    op.drop_column("eval_jobs", "judge_model_name")
    op.drop_column("eval_jobs", "endpoint_name")
    op.drop_column("eval_jobs", "eval_mode")
    op.drop_column("eval_jobs", "task_type")
    op.drop_column("eval_jobs", "access_source")
    op.drop_column("eval_jobs", "model_name")
    op.drop_column("eval_jobs", "created_by_name")
