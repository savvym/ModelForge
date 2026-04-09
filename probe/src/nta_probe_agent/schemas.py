from __future__ import annotations

from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, Field


class ProbeRegistrationRequest(BaseModel):
    name: str
    display_name: str | None = None
    isp: str | None = None
    asn: int | None = None
    region: str | None = None
    country: str | None = None
    city: str | None = None
    network_type: str = "cloud"
    tags: list[str] = Field(default_factory=list)
    agent_version: str | None = None
    device_info: dict[str, Any] = Field(default_factory=dict)
    metadata: dict[str, Any] = Field(default_factory=dict)


class ProbeRegistrationResponse(BaseModel):
    probe_id: UUID
    name: str
    display_name: str
    status: str
    auth_token: str
    heartbeat_interval_seconds: int
    claim_ttl_seconds: int


class ProbeHeartbeatRequest(BaseModel):
    network_metrics: dict[str, Any] = Field(default_factory=dict)
    agent_status: dict[str, Any] = Field(default_factory=dict)


class ProbeHeartbeatResponse(BaseModel):
    status: str
    server_time: datetime


class EvalScopePerfTaskConfig(BaseModel):
    model: str
    url: str
    api: str = "openai"
    headers: dict[str, str] = Field(default_factory=dict)
    api_key: str | None = None
    api_key_env: str | None = None
    prompt: str | None = None
    query_template: str | None = None
    dataset: str = "openqa"
    dataset_path: str | None = None
    number: int | list[int] = 4
    parallel: int | list[int] = 1
    rate: float = -1
    max_tokens: int | None = 256
    min_tokens: int | None = None
    stream: bool = True
    temperature: float = 0.0
    top_p: float | None = None
    top_k: int | None = None
    seed: int | None = None
    connect_timeout: int | None = None
    read_timeout: int | None = None
    total_timeout: int | None = 600
    no_test_connection: bool = False
    enable_progress_tracker: bool = True
    extra_args: dict[str, Any] = Field(default_factory=dict)
    output_name: str | None = None


class ProbeTaskClaim(BaseModel):
    id: UUID
    probe_id: UUID
    name: str
    task_type: str
    timeout_seconds: int
    attempt_count: int
    payload_json: dict[str, Any] = Field(default_factory=dict)
    created_at: datetime
    lease_expires_at: datetime | None = None


class ProbeTaskClaimResponse(BaseModel):
    task: ProbeTaskClaim | None = None


class ProbeTaskStartRequest(BaseModel):
    summary: str | None = None


class ProbeTaskProgressRequest(BaseModel):
    summary: str | None = None
    step: int | None = None
    total: int | None = None
    payload: dict[str, Any] = Field(default_factory=dict)


class ProbeTaskCompleteRequest(BaseModel):
    result_json: dict[str, Any] = Field(default_factory=dict)


class ProbeTaskFailRequest(BaseModel):
    error_message: str
    result_json: dict[str, Any] | None = None


class ProbeTaskTransitionResponse(BaseModel):
    task_id: UUID
    status: str
