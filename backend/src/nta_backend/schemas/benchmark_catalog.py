from datetime import datetime

from pydantic import BaseModel, Field


class BenchmarkVersionSummary(BaseModel):
    id: str
    display_name: str
    description: str
    dataset_path: str | None = None
    dataset_source_uri: str | None = None
    sample_count: int = 0
    enabled: bool = True
    eval_job_count: int = 0
    latest_eval_at: datetime | None = None


class BenchmarkDefinitionSummary(BaseModel):
    name: str
    display_name: str
    family_name: str | None = None
    family_display_name: str | None = None
    description: str
    default_eval_method: str
    metadata_source: str = "runtime"
    runtime_available: bool = False
    requires_judge_model: bool = False
    supports_custom_dataset: bool = False
    dataset_id: str | None = None
    category: str | None = None
    paper_url: str | None = None
    tags: list[str] = Field(default_factory=list)
    metric_names: list[str] = Field(default_factory=list)
    subset_list: list[str] = Field(default_factory=list)
    version_count: int = 0
    enabled_version_count: int = 0
    eval_job_count: int = 0
    latest_eval_at: datetime | None = None
    versions: list[BenchmarkVersionSummary] = Field(default_factory=list)


class BenchmarkDefinitionDetail(BenchmarkDefinitionSummary):
    sample_schema_json: dict = Field(default_factory=dict)
    prompt_schema_json: dict = Field(default_factory=dict)
    prompt_config_json: dict = Field(default_factory=dict)
    few_shot_num: int | None = None
    eval_split: str | None = None
    train_split: str | None = None
    prompt_template: str | None = None
    system_prompt: str | None = None
    few_shot_prompt_template: str | None = None
    sample_example_json: dict | None = None
    statistics_json: dict | None = None
    readme_json: dict | None = None
    meta_updated_at: str | None = None
    meta_translation_updated_at: str | None = None


class BenchmarkDefinitionCreate(BaseModel):
    name: str
    display_name: str
    description: str | None = None
    category: str | None = None
    tags: list[str] = Field(default_factory=list)
    default_eval_method: str = "accuracy"
    field_mapping: dict | None = None
    prompt_template: str | None = None
    system_prompt: str | None = None
    requires_judge_model: bool = False


class BenchmarkDefinitionUpdate(BaseModel):
    display_name: str | None = None
    description: str | None = None
    category: str | None = None
    tags: list[str] | None = None
    default_eval_method: str | None = None
    field_mapping: dict | None = None
    prompt_template: str | None = None
    system_prompt: str | None = None
    requires_judge_model: bool | None = None


class BenchmarkVersionCreate(BaseModel):
    id: str
    display_name: str
    description: str | None = None
    dataset_source_uri: str | None = None
    enabled: bool = True


class BenchmarkVersionUpdate(BaseModel):
    display_name: str | None = None
    description: str | None = None
    dataset_source_uri: str | None = None
    enabled: bool | None = None
