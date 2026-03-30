from datetime import datetime

from sqlalchemy import Boolean, ForeignKey, Index, Text

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


class ModelProvider(Base, UUIDPrimaryKeyMixin, CreatedByMixin, StatusMixin, TimestampMixin):
    __tablename__ = "model_providers"
    __table_args__ = (
        Index("ix_model_providers_project_name", "project_id", "name", unique=True),
    )

    project_id: Mapped[PythonUUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("projects.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    provider_type: Mapped[str] = mapped_column(
        String(64),
        nullable=False,
        default="openai-compatible",
    )
    adapter: Mapped[str] = mapped_column(String(32), nullable=False, default="litellm")
    api_format: Mapped[str] = mapped_column(String(32), nullable=False, default="chat-completions")
    base_url: Mapped[str] = mapped_column(Text, nullable=False)
    api_key: Mapped[str | None] = mapped_column(Text, nullable=True)
    organization: Mapped[str | None] = mapped_column(String(120), nullable=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    headers_json: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    last_synced_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class Model(Base, UUIDPrimaryKeyMixin, CreatedByMixin, StatusMixin, TimestampMixin):
    __tablename__ = "models"
    __table_args__ = (
        Index("ix_models_provider_model_code", "provider_id", "model_code", unique=True),
    )

    project_id: Mapped[PythonUUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("projects.id", ondelete="CASCADE"), nullable=True, index=True
    )
    provider_id: Mapped[PythonUUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("model_providers.id", ondelete="SET NULL"), nullable=True
    )
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    model_code: Mapped[str | None] = mapped_column(String(160), nullable=True)
    vendor: Mapped[str | None] = mapped_column(String(64), nullable=True)
    source: Mapped[str | None] = mapped_column(String(64), nullable=True)
    api_format: Mapped[str | None] = mapped_column(String(32), nullable=True)
    base_model: Mapped[str | None] = mapped_column(String(120), nullable=True)
    category: Mapped[str | None] = mapped_column(String(64), nullable=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    capabilities_json: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    is_provider_managed: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    last_synced_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class Endpoint(Base, UUIDPrimaryKeyMixin, CreatedByMixin, StatusMixin, TimestampMixin):
    __tablename__ = "endpoints"

    project_id: Mapped[PythonUUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("projects.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    endpoint_type: Mapped[str] = mapped_column(String(64), nullable=False)
    model_id: Mapped[PythonUUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("models.id"), nullable=True
    )
    purchase_type: Mapped[str | None] = mapped_column(String(64), nullable=True)
    config_json: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
