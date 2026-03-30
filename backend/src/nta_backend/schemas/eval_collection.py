from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, Field

from nta_backend.schemas.eval_job import EvalJobSummary


class CollectionDatasetEntry(BaseModel):
    benchmark_name: str
    version_id: str
    weight: float = 1.0


class EvalCollectionCreate(BaseModel):
    name: str
    description: str | None = None
    datasets: list[CollectionDatasetEntry] = Field(min_length=1)


class EvalCollectionSummary(BaseModel):
    id: UUID
    name: str
    description: str | None = None
    dataset_count: int = 0
    job_count: int = 0
    created_at: datetime


class EvalCollectionDetail(EvalCollectionSummary):
    schema_json: dict[str, Any]
    jobs: list[EvalJobSummary] = Field(default_factory=list)


class CollectionRunRequest(BaseModel):
    model_id: UUID | None = None
    model_name: str = "Doubao-Seed-2.0-pro 260215"
    model_source: str = "model-square"
    access_source: str = "nta"
    judge_model_id: UUID | None = None
    judge_model_name: str | None = "Doubao-Seed-2.0-pro 250415"


class CollectionRunResponse(BaseModel):
    collection_id: UUID
    jobs: list[EvalJobSummary]
