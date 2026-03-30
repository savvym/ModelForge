from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field


class EvalTemplateCreate(BaseModel):
    name: str
    prompt: str
    template_type: str | None = None
    preset_id: str | None = None
    output_type: str = "numeric"
    output_config: dict = Field(default_factory=dict)
    model: str | None = None
    provider: str | None = None
    model_params: dict | None = None
    description: str | None = None


class EvalTemplateUpdate(BaseModel):
    prompt: str | None = None
    template_type: str | None = None
    preset_id: str | None = None
    output_type: str | None = None
    output_config: dict | None = None
    model: str | None = None
    provider: str | None = None
    model_params: dict | None = None
    description: str | None = None


class EvalTemplateSummary(BaseModel):
    id: UUID
    name: str
    version: int
    prompt: str
    vars: list[str] = Field(default_factory=list)
    template_type: str
    preset_id: str | None = None
    output_type: str
    output_config: dict = Field(default_factory=dict)
    model: str | None = None
    provider: str | None = None
    model_params: dict | None = None
    description: str | None = None
    created_at: datetime
