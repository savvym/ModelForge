from __future__ import annotations

from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class TrainingCosStatus(BaseModel):
    enabled: bool
    configured: bool
    bucket: str | None = None
    bucket_alias: str | None = None
    region: str | None = None
    endpoint: str | None = None
    target_prefix: str | None = None
    addressing_style: str | None = None


class TrainingCosEntry(BaseModel):
    type: Literal["dir", "file"]
    name: str
    key: str
    size: int | None = None
    last_modified: str | None = None
    etag: str | None = None


class TrainingCosListResponse(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    prefix: str
    parent_prefix: str | None = None
    entries: list[TrainingCosEntry]
    next_token: str | None = None
    truncated: bool = False


class TrainingCosPreviewResponse(BaseModel):
    key: str
    name: str
    size: int
    mime_type: str | None = None
    is_binary: bool = False
    encoding: Literal["utf8", "base64"] | None = None
    content: str | None = None
    download_url: str
    last_modified: str | None = None
    etag: str | None = None
    truncated: bool = Field(
        default=False,
        description=(
            "True when content is a partial preview because the file is too large to embed inline."
        ),
    )


TrainingCosHuggingFaceRepoType = Literal["model", "dataset", "space"]
TrainingCosHuggingFaceSyncStatus = Literal["pending", "running", "succeeded", "failed"]


class TrainingCosHuggingFaceRepoSummary(BaseModel):
    repo_id: str
    repo_type: TrainingCosHuggingFaceRepoType
    private: bool | None = None
    author: str | None = None
    tags: list[str] = Field(default_factory=list)
    last_modified: str | None = None
    url: str | None = None


class TrainingCosHuggingFaceRepoSearchResponse(BaseModel):
    repo_type: TrainingCosHuggingFaceRepoType
    query: str
    repos: list[TrainingCosHuggingFaceRepoSummary]


class TrainingCosHuggingFaceFolderFile(BaseModel):
    key: str
    relative_path: str
    name: str
    size: int
    last_modified: str | None = None
    etag: str | None = None


class TrainingCosHuggingFaceFolderFilesResponse(BaseModel):
    prefix: str
    files: list[TrainingCosHuggingFaceFolderFile]
    total_size: int
    truncated: bool = False


class TrainingCosHuggingFaceSyncCreateRequest(BaseModel):
    prefix: str = Field(min_length=1, max_length=2048)
    repo_id: str = Field(min_length=1, max_length=256)
    repo_type: TrainingCosHuggingFaceRepoType = "model"
    create_if_missing: bool = True
    private: bool = False
    create_readme: bool = True
    license: str | None = Field(default=None, max_length=120)
    base_model: str | None = Field(default=None, max_length=256)
    tags: list[str] = Field(default_factory=list, max_length=32)
    exclude_keys: list[str] = Field(default_factory=list, max_length=10000)


class TrainingCosHuggingFaceSyncLog(BaseModel):
    level: str
    message: str
    logged_at: datetime
    payload: dict | None = None


class TrainingCosHuggingFaceSyncJob(BaseModel):
    id: UUID
    prefix: str
    repo_id: str
    repo_type: TrainingCosHuggingFaceRepoType
    status: TrainingCosHuggingFaceSyncStatus
    progress_total: int | None = None
    progress_done: int | None = None
    progress_percent: int = 0
    total_files: int = 0
    total_bytes: int = 0
    downloaded_files: int = 0
    downloaded_bytes: int = 0
    skipped_files: int = 0
    created_repo: bool = False
    repo_url: str | None = None
    error_message: str | None = None
    created_at: datetime
    updated_at: datetime
    started_at: datetime | None = None
    finished_at: datetime | None = None
    logs: list[TrainingCosHuggingFaceSyncLog] = Field(default_factory=list)


class TrainingCosHuggingFaceSyncJobListResponse(BaseModel):
    prefix: str | None = None
    last_sync_at: datetime | None = None
    jobs: list[TrainingCosHuggingFaceSyncJob]
