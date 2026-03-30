from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import AliasChoices, BaseModel, ConfigDict, Field


class EvalJobSummary(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    name: str
    description: str | None = None
    status: str
    model_name: str
    model_source: str
    created_by: str | None = None
    progress_percent: int = 0
    progress_done: int | None = None
    progress_total: int | None = None
    inference_mode: str
    eval_method: str
    temporal_workflow_id: str | None = None
    error_message: str | None = None
    created_at: datetime
    started_at: datetime | None = None
    finished_at: datetime | None = None


class EvalMetric(BaseModel):
    metric_name: str
    metric_value: float
    metric_unit: str | None = None


class EvalSampleAnalysis(BaseModel):
    sample_id: str
    method: str
    input_preview: str | None = None
    system_prompt: str | None = None
    rubric_source: str | None = None
    effective_rubric: str | None = None
    prediction_text: str | None = None
    reference_answers: list[str] = Field(default_factory=list)
    score: float | None = None
    raw_score: float | None = None
    passed: bool = False
    reason: str | None = None
    error: str | None = None
    latency_ms: int | None = None
    total_tokens: int | None = None
    judge_model_name: str | None = None


class EvalJobDetail(EvalJobSummary):
    access_source: str = "nta"
    benchmark_name: str | None = None
    benchmark_version_id: str | None = None
    benchmark_version_name: str | None = None
    dataset_source_type: str = "benchmark-version"
    dataset_version_id: UUID | None = None
    dataset_name: str
    dataset_source_uri: str | None = None
    artifact_prefix_uri: str | None = None
    source_object_uri: str | None = None
    results_prefix_uri: str | None = None
    samples_prefix_uri: str | None = None
    report_object_uri: str | None = None
    task_type: str = "single-turn"
    eval_mode: str = "infer-auto"
    endpoint_name: str | None = None
    judge_model_name: str | None = None
    judge_prompt: str | None = None
    rubric: str | None = None
    batch_job_id: str | None = None
    metrics: list[EvalMetric]
    sample_analysis: list[EvalSampleAnalysis] = Field(default_factory=list)


class EvalJobCreate(BaseModel):
    name: str
    description: str | None = None
    benchmark_name: str | None = None
    benchmark_version_id: str | None = Field(
        default=None,
        validation_alias=AliasChoices("benchmark_version_id", "benchmark_preset_id"),
    )
    benchmark_config: dict[str, Any] | None = None
    model_id: UUID | None = None
    model_name: str = "Doubao-Seed-2.0-pro 260215"
    model_source: str = "model-square"
    access_source: str = "nta"
    dataset_source_type: str = "benchmark-version"
    dataset_version_id: UUID | None = None
    dataset_name: str = ""
    dataset_source_uri: str | None = None
    inference_mode: str = "batch"
    task_type: str = "single-turn"
    eval_mode: str = "infer-auto"
    eval_method: str = "judge-rubric"
    endpoint_name: str | None = None
    judge_model_id: UUID | None = None
    judge_model_name: str | None = "Doubao-Seed-2.0-pro 250415"
    judge_prompt: str | None = None
    rubric: str | None = None


class WorkflowLaunchResponse(BaseModel):
    job_id: str
    workflow_id: str
    status: str
    stream_url: str
