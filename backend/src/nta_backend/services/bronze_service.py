from __future__ import annotations

from datetime import datetime
from pathlib import PurePosixPath
from urllib.parse import quote, urlparse
from uuid import UUID, uuid4

from sqlalchemy import select

from nta_backend.core.config import get_settings
from nta_backend.core.db import SessionLocal
from nta_backend.core.project_context import resolve_active_project_id
from nta_backend.models.lake import LakeAsset, LakeBatch
from nta_backend.schemas.bronze import (
    BronzeArtifactSummary,
    BronzeAssetDetail,
    BronzeAssetPatch,
    BronzeAssetSummary,
    BronzeImportCreate,
    BronzeImportCreateResponse,
    BronzeJobSummary,
    BronzeLineageSummary,
    BronzeSnapshotSummary,
)
from nta_backend.services.lake_service import (
    ASIA_SHANGHAI,
    LAKE_ASSET_CODE_PATTERN,
    LAKE_RAW_BUCKET,
    _lake_asset_code,
    _lake_batch_code,
    _load_asset_or_raise,
    _load_batch_or_raise,
)

BRONZE_METADATA_KEY = "bronze"
SNAPSHOT_PREFIX = "bs"
ARTIFACT_PREFIX = "ba"
CAPTURED_STATUSES = {"captured", "changed", "unchanged", "ready"}
DEFAULT_IMPORT_METHOD_BY_ASSET_TYPE = {
    "web_page": "url",
    "website_batch": "sitemap",
    "pdf": "object_key",
    "markdown": "object_key",
    "markdown_package": "object_prefix",
    "image": "object_key",
    "object_prefix": "object_prefix",
}
ALLOWED_IMPORT_METHODS_BY_ASSET_TYPE = {
    "web_page": {"url"},
    "website_batch": {"sitemap", "url_list"},
    "pdf": {"upload", "object_key"},
    "markdown": {"upload", "object_key"},
    "markdown_package": {"uploaded_package", "object_prefix"},
    "image": {"upload", "object_key"},
    "object_prefix": {"object_prefix"},
}
REGISTERED_ONLY_METHODS = {"url", "url_list", "sitemap"}
REGISTERED_ONLY_ASSET_TYPES = {"markdown_package", "object_prefix"}
FORMAT_BY_ASSET_TYPE = {
    "web_page": "html",
    "website_batch": "html",
    "pdf": "pdf",
    "markdown": "md",
    "markdown_package": "markdown_package",
    "image": "image",
    "object_prefix": "directory",
}
MIME_BY_ASSET_TYPE = {
    "web_page": "text/html",
    "website_batch": "text/html",
    "pdf": "application/pdf",
    "markdown": "text/markdown",
    "markdown_package": "application/vnd.nta.markdown-package",
    "image": None,
    "object_prefix": "application/x-directory",
}
PRIMARY_ARTIFACT_TYPE_BY_ASSET_TYPE = {
    "pdf": "original",
    "markdown": "primary_document",
    "image": "original_image",
}


def _now() -> datetime:
    return datetime.now(ASIA_SHANGHAI)


def _object_bucket() -> str:
    return get_settings().s3_bucket_dataset_raw or LAKE_RAW_BUCKET


def _metadata_dict(value: object) -> dict[str, object]:
    return value if isinstance(value, dict) else {}


def _bronze_metadata(asset: LakeAsset) -> dict[str, object]:
    return _metadata_dict(_metadata_dict(asset.extra_metadata).get(BRONZE_METADATA_KEY))


def _replace_bronze_metadata(asset: LakeAsset, updates: dict[str, object]) -> None:
    metadata = dict(asset.extra_metadata or {})
    bronze = dict(_metadata_dict(metadata.get(BRONZE_METADATA_KEY)))
    bronze.update(updates)
    metadata[BRONZE_METADATA_KEY] = bronze
    asset.extra_metadata = metadata


def _is_http_url(value: str) -> bool:
    parsed = urlparse(value)
    return parsed.scheme in {"http", "https"} and bool(parsed.netloc)


