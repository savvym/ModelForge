from sqlalchemy import BigInteger, ForeignKey, Index, Integer, Text

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


class Dataset(Base, UUIDPrimaryKeyMixin, CreatedByMixin, StatusMixin, TimestampMixin):
    __tablename__ = "datasets"

    project_id: Mapped[PythonUUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("projects.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    purpose: Mapped[str | None] = mapped_column(String(64), nullable=True)
    format: Mapped[str | None] = mapped_column(String(32), nullable=True)
    use_case: Mapped[str | None] = mapped_column(String(64), nullable=True)
    modality: Mapped[str | None] = mapped_column(String(32), nullable=True)
    recipe: Mapped[str | None] = mapped_column(String(64), nullable=True)
    scope: Mapped[str] = mapped_column(String(32), nullable=False, default="my-datasets")
    source_type: Mapped[str | None] = mapped_column(String(32), nullable=True)
    source_uri: Mapped[str | None] = mapped_column(Text, nullable=True)
    owner_name: Mapped[str | None] = mapped_column(String(120), nullable=True)
    tags: Mapped[list[str]] = mapped_column(JSONB, nullable=False, default=list)
    latest_version_id: Mapped[PythonUUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)


class DatasetVersion(Base, UUIDPrimaryKeyMixin, CreatedByMixin, StatusMixin, TimestampMixin):
    __tablename__ = "dataset_versions"
    __table_args__ = (
        Index("ix_dataset_versions_dataset_version", "dataset_id", "version", unique=True),
    )

    dataset_id: Mapped[PythonUUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("datasets.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    format: Mapped[str | None] = mapped_column(String(32), nullable=True)
    source_type: Mapped[str | None] = mapped_column(String(32), nullable=True)
    source_uri: Mapped[str | None] = mapped_column(Text, nullable=True)
    object_key: Mapped[str | None] = mapped_column(Text, nullable=True)
    file_size: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    record_count: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    import_job_id: Mapped[PythonUUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)


class DatasetFile(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "dataset_files"

    dataset_version_id: Mapped[PythonUUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("dataset_versions.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    file_name: Mapped[str] = mapped_column(String(255), nullable=False)
    object_key: Mapped[str] = mapped_column(Text, nullable=False)
    mime_type: Mapped[str | None] = mapped_column(String(120), nullable=True)
    size_bytes: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    etag: Mapped[str | None] = mapped_column(String(128), nullable=True)
