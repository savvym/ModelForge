from __future__ import annotations

from datetime import datetime
from typing import Any, Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, model_validator


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


class ProbeHeartbeatSummary(BaseModel):
    ip_address: str
    network_metrics_json: dict[str, Any] = Field(default_factory=dict)
    agent_status_json: dict[str, Any] = Field(default_factory=dict)
    created_at: datetime


class ProbeSummary(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    name: str
    display_name: str
    status: str
    ip_address: str | None = None
    isp: str | None = None
    asn: int | None = None
    region: str | None = None
    country: str | None = None
    city: str | None = None
    network_type: str
    tags_json: list[Any] = Field(default_factory=list)
    agent_version: str | None = None
    device_info_json: dict[str, Any] = Field(default_factory=dict)
    metadata_json: dict[str, Any] = Field(default_factory=dict)
    last_heartbeat: datetime | None = None
    last_error_message: str | None = None
    created_at: datetime
    updated_at: datetime


class ProbeDetail(ProbeSummary):
    heartbeats: list[ProbeHeartbeatSummary] = Field(default_factory=list)


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


class ProbeTaskCreate(BaseModel):
    probe_id: UUID
    name: str | None = None
    runtime_kind: Literal["evalscope-perf"] = "evalscope-perf"
    timeout_seconds: int = 3600
    config: EvalScopePerfTaskConfig

    @model_validator(mode="after")
    def _validate_timeout(self) -> ProbeTaskCreate:
        if self.timeout_seconds <= 0:
            raise ValueError("timeout_seconds must be greater than 0")
        return self


class ProbeTaskSummary(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    probe_id: UUID
    name: str
    task_type: str
    status: str
    timeout_seconds: int
    attempt_count: int
    payload_json: dict[str, Any] = Field(default_factory=dict)
    progress_json: dict[str, Any] = Field(default_factory=dict)
    result_json: dict[str, Any] | None = None
    error_message: str | None = None
    claimed_at: datetime | None = None
    started_at: datetime | None = None
    finished_at: datetime | None = None
    lease_expires_at: datetime | None = None
    created_at: datetime
    updated_at: datetime


class ProbeTaskDetail(ProbeTaskSummary):
    pass


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