def _parse_object_storage_uri(value: str) -> tuple[str, str, str] | None:
    parsed = urlparse(value.strip())
    if parsed.scheme not in {"s3", "cos"} or not parsed.netloc:
        return None
    object_key = parsed.path.lstrip("/")
    if not object_key:
        return None
    return parsed.scheme, parsed.netloc, object_key


def _normalize_object_prefix(value: str) -> str:
    parsed = _parse_object_storage_uri(value)
    if parsed is None:
        return value
    scheme, bucket, object_key = parsed
    normalized_key = object_key if object_key.endswith("/") else f"{object_key}/"
    return f"{scheme}://{bucket}/{normalized_key}"


def _append_object_path(prefix_uri: str, relative_path: str) -> str | None:
    parsed = _parse_object_storage_uri(prefix_uri)
    if parsed is None:
        return None
    scheme, bucket, object_key = parsed
    prefix = object_key if object_key.endswith("/") else f"{object_key}/"
    child = relative_path.strip().lstrip("/")
    if not child:
        return None
    return f"{scheme}://{bucket}/{prefix}{child}"


def _infer_mime_from_key(object_key: str, fallback: str | None = None) -> str | None:
    suffix = PurePosixPath(object_key).suffix.lower()
    if suffix == ".pdf":
        return "application/pdf"
    if suffix in {".md", ".markdown"}:
        return "text/markdown"
    if suffix in {".html", ".htm"}:
        return "text/html"
    if suffix == ".json":
        return "application/json"
    if suffix in {".jpg", ".jpeg"}:
        return "image/jpeg"
    if suffix == ".png":
        return "image/png"
    if suffix == ".webp":
        return "image/webp"
    if suffix == ".gif":
        return "image/gif"
    if suffix == ".svg":
        return "image/svg+xml"
    return fallback


def _split_url_list(value: str) -> list[str]:
    normalized = value.replace(",", "\n")
    return [line.strip() for line in normalized.splitlines() if line.strip()]


def _resolve_import_method(payload: BronzeImportCreate) -> str:
    import_method = (
        payload.import_method or DEFAULT_IMPORT_METHOD_BY_ASSET_TYPE[payload.asset_type]
    )
    allowed_methods = ALLOWED_IMPORT_METHODS_BY_ASSET_TYPE[payload.asset_type]
    if import_method not in allowed_methods:
        allowed = "、".join(sorted(allowed_methods))
        raise ValueError(f"{payload.asset_type} 不支持 {import_method} 导入方式，可选：{allowed}。")
    return import_method


def _normalize_source_locator(
    asset_type: str,
    import_method: str,
    source_uri: str | None,
) -> str | None:
    normalized = source_uri.strip() if source_uri else None
    if import_method in {"url", "sitemap"}:
        if not normalized or not _is_http_url(normalized):
            raise ValueError("网页类资产需要提供合法的 http(s) URL。")
        return normalized
    if import_method == "url_list":
        urls = _split_url_list(normalized or "")
        if not urls:
            raise ValueError("批量网页资产需要提供至少一个 URL。")
        invalid_urls = [item for item in urls if not _is_http_url(item)]
        if invalid_urls:
            raise ValueError(f"URL 列表中存在非法地址：{invalid_urls[0]}")
        return "\n".join(urls)
    if import_method == "object_key":
        if not normalized or _parse_object_storage_uri(normalized) is None:
            raise ValueError(f"{asset_type} 资产需要提供 s3:// 或 cos:// 对象 URI。")
        return normalized
    if import_method == "object_prefix":
        if not normalized or _parse_object_storage_uri(normalized) is None:
            raise ValueError(f"{asset_type} 资产需要提供 s3:// 或 cos:// 对象目录 URI。")
        return _normalize_object_prefix(normalized)
    if import_method in {"upload", "uploaded_package"}:
        return normalized
    return normalized


def _artifact_from_object_uri(
    source_uri: str,
    artifact_type: str,
    fallback_mime_type: str | None = None,
    name: str | None = None,
) -> dict[str, object] | None:
    parsed = _parse_object_storage_uri(source_uri)
    if parsed is None:
        return None
    _, bucket, object_key = parsed
    return {
        "name": name or PurePosixPath(object_key).name or artifact_type,
        "artifact_type": artifact_type,
        "object_bucket": bucket,
        "object_key": object_key,
        "source_uri": source_uri,
        "mime_type": _infer_mime_from_key(object_key, fallback_mime_type),
    }


