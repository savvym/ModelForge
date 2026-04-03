from sqlalchemy import BigInteger, Boolean, Float, ForeignKey, Integer, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import relationship

from nta_backend.models.base import (
    JSONB,
    UUID,
    Base,
    CreatedByMixin,
    DateTime,
    Mapped,
    PythonUUID,
    StatusMixin,
    String,
    TimestampMixin,
    UUIDPrimaryKeyMixin,
    mapped_column,
)


class EvalSpec(Base, UUIDPrimaryKeyMixin, TimestampMixin, StatusMixin):
    __tablename__ = "eval_specs"
    __table_args__ = (UniqueConstraint("name"),)

    project_id: Mapped[PythonUUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("projects.id", ondelete="CASCADE"),
        nullable=True,
        index=True,
    )
    name: Mapped[str] = mapped_column(String(120), nullable=False, index=True)
    display_name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    capability_group: Mapped[str | None] = mapped_column(String(120), nullable=True)
    capability_category: Mapped[str | None] = mapped_column(String(120), nullable=True)
    tags_json: Mapped[list] = mapped_column(JSONB, nullable=False, default=list)
    input_schema_json: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    output_schema_json: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)

    versions = relationship(
        "EvalSpecVersion",
        back_populates="spec",
        cascade="all, delete-orphan",
        order_by="EvalSpecVersion.created_at.asc()",
    )


class TemplateSpec(Base, UUIDPrimaryKeyMixin, TimestampMixin, StatusMixin):
    __tablename__ = "template_specs"
    __table_args__ = (UniqueConstraint("project_id", "name"),)

    project_id: Mapped[PythonUUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("projects.id", ondelete="CASCADE"),
        nullable=True,
        index=True,
    )
    name: Mapped[str] = mapped_column(String(120), nullable=False, index=True)
    display_name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    template_type: Mapped[str] = mapped_column(String(64), nullable=False)

    versions = relationship(
        "TemplateSpecVersion",
        back_populates="template_spec",
        cascade="all, delete-orphan",
        order_by="TemplateSpecVersion.version.asc()",
    )


