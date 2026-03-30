from sqlalchemy import ForeignKey, UniqueConstraint
from sqlalchemy.orm import relationship

from nta_backend.models.base import (
    UUID,
    Base,
    Mapped,
    PythonUUID,
    String,
    TimestampMixin,
    UUIDPrimaryKeyMixin,
    mapped_column,
)


class BenchmarkLeaderboard(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "benchmark_leaderboards"
    __table_args__ = (UniqueConstraint("project_id", "name"),)

    project_id: Mapped[PythonUUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("projects.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    benchmark_id: Mapped[PythonUUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("benchmark_definitions.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    benchmark_version_row_id: Mapped[PythonUUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("benchmark_versions.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    benchmark = relationship("BenchmarkDefinition")
    benchmark_version = relationship("BenchmarkVersion")
    jobs = relationship(
        "BenchmarkLeaderboardJob",
        back_populates="leaderboard",
        cascade="all, delete-orphan",
        order_by="BenchmarkLeaderboardJob.created_at.asc()",
    )


class BenchmarkLeaderboardJob(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "benchmark_leaderboard_jobs"
    __table_args__ = (UniqueConstraint("leaderboard_id", "eval_job_id"),)

    leaderboard_id: Mapped[PythonUUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("benchmark_leaderboards.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    eval_job_id: Mapped[PythonUUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("eval_jobs.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    leaderboard = relationship("BenchmarkLeaderboard", back_populates="jobs")
    eval_job = relationship("EvalJob")
