from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, func

from nta_backend.models.base import (
    UUID,
    Base,
    Mapped,
    PythonUUID,
    String,
    UUIDPrimaryKeyMixin,
    mapped_column,
)


class SecurityEvent(Base, UUIDPrimaryKeyMixin):
    __tablename__ = "security_events"

    project_id: Mapped[PythonUUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("projects.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    endpoint_id: Mapped[PythonUUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("endpoints.id"), nullable=True
    )
    risk_type: Mapped[str] = mapped_column(String(64), nullable=False)
    severity: Mapped[str] = mapped_column(String(24), nullable=False)
    count: Mapped[int] = mapped_column(nullable=False, default=0)
    event_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )


class VpcBinding(Base, UUIDPrimaryKeyMixin):
    __tablename__ = "vpc_bindings"

    project_id: Mapped[PythonUUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("projects.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    vpc_id: Mapped[str] = mapped_column(String(120), nullable=False)
    subnet_id: Mapped[str | None] = mapped_column(String(120), nullable=True)
    private_link_service_id: Mapped[str | None] = mapped_column(String(120), nullable=True)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="pending")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
