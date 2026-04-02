"""init schema – squashed from 16 migrations

Revision ID: 0001
Revises:
Create Date: 2026-03-30
"""

from __future__ import annotations

import json
import os
from collections.abc import Sequence
from pathlib import Path
from uuid import uuid4

import sqlalchemy as sa
from alembic import op
from sqlalchemy import text
from sqlalchemy.dialects import postgresql

revision: str = "0001"
down_revision: str | None = None
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None

# ---------------------------------------------------------------------------
# Paths to builtin benchmark meta JSON files
# ---------------------------------------------------------------------------
_MIGRATIONS_ROOT = Path(__file__).resolve().parents[2]
_META_DIR_CANDIDATES = (
    _MIGRATIONS_ROOT / "src" / "nta_backend" / "evaluation" / "catalog" / "builtin_meta",
    _MIGRATIONS_ROOT / "src" / "nta_backend" / "eval_catalog" / "builtin_meta",
)


# ---------------------------------------------------------------------------
# Schema
# ---------------------------------------------------------------------------

def upgrade() -> None:
    # -- users --
    op.create_table(
        "users",
        sa.Column("id", sa.dialects.postgresql.UUID(as_uuid=True), primary_key=True, default=uuid4),
        sa.Column("email", sa.String(255), nullable=False, unique=True, index=True),
        sa.Column("name", sa.String(120), nullable=False),
        sa.Column("avatar_url", sa.Text, nullable=True),
        sa.Column("status", sa.String(32), nullable=False, server_default="active"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )

    # -- projects --
    op.create_table(
        "projects",
        sa.Column("id", sa.dialects.postgresql.UUID(as_uuid=True), primary_key=True, default=uuid4),
        sa.Column("name", sa.String(120), nullable=False),
        sa.Column("code", sa.String(64), nullable=False, unique=True),
        sa.Column("description", sa.Text, nullable=True),
        sa.Column("created_by", sa.dialects.postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("status", sa.String(32), nullable=False, server_default="active"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )

    # -- project_members --
    op.create_table(
        "project_members",
        sa.Column("id", sa.dialects.postgresql.UUID(as_uuid=True), primary_key=True, default=uuid4),
        sa.Column("project_id", sa.dialects.postgresql.UUID(as_uuid=True), sa.ForeignKey("projects.id", ondelete="CASCADE"), nullable=False),
        sa.Column("user_id", sa.dialects.postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("role", sa.String(32), nullable=False, server_default="member"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_project_members_project_user", "project_members", ["project_id", "user_id"], unique=True)

    # -- api_keys --
    op.create_table(
        "api_keys",
        sa.Column("id", sa.dialects.postgresql.UUID(as_uuid=True), primary_key=True, default=uuid4),
        sa.Column("project_id", sa.dialects.postgresql.UUID(as_uuid=True), sa.ForeignKey("projects.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("name", sa.String(120), nullable=False),
        sa.Column("key_prefix", sa.String(32), nullable=False, index=True),
        sa.Column("key_hash", sa.String(128), nullable=False, unique=True),
        sa.Column("last_used_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_by", sa.dialects.postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("status", sa.String(32), nullable=False, server_default="active"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )

    # -- datasets --
    op.create_table(
        "datasets",
        sa.Column("id", sa.dialects.postgresql.UUID(as_uuid=True), primary_key=True, default=uuid4),
        sa.Column("project_id", sa.dialects.postgresql.UUID(as_uuid=True), sa.ForeignKey("projects.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("name", sa.String(120), nullable=False),
        sa.Column("description", sa.Text, nullable=True),
        sa.Column("purpose", sa.String(64), nullable=True),
        sa.Column("format", sa.String(32), nullable=True),
        sa.Column("use_case", sa.String(64), nullable=True),
        sa.Column("modality", sa.String(32), nullable=True),
        sa.Column("recipe", sa.String(64), nullable=True),
        sa.Column("scope", sa.String(32), nullable=False, server_default="my-datasets"),
        sa.Column("source_type", sa.String(32), nullable=True),
        sa.Column("source_uri", sa.Text, nullable=True),
        sa.Column("owner_name", sa.String(120), nullable=True),
        sa.Column("tags", postgresql.JSONB, nullable=False, server_default="[]"),
        sa.Column("latest_version_id", sa.dialects.postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("created_by", sa.dialects.postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("status", sa.String(32), nullable=False, server_default="active"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )

    # -- dataset_versions --
    op.create_table(
        "dataset_versions",
        sa.Column("id", sa.dialects.postgresql.UUID(as_uuid=True), primary_key=True, default=uuid4),
        sa.Column("dataset_id", sa.dialects.postgresql.UUID(as_uuid=True), sa.ForeignKey("datasets.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("version", sa.Integer, nullable=False, server_default="1"),
        sa.Column("description", sa.Text, nullable=True),
        sa.Column("format", sa.String(32), nullable=True),
        sa.Column("source_type", sa.String(32), nullable=True),
        sa.Column("source_uri", sa.Text, nullable=True),
        sa.Column("object_key", sa.Text, nullable=True),
        sa.Column("file_size", sa.BigInteger, nullable=True),
        sa.Column("record_count", sa.BigInteger, nullable=True),
        sa.Column("import_job_id", sa.dialects.postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("created_by", sa.dialects.postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("status", sa.String(32), nullable=False, server_default="active"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_dataset_versions_dataset_version", "dataset_versions", ["dataset_id", "version"], unique=True)

    # -- dataset_files --
    op.create_table(
        "dataset_files",
        sa.Column("id", sa.dialects.postgresql.UUID(as_uuid=True), primary_key=True, default=uuid4),
        sa.Column("dataset_version_id", sa.dialects.postgresql.UUID(as_uuid=True), sa.ForeignKey("dataset_versions.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("file_name", sa.String(255), nullable=False),
        sa.Column("object_key", sa.Text, nullable=False),
        sa.Column("mime_type", sa.String(120), nullable=True),
        sa.Column("size_bytes", sa.BigInteger, nullable=True),
        sa.Column("etag", sa.String(128), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )

    # -- model_providers --
    op.create_table(
        "model_providers",
        sa.Column("id", sa.dialects.postgresql.UUID(as_uuid=True), primary_key=True, default=uuid4),
        sa.Column("project_id", sa.dialects.postgresql.UUID(as_uuid=True), sa.ForeignKey("projects.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("name", sa.String(120), nullable=False),
        sa.Column("provider_type", sa.String(64), nullable=False, server_default="openai-compatible"),
        sa.Column("adapter", sa.String(32), nullable=False, server_default="litellm"),
        sa.Column("api_format", sa.String(32), nullable=False, server_default="chat-completions"),
        sa.Column("base_url", sa.Text, nullable=False),
        sa.Column("api_key", sa.Text, nullable=True),
        sa.Column("organization", sa.String(120), nullable=True),
        sa.Column("description", sa.Text, nullable=True),
        sa.Column("headers_json", postgresql.JSONB, nullable=True),
        sa.Column("last_synced_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_by", sa.dialects.postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("status", sa.String(32), nullable=False, server_default="active"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_model_providers_project_name", "model_providers", ["project_id", "name"], unique=True)

    # -- models --
    op.create_table(
        "models",
        sa.Column("id", sa.dialects.postgresql.UUID(as_uuid=True), primary_key=True, default=uuid4),
        sa.Column("project_id", sa.dialects.postgresql.UUID(as_uuid=True), sa.ForeignKey("projects.id", ondelete="CASCADE"), nullable=True, index=True),
        sa.Column("provider_id", sa.dialects.postgresql.UUID(as_uuid=True), sa.ForeignKey("model_providers.id", ondelete="SET NULL"), nullable=True),
        sa.Column("name", sa.String(120), nullable=False),
        sa.Column("model_code", sa.String(160), nullable=True),
        sa.Column("vendor", sa.String(64), nullable=True),
        sa.Column("source", sa.String(64), nullable=True),
        sa.Column("api_format", sa.String(32), nullable=True),
        sa.Column("base_model", sa.String(120), nullable=True),
        sa.Column("category", sa.String(64), nullable=True),
        sa.Column("description", sa.Text, nullable=True),
        sa.Column("capabilities_json", postgresql.JSONB, nullable=True),
        sa.Column("is_provider_managed", sa.Boolean, nullable=False, server_default="false"),
        sa.Column("last_synced_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_by", sa.dialects.postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("status", sa.String(32), nullable=False, server_default="active"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_models_provider_model_code", "models", ["provider_id", "model_code"], unique=True)

    # -- endpoints --
    op.create_table(
        "endpoints",
        sa.Column("id", sa.dialects.postgresql.UUID(as_uuid=True), primary_key=True, default=uuid4),
        sa.Column("project_id", sa.dialects.postgresql.UUID(as_uuid=True), sa.ForeignKey("projects.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("name", sa.String(120), nullable=False),
        sa.Column("endpoint_type", sa.String(64), nullable=False),
        sa.Column("model_id", sa.dialects.postgresql.UUID(as_uuid=True), sa.ForeignKey("models.id"), nullable=True),
        sa.Column("purchase_type", sa.String(64), nullable=True),
        sa.Column("config_json", postgresql.JSONB, nullable=True),
        sa.Column("created_by", sa.dialects.postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("status", sa.String(32), nullable=False, server_default="active"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )

    # -- eval_collections --
    op.create_table(
        "eval_collections",
        sa.Column("id", sa.dialects.postgresql.UUID(as_uuid=True), primary_key=True, default=uuid4),
        sa.Column("project_id", sa.dialects.postgresql.UUID(as_uuid=True), sa.ForeignKey("projects.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("description", sa.Text, nullable=True),
        sa.Column("schema_json", postgresql.JSONB, nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )

    # -- eval_jobs --
    op.create_table(
        "eval_jobs",
        sa.Column("id", sa.dialects.postgresql.UUID(as_uuid=True), primary_key=True, default=uuid4),
        sa.Column("project_id", sa.dialects.postgresql.UUID(as_uuid=True), sa.ForeignKey("projects.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("name", sa.String(120), nullable=False),
        sa.Column("description", sa.Text, nullable=True),
        sa.Column("created_by_name", sa.String(120), nullable=True),
        sa.Column("model_source", sa.String(64), nullable=True),
        sa.Column("model_name", sa.String(255), nullable=True),
        sa.Column("model_id", sa.dialects.postgresql.UUID(as_uuid=True), sa.ForeignKey("models.id"), nullable=True),
        sa.Column("access_source", sa.String(32), nullable=True),
        sa.Column("benchmark_name", sa.String(120), nullable=True),
        sa.Column("benchmark_version_id", sa.String(120), nullable=True),
        sa.Column("benchmark_config_json", postgresql.JSONB, nullable=True),
        sa.Column("inference_mode", sa.String(64), nullable=True),
        sa.Column("task_type", sa.String(64), nullable=True),
        sa.Column("eval_mode", sa.String(64), nullable=True),
        sa.Column("eval_method", sa.String(64), nullable=True),
        sa.Column("criteria_text", sa.Text, nullable=True),
        sa.Column("endpoint_name", sa.String(120), nullable=True),
        sa.Column("judge_model_name", sa.String(255), nullable=True),
        sa.Column("judge_prompt_text", sa.Text, nullable=True),
        sa.Column("dataset_version_id", sa.dialects.postgresql.UUID(as_uuid=True), sa.ForeignKey("dataset_versions.id"), nullable=True),
        sa.Column("dataset_source_type", sa.String(32), nullable=True),
        sa.Column("dataset_name", sa.String(255), nullable=True),
        sa.Column("dataset_source_uri", sa.Text, nullable=True),
        sa.Column("artifact_prefix_uri", sa.Text, nullable=True),
        sa.Column("source_object_uri", sa.Text, nullable=True),
        sa.Column("results_prefix_uri", sa.Text, nullable=True),
        sa.Column("samples_prefix_uri", sa.Text, nullable=True),
        sa.Column("report_object_uri", sa.Text, nullable=True),
        sa.Column("temporal_workflow_id", sa.String(128), nullable=True, index=True),
        sa.Column("batch_job_id", sa.String(128), nullable=True),
        sa.Column("auto_progress", sa.Boolean, nullable=False, server_default="false"),
        sa.Column("progress_total", sa.BigInteger, nullable=True),
        sa.Column("progress_done", sa.BigInteger, nullable=True),
        sa.Column("cancel_requested", sa.Boolean, nullable=False, server_default="false"),
        sa.Column("collection_id", sa.dialects.postgresql.UUID(as_uuid=True), sa.ForeignKey("eval_collections.id", ondelete="SET NULL"), nullable=True, index=True),
        # JobStateMixin
        sa.Column("created_by", sa.dialects.postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("status", sa.String(32), nullable=False, server_default="active"),
        sa.Column("error_code", sa.String(64), nullable=True),
        sa.Column("error_message", sa.String(500), nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )

    # -- eval_job_metrics --
    op.create_table(
        "eval_job_metrics",
        sa.Column("id", sa.dialects.postgresql.UUID(as_uuid=True), primary_key=True, default=uuid4),
        sa.Column("eval_job_id", sa.dialects.postgresql.UUID(as_uuid=True), sa.ForeignKey("eval_jobs.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("metric_name", sa.String(120), nullable=False),
        sa.Column("metric_value", sa.Float, nullable=False),
        sa.Column("metric_unit", sa.String(32), nullable=True),
        sa.Column("extra_json", postgresql.JSONB, nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )

    # -- batch_jobs --
    op.create_table(
        "batch_jobs",
        sa.Column("id", sa.dialects.postgresql.UUID(as_uuid=True), primary_key=True, default=uuid4),
        sa.Column("project_id", sa.dialects.postgresql.UUID(as_uuid=True), sa.ForeignKey("projects.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("name", sa.String(120), nullable=False),
        sa.Column("description", sa.Text, nullable=True),
        sa.Column("endpoint_id", sa.dialects.postgresql.UUID(as_uuid=True), sa.ForeignKey("endpoints.id"), nullable=True),
        sa.Column("input_object_key", sa.Text, nullable=True),
        sa.Column("output_object_key", sa.Text, nullable=True),
        sa.Column("temporal_workflow_id", sa.String(128), nullable=True, index=True),
        sa.Column("progress_total", sa.BigInteger, nullable=True),
        sa.Column("progress_done", sa.BigInteger, nullable=True),
        # JobStateMixin
        sa.Column("created_by", sa.dialects.postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("status", sa.String(32), nullable=False, server_default="active"),
        sa.Column("error_code", sa.String(64), nullable=True),
        sa.Column("error_message", sa.String(500), nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )

    # -- job_logs --
    op.create_table(
        "job_logs",
        sa.Column("id", sa.dialects.postgresql.UUID(as_uuid=True), primary_key=True, default=uuid4),
        sa.Column("project_id", sa.dialects.postgresql.UUID(as_uuid=True), sa.ForeignKey("projects.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("job_type", sa.String(64), nullable=False),
        sa.Column("job_id", sa.dialects.postgresql.UUID(as_uuid=True), nullable=False, index=True),
        sa.Column("level", sa.String(24), nullable=False, server_default="info"),
        sa.Column("message", sa.Text, nullable=False),
        sa.Column("payload_json", postgresql.JSONB, nullable=True),
        sa.Column("logged_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )

    # -- benchmark_definitions --
    op.create_table(
        "benchmark_definitions",
        sa.Column("id", sa.dialects.postgresql.UUID(as_uuid=True), primary_key=True, default=uuid4),
        sa.Column("name", sa.String(120), nullable=False, unique=True, index=True),
        sa.Column("display_name", sa.String(255), nullable=False),
        sa.Column("description", sa.Text, nullable=True),
        sa.Column("family_name", sa.String(120), nullable=True),
        sa.Column("family_display_name", sa.String(255), nullable=True),
        sa.Column("default_eval_method", sa.String(64), nullable=False),
        sa.Column("sample_schema_json", postgresql.JSONB, nullable=False),
        sa.Column("prompt_schema_json", postgresql.JSONB, nullable=False),
        sa.Column("prompt_config_json", postgresql.JSONB, nullable=False),
        sa.Column("requires_judge_model", sa.Boolean, nullable=False, server_default="false"),
        sa.Column("supports_custom_dataset", sa.Boolean, nullable=False, server_default="false"),
        sa.Column("dataset_id", sa.String(255), nullable=True),
        sa.Column("category", sa.String(64), nullable=True),
        sa.Column("paper_url", sa.Text, nullable=True),
        sa.Column("tags", postgresql.JSONB, nullable=True, server_default="[]"),
        sa.Column("metric_names", postgresql.JSONB, nullable=True, server_default="[]"),
        sa.Column("aggregator_names", postgresql.JSONB, nullable=True, server_default="[]"),
        sa.Column("subset_list", postgresql.JSONB, nullable=True, server_default="[]"),
        sa.Column("prompt_template", sa.Text, nullable=True),
        sa.Column("system_prompt", sa.Text, nullable=True),
        sa.Column("few_shot_prompt_template", sa.Text, nullable=True),
        sa.Column("few_shot_num", sa.Integer, nullable=True),
        sa.Column("eval_split", sa.String(64), nullable=True),
        sa.Column("train_split", sa.String(64), nullable=True),
        sa.Column("sample_example_json", postgresql.JSONB, nullable=True),
        sa.Column("statistics_json", postgresql.JSONB, nullable=True),
        sa.Column("readme_json", postgresql.JSONB, nullable=True),
        sa.Column("field_mapping_json", postgresql.JSONB, nullable=True),
        sa.Column("adapter_class", sa.String(255), nullable=True),
        sa.Column("source_type", sa.String(32), nullable=True, server_default="builtin"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )

    # -- benchmark_versions --
    op.create_table(
        "benchmark_versions",
        sa.Column("id", sa.dialects.postgresql.UUID(as_uuid=True), primary_key=True, default=uuid4),
        sa.Column("benchmark_id", sa.dialects.postgresql.UUID(as_uuid=True), sa.ForeignKey("benchmark_definitions.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("version_id", sa.String(120), nullable=False),
        sa.Column("display_name", sa.String(255), nullable=False),
        sa.Column("description", sa.Text, nullable=True),
        sa.Column("dataset_path", sa.Text, nullable=True),
        sa.Column("dataset_source_uri", sa.Text, nullable=True),
        sa.Column("sample_count", sa.BigInteger, nullable=False, server_default="0"),
        sa.Column("enabled", sa.Boolean, nullable=False, server_default="true"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.UniqueConstraint("benchmark_id", "version_id"),
    )

    # -- lake_batches --
    op.create_table(
        "lake_batches",
        sa.Column("id", sa.dialects.postgresql.UUID(as_uuid=True), primary_key=True, default=uuid4),
        sa.Column("project_id", sa.dialects.postgresql.UUID(as_uuid=True), sa.ForeignKey("projects.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("description", sa.Text, nullable=True),
        sa.Column("source_type", sa.String(64), nullable=False, server_default="upload"),
        sa.Column("resource_type", sa.String(64), nullable=True),
        sa.Column("stage", sa.String(32), nullable=False, server_default="raw"),
        sa.Column("planned_file_count", sa.Integer, nullable=False, server_default="1"),
        sa.Column("completed_file_count", sa.Integer, nullable=False, server_default="0"),
        sa.Column("failed_file_count", sa.Integer, nullable=False, server_default="0"),
        sa.Column("total_size_bytes", sa.BigInteger, nullable=False, server_default="0"),
        sa.Column("tags", postgresql.JSONB, nullable=False, server_default="[]"),
        sa.Column("metadata", postgresql.JSONB, nullable=False, server_default="{}"),
        sa.Column("created_by", sa.dialects.postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("status", sa.String(32), nullable=False, server_default="active"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )

    # -- lake_assets --
    op.create_table(
        "lake_assets",
        sa.Column("id", sa.dialects.postgresql.UUID(as_uuid=True), primary_key=True, default=uuid4),
        sa.Column("project_id", sa.dialects.postgresql.UUID(as_uuid=True), sa.ForeignKey("projects.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("batch_id", sa.dialects.postgresql.UUID(as_uuid=True), sa.ForeignKey("lake_batches.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("parent_asset_id", sa.dialects.postgresql.UUID(as_uuid=True), sa.ForeignKey("lake_assets.id", ondelete="SET NULL"), nullable=True, index=True),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("description", sa.Text, nullable=True),
        sa.Column("stage", sa.String(32), nullable=False, server_default="raw"),
        sa.Column("source_type", sa.String(64), nullable=False, server_default="upload"),
        sa.Column("resource_type", sa.String(64), nullable=True),
        sa.Column("format", sa.String(64), nullable=True),
        sa.Column("mime_type", sa.String(120), nullable=True),
        sa.Column("relative_path", sa.Text, nullable=True),
        sa.Column("object_key", sa.Text, nullable=True),
        sa.Column("source_uri", sa.Text, nullable=True),
        sa.Column("size_bytes", sa.BigInteger, nullable=True),
        sa.Column("etag", sa.String(128), nullable=True),
        sa.Column("checksum", sa.String(128), nullable=True),
        sa.Column("record_count", sa.BigInteger, nullable=True),
        sa.Column("tags", postgresql.JSONB, nullable=False, server_default="[]"),
        sa.Column("metadata", postgresql.JSONB, nullable=False, server_default="{}"),
        sa.Column("error_message", sa.Text, nullable=True),
        sa.Column("created_by", sa.dialects.postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("status", sa.String(32), nullable=False, server_default="active"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_lake_assets_project_stage", "lake_assets", ["project_id", "stage"])
    op.create_index("ix_lake_assets_batch_created", "lake_assets", ["batch_id", "created_at"])

    # -- quota_rules --
    op.create_table(
        "quota_rules",
        sa.Column("id", sa.dialects.postgresql.UUID(as_uuid=True), primary_key=True, default=uuid4),
        sa.Column("project_id", sa.dialects.postgresql.UUID(as_uuid=True), sa.ForeignKey("projects.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("resource_type", sa.String(64), nullable=False),
        sa.Column("resource_code", sa.String(120), nullable=False),
        sa.Column("account_quota", sa.BigInteger, nullable=True),
        sa.Column("shared_ratio", sa.Float, nullable=True),
        sa.Column("exclusive_ratio", sa.Float, nullable=True),
        sa.Column("updated_by", sa.dialects.postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )

    # -- usage_events --
    op.create_table(
        "usage_events",
        sa.Column("id", sa.dialects.postgresql.UUID(as_uuid=True), primary_key=True, default=uuid4),
        sa.Column("project_id", sa.dialects.postgresql.UUID(as_uuid=True), sa.ForeignKey("projects.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("resource_type", sa.String(64), nullable=False),
        sa.Column("resource_id", sa.dialects.postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("model_code", sa.String(120), nullable=True),
        sa.Column("input_tokens", sa.BigInteger, nullable=True),
        sa.Column("output_tokens", sa.BigInteger, nullable=True),
        sa.Column("request_count", sa.BigInteger, nullable=True),
        sa.Column("occurred_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )

    # -- usage_daily_agg --
    op.create_table(
        "usage_daily_agg",
        sa.Column("id", sa.dialects.postgresql.UUID(as_uuid=True), primary_key=True, default=uuid4),
        sa.Column("project_id", sa.dialects.postgresql.UUID(as_uuid=True), sa.ForeignKey("projects.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("date", sa.Date, nullable=False),
        sa.Column("model_code", sa.String(120), nullable=True),
        sa.Column("endpoint_id", sa.dialects.postgresql.UUID(as_uuid=True), sa.ForeignKey("endpoints.id"), nullable=True),
        sa.Column("input_tokens", sa.BigInteger, nullable=True),
        sa.Column("output_tokens", sa.BigInteger, nullable=True),
        sa.Column("request_count", sa.BigInteger, nullable=True),
    )
    op.create_index("ix_usage_daily_project_date_model", "usage_daily_agg", ["project_id", "date", "model_code"])

    # -- security_events --
    op.create_table(
        "security_events",
        sa.Column("id", sa.dialects.postgresql.UUID(as_uuid=True), primary_key=True, default=uuid4),
        sa.Column("project_id", sa.dialects.postgresql.UUID(as_uuid=True), sa.ForeignKey("projects.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("endpoint_id", sa.dialects.postgresql.UUID(as_uuid=True), sa.ForeignKey("endpoints.id"), nullable=True),
        sa.Column("risk_type", sa.String(64), nullable=False),
        sa.Column("severity", sa.String(24), nullable=False),
        sa.Column("count", sa.Integer, nullable=False, server_default="0"),
        sa.Column("event_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )

    # -- vpc_bindings --
    op.create_table(
        "vpc_bindings",
        sa.Column("id", sa.dialects.postgresql.UUID(as_uuid=True), primary_key=True, default=uuid4),
        sa.Column("project_id", sa.dialects.postgresql.UUID(as_uuid=True), sa.ForeignKey("projects.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("vpc_id", sa.String(120), nullable=False),
        sa.Column("subnet_id", sa.String(120), nullable=True),
        sa.Column("private_link_service_id", sa.String(120), nullable=True),
        sa.Column("status", sa.String(32), nullable=False, server_default="pending"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )

    # -----------------------------------------------------------------------
    # Seed builtin benchmark metadata from JSON files
    # -----------------------------------------------------------------------
    _seed_builtin_benchmarks()


def _seed_builtin_benchmarks() -> None:
    meta_dir = next((path for path in _META_DIR_CANDIDATES if path.is_dir()), None)
    if meta_dir is None:
        return

    conn = op.get_bind()

    for filepath in sorted(meta_dir.glob("*.json")):
        row = _load_meta_file(os.fspath(filepath))
        if row is None:
            continue

        row["id"] = str(uuid4())
        row["default_eval_method"] = "judge-rubric"
        row["sample_schema_json"] = json.dumps({"type": "object"})
        row["prompt_schema_json"] = json.dumps({"type": "object"})
        row["prompt_config_json"] = json.dumps({})
        row["aggregator_names"] = json.dumps([])
        conn.execute(
            text("""
                INSERT INTO benchmark_definitions (
                    id, name, display_name, description, default_eval_method,
                    sample_schema_json, prompt_schema_json, prompt_config_json,
                    requires_judge_model, supports_custom_dataset,
                    family_name, family_display_name, dataset_id, category, paper_url,
                    tags, metric_names, aggregator_names, subset_list,
                    prompt_template, system_prompt, few_shot_prompt_template,
                    few_shot_num, eval_split, train_split,
                    sample_example_json, statistics_json, readme_json,
                    source_type
                ) VALUES (
                    :id, :name, :display_name, :description, :default_eval_method,
                    CAST(:sample_schema_json AS jsonb), CAST(:prompt_schema_json AS jsonb), CAST(:prompt_config_json AS jsonb),
                    false, false,
                    :family_name, :family_display_name, :dataset_id, :category, :paper_url,
                    CAST(:tags AS jsonb), CAST(:metric_names AS jsonb), CAST(:aggregator_names AS jsonb), CAST(:subset_list AS jsonb),
                    :prompt_template, :system_prompt, :few_shot_prompt_template,
                    :few_shot_num, :eval_split, :train_split,
                    CAST(:sample_example_json AS jsonb), CAST(:statistics_json AS jsonb), CAST(:readme_json AS jsonb),
                    :source_type
                )
            """),
            row,
        )


# ---------------------------------------------------------------------------
# Helpers for loading builtin meta JSON
# ---------------------------------------------------------------------------

def _normalize_string_list(value: object) -> list[str]:
    if not isinstance(value, list):
        return []
    return [item.strip() for item in value if isinstance(item, str) and item.strip()]


def _normalize_optional_dict(value: object) -> dict | None:
    return value if isinstance(value, dict) else None


def _load_meta_file(path: str) -> dict | None:
    try:
        with open(path, encoding="utf-8") as f:
            payload = json.load(f)
    except (json.JSONDecodeError, OSError):
        return None

    if not isinstance(payload, dict):
        return None

    raw_meta = payload.get("meta") if isinstance(payload, dict) else None
    meta = raw_meta if isinstance(raw_meta, dict) else {}

    name = os.path.splitext(os.path.basename(path))[0]
    display_name = str(meta.get("pretty_name") or name).strip() or name

    few_shot_num = meta.get("few_shot_num")
    if not isinstance(few_shot_num, int) or isinstance(few_shot_num, bool):
        few_shot_num = None

    return {
        "name": name,
        "display_name": display_name,
        "description": str(meta.get("description") or "").strip(),
        "family_name": str(meta.get("family_name")).strip() if meta.get("family_name") else None,
        "family_display_name": (
            str(meta.get("family_display_name")).strip()
            if meta.get("family_display_name")
            else None
        ),
        "dataset_id": str(meta.get("dataset_id")).strip() if meta.get("dataset_id") else None,
        "category": str(meta.get("category")).strip() if meta.get("category") else None,
        "paper_url": str(meta.get("paper_url")).strip() if meta.get("paper_url") else None,
        "tags": json.dumps(_normalize_string_list(meta.get("tags"))),
        "metric_names": json.dumps(_normalize_string_list(meta.get("metrics"))),
        "few_shot_num": few_shot_num,
        "eval_split": str(meta.get("eval_split")).strip() if meta.get("eval_split") else None,
        "train_split": str(meta.get("train_split")).strip() if meta.get("train_split") else None,
        "subset_list": json.dumps(_normalize_string_list(meta.get("subset_list"))),
        "prompt_template": (
            str(meta.get("prompt_template")).strip() if meta.get("prompt_template") else None
        ),
        "system_prompt": (
            str(meta.get("system_prompt")).strip() if meta.get("system_prompt") else None
        ),
        "few_shot_prompt_template": (
            str(meta.get("few_shot_prompt_template")).strip()
            if meta.get("few_shot_prompt_template")
            else None
        ),
        "sample_example_json": json.dumps(_normalize_optional_dict(payload.get("sample_example"))),
        "statistics_json": json.dumps(_normalize_optional_dict(payload.get("statistics"))),
        "readme_json": json.dumps(_normalize_optional_dict(payload.get("readme"))),
        "source_type": "builtin",
    }


def downgrade() -> None:
    op.drop_table("vpc_bindings")
    op.drop_table("security_events")
    op.drop_table("usage_daily_agg")
    op.drop_table("usage_events")
    op.drop_table("quota_rules")
    op.drop_table("lake_assets")
    op.drop_table("lake_batches")
    op.drop_table("benchmark_versions")
    op.drop_table("benchmark_definitions")
    op.drop_table("job_logs")
    op.drop_table("batch_jobs")
    op.drop_table("eval_job_metrics")
    op.drop_table("eval_jobs")
    op.drop_table("eval_collections")
    op.drop_table("endpoints")
    op.drop_table("models")
    op.drop_table("model_providers")
    op.drop_table("dataset_files")
    op.drop_table("dataset_versions")
    op.drop_table("datasets")
    op.drop_table("api_keys")
    op.drop_table("project_members")
    op.drop_table("projects")
    op.drop_table("users")
