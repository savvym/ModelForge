from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field


class BenchmarkLeaderboardJobCandidate(BaseModel):
    eval_job_id: str
    eval_job_name: str
    model_name: str
    model_source: str | None = None
    score: float
    metric_name: str
    created_at: datetime
    finished_at: datetime | None = None
    judge_model_name: str | None = None


class BenchmarkLeaderboardEntry(BenchmarkLeaderboardJobCandidate):
    rank: int


class BenchmarkLeaderboardSummary(BaseModel):
    id: UUID
    name: str
    benchmark_name: str
    benchmark_display_name: str
    benchmark_version_id: str
    benchmark_version_display_name: str
    score_metric_name: str | None = None
    job_count: int = 0
    latest_eval_at: datetime | None = None
    created_at: datetime
    updated_at: datetime


class BenchmarkLeaderboardDetail(BenchmarkLeaderboardSummary):
    entries: list[BenchmarkLeaderboardEntry] = Field(default_factory=list)


class BenchmarkLeaderboardCreate(BaseModel):
    name: str
    benchmark_name: str
    benchmark_version_id: str
    eval_job_ids: list[str] = Field(default_factory=list)


class BenchmarkLeaderboardAddJobs(BaseModel):
    eval_job_ids: list[str] = Field(min_length=1)
