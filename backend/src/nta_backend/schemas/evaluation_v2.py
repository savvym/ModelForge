from __future__ import annotations

from datetime import datetime
from typing import Any, Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, model_validator


class EvalSpecVersionSummary(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    version: str
    display_name: str
    description: str | None = None
    engine: str
    execution_mode: str
    engine_benchmark_name: str | None = None
    engine_config_json: dict[str, Any] = Field(default_factory=dict)
    scoring_config_json: dict[str, Any] = Field(default_factory=dict)
    dataset_source_uri: str | None = None
    template_spec_version_id: UUID | None = None
    default_judge_policy_id: UUID | None = None
    enabled: bool
    is_recommended: bool
    sample_count: int | None = None
    dataset_files: list["EvalSpecDatasetFileSummary"] = Field(default_factory=list)


class EvalSpecSummary(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    name: str
    display_name: str
    description: str | None = None
    capability_group: str | None = None
    capability_category: str | None = None
    status: str
    tags_json: list[Any] = Field(default_factory=list)
    input_schema_json: dict[str, Any] = Field(default_factory=dict)
    output_schema_json: dict[str, Any] = Field(default_factory=dict)
    versions: list[EvalSpecVersionSummary] = Field(default_factory=list)


class EvalSuiteItemSummary(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    item_key: str
    display_name: str
    spec_version_id: UUID
    position: int
    weight: float
    group_name: str | None = None
    enabled: bool
    overrides_json: dict[str, Any] = Field(default_factory=dict)


class EvalSuiteVersionSummary(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    version: str
    display_name: str
    description: str | None = None
    enabled: bool
    items: list[EvalSuiteItemSummary] = Field(default_factory=list)


class EvalSuiteSummary(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    name: str
    display_name: str
    description: str | None = None
    capability_group: str | None = None
    status: str
    versions: list[EvalSuiteVersionSummary] = Field(default_factory=list)


class EvalSpecVersionCreate(BaseModel):
    version: str
    display_name: str
    description: str | None = None
    engine: str
    execution_mode: str
    engine_benchmark_name: str | None = None
    engine_config_json: dict[str, Any] = Field(default_factory=dict)
    scoring_config_json: dict[str, Any] = Field(default_factory=dict)
    dataset_source_uri: str | None = None
    template_spec_version_id: UUID | None = None
    default_judge_policy_id: UUID | None = None
    sample_count: int | None = None
    enabled: bool = True
    is_recommended: bool = True
    dataset_files: list[EvalSpecDatasetFileCreate] = Field(default_factory=list)


class EvalSpecCreate(BaseModel):
    name: str
    display_name: str
    description: str | None = None
    capability_group: str | None = None
    capability_category: str | None = None
    tags_json: list[Any] = Field(default_factory=list)
    input_schema_json: dict[str, Any] = Field(default_factory=dict)
    output_schema_json: dict[str, Any] = Field(default_factory=dict)
    initial_version: EvalSpecVersionCreate


class EvalSpecDatasetFileSummary(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    file_key: str
    display_name: str
    role: str
    position: int
    file_name: str | None = None
    format: str | None = None
    source_uri: str | None = None
    object_key: str | None = None
    content_type: str | None = None
    size_bytes: int | None = None
    is_required: bool
    status: str
    error_message: str | None = None
    last_synced_at: datetime | None = None


class EvalSpecDatasetFileCreate(BaseModel):
    file_key: str
    display_name: str
    role: str = "dataset"
    position: int = 0
    file_name: str | None = None
    format: str | None = None
    source_uri: str | None = None
    is_required: bool = True


class EvalSpecVersionUpdate(BaseModel):
    version_id: UUID
    version: str
    display_name: str
    description: str | None = None
    engine: str
    execution_mode: str
    engine_benchmark_name: str | None = None
    engine_config_json: dict[str, Any] = Field(default_factory=dict)
    scoring_config_json: dict[str, Any] = Field(default_factory=dict)
    dataset_source_uri: str | None = None
    template_spec_version_id: UUID | None = None
    default_judge_policy_id: UUID | None = None
    sample_count: int | None = None
    enabled: bool = True
    is_recommended: bool = True
    dataset_files: list[EvalSpecDatasetFileCreate] = Field(default_factory=list)


class EvalSpecUpdate(BaseModel):
    display_name: str
    description: str | None = None
    capability_group: str | None = None
    capability_category: str | None = None
    tags_json: list[Any] = Field(default_factory=list)
    input_schema_json: dict[str, Any] = Field(default_factory=dict)
    output_schema_json: dict[str, Any] = Field(default_factory=dict)
    version: EvalSpecVersionUpdate


class EvalSuiteItemCreate(BaseModel):
    item_key: str
    display_name: str
    spec_version_id: UUID
    position: int = 0
    weight: float = 1.0
    group_name: str | None = None
    overrides_json: dict[str, Any] = Field(default_factory=dict)
    enabled: bool = True


class EvalSuiteVersionCreate(BaseModel):
    version: str
    display_name: str
    description: str | None = None
    enabled: bool = True
    items: list[EvalSuiteItemCreate] = Field(default_factory=list)

    @model_validator(mode="after")
    def _validate_items(self) -> "EvalSuiteVersionCreate":
        if not self.items:
            raise ValueError("Suite version must include at least one item.")
        return self


class EvalSuiteCreate(BaseModel):
    name: str
    display_name: str
    description: str | None = None
    capability_group: str | None = None
    initial_version: EvalSuiteVersionCreate


class EvalSuiteItemUpdate(BaseModel):
    item_key: str
    display_name: str
    spec_version_id: UUID
    position: int = 0
    weight: float = 1.0
    group_name: str | None = None
    overrides_json: dict[str, Any] = Field(default_factory=dict)
    enabled: bool = True


class EvalSuiteVersionUpdate(BaseModel):
    version_id: UUID
    version: str
    display_name: str
    description: str | None = None
    enabled: bool = True
    items: list[EvalSuiteItemUpdate] = Field(default_factory=list)

    @model_validator(mode="after")
    def _validate_items(self) -> "EvalSuiteVersionUpdate":
        if not self.items:
            raise ValueError("Suite version must include at least one item.")
        return self


class EvalSuiteUpdate(BaseModel):
    display_name: str
    description: str | None = None
    capability_group: str | None = None
    version: EvalSuiteVersionUpdate


class TemplateSpecVersionSummary(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    version: int
    prompt: str
    vars_json: list[str] = Field(default_factory=list)
    output_schema_json: dict[str, Any] = Field(default_factory=dict)
    parser_config_json: dict[str, Any] = Field(default_factory=dict)
    is_active: bool


class TemplateSpecSummary(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    name: str
    display_name: str
    description: str | None = None
    template_type: str
    status: str
    versions: list[TemplateSpecVersionSummary] = Field(default_factory=list)


class JudgePolicySummary(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    name: str
    display_name: str
    description: str | None = None
    strategy: str
    status: str
    template_spec_version_id: UUID | None = None
    model_selector_json: dict[str, Any] = Field(default_factory=dict)
    execution_params_json: dict[str, Any] = Field(default_factory=dict)
    parser_config_json: dict[str, Any] = Field(default_factory=dict)
    retry_policy_json: dict[str, Any] = Field(default_factory=dict)


class EvaluationCatalogResponse(BaseModel):
    specs: list[EvalSpecSummary]
    suites: list[EvalSuiteSummary]
    templates: list[TemplateSpecSummary]
    judge_policies: list[JudgePolicySummary]


class EvaluationTargetRef(BaseModel):
    kind: Literal["spec", "suite"]
    name: str
    version: str
    item_keys: list[str] = Field(default_factory=list)


class EvaluationRunCreate(BaseModel):
    name: str | None = None
    description: str | None = None
    target: EvaluationTargetRef
    model_id: UUID
    judge_policy_id: UUID | None = None
    overrides: dict[str, Any] = Field(default_factory=dict)


class EvaluationRunMetricResponse(BaseModel):
    metric_name: str
    metric_value: float
    metric_scope: str
    metric_unit: str | None = None
    dimension_json: dict[str, Any] = Field(default_factory=dict)
    extra_json: dict[str, Any] = Field(default_factory=dict)


class EvaluationRunSampleResponse(BaseModel):
    sample_id: str
    subset_name: str | None = None
    input_preview: str | None = None
    prediction_text: str | None = None
    reference_answers_json: list[str] = Field(default_factory=list)
    score: float | None = None
    raw_score: float | None = None
    passed: bool = False
    reason: str | None = None
    error: str | None = None
    latency_ms: int | None = None
    total_tokens: int | None = None
    metadata_json: dict[str, Any] = Field(default_factory=dict)


class EvaluationRunItemResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    item_key: str
    display_name: str
    group_name: str | None = None
    weight: float = 1.0
    status: str
    engine: str
    execution_mode: str
    report_uri: str | None = None
    raw_output_prefix_uri: str | None = None
    temporal_workflow_id: str | None = None
    progress_total: int | None = None
    progress_done: int | None = None
    error_code: str | None = None
    error_message: str | None = None
    started_at: datetime | None = None
    finished_at: datetime | None = None
    metrics: list[EvaluationRunMetricResponse] = Field(default_factory=list)
    samples: list[EvaluationRunSampleResponse] = Field(default_factory=list)


class EvaluationRunSummary(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    name: str
    description: str | None = None
    kind: str
    status: str
    model_name: str | None = None
    summary_report_uri: str | None = None
    temporal_workflow_id: str | None = None
    progress_total: int | None = None
    progress_done: int | None = None
    error_code: str | None = None
    error_message: str | None = None
    created_at: datetime
    started_at: datetime | None = None
    finished_at: datetime | None = None


class EvaluationRunDetail(EvaluationRunSummary):
    source_spec_id: UUID | None = None
    source_spec_version_id: UUID | None = None
    source_suite_id: UUID | None = None
    source_suite_version_id: UUID | None = None
    judge_policy_id: UUID | None = None
    execution_plan_json: dict[str, Any] = Field(default_factory=dict)
    metrics: list[EvaluationRunMetricResponse] = Field(default_factory=list)
    items: list[EvaluationRunItemResponse] = Field(default_factory=list)


class TemplateSpecCreate(BaseModel):
    name: str
    display_name: str
    description: str | None = None
    template_type: str
    prompt: str
    vars_json: list[str] = Field(default_factory=list)
    output_schema_json: dict[str, Any] = Field(default_factory=dict)
    parser_config_json: dict[str, Any] = Field(default_factory=dict)


class JudgePolicyCreate(BaseModel):
    name: str
    display_name: str
    description: str | None = None
    strategy: str
    template_spec_version_id: UUID | None = None
    model_selector_json: dict[str, Any] = Field(default_factory=dict)
    execution_params_json: dict[str, Any] = Field(default_factory=dict)
    parser_config_json: dict[str, Any] = Field(default_factory=dict)
    retry_policy_json: dict[str, Any] = Field(default_factory=dict)


class EvaluationRunCancelResponse(BaseModel):
    run_id: UUID
    status: str


class EvaluationLeaderboardRunCandidate(BaseModel):
    run_id: UUID
    run_name: str
    model_name: str
    score: float
    metric_name: str
    created_at: datetime
    finished_at: datetime | None = None


class EvaluationLeaderboardEntry(EvaluationLeaderboardRunCandidate):
    rank: int


class EvaluationLeaderboardSummary(BaseModel):
    id: UUID
    name: str
    description: str | None = None
    target_kind: Literal["spec", "suite"]
    target_name: str
    target_display_name: str
    target_version: str
    target_version_display_name: str
    score_metric_name: str
    run_count: int = 0
    latest_run_at: datetime | None = None
    created_at: datetime
    updated_at: datetime


class EvaluationLeaderboardDetail(EvaluationLeaderboardSummary):
    entries: list[EvaluationLeaderboardEntry] = Field(default_factory=list)


class EvaluationLeaderboardCreate(BaseModel):
    name: str
    description: str | None = None
    target: EvaluationTargetRef
    score_metric_name: str = "score"
    run_ids: list[UUID] = Field(default_factory=list)


class EvaluationLeaderboardAddRuns(BaseModel):
    run_ids: list[UUID] = Field(min_length=1)


class ModelBindingSnapshot(BaseModel):
    model_id: UUID | None = None
    model_name: str
    display_name: str
    api_url: str
    api_format: str
    api_key: str | None = None
    organization: str | None = None
    headers: dict[str, str] = Field(default_factory=dict)
    model_params: dict[str, Any] = Field(default_factory=dict)


class CompiledRunItemPlan(BaseModel):
    item_key: str
    display_name: str
    group_name: str | None = None
    weight: float = 1.0
    engine: str
    execution_mode: str
    spec_id: UUID
    spec_version_id: UUID
    spec_name: str
    spec_version: str
    expected_sample_count: int | None = None
    engine_config: dict[str, Any] = Field(default_factory=dict)
    model_binding: ModelBindingSnapshot
    judge_model_binding: ModelBindingSnapshot | None = None
    judge_policy_snapshot: dict[str, Any] | None = None
    template_snapshot: dict[str, Any] | None = None


class CompiledRunPlan(BaseModel):
    kind: Literal["spec", "suite"]
    target_name: str
    target_version: str
    model_binding: ModelBindingSnapshot
    judge_policy_snapshot: dict[str, Any] | None = None
    items: list[CompiledRunItemPlan]
    overrides: dict[str, Any] = Field(default_factory=dict)

    @model_validator(mode="after")
    def _validate_items(self) -> "CompiledRunPlan":
        if not self.items:
            raise ValueError("Compiled plan must include at least one run item.")
        return self
