from sqlalchemy import BigInteger, Boolean, Float, ForeignKey, Text, func
from sqlalchemy.orm import relationship

from nta_backend.models.base import (
    JSONB,
    UUID,
    Base,
    JobStateMixin,
    Mapped,
    PythonUUID,
    String,
    TimestampMixin,
    UUIDPrimaryKeyMixin,
    datetime,
    mapped_column,
)


class EvalJob(Base, UUIDPrimaryKeyMixin, JobStateMixin, TimestampMixin):
    __tablename__ = "eval_jobs"

    project_id: Mapped[PythonUUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("projects.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_by_name: Mapped[str | None] = mapped_column(String(120), nullable=True)
    model_source: Mapped[str | None] = mapped_column(String(64), nullable=True)
    model_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    model_id: Mapped[PythonUUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("models.id"), nullable=True
    )
    access_source: Mapped[str | None] = mapped_column(String(32), nullable=True)
    benchmark_name: Mapped[str | None] = mapped_column(String(120), nullable=True)
    benchmark_version_id: Mapped[str | None] = mapped_column(String(120), nullable=True)
    benchmark_config_json: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    inference_mode: Mapped[str | None] = mapped_column(String(64), nullable=True)
    task_type: Mapped[str | None] = mapped_column(String(64), nullable=True)
    eval_mode: Mapped[str | None] = mapped_column(String(64), nullable=True)
    eval_method: Mapped[str | None] = mapped_column(String(64), nullable=True)
    criteria_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    endpoint_name: Mapped[str | None] = mapped_column(String(120), nullable=True)
    judge_model_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    judge_prompt_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    dataset_version_id: Mapped[PythonUUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("dataset_versions.id"), nullable=True
    )
    dataset_source_type: Mapped[str | None] = mapped_column(String(32), nullable=True)
    dataset_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    dataset_source_uri: Mapped[str | None] = mapped_column(Text, nullable=True)
    artifact_prefix_uri: Mapped[str | None] = mapped_column(Text, nullable=True)
    source_object_uri: Mapped[str | None] = mapped_column(Text, nullable=True)
    results_prefix_uri: Mapped[str | None] = mapped_column(Text, nullable=True)
    samples_prefix_uri: Mapped[str | None] = mapped_column(Text, nullable=True)
    report_object_uri: Mapped[str | None] = mapped_column(Text, nullable=True)
    temporal_workflow_id: Mapped[str | None] = mapped_column(String(128), nullable=True, index=True)
    batch_job_id: Mapped[str | None] = mapped_column(String(128), nullable=True)
    auto_progress: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    progress_total: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    progress_done: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    cancel_requested: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    collection_id: Mapped[PythonUUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("eval_collections.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )

    collection = relationship(
        "EvalCollection",
        back_populates="jobs",
        foreign_keys=[collection_id],
    )


class EvalJobMetric(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "eval_job_metrics"

    eval_job_id: Mapped[PythonUUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("eval_jobs.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    metric_name: Mapped[str] = mapped_column(String(120), nullable=False)
    metric_value: Mapped[float] = mapped_column(Float, nullable=False)
    metric_unit: Mapped[str | None] = mapped_column(String(32), nullable=True)
    extra_json: Mapped[dict | None] = mapped_column(JSONB, nullable=True)


class BatchJob(Base, UUIDPrimaryKeyMixin, JobStateMixin, TimestampMixin):
    __tablename__ = "batch_jobs"

    project_id: Mapped[PythonUUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("projects.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    endpoint_id: Mapped[PythonUUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("endpoints.id"), nullable=True
    )
    input_object_key: Mapped[str | None] = mapped_column(Text, nullable=True)
    output_object_key: Mapped[str | None] = mapped_column(Text, nullable=True)
    temporal_workflow_id: Mapped[str | None] = mapped_column(String(128), nullable=True, index=True)
    progress_total: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    progress_done: Mapped[int | None] = mapped_column(BigInteger, nullable=True)


class JobLog(Base, UUIDPrimaryKeyMixin):
    __tablename__ = "job_logs"

    project_id: Mapped[PythonUUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("projects.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    job_type: Mapped[str] = mapped_column(String(64), nullable=False)
    job_id: Mapped[PythonUUID] = mapped_column(UUID(as_uuid=True), nullable=False, index=True)
    level: Mapped[str] = mapped_column(String(24), nullable=False, default="info")
    message: Mapped[str] = mapped_column(Text, nullable=False)
    payload_json: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    logged_at: Mapped[datetime] = mapped_column(nullable=False, server_default=func.now())
