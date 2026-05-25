from __future__ import annotations

from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, Field, field_validator


class ObjectStorageCredentials(BaseModel):
    access_key_id: str
    secret_access_key: str
    session_token: str | None = None
    expires_at: datetime | None = None


class ObjectStorageSource(BaseModel):
    uri: str
    endpoint_url: str | None = None
    region: str = "us-east-1"
    addressing_style: str = "path"
    credentials: ObjectStorageCredentials | None = None


class HuggingFaceSource(BaseModel):
    repo_id: str
    revision: str = "main"
    repo_type: str = "model"
    allow_patterns: list[str] | None = None
    ignore_patterns: list[str] | None = None
    token: str | None = None
    endpoint_url: str | None = None


class ModelSource(BaseModel):
    type: str = "object_storage"
    uri: str
    object_storage: ObjectStorageSource | None = None
    huggingface: HuggingFaceSource | None = None


class ModelBinding(BaseModel):
    model_id: str
    name: str
    served_name: str
    source: ModelSource
    local_path: str | None = None


class LoraAdapterBinding(BaseModel):
    adapter_id: str
    name: str
    served_name: str
    source: ModelSource
    local_path: str | None = None


class EngineSpec(BaseModel):
    name: str = "vllm"
    image: str
    gpu_ids: list[int]
    tensor_parallel_size: int
    pipeline_parallel_size: int = 1
    listen_host: str = "0.0.0.0"
    listen_port: int = 8000
    dtype: str = "bfloat16"
    gpu_memory_utilization: float = 0.85
    max_model_len: int | None = None
    enable_prefix_caching: bool = True
    enable_lora: bool = True
    api_key: str
    extra_args: dict[str, Any] = Field(default_factory=dict)


class SmokeTestSpec(BaseModel):
    enabled: bool = True
    prompt: str = "Reply with ok."
    timeout_seconds: int = 60


class AgentDeploymentSpec(BaseModel):
    deployment_id: str
    generation: int
    desired_phase: str = "running"
    model: ModelBinding
    lora_adapters: list[LoraAdapterBinding] = Field(default_factory=list)
    engine: EngineSpec
    smoke_test: SmokeTestSpec | None = Field(default_factory=SmokeTestSpec)


class AgentErrorDetail(BaseModel):
    code: str
    message: str


class AgentDeploymentStatus(BaseModel):
    deployment_id: str | None = None
    generation: int = 0
    phase: str = "idle"
    progress: int = 0
    endpoint: str | None = None
    active_model_name: str | None = None
    local_path: str | None = None
    container_id: str | None = None
    last_event: str | None = None
    error: AgentErrorDetail | None = None
    observed_at: datetime | None = None
    last_health_ok_at: datetime | None = None


class ModelDeploymentSummary(BaseModel):
    id: UUID
    name: str
    model_id: UUID | None = None
    model_name: str | None = None
    machine_id: UUID | None = None
    machine_name: str | None = None
    experience_model_id: UUID | None = None
    experience_provider_id: UUID | None = None
    status: str
    endpoint_url: str | None = None
    agent_base_url: str | None = None
    served_model_name: str | None = None
    is_current: bool = False
    generation: int = 0
    phase: str | None = None
    progress: int = 0
    last_event: str | None = None
    error_message: str | None = None
    last_passive_health_status: str | None = None
    last_passive_health_checked_at: datetime | None = None
    last_passive_health_latency_ms: int | None = None
    last_passive_health_error: str | None = None
    unload_task_status: str | None = None
    unload_task_started_at: datetime | None = None
    unload_task_finished_at: datetime | None = None
    unload_task_message: str | None = None
    unload_task_warning: str | None = None
    deleted_task_kinds: list[str] = Field(default_factory=list)
    created_at: datetime
    updated_at: datetime


class ModelDeploymentEvent(BaseModel):
    id: int | None = None
    deployment_id: str | None = None
    generation: int = 0
    event_type: str
    level: str
    message: str
    progress: int | None = None
    payload: dict[str, Any] = Field(default_factory=dict)
    created_at: datetime


class DeployModelRequest(BaseModel):
    name: str | None = Field(default=None, max_length=120)
    machine_id: UUID | None = None
    served_model_name: str | None = Field(default=None, max_length=160)
    adapter_model_id: UUID | None = None
    adapter_served_model_name: str | None = Field(default=None, max_length=160)
    gpu_ids: list[int] | None = None
    tensor_parallel_size: int | None = Field(default=None, ge=1, le=16)
    max_model_len: int | None = Field(default=None, ge=1)
    dtype: str | None = None


class ModelDeploymentPassiveHealth(BaseModel):
    deployment_id: UUID
    status: str
    prompt: str = "hi"
    output_text: str | None = None
    latency_ms: int | None = None
    checked_at: datetime
    error: str | None = None


class InferenceMachineSummary(BaseModel):
    id: UUID
    name: str
    agent_base_url: str
    runtime_public_host: str | None = None
    description: str | None = None
    status: str
    has_agent_token: bool = False
    has_runtime_api_key: bool = False
    vllm_image: str
    gpu_ids: list[int] = Field(default_factory=list)
    tensor_parallel_size: int
    dtype: str
    gpu_memory_utilization: float
    max_model_len: int | None = None
    listen_port: int
    last_health_status: str | None = None
    last_health_checked_at: datetime | None = None
    last_health_error: str | None = None
    last_node_name: str | None = None
    last_gpu_count: int | None = None
    last_gpus: list[dict[str, Any]] = Field(default_factory=list)
    created_at: datetime
    updated_at: datetime


class InferenceMachineCreate(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    agent_base_url: str = Field(min_length=8, max_length=500)
    agent_token: str = Field(min_length=1, max_length=4000)
    runtime_api_key: str = Field(min_length=1, max_length=4000)
    runtime_public_host: str | None = Field(default=None, max_length=255)
    description: str | None = Field(default=None, max_length=500)
    vllm_image: str = Field(default="vllm/vllm-openai:latest", min_length=1, max_length=255)
    gpu_ids: list[int] = Field(default_factory=list)
    tensor_parallel_size: int = Field(default=8, ge=1, le=64)
    dtype: str = Field(default="bfloat16", min_length=1, max_length=32)
    gpu_memory_utilization: float = Field(default=0.85, ge=0.1, le=1.0)
    max_model_len: int | None = Field(default=None, ge=1)
    listen_port: int = Field(default=8000, ge=1, le=65535)

    @field_validator("agent_token", "runtime_api_key")
    @classmethod
    def validate_secret_text(cls, value: str) -> str:
        text = value.strip()
        if not text:
            raise ValueError("token must not be empty")
        return text


class InferenceMachineHealth(BaseModel):
    machine_id: UUID
    status: str
    node_name: str | None = None
    current: dict[str, Any] | None = None
    gpus: list[dict[str, Any]] = Field(default_factory=list)
    checked_at: datetime
    error: str | None = None


class RuntimeMetricSample(BaseModel):
    name: str
    value: float
    labels: dict[str, str] = Field(default_factory=dict)


class InferenceMachineRuntimeMetrics(BaseModel):
    machine_id: UUID
    status: str
    checked_at: datetime
    endpoint: str | None = None
    latency_ms: int | None = None
    metric_count: int = 0
    summary: dict[str, float] = Field(default_factory=dict)
    metrics: list[RuntimeMetricSample] = Field(default_factory=list)
    error: str | None = None