def _build_initial_extra_artifacts(
    payload: BronzeImportCreate,
    source_uri: str | None,
) -> list[dict[str, object]]:
    artifacts: list[dict[str, object]] = []
    entrypoint = payload.entrypoint.strip().lstrip("/") if payload.entrypoint else None
    manifest_uri = payload.manifest_uri.strip() if payload.manifest_uri else None

    if source_uri and entrypoint and payload.asset_type in {"markdown_package", "object_prefix"}:
        entrypoint_uri = _append_object_path(source_uri, entrypoint)
        if entrypoint_uri:
            entrypoint_artifact = _artifact_from_object_uri(
                entrypoint_uri,
                "primary_document",
                "text/markdown" if payload.asset_type == "markdown_package" else None,
                entrypoint,
            )
            if entrypoint_artifact:
                artifacts.append(entrypoint_artifact)

    if manifest_uri:
        manifest_artifact = _artifact_from_object_uri(
            manifest_uri,
            "manifest",
            "application/json",
            "manifest.json",
        )
        if manifest_artifact:
            artifacts.append(manifest_artifact)

    configured_artifacts = payload.metadata.get("artifacts")
    if isinstance(configured_artifacts, list):
        artifacts.extend(item for item in configured_artifacts if isinstance(item, dict))

    return artifacts


def _display_name_for_source(source_uri: str | None, fallback: str) -> str:
    if not source_uri:
        return fallback
    if "\n" in source_uri:
        return fallback
    parsed = urlparse(source_uri)
    if parsed.scheme in {"http", "https"}:
        leaf = PurePosixPath(parsed.path).name
        return leaf or parsed.netloc
    if parsed.scheme in {"s3", "cos"}:
        return PurePosixPath(parsed.path).name or parsed.netloc
    return PurePosixPath(source_uri).name or source_uri[:80]


def _infer_source_type(asset: LakeAsset, batch: LakeBatch) -> str:
    bronze = _bronze_metadata(asset)
    asset_type = bronze.get("asset_type")
    if isinstance(asset_type, str) and asset_type:
        return asset_type
    explicit = bronze.get("source_type")
    if isinstance(explicit, str) and explicit:
        return explicit
    if asset.source_type == "url":
        return "web_page"
    if asset.resource_type == "folder" or asset.format == "folder":
        return "directory"
    if asset.resource_type == "image":
        return "image"
    if asset.format == "pdf":
        return "pdf"
    if asset.format in {"md", "markdown"}:
        return "markdown"
    if asset.source_type == "object_storage":
        return asset.resource_type or "object_storage"
    if batch.source_type == "sitemap":
        return "web_page"
    return asset.resource_type or "document"


def _normalize_asset_status(asset: LakeAsset) -> str:
    status = asset.status
    if status == "ready":
        return "captured"
    if status == "uploading":
        return "capturing"
    if status == "partial":
        return "changed"
    return status


def _normalize_job_status(batch: LakeBatch) -> str:
    if batch.status == "ready":
        return "captured"
    if batch.status == "uploading":
        return "capturing"
    if batch.status == "partial":
        return "changed"
    return batch.status


def _snapshot_id(asset: LakeAsset) -> str:
    return f"{SNAPSHOT_PREFIX}-{_lake_asset_code(asset)}"


def _artifact_id(asset: LakeAsset, artifact_key: str) -> str:
    normalized = "".join(ch if ch.isalnum() else "-" for ch in artifact_key.lower()).strip("-")
    return f"{ARTIFACT_PREFIX}-{_lake_asset_code(asset)}-{normalized or 'artifact'}"


def _artifact_preview_kind(object_key: str | None, mime_type: str | None) -> str:
    normalized_mime = (mime_type or "").lower()
    suffix = PurePosixPath(object_key or "").suffix.lower().lstrip(".")
    image_suffixes = {"png", "jpg", "jpeg", "gif", "webp", "svg"}
    if normalized_mime.startswith("image/") or suffix in image_suffixes:
        return "image"
    if normalized_mime == "application/pdf" or suffix == "pdf":
        return "pdf"
    if normalized_mime.startswith("text/") or suffix in {
        "css",
        "csv",
        "html",
        "htm",
        "json",
        "jsonl",
        "log",
        "md",
        "txt",
        "xml",
        "yaml",
        "yml",
    }:
        return "text"
    return "unsupported"


