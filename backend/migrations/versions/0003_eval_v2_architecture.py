"""introduce evaluation v2 architecture

Revision ID: 0003
Revises: 0002
Create Date: 2026-04-02
"""

from __future__ import annotations

from collections.abc import Sequence
from uuid import UUID

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0003"
down_revision: str = "0002"
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "eval_specs",
        sa.Column("project_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("name", sa.String(length=120), nullable=False),
        sa.Column("display_name", sa.String(length=255), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("capability_group", sa.String(length=120), nullable=True),
        sa.Column("capability_category", sa.String(length=120), nullable=True),
        sa.Column("tags_json", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default="[]"),
        sa.Column("input_schema_json", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default="{}"),
        sa.Column("output_schema_json", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default="{}"),
        sa.Column("status", sa.String(length=32), nullable=False, server_default="active"),
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["project_id"], ["projects.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("name"),
    )
    op.create_index("ix_eval_specs_name", "eval_specs", ["name"], unique=False)
    op.create_index("ix_eval_specs_project_id", "eval_specs", ["project_id"], unique=False)

    op.create_table(
        "template_specs",
        sa.Column("project_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("name", sa.String(length=120), nullable=False),
        sa.Column("display_name", sa.String(length=255), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("template_type", sa.String(length=64), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False, server_default="active"),
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["project_id"], ["projects.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("project_id", "name"),
    )
    op.create_index("ix_template_specs_name", "template_specs", ["name"], unique=False)
    op.create_index("ix_template_specs_project_id", "template_specs", ["project_id"], unique=False)

    op.create_table(
        "template_spec_versions",
        sa.Column("template_spec_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("prompt", sa.Text(), nullable=False),
        sa.Column("vars_json", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default="[]"),
        sa.Column("output_schema_json", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default="{}"),
        sa.Column("parser_config_json", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default="{}"),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["template_spec_id"], ["template_specs.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("template_spec_id", "version"),
    )
    op.create_index(
        "ix_template_spec_versions_template_spec_id",
        "template_spec_versions",
        ["template_spec_id"],
        unique=False,
    )

    op.create_table(
        "judge_policies",
        sa.Column("project_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("name", sa.String(length=120), nullable=False),
        sa.Column("display_name", sa.String(length=255), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("strategy", sa.String(length=64), nullable=False, server_default="judge-template"),
        sa.Column("template_spec_version_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("model_selector_json", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default="{}"),
        sa.Column("execution_params_json", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default="{}"),
        sa.Column("parser_config_json", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default="{}"),
        sa.Column("retry_policy_json", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default="{}"),
        sa.Column("status", sa.String(length=32), nullable=False, server_default="active"),
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["project_id"], ["projects.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["template_spec_version_id"], ["template_spec_versions.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("project_id", "name"),
    )
    op.create_index("ix_judge_policies_name", "judge_policies", ["name"], unique=False)
    op.create_index("ix_judge_policies_project_id", "judge_policies", ["project_id"], unique=False)

    op.create_table(
        "eval_spec_versions",
        sa.Column("spec_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("version", sa.String(length=120), nullable=False),
        sa.Column("display_name", sa.String(length=255), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("engine", sa.String(length=64), nullable=False),
        sa.Column("execution_mode", sa.String(length=64), nullable=False),
        sa.Column("engine_benchmark_name", sa.String(length=255), nullable=True),
        sa.Column("engine_config_json", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default="{}"),
        sa.Column("scoring_config_json", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default="{}"),
        sa.Column("dataset_source_uri", sa.Text(), nullable=True),
        sa.Column("template_spec_version_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("default_judge_policy_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("sample_count", sa.BigInteger(), nullable=True),
        sa.Column("enabled", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("is_recommended", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["default_judge_policy_id"], ["judge_policies.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["spec_id"], ["eval_specs.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["template_spec_version_id"], ["template_spec_versions.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("spec_id", "version"),
    )
    op.create_index("ix_eval_spec_versions_spec_id", "eval_spec_versions", ["spec_id"], unique=False)

    op.create_table(
        "eval_suites",
        sa.Column("project_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("name", sa.String(length=120), nullable=False),
        sa.Column("display_name", sa.String(length=255), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("capability_group", sa.String(length=120), nullable=True),
        sa.Column("status", sa.String(length=32), nullable=False, server_default="active"),
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["project_id"], ["projects.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("name"),
    )
    op.create_index("ix_eval_suites_name", "eval_suites", ["name"], unique=False)
    op.create_index("ix_eval_suites_project_id", "eval_suites", ["project_id"], unique=False)

    op.create_table(
        "eval_suite_versions",
        sa.Column("suite_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("version", sa.String(length=120), nullable=False),
        sa.Column("display_name", sa.String(length=255), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("enabled", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["suite_id"], ["eval_suites.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("suite_id", "version"),
    )
    op.create_index("ix_eval_suite_versions_suite_id", "eval_suite_versions", ["suite_id"], unique=False)

    op.create_table(
        "eval_suite_items",
        sa.Column("suite_version_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("item_key", sa.String(length=120), nullable=False),
        sa.Column("display_name", sa.String(length=255), nullable=False),
        sa.Column("spec_version_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("position", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("weight", sa.Float(), nullable=False, server_default="1"),
        sa.Column("group_name", sa.String(length=120), nullable=True),
        sa.Column("overrides_json", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default="{}"),
        sa.Column("enabled", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["spec_version_id"], ["eval_spec_versions.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["suite_version_id"], ["eval_suite_versions.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("suite_version_id", "item_key"),
    )
    op.create_index("ix_eval_suite_items_suite_version_id", "eval_suite_items", ["suite_version_id"], unique=False)
    op.create_index("ix_eval_suite_items_spec_version_id", "eval_suite_items", ["spec_version_id"], unique=False)

    op.create_table(
        "evaluation_runs",
        sa.Column("project_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("kind", sa.String(length=32), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False, server_default="queued"),
        sa.Column("model_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("model_name", sa.String(length=255), nullable=True),
        sa.Column("source_spec_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("source_spec_version_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("source_suite_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("source_suite_version_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("judge_policy_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("execution_plan_json", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default="{}"),
        sa.Column("summary_report_uri", sa.Text(), nullable=True),
        sa.Column("raw_output_prefix_uri", sa.Text(), nullable=True),
        sa.Column("temporal_workflow_id", sa.String(length=128), nullable=True),
        sa.Column("progress_total", sa.BigInteger(), nullable=True),
        sa.Column("progress_done", sa.BigInteger(), nullable=True),
        sa.Column("cancel_requested", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("error_code", sa.String(length=64), nullable=True),
        sa.Column("error_message", sa.String(length=500), nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_by", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["judge_policy_id"], ["judge_policies.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["model_id"], ["models.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["project_id"], ["projects.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["source_spec_id"], ["eval_specs.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["source_spec_version_id"], ["eval_spec_versions.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["source_suite_id"], ["eval_suites.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["source_suite_version_id"], ["eval_suite_versions.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_evaluation_runs_project_id", "evaluation_runs", ["project_id"], unique=False)
    op.create_index("ix_evaluation_runs_status", "evaluation_runs", ["status"], unique=False)
    op.create_index("ix_evaluation_runs_temporal_workflow_id", "evaluation_runs", ["temporal_workflow_id"], unique=False)

    op.create_table(
        "evaluation_run_items",
        sa.Column("run_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("item_key", sa.String(length=120), nullable=False),
        sa.Column("display_name", sa.String(length=255), nullable=False),
        sa.Column("group_name", sa.String(length=120), nullable=True),
        sa.Column("weight", sa.Float(), nullable=False, server_default="1"),
        sa.Column("status", sa.String(length=32), nullable=False, server_default="queued"),
        sa.Column("spec_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("spec_version_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("engine", sa.String(length=64), nullable=False),
        sa.Column("execution_mode", sa.String(length=64), nullable=False),
        sa.Column("model_binding_json", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default="{}"),
        sa.Column("judge_policy_snapshot_json", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("template_snapshot_json", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("plan_json", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default="{}"),
        sa.Column("report_uri", sa.Text(), nullable=True),
        sa.Column("raw_output_prefix_uri", sa.Text(), nullable=True),
        sa.Column("temporal_workflow_id", sa.String(length=128), nullable=True),
        sa.Column("progress_total", sa.BigInteger(), nullable=True),
        sa.Column("progress_done", sa.BigInteger(), nullable=True),
        sa.Column("error_code", sa.String(length=64), nullable=True),
        sa.Column("error_message", sa.String(length=500), nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["run_id"], ["evaluation_runs.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["spec_id"], ["eval_specs.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["spec_version_id"], ["eval_spec_versions.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("run_id", "item_key"),
    )
    op.create_index("ix_evaluation_run_items_run_id", "evaluation_run_items", ["run_id"], unique=False)
    op.create_index("ix_evaluation_run_items_status", "evaluation_run_items", ["status"], unique=False)
    op.create_index("ix_evaluation_run_items_temporal_workflow_id", "evaluation_run_items", ["temporal_workflow_id"], unique=False)

    op.create_table(
        "evaluation_run_metrics",
        sa.Column("run_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("run_item_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("metric_name", sa.String(length=120), nullable=False),
        sa.Column("metric_value", sa.Float(), nullable=False),
        sa.Column("metric_scope", sa.String(length=32), nullable=False, server_default="overall"),
        sa.Column("metric_unit", sa.String(length=32), nullable=True),
        sa.Column("dimension_json", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default="{}"),
        sa.Column("extra_json", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default="{}"),
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["run_id"], ["evaluation_runs.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["run_item_id"], ["evaluation_run_items.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_evaluation_run_metrics_run_id", "evaluation_run_metrics", ["run_id"], unique=False)
    op.create_index("ix_evaluation_run_metrics_run_item_id", "evaluation_run_metrics", ["run_item_id"], unique=False)

    op.create_table(
        "evaluation_run_samples",
        sa.Column("run_item_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("sample_id", sa.String(length=255), nullable=False),
        sa.Column("subset_name", sa.String(length=255), nullable=True),
        sa.Column("input_preview", sa.Text(), nullable=True),
        sa.Column("prediction_text", sa.Text(), nullable=True),
        sa.Column("reference_answers_json", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default="[]"),
        sa.Column("score", sa.Float(), nullable=True),
        sa.Column("raw_score", sa.Float(), nullable=True),
        sa.Column("passed", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("reason", sa.Text(), nullable=True),
        sa.Column("error", sa.Text(), nullable=True),
        sa.Column("latency_ms", sa.Integer(), nullable=True),
        sa.Column("total_tokens", sa.Integer(), nullable=True),
        sa.Column("metadata_json", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default="{}"),
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["run_item_id"], ["evaluation_run_items.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_evaluation_run_samples_run_item_id", "evaluation_run_samples", ["run_item_id"], unique=False)
    op.create_index("ix_evaluation_run_samples_sample_id", "evaluation_run_samples", ["sample_id"], unique=False)

    op.create_table(
        "evaluation_run_artifacts",
        sa.Column("run_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("run_item_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("artifact_type", sa.String(length=64), nullable=False),
        sa.Column("uri", sa.Text(), nullable=False),
        sa.Column("content_type", sa.String(length=120), nullable=True),
        sa.Column("extra_json", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default="{}"),
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["run_id"], ["evaluation_runs.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["run_item_id"], ["evaluation_run_items.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_evaluation_run_artifacts_run_id", "evaluation_run_artifacts", ["run_id"], unique=False)
    op.create_index("ix_evaluation_run_artifacts_run_item_id", "evaluation_run_artifacts", ["run_item_id"], unique=False)

    op.create_table(
        "evaluation_run_events",
        sa.Column("run_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("run_item_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("event_type", sa.String(length=64), nullable=False),
        sa.Column("level", sa.String(length=24), nullable=False, server_default="info"),
        sa.Column("message", sa.Text(), nullable=False),
        sa.Column("payload_json", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default="{}"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.ForeignKeyConstraint(["run_id"], ["evaluation_runs.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["run_item_id"], ["evaluation_run_items.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_evaluation_run_events_run_id", "evaluation_run_events", ["run_id"], unique=False)
    op.create_index("ix_evaluation_run_events_run_item_id", "evaluation_run_events", ["run_item_id"], unique=False)

    _seed_builtin_catalog()


def _seed_builtin_catalog() -> None:
    conn = op.get_bind()

    eval_specs = sa.table(
        "eval_specs",
        sa.column("id", postgresql.UUID(as_uuid=True)),
        sa.column("project_id", postgresql.UUID(as_uuid=True)),
        sa.column("name", sa.String),
        sa.column("display_name", sa.String),
        sa.column("description", sa.Text),
        sa.column("capability_group", sa.String),
        sa.column("capability_category", sa.String),
        sa.column("tags_json", postgresql.JSONB),
        sa.column("input_schema_json", postgresql.JSONB),
        sa.column("output_schema_json", postgresql.JSONB),
        sa.column("status", sa.String),
    )
    eval_spec_versions = sa.table(
        "eval_spec_versions",
        sa.column("id", postgresql.UUID(as_uuid=True)),
        sa.column("spec_id", postgresql.UUID(as_uuid=True)),
        sa.column("version", sa.String),
        sa.column("display_name", sa.String),
        sa.column("description", sa.Text),
        sa.column("engine", sa.String),
        sa.column("execution_mode", sa.String),
        sa.column("engine_benchmark_name", sa.String),
        sa.column("engine_config_json", postgresql.JSONB),
        sa.column("scoring_config_json", postgresql.JSONB),
        sa.column("dataset_source_uri", sa.Text),
        sa.column("template_spec_version_id", postgresql.UUID(as_uuid=True)),
        sa.column("default_judge_policy_id", postgresql.UUID(as_uuid=True)),
        sa.column("sample_count", sa.BigInteger),
        sa.column("enabled", sa.Boolean),
        sa.column("is_recommended", sa.Boolean),
    )
    eval_suites = sa.table(
        "eval_suites",
        sa.column("id", postgresql.UUID(as_uuid=True)),
        sa.column("project_id", postgresql.UUID(as_uuid=True)),
        sa.column("name", sa.String),
        sa.column("display_name", sa.String),
        sa.column("description", sa.Text),
        sa.column("capability_group", sa.String),
        sa.column("status", sa.String),
    )
    eval_suite_versions = sa.table(
        "eval_suite_versions",
        sa.column("id", postgresql.UUID(as_uuid=True)),
        sa.column("suite_id", postgresql.UUID(as_uuid=True)),
        sa.column("version", sa.String),
        sa.column("display_name", sa.String),
        sa.column("description", sa.Text),
        sa.column("enabled", sa.Boolean),
    )
    eval_suite_items = sa.table(
        "eval_suite_items",
        sa.column("id", postgresql.UUID(as_uuid=True)),
        sa.column("suite_version_id", postgresql.UUID(as_uuid=True)),
        sa.column("item_key", sa.String),
        sa.column("display_name", sa.String),
        sa.column("spec_version_id", postgresql.UUID(as_uuid=True)),
        sa.column("position", sa.Integer),
        sa.column("weight", sa.Float),
        sa.column("group_name", sa.String),
        sa.column("overrides_json", postgresql.JSONB),
        sa.column("enabled", sa.Boolean),
    )

    spec_rows = [
        _builtin_spec_row(
            spec_id="0e0f04d8-1f80-4f64-a65f-f5f1fe2bf101",
            version_id="7fc32db2-2c3c-42ba-89ce-636f72bafd11",
            name="ceval",
            display_name="C-Eval",
            category="学科",
            benchmark_name="ceval",
            description="中文综合考试评测集，适合衡量中文知识与理解能力。",
        ),
        _builtin_spec_row(
            spec_id="0e0f04d8-1f80-4f64-a65f-f5f1fe2bf102",
            version_id="7fc32db2-2c3c-42ba-89ce-636f72bafd12",
            name="mmlu",
            display_name="MMLU",
            category="学科",
            benchmark_name="mmlu",
            description="多学科多项选择 benchmark，用于评估广泛知识面与推理能力。",
        ),
        _builtin_spec_row(
            spec_id="0e0f04d8-1f80-4f64-a65f-f5f1fe2bf103",
            version_id="7fc32db2-2c3c-42ba-89ce-636f72bafd13",
            name="arc",
            display_name="ARC",
            category="学科",
            benchmark_name="arc",
            description="AI2 ARC 学科类选择题评测集。",
        ),
        _builtin_spec_row(
            spec_id="0e0f04d8-1f80-4f64-a65f-f5f1fe2bf104",
            version_id="7fc32db2-2c3c-42ba-89ce-636f72bafd14",
            name="gsm8k",
            display_name="GSM8K",
            category="数学",
            benchmark_name="gsm8k",
            description="小学数学推理 benchmark，用于评估分步计算能力。",
        ),
        _builtin_spec_row(
            spec_id="0e0f04d8-1f80-4f64-a65f-f5f1fe2bf105",
            version_id="7fc32db2-2c3c-42ba-89ce-636f72bafd15",
            name="bbh",
            display_name="BBH",
            category="推理",
            benchmark_name="bbh",
            description="BIG-Bench Hard 高难推理评测集。",
        ),
        _builtin_spec_row(
            spec_id="0e0f04d8-1f80-4f64-a65f-f5f1fe2bf106",
            version_id="7fc32db2-2c3c-42ba-89ce-636f72bafd16",
            name="hellaswag",
            display_name="HellaSwag",
            category="推理",
            benchmark_name="hellaswag",
            description="常识推理 benchmark，用于评估情境延续与选择能力。",
        ),
    ]
    op.bulk_insert(eval_specs, [row["spec"] for row in spec_rows])
    op.bulk_insert(eval_spec_versions, [row["version"] for row in spec_rows])

    suite_id = UUID("6d511960-0c55-4ca0-a2cf-30295375e301")
    suite_version_id = UUID("9c2a6381-6606-42ad-940f-d47f369db001")
    op.bulk_insert(
        eval_suites,
        [
            {
                "id": suite_id,
                "project_id": None,
                "name": "baseline-general",
                "display_name": "Baseline General",
                "description": "通用基线评测套件，覆盖学科、数学与推理能力。",
                "capability_group": "基线评测",
                "status": "active",
            }
        ],
    )
    op.bulk_insert(
        eval_suite_versions,
        [
            {
                "id": suite_version_id,
                "suite_id": suite_id,
                "version": "v1",
                "display_name": "Baseline General v1",
                "description": "首版通用基线套件，包含 6 个 EvalScope 内置 benchmark。",
                "enabled": True,
            }
        ],
    )
    op.bulk_insert(
        eval_suite_items,
        [
            {
                "id": UUID(f"b95cf6e1-d9ab-4b2c-8eec-820f863f61{index:02d}"),
                "suite_version_id": suite_version_id,
                "item_key": row["spec"]["name"],
                "display_name": row["spec"]["display_name"],
                "spec_version_id": row["version"]["id"],
                "position": index,
                "weight": 1.0,
                "group_name": row["spec"]["capability_category"],
                "overrides_json": {},
                "enabled": True,
            }
            for index, row in enumerate(spec_rows, start=1)
        ],
    )


def _builtin_spec_row(
    *,
    spec_id: str,
    version_id: str,
    name: str,
    display_name: str,
    category: str,
    benchmark_name: str,
    description: str,
) -> dict[str, dict]:
    return {
        "spec": {
            "id": UUID(spec_id),
            "project_id": None,
            "name": name,
            "display_name": display_name,
            "description": description,
            "capability_group": "基线评测",
            "capability_category": category,
            "tags_json": ["builtin", "evalscope", category],
            "input_schema_json": {},
            "output_schema_json": {},
            "status": "active",
        },
        "version": {
            "id": UUID(version_id),
            "spec_id": UUID(spec_id),
            "version": "builtin-v1",
            "display_name": f"{display_name} Builtin v1",
            "description": description,
            "engine": "evalscope",
            "execution_mode": "builtin",
            "engine_benchmark_name": benchmark_name,
            "engine_config_json": {"dataset_args": {}},
            "scoring_config_json": {},
            "dataset_source_uri": None,
            "template_spec_version_id": None,
            "default_judge_policy_id": None,
            "sample_count": None,
            "enabled": True,
            "is_recommended": True,
        },
    }


def downgrade() -> None:
    op.drop_index("ix_evaluation_run_events_run_item_id", table_name="evaluation_run_events")
    op.drop_index("ix_evaluation_run_events_run_id", table_name="evaluation_run_events")
    op.drop_table("evaluation_run_events")

    op.drop_index("ix_evaluation_run_artifacts_run_item_id", table_name="evaluation_run_artifacts")
    op.drop_index("ix_evaluation_run_artifacts_run_id", table_name="evaluation_run_artifacts")
    op.drop_table("evaluation_run_artifacts")

    op.drop_index("ix_evaluation_run_samples_sample_id", table_name="evaluation_run_samples")
    op.drop_index("ix_evaluation_run_samples_run_item_id", table_name="evaluation_run_samples")
    op.drop_table("evaluation_run_samples")

    op.drop_index("ix_evaluation_run_metrics_run_item_id", table_name="evaluation_run_metrics")
    op.drop_index("ix_evaluation_run_metrics_run_id", table_name="evaluation_run_metrics")
    op.drop_table("evaluation_run_metrics")

    op.drop_index("ix_evaluation_run_items_temporal_workflow_id", table_name="evaluation_run_items")
    op.drop_index("ix_evaluation_run_items_status", table_name="evaluation_run_items")
    op.drop_index("ix_evaluation_run_items_run_id", table_name="evaluation_run_items")
    op.drop_table("evaluation_run_items")

    op.drop_index("ix_evaluation_runs_temporal_workflow_id", table_name="evaluation_runs")
    op.drop_index("ix_evaluation_runs_status", table_name="evaluation_runs")
    op.drop_index("ix_evaluation_runs_project_id", table_name="evaluation_runs")
    op.drop_table("evaluation_runs")

    op.drop_index("ix_eval_suite_items_spec_version_id", table_name="eval_suite_items")
    op.drop_index("ix_eval_suite_items_suite_version_id", table_name="eval_suite_items")
    op.drop_table("eval_suite_items")

    op.drop_index("ix_eval_suite_versions_suite_id", table_name="eval_suite_versions")
    op.drop_table("eval_suite_versions")

    op.drop_index("ix_eval_suites_project_id", table_name="eval_suites")
    op.drop_index("ix_eval_suites_name", table_name="eval_suites")
    op.drop_table("eval_suites")

    op.drop_index("ix_eval_spec_versions_spec_id", table_name="eval_spec_versions")
    op.drop_table("eval_spec_versions")

    op.drop_index("ix_judge_policies_project_id", table_name="judge_policies")
    op.drop_index("ix_judge_policies_name", table_name="judge_policies")
    op.drop_table("judge_policies")

    op.drop_index("ix_template_spec_versions_template_spec_id", table_name="template_spec_versions")
    op.drop_table("template_spec_versions")

    op.drop_index("ix_template_specs_project_id", table_name="template_specs")
    op.drop_index("ix_template_specs_name", table_name="template_specs")
    op.drop_table("template_specs")

    op.drop_index("ix_eval_specs_project_id", table_name="eval_specs")
    op.drop_index("ix_eval_specs_name", table_name="eval_specs")
    op.drop_table("eval_specs")
