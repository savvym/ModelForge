from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from nta_backend.schemas.object_store import (
    ObjectStoreDirectUploadInitResponse,
    ObjectStoreUploadResponse,
)


class LakeBatchCreate(BaseModel):
    name: str = Field(min_length=1, max_length=255)
    description: str | None = Field(default=None, max_length=1000)
    source_type: str = Field(default="upload", min_length=1, max_length=64)
    resource_type: str | None = Field(default=None, max_length=64)
    planned_file_count: int = Field(default=1, ge=1)
    root_paths: list[str] = Field(default_factory=list)
    tags: list[str] = Field(default_factory=list)
    metadata: dict[str, object] = Field(default_factory=dict)


class LakeBatchSummary(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    name: str
    description: str | None = None
    stage: str
    source_type: str
    resource_type: str | None = None
    status: str
    planned_file_count: int = 0
    completed_file_count: int = 0
    failed_file_count: int = 0
    total_size_bytes: int = 0
    tags: list[str] = Field(default_factory=list)
    metadata: dict[str, object] = Field(default_factory=dict)
    created_at: datetime
    updated_at: datetime


class LakeAssetSummary(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    batch_id: str
    batch_name: str
    parent_asset_id: str | None = None
    name: str
    description: str | None = None
    stage: str
    source_type: str
    resource_type: str | None = None
    format: str | None = None
    mime_type: str | None = None
    relative_path: str | None = None
    object_key: str | None = None
    source_uri: str | None = None
    size_bytes: int | None = None
    record_count: int | None = None
    status: str
    tags: list[str] = Field(default_factory=list)
    metadata: dict[str, object] = Field(default_factory=dict)
    error_message: str | None = None
    created_at: datetime
    updated_at: datetime


class LakeAssetDirectUploadInitRequest(BaseModel):
    batch_id: str
    description: str | None = Field(default=None, max_length=1000)
    source_type: str = Field(default="upload", min_length=1, max_length=64)
    resource_type: str | None = Field(default=None, max_length=64)
    tags: list[str] = Field(default_factory=list)
    metadata: dict[str, object] = Field(default_factory=dict)
    file_name: str
    file_size: int = Field(gt=0)
    content_type: str | None = None
    relative_path: str | None = None


class LakeAssetDirectUploadInitResponse(BaseModel):
    batch_id: str
    asset_id: str
    status: str
    object_key: str
    source_uri: str
    file_name: str
    upload: ObjectStoreDirectUploadInitResponse


class LakeAssetDirectUploadCompleteRequest(BaseModel):
    upload: ObjectStoreUploadResponse


class LakeAssetDirectUploadFailedRequest(BaseModel):
    reason: str | None = None


class LakeUploadAbortRequest(BaseModel):
    batch_id: str | None = None
    asset_ids: list[str] = Field(default_factory=list)
    reason: str | None = None
