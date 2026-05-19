from sqlalchemy import ForeignKey, Index, Text, UniqueConstraint

from nta_backend.models.base import (
    Base,
    CreatedByMixin,
    Mapped,
    PythonUUID,
    StatusMixin,
    String,
    TimestampMixin,
    UUID,
    UUIDPrimaryKeyMixin,
    mapped_column,
)


class LakeRepo(Base, UUIDPrimaryKeyMixin, CreatedByMixin, StatusMixin, TimestampMixin):
    __tablename__ = "lake_repos"
    __table_args__ = (
        UniqueConstraint("project_id", "name", name="uq_lake_repos_project_name"),
        Index("ix_lake_repos_gitea", "gitea_org", "gitea_repo"),
    )

    project_id: Mapped[PythonUUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("projects.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    name: Mapped[str] = mapped_column(String(64), nullable=False)
    display_name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    gitea_org: Mapped[str] = mapped_column(String(64), nullable=False)
    gitea_repo: Mapped[str] = mapped_column(String(64), nullable=False)
    default_branch: Mapped[str] = mapped_column(String(64), nullable=False, default="main")
    visibility: Mapped[str] = mapped_column(String(16), nullable=False, default="private")
