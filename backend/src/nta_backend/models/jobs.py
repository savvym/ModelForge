from sqlalchemy import BigInteger, ForeignKey, Text, func

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
