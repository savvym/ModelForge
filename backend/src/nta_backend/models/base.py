from datetime import date, datetime
from uuid import UUID as PythonUUID
from uuid import uuid4

from sqlalchemy import Date, DateTime, String, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from nta_backend.core.db import Base, TimestampMixin


class UUIDPrimaryKeyMixin:
    id: Mapped[PythonUUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid4)


class CreatedByMixin:
    created_by: Mapped[PythonUUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)


class StatusMixin:
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="active")


class JobStateMixin(CreatedByMixin, StatusMixin):
    error_code: Mapped[str | None] = mapped_column(String(64), nullable=True)
    error_message: Mapped[str | None] = mapped_column(String(500), nullable=True)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


__all__ = [
    "Base",
    "CreatedByMixin",
    "Date",
    "DateTime",
    "JSONB",
    "JobStateMixin",
    "Mapped",
    "PythonUUID",
    "StatusMixin",
    "String",
    "TimestampMixin",
    "UUID",
    "UUIDPrimaryKeyMixin",
    "date",
    "datetime",
    "func",
    "mapped_column",
]
