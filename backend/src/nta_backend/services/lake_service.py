from __future__ import annotations

import re
from datetime import datetime
from pathlib import PurePosixPath
from uuid import UUID, uuid4
from zoneinfo import ZoneInfo

from sqlalchemy import case, func, select

from nta_backend.core.config import get_settings
from nta_backend.core.db import SessionLocal
from nta_backend.core.object_store import delete_object, delete_object_prefix
from nta_backend.core.project_context import resolve_active_project_id
from nta_backend.core.s3 import build_presigned_upload
from nta_backend.core.storage_layout import (
    build_lake_asset_code,
    build_lake_batch_code,
    build_lake_prefix,
    build_lake_raw_key,
    normalize_relative_object_path,
)
from nta_backend.models.lake import LakeAsset, LakeBatch
from nta_backend.schemas.lake import (
    LakeAssetDirectUploadCompleteRequest,
    LakeAssetDirectUploadFailedRequest,
    LakeAssetDirectUploadInitRequest,
    LakeAssetDirectUploadInitResponse,
    LakeAssetSummary,
    LakeBatchCreate,
    LakeBatchSummary,
    LakeUploadAbortRequest,
)
from nta_backend.schemas.object_store import ObjectStoreDirectUploadInitResponse

ASIA_SHANGHAI = ZoneInfo("Asia/Shanghai")
DIRECT_UPLOAD_EXPIRES_IN_SECONDS = 900
LAKE_RAW_BUCKET = get_settings().s3_bucket_dataset_raw
LAKE_BATCH_CODE_PATTERN = re.compile(r"^lb-\d{14}-[0-9a-z]{5}$")
LAKE_ASSET_CODE_PATTERN = re.compile(r"^la-\d{14}-[0-9a-z]{5}$")


def _now() -> datetime:
    return datetime.now(ASIA_SHANGHAI)


def _lake_batch_code(batch: LakeBatch) -> str:
    return build_lake_batch_code(batch.created_at.astimezone(ASIA_SHANGHAI), batch.id)


def _lake_asset_code(asset: LakeAsset) -> str:
    return build_lake_asset_code(asset.created_at.astimezone(ASIA_SHANGHAI), asset.id)


def _build_source_uri(bucket: str, object_key: str) -> str:
    return f"s3://{bucket}/{object_key}"


def _infer_asset_format(file_name: str) -> str:
    suffix = PurePosixPath(file_name).suffix.lower().lstrip(".")
    return suffix or "bin"


def _infer_resource_type(file_name: str, content_type: str | None = None) -> str:
    normalized_content_type = (content_type or "").lower()
    suffix = PurePosixPath(file_name).suffix.lower()

    if normalized_content_type.startswith("image/") or suffix in {
        ".png",
        ".jpg",
        ".jpeg",
        ".gif",
        ".webp",
        ".svg",
    }:
        return "image"
    if suffix in {".csv", ".tsv", ".xls", ".xlsx", ".parquet"}:
        return "tabular"
    if suffix in {".zip", ".tar", ".gz", ".bz2", ".7z", ".rar"}:
        return "archive"
    if suffix in {".pdf", ".doc", ".docx", ".md", ".txt", ".html", ".htm", ".json", ".jsonl"}:
        return "document"
    return "binary"


def _build_direct_upload_response(
    *,
    bucket: str,
    object_key: str,
    file_name: str,
    file_size: int,
    content_type: str | None,
    browser_endpoint_url: str | None = None,
) -> ObjectStoreDirectUploadInitResponse:
    presigned = build_presigned_upload(
        bucket=bucket,
        object_key=object_key,
        expires_in=DIRECT_UPLOAD_EXPIRES_IN_SECONDS,
        content_type=content_type,
        browser_endpoint_url=browser_endpoint_url,
    )
    return ObjectStoreDirectUploadInitResponse(
        bucket=bucket,
        object_key=object_key,
        uri=_build_source_uri(bucket, object_key),
        file_name=file_name,
        size_bytes=file_size,
        content_type=content_type,
        expires_in=DIRECT_UPLOAD_EXPIRES_IN_SECONDS,
        method=str(presigned["method"]),
        headers=dict(presigned["headers"]),
        url=str(presigned["url"]),
    )


async def _load_batch_or_raise(session, project_id: UUID, batch_identifier: str) -> LakeBatch:
    if not LAKE_BATCH_CODE_PATTERN.match(batch_identifier):
        raise KeyError(batch_identifier)

    rows = await session.execute(
        select(LakeBatch)
        .where(
            LakeBatch.project_id == project_id,
            LakeBatch.status != "deleted",
        )
        .order_by(LakeBatch.created_at.desc(), LakeBatch.id.desc())
    )
    for batch in rows.scalars().all():
        if _lake_batch_code(batch) == batch_identifier:
            return batch
    raise KeyError(batch_identifier)


