from __future__ import annotations

from typing import Literal

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
        description="True when content is a partial preview because the file is too large to embed inline.",
    )