class TemplateSpecVersion(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "template_spec_versions"
    __table_args__ = (UniqueConstraint("template_spec_id", "version"),)

    template_spec_id: Mapped[PythonUUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("template_specs.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    version: Mapped[int] = mapped_column(Integer, nullable=False)
    prompt: Mapped[str] = mapped_column(Text, nullable=False)
    vars_json: Mapped[list] = mapped_column(JSONB, nullable=False, default=list)
    output_schema_json: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    parser_config_json: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)

    template_spec = relationship("TemplateSpec", back_populates="versions")


class JudgePolicy(Base, UUIDPrimaryKeyMixin, TimestampMixin, StatusMixin):
    __tablename__ = "judge_policies"
    __table_args__ = (UniqueConstraint("project_id", "name"),)

    project_id: Mapped[PythonUUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("projects.id", ondelete="CASCADE"),
        nullable=True,
        index=True,
    )
    name: Mapped[str] = mapped_column(String(120), nullable=False, index=True)
    display_name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    strategy: Mapped[str] = mapped_column(String(64), nullable=False, default="judge-template")
    template_spec_version_id: Mapped[PythonUUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("template_spec_versions.id", ondelete="SET NULL"),
        nullable=True,
    )
    model_selector_json: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    execution_params_json: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    parser_config_json: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    retry_policy_json: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)


class EvalSpecVersion(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "eval_spec_versions"
    __table_args__ = (UniqueConstraint("spec_id", "version"),)

    spec_id: Mapped[PythonUUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("eval_specs.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    version: Mapped[str] = mapped_column(String(120), nullable=False)
    display_name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    engine: Mapped[str] = mapped_column(String(64), nullable=False)
    execution_mode: Mapped[str] = mapped_column(String(64), nullable=False)
    engine_benchmark_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    engine_config_json: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    scoring_config_json: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    dataset_source_uri: Mapped[str | None] = mapped_column(Text, nullable=True)
    template_spec_version_id: Mapped[PythonUUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("template_spec_versions.id", ondelete="SET NULL"),
        nullable=True,
    )
    default_judge_policy_id: Mapped[PythonUUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("judge_policies.id", ondelete="SET NULL"),
        nullable=True,
    )
    sample_count: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    is_recommended: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)

    spec = relationship("EvalSpec", back_populates="versions")


class EvalSuite(Base, UUIDPrimaryKeyMixin, TimestampMixin, StatusMixin):
    __tablename__ = "eval_suites"
    __table_args__ = (UniqueConstraint("name"),)

    project_id: Mapped[PythonUUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("projects.id", ondelete="CASCADE"),
        nullable=True,
        index=True,
    )
    name: Mapped[str] = mapped_column(String(120), nullable=False, index=True)
    display_name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    capability_group: Mapped[str | None] = mapped_column(String(120), nullable=True)

    versions = relationship(
        "EvalSuiteVersion",
        back_populates="suite",
        cascade="all, delete-orphan",
        order_by="EvalSuiteVersion.created_at.asc()",
    )


class EvalSuiteVersion(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "eval_suite_versions"
    __table_args__ = (UniqueConstraint("suite_id", "version"),)

    suite_id: Mapped[PythonUUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("eval_suites.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    version: Mapped[str] = mapped_column(String(120), nullable=False)
    display_name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)

    suite = relationship("EvalSuite", back_populates="versions")
    items = relationship(
        "EvalSuiteItem",
        back_populates="suite_version",
        cascade="all, delete-orphan",
        order_by="EvalSuiteItem.position.asc()",
    )


class EvalSuiteItem(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "eval_suite_items"
    __table_args__ = (UniqueConstraint("suite_version_id", "item_key"),)

    suite_version_id: Mapped[PythonUUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("eval_suite_versions.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    item_key: Mapped[str] = mapped_column(String(120), nullable=False)
    display_name: Mapped[str] = mapped_column(String(255), nullable=False)
    spec_version_id: Mapped[PythonUUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("eval_spec_versions.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    position: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    weight: Mapped[float] = mapped_column(Float, nullable=False, default=1.0)
    group_name: Mapped[str | None] = mapped_column(String(120), nullable=True)
    overrides_json: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)

    suite_version = relationship("EvalSuiteVersion", back_populates="items")


class EvaluationRun(Base, UUIDPrimaryKeyMixin, TimestampMixin, CreatedByMixin):
    __tablename__ = "evaluation_runs"

    project_id: Mapped[PythonUUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("projects.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    kind: Mapped[str] = mapped_column(String(32), nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="queued", index=True)
    model_id: Mapped[PythonUUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("models.id", ondelete="SET NULL"),
        nullable=True,
    )
    model_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    source_spec_id: Mapped[PythonUUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("eval_specs.id", ondelete="SET NULL"),
        nullable=True,
    )
    source_spec_version_id: Mapped[PythonUUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("eval_spec_versions.id", ondelete="SET NULL"),
        nullable=True,
    )
    source_suite_id: Mapped[PythonUUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("eval_suites.id", ondelete="SET NULL"),
        nullable=True,
    )
    source_suite_version_id: Mapped[PythonUUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("eval_suite_versions.id", ondelete="SET NULL"),
        nullable=True,
    )
    judge_policy_id: Mapped[PythonUUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("judge_policies.id", ondelete="SET NULL"),
        nullable=True,
    )
    execution_plan_json: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    summary_report_uri: Mapped[str | None] = mapped_column(Text, nullable=True)
    raw_output_prefix_uri: Mapped[str | None] = mapped_column(Text, nullable=True)
    temporal_workflow_id: Mapped[str | None] = mapped_column(String(128), nullable=True, index=True)
    progress_total: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    progress_done: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    cancel_requested: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    error_code: Mapped[str | None] = mapped_column(String(64), nullable=True)
    error_message: Mapped[str | None] = mapped_column(String(500), nullable=True)
    started_at: Mapped[DateTime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    finished_at: Mapped[DateTime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    items = relationship(
        "EvaluationRunItem",
        back_populates="run",
        cascade="all, delete-orphan",
        order_by="EvaluationRunItem.created_at.asc()",
    )


class EvaluationRunItem(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "evaluation_run_items"
    __table_args__ = (UniqueConstraint("run_id", "item_key"),)

    run_id: Mapped[PythonUUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("evaluation_runs.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    item_key: Mapped[str] = mapped_column(String(120), nullable=False)
    display_name: Mapped[str] = mapped_column(String(255), nullable=False)
    group_name: Mapped[str | None] = mapped_column(String(120), nullable=True)
    weight: Mapped[float] = mapped_column(Float, nullable=False, default=1.0)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="queued", index=True)
    spec_id: Mapped[PythonUUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("eval_specs.id", ondelete="SET NULL"),
        nullable=True,
    )
    spec_version_id: Mapped[PythonUUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("eval_spec_versions.id", ondelete="SET NULL"),
        nullable=True,
    )
    engine: Mapped[str] = mapped_column(String(64), nullable=False)
    execution_mode: Mapped[str] = mapped_column(String(64), nullable=False)
    model_binding_json: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    judge_policy_snapshot_json: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    template_snapshot_json: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    plan_json: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    report_uri: Mapped[str | None] = mapped_column(Text, nullable=True)
    raw_output_prefix_uri: Mapped[str | None] = mapped_column(Text, nullable=True)
    temporal_workflow_id: Mapped[str | None] = mapped_column(String(128), nullable=True, index=True)
    progress_total: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    progress_done: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    error_code: Mapped[str | None] = mapped_column(String(64), nullable=True)
    error_message: Mapped[str | None] = mapped_column(String(500), nullable=True)
    started_at: Mapped[DateTime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    finished_at: Mapped[DateTime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    run = relationship("EvaluationRun", back_populates="items")


class EvaluationRunMetric(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "evaluation_run_metrics"

    run_id: Mapped[PythonUUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("evaluation_runs.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    run_item_id: Mapped[PythonUUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("evaluation_run_items.id", ondelete="CASCADE"),
        nullable=True,
        index=True,
    )
    metric_name: Mapped[str] = mapped_column(String(120), nullable=False)
    metric_value: Mapped[float] = mapped_column(Float, nullable=False)
    metric_scope: Mapped[str] = mapped_column(String(32), nullable=False, default="overall")
    metric_unit: Mapped[str | None] = mapped_column(String(32), nullable=True)
    dimension_json: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    extra_json: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)


class EvaluationRunSample(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "evaluation_run_samples"

    run_item_id: Mapped[PythonUUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("evaluation_run_items.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    sample_id: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    subset_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    input_preview: Mapped[str | None] = mapped_column(Text, nullable=True)
    prediction_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    reference_answers_json: Mapped[list] = mapped_column(JSONB, nullable=False, default=list)
    score: Mapped[float | None] = mapped_column(Float, nullable=True)
    raw_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    passed: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    error: Mapped[str | None] = mapped_column(Text, nullable=True)
    latency_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)
    total_tokens: Mapped[int | None] = mapped_column(Integer, nullable=True)
    metadata_json: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)


class EvaluationRunArtifact(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "evaluation_run_artifacts"

    run_id: Mapped[PythonUUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("evaluation_runs.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    run_item_id: Mapped[PythonUUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("evaluation_run_items.id", ondelete="CASCADE"),
        nullable=True,
        index=True,
    )
    artifact_type: Mapped[str] = mapped_column(String(64), nullable=False)
    uri: Mapped[str] = mapped_column(Text, nullable=False)
    content_type: Mapped[str | None] = mapped_column(String(120), nullable=True)
    extra_json: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)


class EvaluationRunEvent(Base, UUIDPrimaryKeyMixin):
    __tablename__ = "evaluation_run_events"

    run_id: Mapped[PythonUUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("evaluation_runs.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    run_item_id: Mapped[PythonUUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("evaluation_run_items.id", ondelete="CASCADE"),
        nullable=True,
        index=True,
    )
    event_type: Mapped[str] = mapped_column(String(64), nullable=False)
    level: Mapped[str] = mapped_column(String(24), nullable=False, default="info")
    message: Mapped[str] = mapped_column(Text, nullable=False)
    payload_json: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    created_at: Mapped[DateTime] = mapped_column(DateTime(timezone=True), nullable=False)