async def _load_asset_or_raise(session, project_id: UUID, asset_identifier: str) -> LakeAsset:
    if not LAKE_ASSET_CODE_PATTERN.match(asset_identifier):
        raise KeyError(asset_identifier)

    rows = await session.execute(
        select(LakeAsset)
        .where(
            LakeAsset.project_id == project_id,
            LakeAsset.status != "deleted",
        )
        .order_by(LakeAsset.created_at.desc(), LakeAsset.id.desc())
    )
    for asset in rows.scalars().all():
        if _lake_asset_code(asset) == asset_identifier:
            return asset
    raise KeyError(asset_identifier)


async def _refresh_batch_aggregates(session, batch: LakeBatch) -> None:
    counts_row = await session.execute(
        select(
            func.count(LakeAsset.id),
            func.sum(
                case((LakeAsset.status == "ready", 1), else_=0)
            ),
            func.sum(
                case((LakeAsset.status == "failed", 1), else_=0)
            ),
            func.sum(
                case((LakeAsset.status == "uploading", 1), else_=0)
            ),
            func.coalesce(func.sum(LakeAsset.size_bytes), 0),
        ).where(
            LakeAsset.batch_id == batch.id,
            LakeAsset.status != "deleted",
            LakeAsset.object_key.is_not(None),
        )
    )
    total_assets, ready_assets, failed_assets, uploading_assets, total_size = counts_row.one()
    ready_count = int(ready_assets or 0)
    failed_count = int(failed_assets or 0)
    uploading_count = int(uploading_assets or 0)
    total_count = int(total_assets or 0)

    batch.completed_file_count = ready_count
    batch.failed_file_count = failed_count
    batch.total_size_bytes = int(total_size or 0)

    planned_count = max(batch.planned_file_count, total_count)
    if uploading_count > 0 or ready_count + failed_count < planned_count:
        batch.status = "uploading"
    elif ready_count > 0 and failed_count > 0:
        batch.status = "partial"
    elif ready_count > 0:
        batch.status = "ready"
    elif failed_count > 0:
        batch.status = "failed"
    else:
        batch.status = "uploading"


async def _count_batch_assets(session, batch_id: UUID) -> tuple[int, int, int, int]:
    counts_row = await session.execute(
        select(
            func.count(LakeAsset.id),
            func.sum(case((LakeAsset.status == "ready", 1), else_=0)),
            func.sum(case((LakeAsset.status == "failed", 1), else_=0)),
            func.coalesce(func.sum(LakeAsset.size_bytes), 0),
        ).where(
            LakeAsset.batch_id == batch_id,
            LakeAsset.status != "deleted",
            LakeAsset.object_key.is_not(None),
        )
    )
    total_assets, ready_assets, failed_assets, total_size = counts_row.one()
    return (
        int(total_assets or 0),
        int(ready_assets or 0),
        int(failed_assets or 0),
        int(total_size or 0),
    )


async def _mark_batch_aborted(session, batch: LakeBatch) -> None:
    total_assets, ready_count, failed_count, total_size = await _count_batch_assets(
        session,
        batch.id,
    )
    batch.completed_file_count = ready_count
    batch.total_size_bytes = total_size
    interrupted_count = max(batch.planned_file_count - ready_count, 0)
    batch.failed_file_count = max(failed_count, interrupted_count)

    if ready_count > 0 and ready_count < batch.planned_file_count:
        batch.status = "partial"
        return
    if ready_count >= batch.planned_file_count and batch.planned_file_count > 0:
        batch.status = "ready"
        return
    if total_assets == 0:
        batch.failed_file_count = max(batch.failed_file_count, batch.planned_file_count)
    batch.status = "failed"


def _to_batch_summary(batch: LakeBatch) -> LakeBatchSummary:
    return LakeBatchSummary(
        id=_lake_batch_code(batch),
        name=batch.name,
        description=batch.description,
        stage=batch.stage,
        source_type=batch.source_type,
        resource_type=batch.resource_type,
        status=batch.status,
        planned_file_count=batch.planned_file_count,
        completed_file_count=batch.completed_file_count,
        failed_file_count=batch.failed_file_count,
        total_size_bytes=batch.total_size_bytes,
        tags=list(batch.tags or []),
        metadata=dict(batch.extra_metadata or {}),
        created_at=batch.created_at,
        updated_at=batch.updated_at,
    )