def _build_artifacts(asset: LakeAsset) -> list[BronzeArtifactSummary]:
    artifacts: list[BronzeArtifactSummary] = []
    snapshot_id = _snapshot_id(asset)
    bronze = _bronze_metadata(asset)
    object_bucket = bronze.get("object_bucket")

    if asset.object_key:
        artifacts.append(
            BronzeArtifactSummary(
                id=_artifact_id(asset, "original"),
                snapshot_id=snapshot_id,
                name=PurePosixPath(asset.object_key).name or asset.name,
                artifact_type=str(bronze.get("primary_artifact_type") or "original"),
                object_bucket=str(object_bucket) if object_bucket else _object_bucket(),
                object_key=asset.object_key,
                source_uri=asset.source_uri,
                mime_type=asset.mime_type,
                size_bytes=asset.size_bytes,
                preview_kind=_artifact_preview_kind(asset.object_key, asset.mime_type),
                created_at=asset.created_at,
            )
        )

    extra_artifacts = bronze.get("artifacts")
    if isinstance(extra_artifacts, list):
        for index, raw_artifact in enumerate(extra_artifacts):
            if not isinstance(raw_artifact, dict):
                continue
            object_key = raw_artifact.get("object_key")
            mime_type = raw_artifact.get("mime_type")
            name = raw_artifact.get("name") or (
                PurePosixPath(str(object_key)).name if object_key else f"artifact-{index + 1}"
            )
            artifact_type = (
                raw_artifact.get("artifact_type") or raw_artifact.get("type") or "artifact"
            )
            artifact_source_uri = raw_artifact.get("source_uri")
            artifacts.append(
                BronzeArtifactSummary(
                    id=_artifact_id(asset, f"{artifact_type}-{index}"),
                    snapshot_id=snapshot_id,
                    name=str(name),
                    artifact_type=str(artifact_type),
                    object_bucket=str(raw_artifact.get("object_bucket") or _object_bucket())
                    if object_key
                    else None,
                    object_key=str(object_key) if object_key else None,
                    source_uri=str(artifact_source_uri) if artifact_source_uri else None,
                    mime_type=str(mime_type) if mime_type else None,
                    size_bytes=int(raw_artifact["size_bytes"])
                    if isinstance(raw_artifact.get("size_bytes"), int)
                    else None,
                    preview_kind=_artifact_preview_kind(
                        str(object_key) if object_key else None,
                        str(mime_type) if mime_type else None,
                    ),
                    created_at=asset.updated_at,
                )
            )

    return artifacts


def _build_snapshots(asset: LakeAsset) -> list[BronzeSnapshotSummary]:
    normalized_status = _normalize_asset_status(asset)
    if normalized_status == "registered":
        return []

    artifacts = _build_artifacts(asset)
    if not artifacts and normalized_status not in CAPTURED_STATUSES:
        return []

    bronze = _bronze_metadata(asset)
    hash_status = str(bronze.get("hash_status") or "new")
    content_hash = str(bronze.get("content_hash") or asset.checksum or asset.etag or "") or None

    return [
        BronzeSnapshotSummary(
            id=_snapshot_id(asset),
            asset_id=_lake_asset_code(asset),
            status=normalized_status,
            snapshot_time=asset.updated_at,
            raw_hash=str(bronze.get("raw_hash") or asset.etag or "") or None,
            rendered_hash=str(bronze.get("rendered_hash") or "") or None,
            text_hash=str(bronze.get("text_hash") or asset.checksum or "") or None,
            content_hash=content_hash,
            artifact_count=len(artifacts),
            diff_status=hash_status,
            metadata=dict(bronze),
        )
    ]


