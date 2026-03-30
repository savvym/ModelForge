from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from nta_backend.schemas.object_store import (
    ObjectStoreDirectUploadInitResponse,
    ObjectStoreUploadResponse,
)


class DatasetSummary(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    name: str
    description: str | None = None
    purpose: str | None = None
    format: str | None = None
    use_case: str | None = None
    modality: str | None = None
    recipe: str | None = None
    scope: str = "my-datasets"
    source_type: str = "local-upload"
    status: str
    latest_version: int | None = None
    latest_version_id: UUID | None = None
    owner_name: str | None = None
    tags: list[str] = []
    record_count: int | None = None
    created_at: datetime
    updated_at: datetime | None = None


class DatasetFileSummary(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    version_id: UUID
    file_name: str
    object_key: str
    mime_type: str | None = None
    size_bytes: int | None = None
    etag: str | None = None
    created_at: datetime
    updated_at: datetime | None = None


class DatasetVersionSummary(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    dataset_id: str
    version: int
    status: str
    description: str | None = None
    file_name: str | None = None
    format: str | None = None
    source_type: str
    source_uri: str | None = None
    object_key: str | None = None
    record_count: int | None = None
    created_at: datetime
    updated_at: datetime | None = None
    created_by: str | None = None
    file_count: int = 0
    files: list[DatasetFileSummary] = []


class DatasetVersionPreview(BaseModel):
    dataset_id: str
    version_id: UUID
    file_id: UUID | None = None
    file_name: str
    content: str
    truncated: bool
    content_bytes: int


class DatasetDetail(DatasetSummary):
    source_uri: str | None = None
    versions: list[DatasetVersionSummary]


class DatasetCreate(BaseModel):
    name: str
    description: str | None = None
    purpose: str = "evaluation"
    format: str = "jsonl"
    use_case: str | None = None
    modality: str | None = None
    recipe: str | None = None
    scope: str = "my-datasets"
    source_type: str = "local-upload"
    tags: list[str] = []
    file_name: str | None = None
    source_uri: str | None = None


class DatasetVersionCreate(BaseModel):
    description: str | None = None
    source_type: str = "local-upload"
    format: str | None = None
    file_name: str | None = None
    source_uri: str | None = None


class DatasetCreateResponse(BaseModel):
    dataset_id: str
    version_id: UUID
    status: str
    object_key: str | None = None
    source_uri: str | None = None


class DatasetDirectUploadInitRequest(BaseModel):
    name: str
    description: str | None = None
    purpose: str = "evaluation"
    format: str = "jsonl"
    use_case: str | None = None
    modality: str | None = None
    recipe: str | None = None
    scope: str = "my-datasets"
    tags: list[str] = Field(default_factory=list)
    file_name: str
    file_size: int
    content_type: str | None = None


class DatasetVersionDirectUploadInitRequest(BaseModel):
    description: str | None = None
    format: str | None = None
    file_name: str
    file_size: int
    content_type: str | None = None


class DatasetDirectUploadInitResponse(DatasetCreateResponse):
    file_name: str
    upload: ObjectStoreDirectUploadInitResponse


class DatasetDirectUploadCompleteRequest(BaseModel):
    upload: ObjectStoreUploadResponse


class DatasetDirectUploadFailedRequest(BaseModel):
    reason: str | None = None


class PresignUploadRequest(BaseModel):
    dataset_id: str | None = None
    file_name: str
    bucket: str = "nta-default"


class PresignUploadResponse(BaseModel):
    bucket: str
    object_key: str
    url: str
    expires_in: int