def _to_asset_summary(asset: LakeAsset, batch: LakeBatch) -> LakeAssetSummary:
    return LakeAssetSummary(
        id=_lake_asset_code(asset),
        batch_id=_lake_batch_code(batch),
        batch_name=batch.name,
        parent_asset_id=str(asset.parent_asset_id) if asset.parent_asset_id else None,
        name=asset.name,
        description=asset.description,
        stage=asset.stage,
        source_type=asset.source_type,
        resource_type=asset.resource_type,
        format=asset.format,
        mime_type=asset.mime_type,
        relative_path=asset.relative_path,
        object_key=asset.object_key,
        source_uri=asset.source_uri,
        size_bytes=asset.size_bytes,
        record_count=asset.record_count,
        status=asset.status,
        tags=list(asset.tags or []),
        metadata=dict(asset.extra_metadata or {}),
        error_message=asset.error_message,
        created_at=asset.created_at,
        updated_at=asset.updated_at,
    )


async def _load_batch_assets(session, batch_id: UUID) -> list[LakeAsset]:
    rows = await session.execute(
        select(LakeAsset)
        .where(
            LakeAsset.batch_id == batch_id,
            LakeAsset.status != "deleted",
        )
        .order_by(LakeAsset.created_at.asc(), LakeAsset.id.asc())
    )
    return rows.scalars().all()


def _collect_descendant_assets(assets: list[LakeAsset], root_asset_id: UUID) -> list[LakeAsset]:
    assets_by_id = {asset.id: asset for asset in assets}
    children_by_parent: dict[UUID, list[LakeAsset]] = {}
    for asset in assets:
        if asset.parent_asset_id is not None:
            children_by_parent.setdefault(asset.parent_asset_id, []).append(asset)

    collected: list[LakeAsset] = []
    pending_ids = [root_asset_id]
    seen_ids: set[UUID] = set()
    while pending_ids:
        current_id = pending_ids.pop()
        if current_id in seen_ids:
            continue
        seen_ids.add(current_id)
        asset = assets_by_id.get(current_id)
        if asset is not None:
            collected.append(asset)
        for child in children_by_parent.get(current_id, []):
            pending_ids.append(child.id)
    return collected