def _build_lineage(asset: LakeAsset) -> BronzeLineageSummary:
    bronze = _bronze_metadata(asset)
    gold_outputs = bronze.get("gold_outputs")
    downstream_jobs = bronze.get("downstream_jobs")
    return BronzeLineageSummary(
        silver_ready=bool(bronze.get("silver_ready", False)),
        gold_outputs=[str(item) for item in gold_outputs] if isinstance(gold_outputs, list) else [],
        downstream_jobs=(
            [str(item) for item in downstream_jobs]
            if isinstance(downstream_jobs, list)
            else []
        ),
    )


def _to_job_summary(batch: LakeBatch) -> BronzeJobSummary:
    return BronzeJobSummary(
        id=_lake_batch_code(batch),
        name=batch.name,
        source_type=batch.source_type,
        resource_type=batch.resource_type,
        status=_normalize_job_status(batch),
        planned_asset_count=batch.planned_file_count,
        completed_asset_count=batch.completed_file_count,
        failed_asset_count=batch.failed_file_count,
        tags=list(batch.tags or []),
        metadata=dict(batch.extra_metadata or {}),
        created_at=batch.created_at,
        updated_at=batch.updated_at,
    )


def _to_asset_summary(asset: LakeAsset, batch: LakeBatch) -> BronzeAssetSummary:
    bronze = _bronze_metadata(asset)
    artifacts = _build_artifacts(asset)
    snapshots = _build_snapshots(asset)
    source_uri = (
        bronze.get("canonical_url")
        or bronze.get("source_uri")
        or asset.source_uri
        or asset.relative_path
    )
    image_count = sum(1 for artifact in artifacts if artifact.preview_kind == "image")
    configured_image_count = bronze.get("image_count")
    if isinstance(configured_image_count, int):
        image_count = configured_image_count

    return BronzeAssetSummary(
        id=_lake_asset_code(asset),
        name=asset.name,
        description=asset.description,
        source_type=_infer_source_type(asset, batch),
        source_uri=str(source_uri) if source_uri else None,
        provider=str(bronze.get("provider")) if bronze.get("provider") else None,
        product=str(bronze.get("product")) if bronze.get("product") else None,
        tags=list(asset.tags or []),
        latest_snapshot_id=snapshots[0].id if snapshots else None,
        latest_snapshot_at=snapshots[0].snapshot_time if snapshots else None,
        artifact_count=len(artifacts),
        image_count=image_count,
        hash_status=str(bronze.get("hash_status") or ("new" if snapshots else "none")),
        status=_normalize_asset_status(asset),
        ingestion_job_id=_lake_batch_code(batch),
        ingestion_job_name=batch.name,
        object_bucket=str(bronze.get("object_bucket") or _object_bucket())
        if asset.object_key
        else None,
        object_key=asset.object_key,
        size_bytes=asset.size_bytes,
        metadata=dict(asset.extra_metadata or {}),
        error_message=asset.error_message,
        created_at=asset.created_at,
        updated_at=asset.updated_at,
    )


def _to_asset_detail(asset: LakeAsset, batch: LakeBatch) -> BronzeAssetDetail:
    summary = _to_asset_summary(asset, batch)
    bronze = _bronze_metadata(asset)
    logs = bronze.get("logs")
    normalized_logs = [str(item) for item in logs] if isinstance(logs, list) else []
    if asset.error_message:
        normalized_logs.append(asset.error_message)

    return BronzeAssetDetail(
        **summary.model_dump(),
        snapshots=_build_snapshots(asset),
        artifacts=_build_artifacts(asset),
        logs=normalized_logs,
        lineage=_build_lineage(asset),
    )


async def _load_asset_with_batch(
    session,
    project_id: UUID,
    asset_id: str,
) -> tuple[LakeAsset, LakeBatch]:
    asset = await _load_asset_or_raise(session, project_id, asset_id)
    batch = await session.get(LakeBatch, asset.batch_id)
    if batch is None or batch.project_id != project_id or batch.status == "deleted":
        raise KeyError(asset_id)
    return asset, batch


