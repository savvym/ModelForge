from __future__ import annotations

from datetime import UTC, datetime

from pydantic import BaseModel, Field

from nta_backend.eval_core.api.metric import AggScore, SampleScore


class SubsetReport(BaseModel):
    subset: str
    sample_count: int
    metrics: list[AggScore] = Field(default_factory=list)
    sample_scores: list[SampleScore] = Field(default_factory=list)


class EvalReport(BaseModel):
    benchmark_name: str
    model_name: str
    subset_reports: list[SubsetReport] = Field(default_factory=list)
    generated_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
