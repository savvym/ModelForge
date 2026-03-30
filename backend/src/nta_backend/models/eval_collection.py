from sqlalchemy import ForeignKey, Text
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


class EvalCollection(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "eval_collections"

    project_id: Mapped[PythonUUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("projects.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    schema_json: Mapped[dict] = mapped_column(JSONB, nullable=False)

    jobs = relationship(
        "EvalJob",
        back_populates="collection",
        foreign_keys="EvalJob.collection_id",
        order_by="EvalJob.created_at.asc()",
    )