class BronzeService:
    async def list_assets(self) -> list[BronzeAssetSummary]:
        async with SessionLocal() as session:
            project_id = await resolve_active_project_id(session)
            rows = await session.execute(
                select(LakeAsset, LakeBatch)
                .join(LakeBatch, LakeBatch.id == LakeAsset.batch_id)
                .where(
                    LakeAsset.project_id == project_id,
                    LakeAsset.stage == "raw",
                    LakeAsset.status != "deleted",
                    LakeBatch.status != "deleted",
                )
                .order_by(
                    LakeAsset.updated_at.desc(),
                    LakeAsset.created_at.desc(),
                    LakeAsset.id.desc(),
                )
            )
            return [_to_asset_summary(asset, batch) for asset, batch in rows.all()]

    async def get_asset(self, asset_id: str) -> BronzeAssetDetail:
        async with SessionLocal() as session:
            project_id = await resolve_active_project_id(session)
            asset, batch = await _load_asset_with_batch(session, project_id, asset_id)
            return _to_asset_detail(asset, batch)

    async def list_jobs(self) -> list[BronzeJobSummary]:
        async with SessionLocal() as session:
            project_id = await resolve_active_project_id(session)
            rows = await session.execute(
                select(LakeBatch)
                .where(
                    LakeBatch.project_id == project_id,
                    LakeBatch.status != "deleted",
                )
                .order_by(
                    LakeBatch.updated_at.desc(),
                    LakeBatch.created_at.desc(),
                    LakeBatch.id.desc(),
                )
            )
            return [_to_job_summary(batch) for batch in rows.scalars().all()]

    async def get_job(self, job_id: str) -> BronzeJobSummary:
        async with SessionLocal() as session:
            project_id = await resolve_active_project_id(session)
            batch = await _load_batch_or_raise(session, project_id, job_id)
            return _to_job_summary(batch)

    async def create_import(self, payload: BronzeImportCreate) -> BronzeImportCreateResponse:
        import_method = _resolve_import_method(payload)
        source_uri = _normalize_source_locator(
            payload.asset_type,
            import_method,
            payload.source_uri,
        )
        object_storage_location = (
            _parse_object_storage_uri(source_uri) if source_uri else None
        )
        object_bucket = object_storage_location[1] if object_storage_location else None
        object_key = (
            object_storage_location[2]
            if object_storage_location and import_method == "object_key"
            else None
        )
        primary_artifact_type = PRIMARY_ARTIFACT_TYPE_BY_ASSET_TYPE.get(
            payload.asset_type,
            "original",
        )

        async with SessionLocal() as session:
            project_id = await resolve_active_project_id(session)
            created_at = _now()
            is_registered_only = (
                import_method in REGISTERED_ONLY_METHODS
                or payload.asset_type in REGISTERED_ONLY_ASSET_TYPES
            )
            asset_status = "registered" if is_registered_only else "captured"
            batch_status = asset_status
            completed_count = 0 if is_registered_only else 1
            resource_type = payload.asset_type
            source_type = import_method
            fallback_name = payload.asset_type.replace("_", " ")
            name = (payload.name or _display_name_for_source(source_uri, fallback_name)).strip()
            if not name:
                raise ValueError("资产名称不能为空。")

            initial_artifacts = _build_initial_extra_artifacts(payload, source_uri)
            metadata_updates = dict(payload.metadata)
            metadata_updates.pop("artifacts", None)

            bronze_meta = {
                "asset_type": payload.asset_type,
                "source_type": payload.asset_type,
                "import_method": import_method,
                "source_uri": source_uri,
                "source_locator": source_uri,
                "provider": payload.provider.strip() if payload.provider else None,
                "product": payload.product.strip() if payload.product else None,
                "capture_mode": payload.capture_mode,
                "extract_images": payload.extract_images,
                "trigger_silver": payload.trigger_silver,
                "entrypoint": payload.entrypoint.strip() if payload.entrypoint else None,
                "manifest_uri": payload.manifest_uri.strip() if payload.manifest_uri else None,
                "object_bucket": object_bucket,
                "primary_artifact_type": primary_artifact_type,
                "artifacts": initial_artifacts,
                "hash_status": "new" if not is_registered_only else "none",
                "registered_at": created_at.isoformat(),
                "silver_ready": False,
                "logs": [
                    f"已登记 {payload.asset_type} 资产，等待 worker 冻结证据包。"
                    if is_registered_only
                    else f"已通过 {import_method} 登记为 Bronze 快照。"
                ],
                **metadata_updates,
            }
            if payload.asset_type == "web_page":
                bronze_meta["canonical_url"] = source_uri

            batch = LakeBatch(
                id=uuid4(),
                project_id=project_id,
                name=f"Bronze 导入 · {name}",
                description=f"{resource_type} · {source_uri or import_method}",
                source_type=source_type,
                resource_type=resource_type,
                stage="raw",
                planned_file_count=1,
                completed_file_count=completed_count,
                failed_file_count=0,
                total_size_bytes=0,
                tags=list(payload.tags),
                extra_metadata={
                    BRONZE_METADATA_KEY: {
                        "asset_type": payload.asset_type,
                        "import_method": import_method,
                    }
                },
                status=batch_status,
                created_at=created_at,
                updated_at=created_at,
            )
            asset = LakeAsset(
                id=uuid4(),
                project_id=project_id,
                batch_id=batch.id,
                parent_asset_id=None,
                name=name,
                description=None,
                stage="raw",
                source_type=source_type,
                resource_type=resource_type,
                format=FORMAT_BY_ASSET_TYPE.get(payload.asset_type),
                mime_type=_infer_mime_from_key(
                    object_key,
                    MIME_BY_ASSET_TYPE.get(payload.asset_type),
                )
                if object_key
                else MIME_BY_ASSET_TYPE.get(payload.asset_type),
                relative_path=None,
                object_key=object_key,
                source_uri=source_uri,
                size_bytes=None,
                tags=list(payload.tags),
                extra_metadata={BRONZE_METADATA_KEY: bronze_meta},
                status=asset_status,
                created_at=created_at,
                updated_at=created_at,
            )

            session.add(batch)
            session.add(asset)
            await session.commit()
            return BronzeImportCreateResponse(
                asset=_to_asset_detail(asset, batch),
                job=_to_job_summary(batch),
            )

    async def update_asset(self, asset_id: str, payload: BronzeAssetPatch) -> BronzeAssetDetail:
        async with SessionLocal() as session:
            project_id = await resolve_active_project_id(session)
            asset, batch = await _load_asset_with_batch(session, project_id, asset_id)
            updated_at = _now()

            if payload.name is not None:
                name = payload.name.strip()
                if not name:
                    raise ValueError("资产名称不能为空。")
                asset.name = name
            if payload.tags is not None:
                asset.tags = list(payload.tags)

            bronze_updates: dict[str, object] = {}
            if payload.provider is not None:
                bronze_updates["provider"] = payload.provider.strip() or None
            if payload.product is not None:
                bronze_updates["product"] = payload.product.strip() or None
            if payload.metadata:
                bronze_updates.update(payload.metadata)
            if bronze_updates:
                _replace_bronze_metadata(asset, bronze_updates)

            asset.updated_at = updated_at
            batch.updated_at = updated_at
            await session.commit()
            return _to_asset_detail(asset, batch)

    async def refresh_asset(self, asset_id: str) -> BronzeJobSummary:
        async with SessionLocal() as session:
            project_id = await resolve_active_project_id(session)
            asset, batch = await _load_asset_with_batch(session, project_id, asset_id)
            updated_at = _now()
            asset.status = "capturing"
            batch.status = "capturing"
            asset.updated_at = updated_at
            batch.updated_at = updated_at
            existing_logs = _bronze_metadata(asset).get("logs")
            normalized_logs = (
                [str(item) for item in existing_logs] if isinstance(existing_logs, list) else []
            )
            _replace_bronze_metadata(
                asset,
                {
                    "hash_status": "pending",
                    "refresh_requested_at": updated_at.isoformat(),
                    "logs": [*normalized_logs, "已提交刷新抓取请求，等待 worker 生成新 snapshot。"],
                },
            )
            await session.commit()
            return _to_job_summary(batch)

    async def archive_asset(self, asset_id: str) -> BronzeAssetDetail:
        async with SessionLocal() as session:
            project_id = await resolve_active_project_id(session)
            asset, batch = await _load_asset_with_batch(session, project_id, asset_id)
            updated_at = _now()
            asset.status = "archived"
            asset.updated_at = updated_at
            batch.updated_at = updated_at
            _replace_bronze_metadata(asset, {"archived_at": updated_at.isoformat()})
            await session.commit()
            return _to_asset_detail(asset, batch)

    async def soft_delete_asset(self, asset_id: str) -> None:
        async with SessionLocal() as session:
            project_id = await resolve_active_project_id(session)
            asset, batch = await _load_asset_with_batch(session, project_id, asset_id)
            updated_at = _now()
            asset.status = "deleted"
            asset.updated_at = updated_at
            batch.updated_at = updated_at
            _replace_bronze_metadata(asset, {"deleted_at": updated_at.isoformat()})
            await session.commit()

    async def list_snapshots(self, asset_id: str) -> list[BronzeSnapshotSummary]:
        detail = await self.get_asset(asset_id)
        return detail.snapshots

    async def get_snapshot(self, snapshot_id: str) -> BronzeSnapshotSummary:
        asset_id = self._asset_id_from_snapshot_id(snapshot_id)
        snapshots = await self.list_snapshots(asset_id)
        for snapshot in snapshots:
            if snapshot.id == snapshot_id:
                return snapshot
        raise KeyError(snapshot_id)

    async def list_snapshot_artifacts(self, snapshot_id: str) -> list[BronzeArtifactSummary]:
        asset_id = self._asset_id_from_snapshot_id(snapshot_id)
        detail = await self.get_asset(asset_id)
        return [artifact for artifact in detail.artifacts if artifact.snapshot_id == snapshot_id]

    async def get_artifact(self, artifact_id: str) -> BronzeArtifactSummary:
        asset_id = self._asset_id_from_artifact_id(artifact_id)
        detail = await self.get_asset(asset_id)
        for artifact in detail.artifacts:
            if artifact.id == artifact_id:
                return artifact
        raise KeyError(artifact_id)

    async def cancel_job(self, job_id: str) -> BronzeJobSummary:
        async with SessionLocal() as session:
            project_id = await resolve_active_project_id(session)
            batch = await _load_batch_or_raise(session, project_id, job_id)
            cancelled_at = _now()
            batch.status = "failed"
            batch.failed_file_count = max(batch.failed_file_count, batch.planned_file_count)
            batch.updated_at = cancelled_at
            rows = await session.execute(
                select(LakeAsset).where(
                    LakeAsset.batch_id == batch.id,
                    LakeAsset.status.in_(["registered", "capturing", "uploading"]),
                )
            )
            for asset in rows.scalars().all():
                asset.status = "failed"
                asset.error_message = "导入任务已取消"
                asset.updated_at = cancelled_at
            await session.commit()
            return _to_job_summary(batch)

    @staticmethod
    def _asset_id_from_snapshot_id(snapshot_id: str) -> str:
        prefix = f"{SNAPSHOT_PREFIX}-"
        if not snapshot_id.startswith(prefix):
            raise KeyError(snapshot_id)
        asset_id = snapshot_id[len(prefix) :]
        if not LAKE_ASSET_CODE_PATTERN.match(asset_id):
            raise KeyError(snapshot_id)
        return asset_id

    @staticmethod
    def _asset_id_from_artifact_id(artifact_id: str) -> str:
        prefix = f"{ARTIFACT_PREFIX}-"
        if not artifact_id.startswith(prefix):
            raise KeyError(artifact_id)
        parts = artifact_id[len(prefix) :].split("-")
        if len(parts) < 4:
            raise KeyError(artifact_id)
        asset_id = "-".join(parts[:3])
        if not LAKE_ASSET_CODE_PATTERN.match(asset_id):
            raise KeyError(artifact_id)
        return asset_id


def build_artifact_download_url(api_base_path: str, artifact: BronzeArtifactSummary) -> str:
    if not artifact.object_bucket or not artifact.object_key:
        raise ValueError("当前 artifact 还没有可下载对象。")
    base = api_base_path.rstrip("/")
    bucket = quote(artifact.object_bucket, safe="")
    key = quote(artifact.object_key, safe="")
    return f"{base}/uploads/object/download?bucket={bucket}&key={key}&disposition=inline"
