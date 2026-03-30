from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class ProjectSummary(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    code: str
    name: str
    description: str | None = None
    status: str
    is_default: bool = False
    resource_count: int = 0
    member_count: int = 0
    dataset_count: int = 0
    eval_job_count: int = 0
    created_at: datetime
    updated_at: datetime


class ProjectDetail(ProjectSummary):
    endpoint_count: int = 0
    model_provider_count: int = 0
    model_count: int = 0


class ProjectCreate(BaseModel):
    code: str = Field(min_length=2, max_length=64)
    name: str = Field(min_length=1, max_length=120)
    description: str | None = Field(default=None, max_length=500)
