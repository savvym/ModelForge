from sqlalchemy import BigInteger, ForeignKey, Index, Text

from nta_backend.models.base import (
    JSONB,
    UUID,
    Base,
    CreatedByMixin,
    Mapped,
    PythonUUID,
    StatusMixin,
    String,
    TimestampMixin,
    UUIDPrimaryKeyMixin,
    mapped_column,
)


class LakeBatch(Base, UUIDPrimaryKeyMixin, CreatedByMixin, StatusMixin, TimestampMixin):
    __tablename__ = "lake_batches"

    project_id: Mapped[PythonUUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("projects.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    source_type: Mapped[str] = mapped_column(String(64), nullable=False, default="upload")
    resource_type: Mapped[str | None] = mapped_column(String(64), nullable=True)
    stage: Mapped[str] = mapped_column(String(32), nullable=False, default="raw")
    planned_file_count: Mapped[int] = mapped_column(nullable=False, default=1)
    completed_file_count: Mapped[int] = mapped_column(nullable=False, default=0)
    failed_file_count: Mapped[int] = mapped_column(nullable=False, default=0)
    total_size_bytes: Mapped[int] = mapped_column(BigInteger, nullable=False, default=0)
    tags: Mapped[list[str]] = mapped_column(JSONB, nullable=False, default=list)
    extra_metadata: Mapped[dict[str, object]] = mapped_column(
        "metadata",
        JSONB,
        nullable=False,
        default=dict,
    )


class LakeAsset(Base, UUIDPrimaryKeyMixin, CreatedByMixin, StatusMixin, TimestampMixin):
    __tablename__ = "lake_assets"
    __table_args__ = (
        Index("ix_lake_assets_project_stage", "project_id", "stage"),
        Index("ix_lake_assets_batch_created", "batch_id", "created_at"),
    )

    project_id: Mapped[PythonUUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("projects.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    batch_id: Mapped[PythonUUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("lake_batches.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    parent_asset_id: Mapped[PythonUUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("lake_assets.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    stage: Mapped[str] = mapped_column(String(32), nullable=False, default="raw")
    source_type: Mapped[str] = mapped_column(String(64), nullable=False, default="upload")
    resource_type: Mapped[str | None] = mapped_column(String(64), nullable=True)
    format: Mapped[str | None] = mapped_column(String(64), nullable=True)
    mime_type: Mapped[str | None] = mapped_column(String(120), nullable=True)
    relative_path: Mapped[str | None] = mapped_column(Text, nullable=True)
    object_key: Mapped[str | None] = mapped_column(Text, nullable=True)
    source_uri: Mapped[str | None] = mapped_column(Text, nullable=True)
    size_bytes: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    etag: Mapped[str | None] = mapped_column(String(128), nullable=True)
    checksum: Mapped[str | None] = mapped_column(String(128), nullable=True)
    record_count: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    tags: Mapped[list[str]] = mapped_column(JSONB, nullable=False, default=list)
    extra_metadata: Mapped[dict[str, object]] = mapped_column(
        "metadata",
        JSONB,
        nullable=False,
        default=dict,
    )
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
