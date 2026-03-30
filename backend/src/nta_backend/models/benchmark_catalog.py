from sqlalchemy import BigInteger, Boolean, ForeignKey, Integer, Text, UniqueConstraint
from sqlalchemy.orm import relationship

from nta_backend.models.base import (
    JSONB,
    UUID,
    Base,
    Mapped,
    PythonUUID,
    String,
    TimestampMixin,
    UUIDPrimaryKeyMixin,
    mapped_column,
)


class BenchmarkDefinition(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "benchmark_definitions"

    # -- Core identity --
    name: Mapped[str] = mapped_column(String(120), nullable=False, unique=True, index=True)
    display_name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)

    # -- Family grouping --
    family_name: Mapped[str | None] = mapped_column(String(120), nullable=True)
    family_display_name: Mapped[str | None] = mapped_column(String(255), nullable=True)

    # -- Evaluation configuration --
    default_eval_method: Mapped[str] = mapped_column(String(64), nullable=False)
    sample_schema_json: Mapped[dict] = mapped_column(JSONB, nullable=False)
    prompt_schema_json: Mapped[dict] = mapped_column(JSONB, nullable=False)
    prompt_config_json: Mapped[dict] = mapped_column(JSONB, nullable=False)
    requires_judge_model: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    supports_custom_dataset: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)

    # -- Discovery / catalog metadata --
    dataset_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    category: Mapped[str | None] = mapped_column(String(64), nullable=True)
    paper_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    tags: Mapped[list | None] = mapped_column(JSONB, nullable=True, default=list)
    metric_names: Mapped[list | None] = mapped_column(JSONB, nullable=True, default=list)
    aggregator_names: Mapped[list | None] = mapped_column(JSONB, nullable=True, default=list)
    subset_list: Mapped[list | None] = mapped_column(JSONB, nullable=True, default=list)

    # -- Prompt templates --
    prompt_template: Mapped[str | None] = mapped_column(Text, nullable=True)
    system_prompt: Mapped[str | None] = mapped_column(Text, nullable=True)
    few_shot_prompt_template: Mapped[str | None] = mapped_column(Text, nullable=True)
    few_shot_num: Mapped[int | None] = mapped_column(Integer, nullable=True)
    eval_split: Mapped[str | None] = mapped_column(String(64), nullable=True)
    train_split: Mapped[str | None] = mapped_column(String(64), nullable=True)

    # -- Rich metadata (JSON blobs) --
    sample_example_json: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    statistics_json: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    readme_json: Mapped[dict | None] = mapped_column(JSONB, nullable=True)

    # -- Field mapping (for generic adapter) --
    field_mapping_json: Mapped[dict | None] = mapped_column(JSONB, nullable=True)

    # -- Runtime / operational --
    adapter_class: Mapped[str | None] = mapped_column(String(255), nullable=True)
    source_type: Mapped[str | None] = mapped_column(String(32), nullable=True, default="builtin")
    is_runnable: Mapped[bool] = mapped_column(Boolean, nullable=True, default=False)

    # -- Relationships --
    versions = relationship(
        "BenchmarkVersion",
        back_populates="benchmark",
        cascade="all, delete-orphan",
        order_by="BenchmarkVersion.created_at.asc()",
    )


class BenchmarkVersion(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "benchmark_versions"
    __table_args__ = (
        UniqueConstraint("benchmark_id", "version_id"),
    )

    benchmark_id: Mapped[PythonUUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("benchmark_definitions.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    version_id: Mapped[str] = mapped_column(String(120), nullable=False)
    display_name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    dataset_path: Mapped[str | None] = mapped_column(Text, nullable=True)
    dataset_source_uri: Mapped[str | None] = mapped_column(Text, nullable=True)
    sample_count: Mapped[int] = mapped_column(BigInteger, nullable=False, default=0)
    enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)

    benchmark = relationship("BenchmarkDefinition", back_populates="versions")
