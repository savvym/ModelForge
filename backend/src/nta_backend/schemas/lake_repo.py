from __future__ import annotations

import re
from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator

REPO_NAME_RE = re.compile(r"^[a-z0-9][a-z0-9._-]{0,62}[a-z0-9]$|^[a-z0-9]$")


class LakeRepoCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=64)
    display_name: str | None = Field(default=None, max_length=255)
    description: str | None = None
    visibility: Literal["private", "internal"] = "private"

    @field_validator("name")
    @classmethod
    def _validate_name(cls, value: str) -> str:
        normalized = value.strip().lower()
        if not REPO_NAME_RE.fullmatch(normalized):
            raise ValueError(
                "仓库名称只能包含小写字母、数字、点、下划线和连字符，且需以字母或数字开头和结尾。"
            )
        return normalized


class LakeRepoUpdate(BaseModel):
    display_name: str | None = Field(default=None, max_length=255)
    description: str | None = None
    default_branch: str | None = Field(default=None, max_length=64)


class CommitSummary(BaseModel):
    sha: str
    message: str
    author_name: str
    author_email: str
    committed_at: datetime
    parents: list[str] = Field(default_factory=list)


class LakeRepoSummary(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    project_id: UUID
    name: str
    display_name: str
    description: str | None = None
    gitea_org: str
    gitea_repo: str
    default_branch: str
    visibility: str
    status: str
    created_at: datetime
    updated_at: datetime


class LakeRepoDetail(LakeRepoSummary):
    web_url: str | None = None
    clone_url: str | None = None
    last_commit: CommitSummary | None = None
    size_kib: int | None = None
    empty: bool = False


class TreeEntry(BaseModel):
    type: Literal["dir", "file", "symlink", "submodule"]
    path: str
    name: str
    sha: str
    size: int | None = None
    is_lfs: bool = False


class TreeResponse(BaseModel):
    ref: str
    path: str
    entries: list[TreeEntry]


class FileResponse(BaseModel):
    path: str
    ref: str
    name: str
    sha: str
    size: int
    mime_type: str | None = None
    is_binary: bool = False
    is_lfs: bool = False
    encoding: Literal["utf8", "base64"] | None = None
    content: str | None = None
    download_url: str | None = None


class CommitListResponse(BaseModel):
    commits: list[CommitSummary]
    page: int
    page_size: int
    total: int


class BranchSummary(BaseModel):
    name: str
    commit_sha: str
    is_default: bool


class UploadFile(BaseModel):
    path: str = Field(..., min_length=1, max_length=4096)
    content_b64: str = Field(..., description="Base64-encoded file content.")

    @field_validator("path")
    @classmethod
    def _validate_path(cls, value: str) -> str:
        normalized = value.strip().lstrip("/").replace("\\", "/")
        if not normalized or ".." in normalized.split("/"):
            raise ValueError("文件路径不合法")
        return normalized


class BatchUploadRequest(BaseModel):
    branch: str = Field(..., min_length=1, max_length=64)
    message: str = Field(..., min_length=1, max_length=4096)
    files: list[UploadFile] = Field(..., min_length=1, max_length=100)


class BatchUploadResponse(BaseModel):
    commit_sha: str
    committed_at: datetime | None = None


class LakeRepoListResponse(BaseModel):
    items: list[LakeRepoSummary]
    total: int
    page: int
    page_size: int
