from sqlalchemy import ForeignKey, Integer, Text, UniqueConstraint

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


class EvalTemplate(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "eval_templates"
    __table_args__ = (
        UniqueConstraint("project_id", "name", "version"),
    )

    project_id: Mapped[PythonUUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("projects.id", ondelete="CASCADE"),
        nullable=True,
        index=True,
    )
    name: Mapped[str] = mapped_column(String(120), nullable=False, index=True)
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    prompt: Mapped[str] = mapped_column(Text, nullable=False)
    vars: Mapped[list] = mapped_column(JSONB, nullable=False, default=list)
    template_type: Mapped[str] = mapped_column(String(64), nullable=False, default="llm_numeric")
    preset_id: Mapped[str | None] = mapped_column(String(120), nullable=True)
    output_type: Mapped[str] = mapped_column(String(32), nullable=False, default="numeric")
    output_config: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    model: Mapped[str | None] = mapped_column(String(255), nullable=True)
    provider: Mapped[str | None] = mapped_column(String(120), nullable=True)
    model_params: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
