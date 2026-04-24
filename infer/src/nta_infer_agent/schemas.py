from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, Field, SecretStr, field_validator


class ObjectStorageCredentials(BaseModel):
    access_key_id: str
    secret_access_key: SecretStr
    session_token: str | None = None
    expires_at: datetime | None = None


class ObjectStorageSource(BaseModel):
    uri: str = Field(min_length=8)
    endpoint_url: str | None = None
    region: str = "us-east-1"
    addressing_style: Literal["auto", "path", "virtual"] = "path"
    credentials: ObjectStorageCredentials | None = None


class HuggingFaceSource(BaseModel):
    repo_id: str = Field(min_length=1)
    revision: str = "main"
    repo_type: Literal["model"] = "model"
    allow_patterns: list[str] | None = None
    ignore_patterns: list[str] | None = None
    token: SecretStr | None = None
    endpoint_url: str | None = None


class ModelSource(BaseModel):
    type: Literal["object_storage", "huggingface", "local"] = "object_storage"
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
    name: Literal["vllm"] = "vllm"
    image: str
    gpu_ids: list[int] = Field(default_factory=list)
    tensor_parallel_size: int = 8
    pipeline_parallel_size: int = 1
    listen_host: str = "0.0.0.0"
    listen_port: int = 8000
    dtype: str = "bfloat16"
    gpu_memory_utilization: float = 0.85
    max_model_len: int | None = None
    enable_prefix_caching: bool = True
    enable_lora: bool = True
    api_key: SecretStr
    extra_args: dict[str, Any] = Field(default_factory=dict)

    @field_validator("api_key")
    @classmethod
    def validate_api_key(cls, value: SecretStr) -> SecretStr:
        api_key = value.get_secret_value().strip()
        if not api_key:
            raise ValueError("vLLM runtime api_key must not be empty")
        return SecretStr(api_key)


class SmokeTestSpec(BaseModel):
    enabled: bool = True
    prompt: str = "Reply with ok."
    timeout_seconds: int = 60


class DeploymentSpec(BaseModel):
    deployment_id: str
    generation: int = Field(ge=1)
    desired_phase: Literal["running", "stopped"] = "running"
    model: ModelBinding
    engine: EngineSpec
    smoke_test: SmokeTestSpec | None = Field(default_factory=SmokeTestSpec)


class ErrorDetail(BaseModel):
    code: str
    message: str


class DeploymentStatus(BaseModel):
    deployment_id: str | None = None
    generation: int = 0
    phase: str = "idle"
    progress: int = 0
    endpoint: str | None = None
    active_model_name: str | None = None
    local_path: str | None = None
    container_id: str | None = None
    last_event: str | None = None
    error: ErrorDetail | None = None
    observed_at: datetime | None = None
    last_health_ok_at: datetime | None = None


class DeploymentEvent(BaseModel):
    id: int | None = None
    deployment_id: str | None = None
    generation: int = 0
    event_type: str
    level: Literal["info", "warning", "error"] = "info"
    message: str
    progress: int | None = None
    payload: dict[str, Any] = Field(default_factory=dict)
    created_at: datetime


class HealthResponse(BaseModel):
    status: Literal["ok"]
    node_name: str
    current: DeploymentStatus
    gpus: list[dict[str, Any]] = Field(default_factory=list)


class RuntimeMetricSample(BaseModel):
    name: str
    value: float
    labels: dict[str, str] = Field(default_factory=dict)


class RuntimeMetricsResponse(BaseModel):
    status: Literal["ok", "unavailable", "error"]
    checked_at: datetime
    endpoint: str | None = None
    latency_ms: int | None = None
    metric_count: int = 0
    summary: dict[str, float] = Field(default_factory=dict)
    metrics: list[RuntimeMetricSample] = Field(default_factory=list)
    error: str | None = None