class LakeService:
    async def list_batches(self) -> list[LakeBatchSummary]:
        async with SessionLocal() as session:
            project_id = await resolve_active_project_id(session)
            rows = await session.execute(
                select(LakeBatch)
                .where(
                    LakeBatch.project_id == project_id,
                    LakeBatch.status != "deleted",
                )
                .order_by(LakeBatch.created_at.desc(), LakeBatch.id.desc())
            )
            return [_to_batch_summary(batch) for batch in rows.scalars().all()]

    async def list_assets(self, *, stage: str | None = None) -> list[LakeAssetSummary]:
        async with SessionLocal() as session:
            project_id = await resolve_active_project_id(session)
            stmt = (
                select(LakeAsset, LakeBatch)
                .join(LakeBatch, LakeBatch.id == LakeAsset.batch_id)
                .where(
                    LakeAsset.project_id == project_id,
                    LakeAsset.status != "deleted",
                    LakeBatch.status != "deleted",
                )
                .order_by(
                    LakeBatch.created_at.desc(),
                    case((LakeAsset.object_key.is_(None), 0), else_=1),
                    LakeAsset.created_at.desc(),
                    LakeAsset.id.desc(),
                )
            )
            if stage:
                stmt = stmt.where(LakeAsset.stage == stage)

            rows = await session.execute(stmt)
            return [_to_asset_summary(asset, batch) for asset, batch in rows.all()]

    async def create_batch(self, payload: LakeBatchCreate) -> LakeBatchSummary:
        async with SessionLocal() as session:
            project_id = await resolve_active_project_id(session)
            created_at = _now()
            name = payload.name.strip()
            if not name:
                raise ValueError("批次名称不能为空")
            source_type = payload.source_type.strip()
            if not source_type:
                raise ValueError("来源类型不能为空")
            batch = LakeBatch(
                id=uuid4(),
                project_id=project_id,
                name=name,
                description=payload.description.strip() if payload.description else None,
                source_type=source_type,
                resource_type=payload.resource_type.strip() if payload.resource_type else None,
                stage="raw",
                planned_file_count=payload.planned_file_count,
                completed_file_count=0,
                failed_file_count=0,
                total_size_bytes=0,
                tags=list(payload.tags),
                extra_metadata=dict(payload.metadata),
                status="uploading",
                created_at=created_at,
                updated_at=created_at,
            )
            session.add(batch)
            await session.flush()

            root_paths = []
            seen_root_paths: set[str] = set()
            for root_path in payload.root_paths:
                normalized_root_path = normalize_relative_object_path(
                    root_path,
                    fallback_name="folder",
                ).rstrip("/")
                if not normalized_root_path or normalized_root_path in seen_root_paths:
                    continue
                seen_root_paths.add(normalized_root_path)
                root_paths.append(normalized_root_path)

            for root_path in root_paths:
                root_name = PurePosixPath(root_path).name or root_path
                session.add(
                    LakeAsset(
                        id=uuid4(),
                        project_id=project_id,
                        batch_id=batch.id,
                        name=root_name,
                        description=None,
                        stage="raw",
                        source_type=source_type,
                        resource_type="folder",
                        format="folder",
                        mime_type=None,
                        relative_path=root_path,
                        object_key=None,
                        source_uri=None,
                        size_bytes=None,
                        tags=[],
                        extra_metadata={"kind": "folder", "root_path": root_path},
                        status="ready",
                        created_at=created_at,
                        updated_at=created_at,
                    )
                )
            await session.commit()
            return _to_batch_summary(batch)

    async def prepare_asset_direct_upload(
        self,
        payload: LakeAssetDirectUploadInitRequest,
        browser_endpoint_url: str | None = None,
    ) -> LakeAssetDirectUploadInitResponse:
        async with SessionLocal() as session:
            project_id = await resolve_active_project_id(session)
            batch = await _load_batch_or_raise(session, project_id, payload.batch_id)
            source_type = payload.source_type.strip()
            if not source_type:
                raise ValueError("来源类型不能为空")
            parent_asset_id = None
            if payload.relative_path:
                normalized_relative_path = normalize_relative_object_path(
                    payload.relative_path,
                    fallback_name=payload.file_name,
                )
                top_level_path = PurePosixPath(normalized_relative_path).parts[:1]
                if top_level_path:
                    root_path = top_level_path[0]
                    root_asset_rows = await session.execute(
                        select(LakeAsset)
                        .where(
                            LakeAsset.project_id == project_id,
                            LakeAsset.batch_id == batch.id,
                            LakeAsset.object_key.is_(None),
                            LakeAsset.relative_path == root_path,
                            LakeAsset.status != "deleted",
                        )
                        .order_by(LakeAsset.created_at.asc(), LakeAsset.id.asc())
                    )
                    root_asset = root_asset_rows.scalars().first()
                    if root_asset is not None:
                        parent_asset_id = root_asset.id

            created_at = _now()
            asset = LakeAsset(
                id=uuid4(),
                project_id=project_id,
                batch_id=batch.id,
                parent_asset_id=parent_asset_id,
                name=PurePosixPath(payload.file_name).name,
                description=payload.description.strip() if payload.description else None,
                stage="raw",
                source_type=source_type,
                resource_type=payload.resource_type.strip()
                if payload.resource_type
                else _infer_resource_type(payload.file_name, payload.content_type),
                format=_infer_asset_format(payload.file_name),
                mime_type=payload.content_type,
                relative_path=payload.relative_path,
                tags=list(payload.tags),
                extra_metadata=dict(payload.metadata),
                status="uploading",
                created_at=created_at,
                updated_at=created_at,
            )
            object_key = build_lake_raw_key(
                project_id,
                _lake_batch_code(batch),
                build_lake_asset_code(created_at, asset.id),
                payload.relative_path or payload.file_name,
            )
            source_uri = _build_source_uri(LAKE_RAW_BUCKET, object_key)
            asset.object_key = object_key
            asset.source_uri = source_uri
            asset.size_bytes = payload.file_size

            upload = _build_direct_upload_response(
                bucket=LAKE_RAW_BUCKET,
                object_key=object_key,
                file_name=payload.file_name,
                file_size=payload.file_size,
                content_type=payload.content_type,
                browser_endpoint_url=browser_endpoint_url,
            )

            session.add(asset)
            batch.updated_at = created_at
            await session.commit()

            return LakeAssetDirectUploadInitResponse(
                batch_id=_lake_batch_code(batch),
                asset_id=build_lake_asset_code(created_at, asset.id),
                status="uploading",
                object_key=object_key,
                source_uri=source_uri,
                file_name=payload.file_name,
                upload=upload,
            )

    async def complete_asset_direct_upload(
        self,
        asset_id: str,
        payload: LakeAssetDirectUploadCompleteRequest,
    ) -> LakeAssetSummary:
        async with SessionLocal() as session:
            project_id = await resolve_active_project_id(session)
            asset = await _load_asset_or_raise(session, project_id, asset_id)
            batch = await session.get(LakeBatch, asset.batch_id)
            if batch is None or batch.project_id != project_id or batch.status == "deleted":
                raise KeyError(asset_id)
            if payload.upload.bucket != LAKE_RAW_BUCKET:
                raise ValueError("上传目标桶不正确")
            if asset.object_key != payload.upload.object_key:
                raise ValueError("上传对象路径不匹配")

            completed_at = _now()
            asset.status = "ready"
            asset.size_bytes = payload.upload.size_bytes
            asset.mime_type = payload.upload.content_type or asset.mime_type
            asset.source_uri = payload.upload.uri
            asset.updated_at = completed_at
            await session.flush()
            await _refresh_batch_aggregates(session, batch)
            batch.updated_at = completed_at
            await session.commit()
            return _to_asset_summary(asset, batch)

    async def fail_asset_direct_upload(
        self,
        asset_id: str,
        payload: LakeAssetDirectUploadFailedRequest,
    ) -> None:
        async with SessionLocal() as session:
            project_id = await resolve_active_project_id(session)
            asset = await _load_asset_or_raise(session, project_id, asset_id)
            batch = await session.get(LakeBatch, asset.batch_id)
            if batch is None or batch.project_id != project_id or batch.status == "deleted":
                raise KeyError(asset_id)

            failed_at = _now()
            asset.status = "failed"
            asset.error_message = payload.reason.strip() if payload.reason else None
            asset.updated_at = failed_at
            await session.flush()
            await _refresh_batch_aggregates(session, batch)
            batch.updated_at = failed_at
            await session.commit()

    async def delete_asset(self, asset_id: str) -> None:
        async with SessionLocal() as session:
            project_id = await resolve_active_project_id(session)
            asset = await _load_asset_or_raise(session, project_id, asset_id)
            batch = await session.get(LakeBatch, asset.batch_id)
            if batch is None or batch.project_id != project_id or batch.status == "deleted":
                raise KeyError(asset_id)

            batch_assets = await _load_batch_assets(session, batch.id)
            if asset.object_key is None and asset.resource_type == "folder":
                target_assets = _collect_descendant_assets(batch_assets, asset.id)
                normalized_root_path = normalize_relative_object_path(
                    asset.relative_path,
                    fallback_name=asset.name,
                ).rstrip("/")
                delete_object_prefix(
                    LAKE_RAW_BUCKET,
                    (
                        f"{build_lake_prefix(project_id, 'raw')}"
                        f"{_lake_batch_code(batch)}/original/{normalized_root_path}/"
                    ),
                )
            else:
                target_assets = [item for item in batch_assets if item.id == asset.id]
                if asset.object_key:
                    delete_object(LAKE_RAW_BUCKET, asset.object_key)

            target_asset_ids = {item.id for item in target_assets}
            for target_asset in target_assets:
                await session.delete(target_asset)

            await session.flush()

            remaining_assets = [
                item
                for item in batch_assets
                if item.id not in target_asset_ids
            ]
            remaining_file_assets = [item for item in remaining_assets if item.object_key]

            if not remaining_file_assets:
                for remaining_asset in remaining_assets:
                    await session.delete(remaining_asset)
                await session.flush()
                await session.delete(batch)
                await session.commit()
                return

            await _refresh_batch_aggregates(session, batch)
            batch.updated_at = _now()
            await session.commit()

    async def abort_uploads(self, payload: LakeUploadAbortRequest) -> None:
        async with SessionLocal() as session:
            project_id = await resolve_active_project_id(session)
            aborted_at = _now()
            batch: LakeBatch | None = None
            batch_ids: set[UUID] = set()

            if payload.batch_id:
                batch = await _load_batch_or_raise(session, project_id, payload.batch_id)
                batch_ids.add(batch.id)

            for asset_identifier in payload.asset_ids:
                asset = await _load_asset_or_raise(session, project_id, asset_identifier)
                if asset.status in {"ready", "failed"}:
                    batch_ids.add(asset.batch_id)
                    continue
                asset.status = "failed"
                asset.error_message = payload.reason.strip() if payload.reason else "上传已中断"
                asset.updated_at = aborted_at
                batch_ids.add(asset.batch_id)

            await session.flush()

            for batch_id in batch_ids:
                if batch and batch.id == batch_id:
                    current_batch = batch
                else:
                    current_batch = await session.get(LakeBatch, batch_id)
                if current_batch is None or current_batch.project_id != project_id:
                    continue
                await _mark_batch_aborted(session, current_batch)
                current_batch.updated_at = aborted_at

            await session.commit()
