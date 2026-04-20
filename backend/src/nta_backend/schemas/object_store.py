from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field


class ObjectStorePrefixEntry(BaseModel):
    name: str
    prefix: str


class ObjectStoreObjectEntry(BaseModel):
    key: str
    name: str
    size_bytes: int
    last_modified: datetime | None = None


class ObjectStoreBrowserResponse(BaseModel):
    bucket: str
    prefix: str = ""
    parent_prefix: str | None = None
    search_query: str | None = None
    buckets: list[str]
    prefixes: list[ObjectStorePrefixEntry]
    objects: list[ObjectStoreObjectEntry]


class ObjectStoreUploadResponse(BaseModel):
    bucket: str
    object_key: str
    uri: str
    file_name: str
    size_bytes: int
    content_type: str | None = None
    last_modified: datetime


class ObjectStoreObjectPreviewResponse(BaseModel):
    bucket: str
    object_key: str
    file_name: str
    preview_kind: Literal["text", "image", "pdf", "unsupported"]
    content_type: str | None = None
    content: str | None = None
    truncated: bool = False
    content_bytes: int | None = None


class ObjectStoreObjectTextUpdateRequest(BaseModel):
    bucket: str
    object_key: str
    content: str
    content_type: str | None = None


class ObjectStoreFolderCreateRequest(BaseModel):
    bucket: str | None = None
    prefix: str | None = None
    name: str


class ObjectStoreFolderResponse(BaseModel):
    bucket: str
    prefix: str
    name: str
    uri: str


class ObjectStoreDirectUploadInitRequest(BaseModel):
    bucket: str | None = None
    prefix: str | None = None
    file_name: str
    file_size: int
    content_type: str | None = None
    relative_path: str | None = None


class ObjectStoreDirectUploadStsCredentials(BaseModel):
    tmp_secret_id: str
    tmp_secret_key: str
    session_token: str
    start_time: int
    expired_time: int
    scope_limit: bool = True


class ObjectStoreDirectUploadInitResponse(BaseModel):
    bucket: str
    object_key: str
    uri: str
    file_name: str
    size_bytes: int
    content_type: str | None = None
    expires_in: int
    provider: Literal["presigned", "cos-sts"] = "presigned"
    region: str | None = None
    domain: str | None = None
    protocol: str | None = None
    sts: ObjectStoreDirectUploadStsCredentials | None = None
    method: str | None = "PUT"
    headers: dict[str, str] = Field(default_factory=dict)
    url: str | None = None
