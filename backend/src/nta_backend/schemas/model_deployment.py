from __future__ import annotations

from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, Field


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
    api_key: str | None = None
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
    status: str
    endpoint_url: str | None = None
    agent_base_url: str | None = None
    served_model_name: str | None = None
    generation: int = 0
    phase: str | None = None
    progress: int = 0
    last_event: str | None = None
    error_message: str | None = None
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
    served_model_name: str | None = Field(default=None, max_length=160)
    gpu_ids: list[int] | None = None
    tensor_parallel_size: int | None = Field(default=None, ge=1, le=16)
    max_model_len: int | None = Field(default=None, ge=1)
    dtype: str | None = None
