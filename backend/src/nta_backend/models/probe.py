from sqlalchemy import ForeignKey, Integer, Text, UniqueConstraint
from sqlalchemy.orm import relationship

from nta_backend.models.base import (
    JSONB,
    UUID,
    Base,
    CreatedByMixin,
    DateTime,
    Mapped,
    PythonUUID,
    String,
    TimestampMixin,
    UUIDPrimaryKeyMixin,
    mapped_column,
)


class Probe(Base, UUIDPrimaryKeyMixin, TimestampMixin, CreatedByMixin):
    __tablename__ = "probes"
    __table_args__ = (UniqueConstraint("project_id", "name"),)

    project_id: Mapped[PythonUUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("projects.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    name: Mapped[str] = mapped_column(String(120), nullable=False, index=True)
    display_name: Mapped[str] = mapped_column(String(255), nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="offline", index=True)
    ip_address: Mapped[str | None] = mapped_column(String(64), nullable=True)
    isp: Mapped[str | None] = mapped_column(String(120), nullable=True)
    asn: Mapped[int | None] = mapped_column(Integer, nullable=True)
    region: Mapped[str | None] = mapped_column(String(64), nullable=True)
    country: Mapped[str | None] = mapped_column(String(8), nullable=True)
    city: Mapped[str | None] = mapped_column(String(120), nullable=True)
    network_type: Mapped[str] = mapped_column(String(32), nullable=False, default="cloud")
    tags_json: Mapped[list] = mapped_column(JSONB, nullable=False, default=list)
    agent_version: Mapped[str | None] = mapped_column(String(64), nullable=True)
    device_info_json: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    metadata_json: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    last_heartbeat: Mapped[DateTime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    auth_token_hash: Mapped[str | None] = mapped_column(String(255), nullable=True)

    heartbeats = relationship(
        "ProbeHeartbeat",
        back_populates="probe",
        cascade="all, delete-orphan",
        order_by="ProbeHeartbeat.created_at.desc()",
    )
    tasks = relationship(
        "ProbeTask",
        back_populates="probe",
        cascade="all, delete-orphan",
        order_by="ProbeTask.created_at.desc()",
    )


class ProbeHeartbeat(Base, UUIDPrimaryKeyMixin):
    __tablename__ = "probe_heartbeats"

    probe_id: Mapped[PythonUUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("probes.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    ip_address: Mapped[str] = mapped_column(String(64), nullable=False)
    network_metrics_json: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    agent_status_json: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    created_at: Mapped[DateTime] = mapped_column(DateTime(timezone=True), nullable=False)

    probe = relationship("Probe", back_populates="heartbeats")


class ProbeTask(Base, UUIDPrimaryKeyMixin, TimestampMixin, CreatedByMixin):
    __tablename__ = "probe_tasks"

    project_id: Mapped[PythonUUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("projects.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    probe_id: Mapped[PythonUUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("probes.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    task_type: Mapped[str] = mapped_column(String(64), nullable=False, default="evalscope-perf")
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="queued", index=True)
    timeout_seconds: Mapped[int] = mapped_column(Integer, nullable=False, default=3600)
    attempt_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    payload_json: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    progress_json: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    result_json: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    claimed_at: Mapped[DateTime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    started_at: Mapped[DateTime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    finished_at: Mapped[DateTime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    lease_expires_at: Mapped[DateTime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    probe = relationship("Probe", back_populates="tasks")
