from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

BronzeAssetType = Literal[
    "web_page",
    "website_batch",
    "pdf",
    "markdown",
    "markdown_package",
    "image",
    "object_prefix",
]
BronzeImportMethod = Literal[
    "url",
    "url_list",
    "sitemap",
    "upload",
    "uploaded_package",
    "object_key",
    "object_prefix",
]


class BronzeImportCreate(BaseModel):
    asset_type: BronzeAssetType = "web_page"
    import_method: BronzeImportMethod | None = None
    source_uri: str | None = Field(default=None, max_length=20000)
    name: str | None = Field(default=None, max_length=255)
    provider: str | None = Field(default=None, max_length=120)
    product: str | None = Field(default=None, max_length=120)
    tags: list[str] = Field(default_factory=list)
    capture_mode: str = Field(default="raw_render_screenshot", max_length=120)
    extract_images: bool = True
    trigger_silver: bool = False
    entrypoint: str | None = Field(default=None, max_length=1000)
    manifest_uri: str | None = Field(default=None, max_length=4000)
    metadata: dict[str, object] = Field(default_factory=dict)


class BronzeAssetPatch(BaseModel):
    name: str | None = Field(default=None, max_length=255)
    provider: str | None = Field(default=None, max_length=120)
    product: str | None = Field(default=None, max_length=120)
    tags: list[str] | None = None
    metadata: dict[str, object] | None = None


class BronzeArtifactSummary(BaseModel):
    id: str
    snapshot_id: str | None = None
    name: str
    artifact_type: str
    object_bucket: str | None = None
    object_key: str | None = None
    source_uri: str | None = None
    mime_type: str | None = None
    size_bytes: int | None = None
    preview_kind: str = "unsupported"
    created_at: datetime | None = None


class BronzeSnapshotSummary(BaseModel):
    id: str
    asset_id: str
    status: str
    snapshot_time: datetime
    raw_hash: str | None = None
    rendered_hash: str | None = None
    text_hash: str | None = None
    content_hash: str | None = None
    artifact_count: int = 0
    diff_status: str = "new"
    metadata: dict[str, object] = Field(default_factory=dict)


class BronzeJobSummary(BaseModel):
    id: str
    name: str
    source_type: str
    resource_type: str | None = None
    status: str
    planned_asset_count: int = 0
    completed_asset_count: int = 0
    failed_asset_count: int = 0
    tags: list[str] = Field(default_factory=list)
    metadata: dict[str, object] = Field(default_factory=dict)
    created_at: datetime
    updated_at: datetime


class BronzeLineageSummary(BaseModel):
    silver_ready: bool = False
    gold_outputs: list[str] = Field(default_factory=list)
    downstream_jobs: list[str] = Field(default_factory=list)


class BronzeAssetSummary(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    name: str
    description: str | None = None
    source_type: str
    source_uri: str | None = None
    provider: str | None = None
    product: str | None = None
    tags: list[str] = Field(default_factory=list)
    latest_snapshot_id: str | None = None
    latest_snapshot_at: datetime | None = None
    artifact_count: int = 0
    image_count: int = 0
    hash_status: str = "new"
    status: str
    ingestion_job_id: str
    ingestion_job_name: str
    object_bucket: str | None = None
    object_key: str | None = None
    size_bytes: int | None = None
    metadata: dict[str, object] = Field(default_factory=dict)
    error_message: str | None = None
    created_at: datetime
    updated_at: datetime


class BronzeAssetDetail(BronzeAssetSummary):
    snapshots: list[BronzeSnapshotSummary] = Field(default_factory=list)
    artifacts: list[BronzeArtifactSummary] = Field(default_factory=list)
    logs: list[str] = Field(default_factory=list)
    lineage: BronzeLineageSummary = Field(default_factory=BronzeLineageSummary)


class BronzeImportCreateResponse(BaseModel):
    asset: BronzeAssetDetail
    job: BronzeJobSummary


class BronzeArtifactSignedUrl(BaseModel):
    artifact_id: str
    url: str
    expires_in: int = 900
