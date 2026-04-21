from datetime import datetime
from typing import Any, Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class ModelProviderSummary(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    name: str
    provider_type: str
    adapter: str
    api_format: str
    base_url: str
    organization: str | None = None
    description: str | None = None
    status: str
    has_api_key: bool = False
    model_count: int = 0
    last_synced_at: datetime | None = None
    created_at: datetime
    updated_at: datetime


class ModelProviderCreate(BaseModel):
    name: str = Field(min_length=2, max_length=120)
    provider_type: str = "openai-compatible"
    adapter: str = "litellm"
    api_format: str = "chat-completions"
    base_url: str = Field(min_length=8, max_length=500)
    api_key: str | None = Field(default=None, max_length=4000)
    organization: str | None = Field(default=None, max_length=120)
    description: str | None = Field(default=None, max_length=500)


class ModelProviderUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=2, max_length=120)
    api_format: str | None = None
    base_url: str | None = Field(default=None, min_length=8, max_length=500)
    api_key: str | None = Field(default=None, max_length=4000)
    organization: str | None = Field(default=None, max_length=120)
    status: str | None = None
    description: str | None = Field(default=None, max_length=500)


class ModelProviderSyncResult(BaseModel):
    provider_id: UUID
    provider_name: str
    synced_count: int
    created_count: int
    updated_count: int
    last_synced_at: datetime


class RegistryModelSummary(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    name: str
    model_code: str | None = None
    vendor: str | None = None
    source: str | None = None
    api_format: str | None = None
    base_model: str | None = None
    category: str | None = None
    description: str | None = None
    import_source_type: str | None = None
    import_source_uri: str | None = None
    import_bucket: str | None = None
    import_object_key: str | None = None
    import_repo_id: str | None = None
    import_revision: str | None = None
    status: str
    provider_id: UUID | None = None
    provider_name: str | None = None
    is_provider_managed: bool = False
    last_synced_at: datetime | None = None
    created_at: datetime
    updated_at: datetime


class RegistryModelCreate(BaseModel):
    name: str = Field(min_length=2, max_length=120)
    model_code: str = Field(min_length=1, max_length=160)
    provider_id: UUID | None = None
    vendor: str | None = Field(default=None, max_length=64)
    source: str = "manual"
    api_format: str = "chat-completions"
    category: str | None = Field(default=None, max_length=64)
    description: str | None = Field(default=None, max_length=500)


class RegistryModelObjectStorageImport(BaseModel):
    name: str = Field(min_length=2, max_length=120)
    base_model: str = Field(min_length=1, max_length=120)
    source_uri: str = Field(min_length=8, max_length=2000)
    description: str | None = Field(default=None, max_length=500)


class RegistryModelHuggingFaceImport(BaseModel):
    name: str = Field(min_length=2, max_length=120)
    base_model: str = Field(min_length=1, max_length=120)
    repo_id: str = Field(min_length=1, max_length=500)
    revision: str | None = Field(default=None, max_length=160)
    hf_token: str | None = Field(default=None, max_length=4000)
    description: str | None = Field(default=None, max_length=500)


class RegistryModelHuggingFaceSearchRequest(BaseModel):
    query: str = Field(min_length=2, max_length=200)
    hf_token: str | None = Field(default=None, max_length=4000)
    limit: int = Field(default=12, ge=1, le=30)


class RegistryModelHuggingFaceSearchResult(BaseModel):
    repo_id: str
    author: str | None = None
    pipeline_tag: str | None = None
    library_name: str | None = None
    downloads: int | None = None
    likes: int | None = None
    is_private: bool = False
    is_gated: bool = False
    tags: list[str] = Field(default_factory=list)
    last_modified: str | None = None


class RegistryModelHuggingFaceRevisionRequest(BaseModel):
    repo_id: str = Field(min_length=1, max_length=500)


class RegistryModelHuggingFaceRevisionResult(BaseModel):
    name: str
    kind: Literal["branch", "tag", "convert"]
    ref: str | None = None
    target_commit: str | None = None


class RegistryModelUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=2, max_length=120)
    model_code: str | None = Field(default=None, min_length=1, max_length=160)
    provider_id: UUID | None = None
    vendor: str | None = Field(default=None, max_length=64)
    api_format: str | None = None
    category: str | None = Field(default=None, max_length=64)
    status: str | None = None
    description: str | None = Field(default=None, max_length=500)


class RegistryModelTestRequest(BaseModel):
    prompt: str = Field(min_length=1, max_length=8000)


class RegistryModelTestResponse(BaseModel):
    model_id: UUID
    model_name: str
    model_code: str
    provider_id: UUID
    provider_name: str
    api_format: str
    prompt: str
    output_text: str
    latency_ms: int
    request_id: str | None = None


class RegistryModelChatMessage(BaseModel):
    role: str = Field(pattern="^(system|user|assistant)$")
    content: str = Field(min_length=1, max_length=16000)


class RegistryModelChatRequest(BaseModel):
    messages: list[RegistryModelChatMessage] = Field(min_length=1, max_length=32)
    reasoning_depth: str | None = Field(default=None, max_length=16)
    parameters: dict[str, Any] | None = None


class RegistryModelChatResponse(BaseModel):
    model_id: UUID
    model_name: str
    model_code: str
    provider_id: UUID
    provider_name: str
    api_format: str
    output_text: str
    reasoning_text: str | None = None
    latency_ms: int
    request_id: str | None = None
    input_tokens: int | None = None
    output_tokens: int | None = None
    total_tokens: int | None = None
