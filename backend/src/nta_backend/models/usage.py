from datetime import datetime

from sqlalchemy import BigInteger, Date, DateTime, Float, ForeignKey, Index, func

from nta_backend.models.base import (
    UUID,
    Base,
    Mapped,
    PythonUUID,
    String,
    TimestampMixin,
    UUIDPrimaryKeyMixin,
    date,
    mapped_column,
)


class QuotaRule(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "quota_rules"

    project_id: Mapped[PythonUUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("projects.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    resource_type: Mapped[str] = mapped_column(String(64), nullable=False)
    resource_code: Mapped[str] = mapped_column(String(120), nullable=False)
    account_quota: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    shared_ratio: Mapped[float | None] = mapped_column(Float, nullable=True)
    exclusive_ratio: Mapped[float | None] = mapped_column(Float, nullable=True)
    updated_by: Mapped[PythonUUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)


class UsageEvent(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "usage_events"

    project_id: Mapped[PythonUUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("projects.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    resource_type: Mapped[str] = mapped_column(String(64), nullable=False)
    resource_id: Mapped[PythonUUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)
    model_code: Mapped[str | None] = mapped_column(String(120), nullable=True)
    input_tokens: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    output_tokens: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    request_count: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    occurred_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )


class UsageDailyAggregate(Base, UUIDPrimaryKeyMixin):
    __tablename__ = "usage_daily_agg"
    __table_args__ = (
        Index("ix_usage_daily_project_date_model", "project_id", "date", "model_code"),
    )

    project_id: Mapped[PythonUUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("projects.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    date: Mapped[date] = mapped_column(Date, nullable=False)
    model_code: Mapped[str | None] = mapped_column(String(120), nullable=True)
    endpoint_id: Mapped[PythonUUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("endpoints.id"), nullable=True
    )
    input_tokens: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    output_tokens: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    request_count: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
