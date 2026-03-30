from __future__ import annotations

import asyncio
import json
import re
from dataclasses import dataclass
from datetime import datetime
from mimetypes import guess_type
from pathlib import PurePosixPath
from uuid import UUID, uuid4
from zoneinfo import ZoneInfo

from fastapi import UploadFile
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from nta_backend.core.config import get_settings
from nta_backend.core.db import SessionLocal
from nta_backend.core.object_store import (
    ObjectPayload,
    delete_object,
    delete_object_prefix,
    get_object_bytes,
    put_object_bytes,
)
from nta_backend.core.project_context import resolve_active_project_id
from nta_backend.core.s3 import build_presigned_upload
from nta_backend.core.storage_layout import (
    build_dataset_artifact_key,
    build_dataset_code,
    build_dataset_source_key,
    build_dataset_version_prefix,
)
from nta_backend.eval import normalize_eval_dataset_bytes
from nta_backend.models.dataset import Dataset, DatasetFile, DatasetVersion
from nta_backend.models.jobs import EvalJob
from nta_backend.schemas.dataset import (
    DatasetCreate,
    DatasetCreateResponse,
    DatasetDetail,
    DatasetDirectUploadCompleteRequest,
    DatasetDirectUploadFailedRequest,
    DatasetDirectUploadInitRequest,
    DatasetDirectUploadInitResponse,
    DatasetFileSummary,
    DatasetSummary,
    DatasetVersionCreate,
    DatasetVersionDirectUploadInitRequest,
    DatasetVersionPreview,
    DatasetVersionSummary,
    PresignUploadRequest,
    PresignUploadResponse,
)
from nta_backend.schemas.object_store import ObjectStoreDirectUploadInitResponse

ASIA_SHANGHAI = ZoneInfo("Asia/Shanghai")
PREVIEW_LIMIT_LINES = 50
DATASET_RAW_BUCKET = get_settings().s3_bucket_dataset_raw
DIRECT_UPLOAD_EXPIRES_IN_SECONDS = 900
DATASET_CODE_PATTERN = re.compile(r"^ds-\d{14}-[0-9a-z]{5}$")


@dataclass(frozen=True)
class DatasetDownloadPayload:
    file_name: str
    object_payload: ObjectPayload


def _now() -> datetime:
    return datetime.now(ASIA_SHANGHAI)


def _guess_content_type(file_name: str) -> str:
    lower_name = file_name.lower()
    if lower_name.endswith(".jsonl"):
        return "application/x-ndjson"
    if lower_name.endswith(".json"):
        return "application/json"
    if lower_name.endswith(".xlsx"):
        return "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    if lower_name.endswith(".xls"):
        return "application/vnd.ms-excel"

    guessed, _ = guess_type(file_name)
    return guessed or "application/octet-stream"


def _count_records(body: bytes) -> int:
    return max(
        1,
        sum(1 for line in body.decode("utf-8", errors="replace").splitlines() if line.strip()),
    )


def _record_count_for_dataset_body(
    *,
    file_name: str,
    body: bytes,
    purpose: str | None = None,
    use_case: str | None = None,
) -> int:
    if _is_eval_dataset(purpose=purpose, use_case=use_case):
        return normalize_eval_dataset_bytes(file_name, body).record_count
    return _count_records(body)


def _build_dataset_preview(
    *,
    file_name: str,
    body: bytes,
    total_size_bytes: int,
    purpose: str | None = None,
    use_case: str | None = None,
) -> tuple[str, bool, int]:
    if _is_eval_dataset(purpose=purpose, use_case=use_case):
        try:
            normalized_bytes = normalize_eval_dataset_bytes(file_name, body).to_jsonl_bytes()
        except ValueError:
            pass
        else:
            preview_bytes, truncated = _slice_preview_bytes_by_lines(normalized_bytes)
            return (
                preview_bytes.decode("utf-8", errors="replace"),
                truncated,
                len(normalized_bytes),
            )

    preview_bytes, truncated = _slice_preview_bytes_by_lines(body)
    return (
        preview_bytes.decode("utf-8", errors="replace"),
        truncated,
        total_size_bytes,
    )


def _slice_preview_bytes_by_lines(body: bytes) -> tuple[bytes, bool]:
    lines = body.splitlines(keepends=True)
    if len(lines) <= PREVIEW_LIMIT_LINES:
        return body, False
    return b"".join(lines[:PREVIEW_LIMIT_LINES]), True


def _is_eval_dataset(*, purpose: str | None = None, use_case: str | None = None) -> bool:
    return purpose == "evaluation" or use_case == "evaluation"


def _dataset_code(dataset: Dataset) -> str:
    return build_dataset_code(dataset.created_at.astimezone(ASIA_SHANGHAI), dataset.id)


def _build_object_key(
    *,
    project_id: UUID,
    dataset_id: UUID,
    dataset_created_at: datetime,
    version_id: UUID,
    version_created_at: datetime,
    file_name: str,
) -> str:
    return build_dataset_source_key(
        project_id,
        dataset_id,
        dataset_created_at.astimezone(ASIA_SHANGHAI),
        version_id,
        version_created_at.astimezone(ASIA_SHANGHAI),
        file_name,
    )


def _parse_s3_uri(value: str | None) -> tuple[str, str] | None:
    if not value or not value.startswith("s3://"):
        return None

    stripped = value.removeprefix("s3://")
    if "/" not in stripped:
        return None

    bucket, object_key = stripped.split("/", 1)
    if not bucket or not object_key:
        return None

    return bucket, object_key


def _basename_from_source_uri(value: str | None) -> str | None:
    parsed = _parse_s3_uri(value)
    if parsed is None:
        return None

    _, object_key = parsed
    return PurePosixPath(object_key).name


def _delete_managed_object(object_key: str) -> None:
    delete_object(DATASET_RAW_BUCKET, object_key)


def _build_source_uri(bucket: str, object_key: str) -> str:
    return f"s3://{bucket}/{object_key}"


def _build_direct_upload_response(
    *,
    bucket: str,
    object_key: str,
    file_name: str,
    file_size: int,
    content_type: str | None,
    browser_endpoint_url: str | None = None,
) -> ObjectStoreDirectUploadInitResponse:
    if file_size <= 0:
        raise ValueError("请选择待上传的数据集文件")

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


async def _get_version_files(
    session: AsyncSession,
    version_ids: list[UUID],
) -> dict[UUID, list[DatasetFile]]:
    if not version_ids:
        return {}

    rows = await session.execute(
        select(DatasetFile)
        .where(DatasetFile.dataset_version_id.in_(version_ids))
        .order_by(DatasetFile.created_at.asc(), DatasetFile.id.asc())
    )
    mapping: dict[UUID, list[DatasetFile]] = {}
    for item in rows.scalars().all():
        mapping.setdefault(item.dataset_version_id, []).append(item)
    return mapping


async def _resolve_dataset_or_raise(
    session: AsyncSession,
    dataset_identifier: str,
    project_id: UUID,
) -> Dataset:
    if not DATASET_CODE_PATTERN.match(dataset_identifier):
        raise KeyError(dataset_identifier)

    rows = await session.execute(
        select(Dataset)
        .where(
            Dataset.project_id == project_id,
            Dataset.status != "deleted",
        )
        .order_by(Dataset.created_at.desc(), Dataset.id.desc())
    )
    for dataset in rows.scalars().all():
        if _dataset_code(dataset) == dataset_identifier:
            return dataset
    raise KeyError(dataset_identifier)


def _to_version_summary(
    dataset: Dataset,
    version: DatasetVersion,
    files: list[DatasetFile],
) -> DatasetVersionSummary:
    file_item = files[0] if files else None
    return DatasetVersionSummary(
        id=version.id,
        dataset_id=_dataset_code(dataset),
        version=version.version,
        status=version.status,
        description=version.description,
        file_name=file_item.file_name if file_item else None,
        format=version.format,
        source_type=version.source_type or "local-upload",
        source_uri=version.source_uri,
        object_key=file_item.object_key if file_item else version.object_key,
        record_count=version.record_count,
        created_at=version.created_at,
        updated_at=version.updated_at,
        created_by=None,
        file_count=len(files),
        files=[_to_file_summary(file_item) for file_item in files],
    )


def _to_file_summary(file_item: DatasetFile) -> DatasetFileSummary:
    return DatasetFileSummary(
        id=file_item.id,
        version_id=file_item.dataset_version_id,
        file_name=file_item.file_name,
        object_key=file_item.object_key,
        mime_type=file_item.mime_type,
        size_bytes=file_item.size_bytes,
        etag=file_item.etag,
        created_at=file_item.created_at,
        updated_at=file_item.updated_at,
    )


def _to_dataset_summary(
    dataset: Dataset,
    latest_version: DatasetVersion | None,
) -> DatasetSummary:
    return DatasetSummary(
        id=_dataset_code(dataset),
        name=dataset.name,
        description=dataset.description,
        purpose=dataset.purpose,
        format=dataset.format,
        use_case=dataset.use_case,
        modality=dataset.modality,
        recipe=dataset.recipe,
        scope=dataset.scope,
        source_type=dataset.source_type or "local-upload",
        status=dataset.status,
        latest_version=latest_version.version if latest_version else None,
        latest_version_id=latest_version.id if latest_version else None,
        owner_name=dataset.owner_name,
        tags=dataset.tags or [],
        record_count=latest_version.record_count if latest_version else None,
        created_at=dataset.created_at,
        updated_at=dataset.updated_at,
    )


def _to_dataset_detail(
    dataset: Dataset,
    versions: list[DatasetVersion],
    files_by_version: dict[UUID, list[DatasetFile]],
) -> DatasetDetail:
    latest_version = next((item for item in versions if item.id == dataset.latest_version_id), None)
    if latest_version is None and versions:
        latest_version = max(versions, key=lambda item: item.version)

    return DatasetDetail(
        **_to_dataset_summary(dataset, latest_version).model_dump(),
        source_uri=dataset.source_uri,
        versions=[
            _to_version_summary(dataset, version, files_by_version.get(version.id, []))
            for version in versions
        ],
    )


async def _read_dataset_payload(
    files: list[DatasetFile],
    version: DatasetVersion,
    file_id: UUID | None = None,
) -> tuple[str, ObjectPayload]:
    if file_id is not None:
        file_item = next((item for item in files if item.id == file_id), None)
        if file_item is None:
            raise KeyError(str(file_id))
    else:
        file_item = files[0] if files else None

    if file_item is not None:
        payload = get_object_bytes(DATASET_RAW_BUCKET, file_item.object_key)
        return file_item.file_name, payload

    if version.object_key:
        payload = get_object_bytes(DATASET_RAW_BUCKET, version.object_key)
        file_name = PurePosixPath(version.object_key).name or "dataset.jsonl"
        return file_name, payload

    parsed = _parse_s3_uri(version.source_uri)
    if parsed is None:
        raise FileNotFoundError(str(version.id))

    bucket, object_key = parsed
    payload = get_object_bytes(bucket, object_key)
    file_name = _basename_from_source_uri(version.source_uri) or "dataset.jsonl"
    return file_name, payload


async def _get_dataset_or_raise(
    session: AsyncSession,
    dataset_id: str,
    project_id: UUID,
) -> Dataset:
    return await _resolve_dataset_or_raise(session, dataset_id, project_id)


async def _get_dataset_version_or_raise(
    session: AsyncSession,
    *,
    dataset: Dataset,
    version_id: UUID,
) -> DatasetVersion:
    version = await session.get(DatasetVersion, version_id)
    if version is None or version.dataset_id != dataset.id:
        raise KeyError(str(version_id))
    return version


async def _list_versions(session: AsyncSession, dataset_id: UUID) -> list[DatasetVersion]:
    rows = await session.execute(
        select(DatasetVersion)
        .where(DatasetVersion.dataset_id == dataset_id)
        .order_by(DatasetVersion.version.desc())
    )
    return rows.scalars().all()


async def _sync_dataset_latest_version(
    session: AsyncSession,
    dataset: Dataset,
    versions: list[DatasetVersion] | None = None,
) -> None:
    current_versions = (
        versions if versions is not None else await _list_versions(session, dataset.id)
    )
    if not current_versions:
        dataset.latest_version_id = None
        dataset.status = "deleted"
        dataset.updated_at = _now()
        return

    latest_version = max(current_versions, key=lambda item: item.version)
    dataset.latest_version_id = latest_version.id
    dataset.status = latest_version.status
    dataset.updated_at = latest_version.updated_at


async def _list_eval_job_references(
    session: AsyncSession,
    version_ids: list[UUID],
) -> list[EvalJob]:
    if not version_ids:
        return []

    rows = await session.execute(
        select(EvalJob)
        .where(EvalJob.dataset_version_id.in_(version_ids))
        .order_by(EvalJob.created_at.asc(), EvalJob.id.asc())
    )
    return list(rows.scalars().all())


def _build_eval_reference_error(scope: str, jobs: list[EvalJob]) -> str:
    preview = "、".join(job.name for job in jobs[:3])
    if len(jobs) > 3:
        preview = f"{preview} 等 {len(jobs)} 个任务"

    if scope == "dataset":
        return f"该数据集已被评测任务引用：{preview}。请先处理相关评测任务后再删除。"
    return f"该版本已被评测任务引用：{preview}。请先处理相关评测任务后再删除。"


def _store_object_bytes(
    *,
    project_id: UUID,
    dataset_id: UUID,
    dataset_created_at: datetime,
    version_id: UUID,
    version_created_at: datetime,
    file_name: str,
    body: bytes,
    content_type: str | None,
) -> tuple[str, ObjectPayload]:
    object_key = _build_object_key(
        project_id=project_id,
        dataset_id=dataset_id,
        dataset_created_at=dataset_created_at,
        version_id=version_id,
        version_created_at=version_created_at,
        file_name=file_name,
    )
    payload = put_object_bytes(
        DATASET_RAW_BUCKET,
        object_key,
        body,
        content_type=content_type or _guess_content_type(file_name),
    )
    return object_key, payload


def _store_normalized_eval_artifacts(
    *,
    project_id: UUID,
    dataset_id: UUID,
    dataset_created_at: datetime,
    version_id: UUID,
    version_created_at: datetime,
    source_file_name: str,
    body: bytes,
) -> None:
    normalized_key = build_dataset_artifact_key(
        project_id,
        dataset_id,
        dataset_created_at.astimezone(ASIA_SHANGHAI),
        version_id,
        version_created_at.astimezone(ASIA_SHANGHAI),
        "eval-samples.jsonl",
    )
    report_key = build_dataset_artifact_key(
        project_id,
        dataset_id,
        dataset_created_at.astimezone(ASIA_SHANGHAI),
        version_id,
        version_created_at.astimezone(ASIA_SHANGHAI),
        "schema-report.json",
    )
    normalized = normalize_eval_dataset_bytes(source_file_name, body)
    put_object_bytes(
        DATASET_RAW_BUCKET,
        normalized_key,
        normalized.to_jsonl_bytes(),
        content_type="application/x-ndjson",
    )
    put_object_bytes(
        DATASET_RAW_BUCKET,
        report_key,
        json.dumps(normalized.schema_report(), ensure_ascii=False, indent=2).encode("utf-8"),
        content_type="application/json",
    )


def _normalize_eval_artifacts_if_needed(
    *,
    project_id: UUID,
    dataset_id: UUID,
    dataset_created_at: datetime,
    version_id: UUID,
    version_created_at: datetime,
    file_name: str,
    purpose: str | None = None,
    use_case: str | None = None,
    body: bytes,
) -> None:
    if not _is_eval_dataset(purpose=purpose, use_case=use_case):
        return
    _store_normalized_eval_artifacts(
        project_id=project_id,
        dataset_id=dataset_id,
        dataset_created_at=dataset_created_at,
        version_id=version_id,
        version_created_at=version_created_at,
        source_file_name=file_name,
        body=body,
    )


async def _store_uploaded_file(
    *,
    project_id: UUID,
    dataset_id: UUID,
    dataset_created_at: datetime,
    version_id: UUID,
    version_created_at: datetime,
    upload_file: UploadFile,
) -> tuple[str, str, ObjectPayload]:
    file_name = upload_file.filename or "dataset.jsonl"
    body = await upload_file.read()
    object_key, payload = _store_object_bytes(
        project_id=project_id,
        dataset_id=dataset_id,
        dataset_created_at=dataset_created_at,
        version_id=version_id,
        version_created_at=version_created_at,
        file_name=file_name,
        body=body,
        content_type=upload_file.content_type,
    )
    return file_name, object_key, payload


def _mirror_s3_import(
    *,
    project_id: UUID,
    dataset_id: UUID,
    dataset_created_at: datetime,
    version_id: UUID,
    version_created_at: datetime,
    source_uri: str,
) -> tuple[str, str, ObjectPayload]:
    parsed = _parse_s3_uri(source_uri)
    if parsed is None:
        raise ValueError("请输入合法的 S3 对象存储路径")

    source_bucket, source_key = parsed
    try:
        source_payload = get_object_bytes(source_bucket, source_key)
    except FileNotFoundError as exc:
        raise ValueError("S3 对象不存在或尚未上传") from exc
    file_name = PurePosixPath(source_key).name or "dataset.jsonl"
    object_key, stored_payload = _store_object_bytes(
        project_id=project_id,
        dataset_id=dataset_id,
        dataset_created_at=dataset_created_at,
        version_id=version_id,
        version_created_at=version_created_at,
        file_name=file_name,
        body=source_payload.body,
        content_type=source_payload.content_type or _guess_content_type(file_name),
    )
    return file_name, object_key, stored_payload


async def activity_process_dataset_import(
    *,
    project_id: str,
    dataset_id: str,
    dataset_version_id: str,
) -> dict[str, object]:
    async with SessionLocal() as session:
        dataset = await _get_dataset_or_raise(session, dataset_id, UUID(project_id))
        version = await _get_dataset_version_or_raise(
            session,
            dataset=dataset,
            version_id=UUID(dataset_version_id),
        )
        files_by_version = await _get_version_files(session, [version.id])
        version_files = files_by_version.get(version.id, [])
        file_item = version_files[0] if version_files else None
        file_name, object_payload = await _read_dataset_payload(version_files, version)
        object_key = (
            file_item.object_key
            if file_item is not None
            else version.object_key
        )
        if not object_key:
            raise ValueError("数据集对象存储路径缺失")

        return {
            "status": "processing",
            "dataset_id": str(dataset.id),
            "dataset_version_id": str(version.id),
            "object_key": object_key,
            "file_name": file_name,
            "file_size": object_payload.size_bytes,
            "record_count": _record_count_for_dataset_body(
                file_name=file_name,
                body=object_payload.body,
                purpose=dataset.purpose,
                use_case=dataset.use_case,
            ),
        }


async def activity_finalize_dataset_import(
    *,
    project_id: str,
    dataset_id: str,
    dataset_version_id: str,
) -> dict[str, object]:
    async with SessionLocal() as session:
        dataset = await _get_dataset_or_raise(session, dataset_id, UUID(project_id))
        version = await _get_dataset_version_or_raise(
            session,
            dataset=dataset,
            version_id=UUID(dataset_version_id),
        )
        files_by_version = await _get_version_files(session, [version.id])
        version_files = files_by_version.get(version.id, [])
        file_item = version_files[0] if version_files else None
        file_name, object_payload = await _read_dataset_payload(version_files, version)
        object_key = (
            file_item.object_key
            if file_item is not None
            else version.object_key
        )
        if not object_key:
            raise ValueError("数据集对象存储路径缺失")

        _normalize_eval_artifacts_if_needed(
            project_id=dataset.project_id,
            dataset_id=dataset.id,
            dataset_created_at=dataset.created_at,
            version_id=version.id,
            version_created_at=version.created_at,
            file_name=file_name,
            purpose=dataset.purpose,
            use_case=dataset.use_case,
            body=object_payload.body,
        )

        processed_at = _now()
        version.object_key = object_key
        version.source_uri = version.source_uri or _build_source_uri(DATASET_RAW_BUCKET, object_key)
        version.file_size = object_payload.size_bytes
        version.record_count = _record_count_for_dataset_body(
            file_name=file_name,
            body=object_payload.body,
            purpose=dataset.purpose,
            use_case=dataset.use_case,
        )
        version.status = "ready"
        version.updated_at = processed_at

        if file_item is not None:
            file_item.mime_type = object_payload.content_type or _guess_content_type(file_name)
            file_item.size_bytes = object_payload.size_bytes
            file_item.etag = object_payload.etag
            file_item.updated_at = processed_at

        dataset.latest_version_id = version.id
        dataset.source_uri = dataset.source_uri or version.source_uri
        dataset.status = "ready"
        dataset.updated_at = processed_at
        await session.commit()

        return {
            "status": "ready",
            "dataset_id": str(dataset.id),
            "dataset_version_id": str(version.id),
            "object_key": object_key,
            "record_count": version.record_count,
        }


async def activity_mark_dataset_import_failed(
    *,
    project_id: str,
    dataset_id: str,
    dataset_version_id: str,
) -> dict[str, str]:
    async with SessionLocal() as session:
        try:
            dataset = await _get_dataset_or_raise(session, dataset_id, UUID(project_id))
            version = await _get_dataset_version_or_raise(
                session,
                dataset=dataset,
                version_id=UUID(dataset_version_id),
            )
        except KeyError:
            return {
                "status": "failed",
                "dataset_id": dataset_id,
                "dataset_version_id": dataset_version_id,
            }
        failed_at = _now()
        version.status = "failed"
        version.updated_at = failed_at
        dataset.latest_version_id = version.id
        dataset.status = "failed"
        dataset.updated_at = failed_at
        await session.commit()

    return {
        "status": "failed",
        "dataset_id": dataset_id,
        "dataset_version_id": dataset_version_id,
    }


async def _run_dataset_import_locally(
    project_id: str,
    dataset_id: str,
    dataset_version_id: str,
) -> None:
    try:
        await activity_finalize_dataset_import(
            project_id=project_id,
            dataset_id=dataset_id,
            dataset_version_id=dataset_version_id,
        )
    except Exception:
        await activity_mark_dataset_import_failed(
            project_id=project_id,
            dataset_id=dataset_id,
            dataset_version_id=dataset_version_id,
        )


async def _start_dataset_import_job(
    *,
    project_id: UUID,
    dataset_id: str,
    dataset_version_id: UUID,
    object_key: str,
) -> None:
    from nta_backend.core.temporal import start_dataset_import_workflow
    from nta_backend.workflows.dataset_import import DatasetImportWorkflowInput

    workflow_input = DatasetImportWorkflowInput(
        project_id=str(project_id),
        dataset_id=dataset_id,
        dataset_version_id=str(dataset_version_id),
        object_key=object_key,
    )

    try:
        await start_dataset_import_workflow(
            workflow_input,
            workflow_id=f"dataset-import-{dataset_version_id}",
        )
    except Exception:
        asyncio.create_task(
            _run_dataset_import_locally(
                str(project_id),
                dataset_id,
                str(dataset_version_id),
            )
        )


class DatasetService:
    async def list_datasets(self) -> list[DatasetSummary]:
        async with SessionLocal() as session:
            project_id = await resolve_active_project_id(session)
            rows = await session.execute(
                select(Dataset)
                .where(Dataset.status != "deleted")
                .where(Dataset.project_id == project_id)
                .order_by(Dataset.updated_at.desc())
            )
            datasets = rows.scalars().all()
            version_ids = [item.latest_version_id for item in datasets if item.latest_version_id]
            versions_by_id: dict[UUID, DatasetVersion] = {}
            if version_ids:
                latest_rows = await session.execute(
                    select(DatasetVersion).where(DatasetVersion.id.in_(version_ids))
                )
                versions_by_id = {item.id: item for item in latest_rows.scalars().all()}

            return [
                _to_dataset_summary(dataset, versions_by_id.get(dataset.latest_version_id))
                for dataset in datasets
            ]

    async def get_dataset(self, dataset_id: str) -> DatasetDetail:
        async with SessionLocal() as session:
            project_id = await resolve_active_project_id(session)
            dataset = await _get_dataset_or_raise(session, dataset_id, project_id)
            versions = await _list_versions(session, dataset.id)
            files_by_version = await _get_version_files(
                session,
                [version.id for version in versions],
            )
            return _to_dataset_detail(dataset, versions, files_by_version)

    async def get_dataset_version_preview(
        self,
        dataset_id: str,
        version_id: str,
        file_id: str | None = None,
    ) -> DatasetVersionPreview:
        async with SessionLocal() as session:
            project_id = await resolve_active_project_id(session)
            dataset = await _get_dataset_or_raise(session, dataset_id, project_id)
            version = await session.get(DatasetVersion, UUID(version_id))
            if version is None or version.dataset_id != dataset.id:
                raise KeyError(version_id)

            files_by_version = await _get_version_files(session, [version.id])
            version_files = files_by_version.get(version.id, [])
            selected_file_id = UUID(file_id) if file_id else None
            try:
                file_name, payload = await _read_dataset_payload(
                    version_files,
                    version,
                    selected_file_id,
                )
            except (FileNotFoundError, KeyError) as exc:
                raise KeyError(version_id) from exc
            preview_content, truncated, content_bytes = _build_dataset_preview(
                file_name=file_name,
                body=payload.body,
                total_size_bytes=payload.size_bytes,
                purpose=dataset.purpose,
                use_case=dataset.use_case,
            )
            return DatasetVersionPreview(
                dataset_id=_dataset_code(dataset),
                version_id=version.id,
                file_id=selected_file_id or (version_files[0].id if version_files else None),
                file_name=file_name,
                content=preview_content,
                truncated=truncated,
                content_bytes=content_bytes,
            )

    async def get_dataset_version_download(
        self,
        dataset_id: str,
        version_id: str,
        file_id: str | None = None,
    ) -> DatasetDownloadPayload:
        async with SessionLocal() as session:
            project_id = await resolve_active_project_id(session)
            dataset = await _get_dataset_or_raise(session, dataset_id, project_id)
            version = await session.get(DatasetVersion, UUID(version_id))
            if version is None or version.dataset_id != dataset.id:
                raise KeyError(version_id)

            files_by_version = await _get_version_files(session, [version.id])
            selected_file_id = UUID(file_id) if file_id else None
            try:
                file_name, payload = await _read_dataset_payload(
                    files_by_version.get(version.id, []),
                    version,
                    selected_file_id,
                )
            except (FileNotFoundError, KeyError) as exc:
                raise KeyError(version_id) from exc
            return DatasetDownloadPayload(file_name=file_name, object_payload=payload)

    async def create_dataset(self, payload: DatasetCreate) -> DatasetCreateResponse:
        if payload.source_type != "s3-import":
            raise ValueError("本地上传请使用上传接口")
        if not payload.source_uri:
            raise ValueError("请输入 S3 对象存储路径")

        async with SessionLocal() as session:
            project_id = await resolve_active_project_id(session)

            created_at = _now()
            dataset_id = uuid4()
            version_id = uuid4()
            file_name, object_key, stored_payload = _mirror_s3_import(
                project_id=project_id,
                dataset_id=dataset_id,
                dataset_created_at=created_at,
                version_id=version_id,
                version_created_at=created_at,
                source_uri=payload.source_uri,
            )
            try:
                _normalize_eval_artifacts_if_needed(
                    project_id=project_id,
                    dataset_id=dataset_id,
                    dataset_created_at=created_at,
                    version_id=version_id,
                    version_created_at=created_at,
                    file_name=file_name,
                    purpose=payload.purpose,
                    use_case=payload.use_case,
                    body=stored_payload.body,
                )
            except ValueError:
                _delete_managed_object(object_key)
                raise

            dataset = Dataset(
                id=dataset_id,
                project_id=project_id,
                name=payload.name,
                description=payload.description,
                purpose=payload.use_case or payload.purpose,
                format=payload.modality or payload.format,
                use_case=payload.use_case or payload.purpose,
                modality=payload.modality or payload.format,
                recipe=payload.recipe or "sft",
                scope=payload.scope,
                source_type="s3-import",
                source_uri=payload.source_uri,
                tags=payload.tags,
                latest_version_id=version_id,
                status="ready",
                created_at=created_at,
                updated_at=created_at,
            )
            version = DatasetVersion(
                id=version_id,
                dataset_id=dataset_id,
                version=1,
                description=payload.description,
                format=payload.modality or payload.format,
                source_type="s3-import",
                source_uri=payload.source_uri,
                object_key=object_key,
                file_size=stored_payload.size_bytes,
                record_count=_record_count_for_dataset_body(
                    file_name=file_name,
                    body=stored_payload.body,
                    purpose=payload.purpose,
                    use_case=payload.use_case,
                ),
                status="ready",
                created_at=created_at,
                updated_at=created_at,
            )
            file_item = DatasetFile(
                dataset_version_id=version_id,
                file_name=file_name,
                object_key=object_key,
                mime_type=stored_payload.content_type or _guess_content_type(file_name),
                size_bytes=stored_payload.size_bytes,
                etag=stored_payload.etag,
                created_at=created_at,
                updated_at=created_at,
            )
            session.add(dataset)
            session.add(version)
            await session.flush()
            session.add(file_item)
            await session.commit()

            return DatasetCreateResponse(
                dataset_id=_dataset_code(dataset),
                version_id=version_id,
                status="ready",
                object_key=object_key,
                source_uri=payload.source_uri,
            )

    async def prepare_dataset_direct_upload(
        self,
        payload: DatasetDirectUploadInitRequest,
        browser_endpoint_url: str | None = None,
    ) -> DatasetDirectUploadInitResponse:
        async with SessionLocal() as session:
            project_id = await resolve_active_project_id(session)

            created_at = _now()
            dataset_id = uuid4()
            version_id = uuid4()
            object_key = _build_object_key(
                project_id=project_id,
                dataset_id=dataset_id,
                dataset_created_at=created_at,
                version_id=version_id,
                version_created_at=created_at,
                file_name=payload.file_name,
            )
            source_uri = _build_source_uri(DATASET_RAW_BUCKET, object_key)
            upload = _build_direct_upload_response(
                bucket=DATASET_RAW_BUCKET,
                object_key=object_key,
                file_name=payload.file_name,
                file_size=payload.file_size,
                content_type=payload.content_type,
                browser_endpoint_url=browser_endpoint_url,
            )

            dataset = Dataset(
                id=dataset_id,
                project_id=project_id,
                name=payload.name,
                description=payload.description,
                purpose=payload.use_case or payload.purpose,
                format=payload.modality or payload.format,
                use_case=payload.use_case or payload.purpose,
                modality=payload.modality or payload.format,
                recipe=payload.recipe or "sft",
                scope=payload.scope,
                source_type="local-upload",
                source_uri=source_uri,
                tags=payload.tags,
                latest_version_id=version_id,
                status="uploading",
                created_at=created_at,
                updated_at=created_at,
            )
            version = DatasetVersion(
                id=version_id,
                dataset_id=dataset_id,
                version=1,
                description=payload.description,
                format=payload.modality or payload.format,
                source_type="local-upload",
                source_uri=source_uri,
                object_key=object_key,
                file_size=payload.file_size,
                record_count=None,
                status="uploading",
                created_at=created_at,
                updated_at=created_at,
            )
            file_item = DatasetFile(
                dataset_version_id=version_id,
                file_name=payload.file_name,
                object_key=object_key,
                mime_type=payload.content_type or _guess_content_type(payload.file_name),
                size_bytes=payload.file_size,
                etag=None,
                created_at=created_at,
                updated_at=created_at,
            )
            session.add(dataset)
            session.add(version)
            await session.flush()
            session.add(file_item)
            await session.commit()

            return DatasetDirectUploadInitResponse(
                dataset_id=_dataset_code(dataset),
                version_id=version_id,
                status="uploading",
                object_key=object_key,
                source_uri=source_uri,
                file_name=payload.file_name,
                upload=upload,
            )

    async def complete_dataset_direct_upload(
        self,
        dataset_id: str,
        version_id: str,
        payload: DatasetDirectUploadCompleteRequest,
    ) -> DatasetCreateResponse:
        async with SessionLocal() as session:
            project_id = await resolve_active_project_id(session)
            dataset = await _get_dataset_or_raise(session, dataset_id, project_id)
            version = await _get_dataset_version_or_raise(
                session,
                dataset=dataset,
                version_id=UUID(version_id),
            )
            files_by_version = await _get_version_files(session, [version.id])
            version_files = files_by_version.get(version.id, [])
            file_item = version_files[0] if version_files else None
            expected_object_key = (
                file_item.object_key
                if file_item is not None
                else version.object_key
            )
            if payload.upload.bucket != DATASET_RAW_BUCKET:
                raise ValueError("上传目标桶不正确")
            if not expected_object_key or payload.upload.object_key != expected_object_key:
                raise ValueError("上传对象路径不匹配")

            if version.status in {"processing", "ready"}:
                return DatasetCreateResponse(
                    dataset_id=_dataset_code(dataset),
                    version_id=version.id,
                    status=version.status,
                    object_key=expected_object_key,
                    source_uri=version.source_uri or payload.upload.uri,
                )

            finalized_at = _now()
            version.source_uri = payload.upload.uri
            version.object_key = payload.upload.object_key
            version.file_size = payload.upload.size_bytes
            version.status = "processing"
            version.updated_at = finalized_at

            if file_item is not None:
                file_item.file_name = payload.upload.file_name
                file_item.object_key = payload.upload.object_key
                file_item.mime_type = (
                    payload.upload.content_type
                    or file_item.mime_type
                    or _guess_content_type(payload.upload.file_name)
                )
                file_item.size_bytes = payload.upload.size_bytes
                file_item.updated_at = finalized_at

            dataset.latest_version_id = version.id
            dataset.source_uri = payload.upload.uri
            dataset.status = "processing"
            dataset.updated_at = finalized_at
            await session.commit()

        try:
            await _start_dataset_import_job(
                project_id=project_id,
                dataset_id=_dataset_code(dataset),
                dataset_version_id=UUID(version_id),
                object_key=payload.upload.object_key,
            )
        except Exception as exc:
            await activity_mark_dataset_import_failed(
                project_id=str(project_id),
                dataset_id=_dataset_code(dataset),
                dataset_version_id=version_id,
            )
            raise ValueError("启动数据集导入任务失败") from exc

        return DatasetCreateResponse(
            dataset_id=_dataset_code(dataset),
            version_id=UUID(version_id),
            status="processing",
            object_key=payload.upload.object_key,
            source_uri=payload.upload.uri,
        )

    async def fail_dataset_direct_upload(
        self,
        dataset_id: str,
        version_id: str,
        payload: DatasetDirectUploadFailedRequest,
    ) -> None:
        async with SessionLocal() as session:
            project_id = await resolve_active_project_id(session)
            dataset = await _get_dataset_or_raise(session, dataset_id, project_id)
            version = await _get_dataset_version_or_raise(
                session,
                dataset=dataset,
                version_id=UUID(version_id),
            )

            if version.status in {"ready", "processing"}:
                return

            failed_at = _now()
            version.status = "failed"
            version.updated_at = failed_at
            dataset.latest_version_id = version.id
            dataset.status = "failed"
            dataset.updated_at = failed_at
            await session.commit()

    async def create_dataset_from_upload(
        self,
        *,
        name: str,
        description: str | None,
        use_case: str,
        modality: str,
        recipe: str,
        upload_file: UploadFile,
    ) -> DatasetCreateResponse:
        async with SessionLocal() as session:
            project_id = await resolve_active_project_id(session)

            created_at = _now()
            dataset_id = uuid4()
            version_id = uuid4()
            file_name, object_key, stored_payload = await _store_uploaded_file(
                project_id=project_id,
                dataset_id=dataset_id,
                dataset_created_at=created_at,
                version_id=version_id,
                version_created_at=created_at,
                upload_file=upload_file,
            )
            try:
                _normalize_eval_artifacts_if_needed(
                    project_id=project_id,
                    dataset_id=dataset_id,
                    dataset_created_at=created_at,
                    version_id=version_id,
                    version_created_at=created_at,
                    file_name=file_name,
                    purpose=use_case,
                    use_case=use_case,
                    body=stored_payload.body,
                )
            except ValueError:
                _delete_managed_object(object_key)
                raise

            dataset = Dataset(
                id=dataset_id,
                project_id=project_id,
                name=name,
                description=description,
                purpose=use_case,
                format=modality,
                use_case=use_case,
                modality=modality,
                recipe=recipe,
                scope="my-datasets",
                source_type="local-upload",
                source_uri=None,
                tags=[],
                latest_version_id=version_id,
                status="ready",
                created_at=created_at,
                updated_at=created_at,
            )
            version = DatasetVersion(
                id=version_id,
                dataset_id=dataset_id,
                version=1,
                description=description,
                format=modality,
                source_type="local-upload",
                source_uri=None,
                object_key=object_key,
                file_size=stored_payload.size_bytes,
                record_count=_record_count_for_dataset_body(
                    file_name=file_name,
                    body=stored_payload.body,
                    purpose=use_case,
                    use_case=use_case,
                ),
                status="ready",
                created_at=created_at,
                updated_at=created_at,
            )
            file_item = DatasetFile(
                dataset_version_id=version_id,
                file_name=file_name,
                object_key=object_key,
                mime_type=stored_payload.content_type or _guess_content_type(file_name),
                size_bytes=stored_payload.size_bytes,
                etag=stored_payload.etag,
                created_at=created_at,
                updated_at=created_at,
            )
            session.add(dataset)
            session.add(version)
            await session.flush()
            session.add(file_item)
            await session.commit()

            return DatasetCreateResponse(
                dataset_id=_dataset_code(dataset),
                version_id=version_id,
                status="ready",
                object_key=object_key,
                source_uri=None,
            )

    async def create_dataset_version(
        self,
        dataset_id: str,
        payload: DatasetVersionCreate,
    ) -> DatasetCreateResponse:
        if payload.source_type != "s3-import":
            raise ValueError("本地上传请使用上传接口")
        if not payload.source_uri:
            raise ValueError("请输入 S3 对象存储路径")

        async with SessionLocal() as session:
            project_id = await resolve_active_project_id(session)
            dataset = await _get_dataset_or_raise(session, dataset_id, project_id)

            created_at = _now()
            next_version = int(
                await session.scalar(
                    select(func.max(DatasetVersion.version)).where(
                        DatasetVersion.dataset_id == dataset.id
                    )
                )
                or 0
            ) + 1
            version_id = uuid4()
            file_name, object_key, stored_payload = _mirror_s3_import(
                project_id=project_id,
                dataset_id=dataset.id,
                dataset_created_at=dataset.created_at,
                version_id=version_id,
                version_created_at=created_at,
                source_uri=payload.source_uri,
            )
            try:
                _normalize_eval_artifacts_if_needed(
                    project_id=project_id,
                    dataset_id=dataset.id,
                    dataset_created_at=dataset.created_at,
                    version_id=version_id,
                    version_created_at=created_at,
                    file_name=file_name,
                    purpose=dataset.purpose,
                    use_case=dataset.use_case,
                    body=stored_payload.body,
                )
            except ValueError:
                _delete_managed_object(object_key)
                raise

            version = DatasetVersion(
                id=version_id,
                dataset_id=dataset.id,
                version=next_version,
                description=payload.description,
                format=payload.format or dataset.modality or dataset.format,
                source_type="s3-import",
                source_uri=payload.source_uri,
                object_key=object_key,
                file_size=stored_payload.size_bytes,
                record_count=_record_count_for_dataset_body(
                    file_name=file_name,
                    body=stored_payload.body,
                    purpose=dataset.purpose,
                    use_case=dataset.use_case,
                ),
                status="ready",
                created_at=created_at,
                updated_at=created_at,
            )
            file_item = DatasetFile(
                dataset_version_id=version_id,
                file_name=file_name,
                object_key=object_key,
                mime_type=stored_payload.content_type or _guess_content_type(file_name),
                size_bytes=stored_payload.size_bytes,
                etag=stored_payload.etag,
                created_at=created_at,
                updated_at=created_at,
            )
            session.add(version)
            await session.flush()
            session.add(file_item)
            dataset.latest_version_id = version_id
            dataset.status = "ready"
            dataset.updated_at = created_at
            await session.commit()

            return DatasetCreateResponse(
                dataset_id=_dataset_code(dataset),
                version_id=version_id,
                status="ready",
                object_key=object_key,
                source_uri=payload.source_uri,
            )

    async def prepare_dataset_version_direct_upload(
        self,
        dataset_id: str,
        payload: DatasetVersionDirectUploadInitRequest,
        browser_endpoint_url: str | None = None,
    ) -> DatasetDirectUploadInitResponse:
        async with SessionLocal() as session:
            project_id = await resolve_active_project_id(session)
            dataset = await _get_dataset_or_raise(session, dataset_id, project_id)

            created_at = _now()
            next_version = int(
                await session.scalar(
                    select(func.max(DatasetVersion.version)).where(
                        DatasetVersion.dataset_id == dataset.id
                    )
                )
                or 0
            ) + 1
            version_id = uuid4()
            object_key = _build_object_key(
                project_id=project_id,
                dataset_id=dataset.id,
                dataset_created_at=dataset.created_at,
                version_id=version_id,
                version_created_at=created_at,
                file_name=payload.file_name,
            )
            source_uri = _build_source_uri(DATASET_RAW_BUCKET, object_key)
            upload = _build_direct_upload_response(
                bucket=DATASET_RAW_BUCKET,
                object_key=object_key,
                file_name=payload.file_name,
                file_size=payload.file_size,
                content_type=payload.content_type,
                browser_endpoint_url=browser_endpoint_url,
            )

            version = DatasetVersion(
                id=version_id,
                dataset_id=dataset.id,
                version=next_version,
                description=payload.description,
                format=payload.format or dataset.modality or dataset.format,
                source_type="local-upload",
                source_uri=source_uri,
                object_key=object_key,
                file_size=payload.file_size,
                record_count=None,
                status="uploading",
                created_at=created_at,
                updated_at=created_at,
            )
            file_item = DatasetFile(
                dataset_version_id=version_id,
                file_name=payload.file_name,
                object_key=object_key,
                mime_type=payload.content_type or _guess_content_type(payload.file_name),
                size_bytes=payload.file_size,
                etag=None,
                created_at=created_at,
                updated_at=created_at,
            )
            session.add(version)
            await session.flush()
            session.add(file_item)
            dataset.latest_version_id = version_id
            dataset.source_uri = source_uri
            dataset.status = "uploading"
            dataset.updated_at = created_at
            await session.commit()

            return DatasetDirectUploadInitResponse(
                dataset_id=_dataset_code(dataset),
                version_id=version_id,
                status="uploading",
                object_key=object_key,
                source_uri=source_uri,
                file_name=payload.file_name,
                upload=upload,
            )

    async def create_dataset_version_from_upload(
        self,
        dataset_id: str,
        description: str | None,
        upload_file: UploadFile,
    ) -> DatasetCreateResponse:
        async with SessionLocal() as session:
            project_id = await resolve_active_project_id(session)
            dataset = await _get_dataset_or_raise(session, dataset_id, project_id)

            created_at = _now()
            next_version = int(
                await session.scalar(
                    select(func.max(DatasetVersion.version)).where(
                        DatasetVersion.dataset_id == dataset.id
                    )
                )
                or 0
            ) + 1
            version_id = uuid4()
            file_name, object_key, stored_payload = await _store_uploaded_file(
                project_id=project_id,
                dataset_id=dataset.id,
                dataset_created_at=dataset.created_at,
                version_id=version_id,
                version_created_at=created_at,
                upload_file=upload_file,
            )
            try:
                _normalize_eval_artifacts_if_needed(
                    project_id=project_id,
                    dataset_id=dataset.id,
                    dataset_created_at=dataset.created_at,
                    version_id=version_id,
                    version_created_at=created_at,
                    file_name=file_name,
                    purpose=dataset.purpose,
                    use_case=dataset.use_case,
                    body=stored_payload.body,
                )
            except ValueError:
                _delete_managed_object(object_key)
                raise

            version = DatasetVersion(
                id=version_id,
                dataset_id=dataset.id,
                version=next_version,
                description=description,
                format=dataset.modality or dataset.format,
                source_type="local-upload",
                source_uri=None,
                object_key=object_key,
                file_size=stored_payload.size_bytes,
                record_count=_record_count_for_dataset_body(
                    file_name=file_name,
                    body=stored_payload.body,
                    purpose=dataset.purpose,
                    use_case=dataset.use_case,
                ),
                status="ready",
                created_at=created_at,
                updated_at=created_at,
            )
            file_item = DatasetFile(
                dataset_version_id=version_id,
                file_name=file_name,
                object_key=object_key,
                mime_type=stored_payload.content_type or _guess_content_type(file_name),
                size_bytes=stored_payload.size_bytes,
                etag=stored_payload.etag,
                created_at=created_at,
                updated_at=created_at,
            )
            session.add(version)
            await session.flush()
            session.add(file_item)
            dataset.latest_version_id = version_id
            dataset.status = "ready"
            dataset.updated_at = created_at
            await session.commit()

            return DatasetCreateResponse(
                dataset_id=_dataset_code(dataset),
                version_id=version_id,
                status="ready",
                object_key=object_key,
                source_uri=None,
            )

    async def delete_dataset(self, dataset_id: str) -> None:
        async with SessionLocal() as session:
            project_id = await resolve_active_project_id(session)
            dataset = await _get_dataset_or_raise(session, dataset_id, project_id)
            versions = await _list_versions(session, dataset.id)
            files_by_version = await _get_version_files(
                session,
                [version.id for version in versions],
            )
            version_ids = [version.id for version in versions]
            object_keys = [
                file_item.object_key
                for files in files_by_version.values()
                for file_item in files
            ]
            object_prefixes = {
                build_dataset_version_prefix(
                    project_id,
                    dataset.id,
                    dataset.created_at.astimezone(ASIA_SHANGHAI),
                    version.id,
                    version.created_at.astimezone(ASIA_SHANGHAI),
                )
                for version in versions
            }
            legacy_artifact_prefixes = {
                str(PurePosixPath(object_key).parent / "_normalized") + "/"
                for object_key in object_keys
            }
            references = await _list_eval_job_references(session, version_ids)
            if references:
                raise ValueError(_build_eval_reference_error("dataset", references))

            await session.delete(dataset)
            await session.commit()

        for object_key in object_keys:
            _delete_managed_object(object_key)
        for prefix in object_prefixes | legacy_artifact_prefixes:
            delete_object_prefix(DATASET_RAW_BUCKET, prefix)

    async def delete_dataset_version(self, dataset_id: str, version_id: str) -> None:
        async with SessionLocal() as session:
            project_id = await resolve_active_project_id(session)
            dataset = await _get_dataset_or_raise(session, dataset_id, project_id)
            versions = await _list_versions(session, dataset.id)
            if len(versions) <= 1:
                raise ValueError("至少保留一个版本，请直接删除整个数据集。")

            version = next((item for item in versions if str(item.id) == version_id), None)
            if version is None:
                raise KeyError(version_id)

            files_by_version = await _get_version_files(session, [version.id])
            object_keys = [
                file_item.object_key
                for file_item in files_by_version.get(version.id, [])
            ]
            object_prefixes = {
                build_dataset_version_prefix(
                    project_id,
                    dataset.id,
                    dataset.created_at.astimezone(ASIA_SHANGHAI),
                    version.id,
                    version.created_at.astimezone(ASIA_SHANGHAI),
                ),
            }
            legacy_artifact_prefixes = {
                str(PurePosixPath(object_key).parent / "_normalized") + "/"
                for object_key in object_keys
            }
            references = await _list_eval_job_references(session, [version.id])
            if references:
                raise ValueError(_build_eval_reference_error("version", references))

            await session.delete(version)
            remaining_versions = [item for item in versions if item.id != version.id]
            await _sync_dataset_latest_version(session, dataset, remaining_versions)
            await session.commit()

        for object_key in object_keys:
            _delete_managed_object(object_key)
        for prefix in object_prefixes | legacy_artifact_prefixes:
            delete_object_prefix(DATASET_RAW_BUCKET, prefix)

    async def presign_upload(
        self,
        payload: PresignUploadRequest,
        browser_endpoint_url: str | None = None,
    ) -> PresignUploadResponse:
        async with SessionLocal() as session:
            project_id = await resolve_active_project_id(session)
            dataset = (
                await _get_dataset_or_raise(session, payload.dataset_id, project_id)
                if payload.dataset_id
                else None
            )

        dataset_id = dataset.id if dataset is not None else uuid4()
        dataset_created_at = dataset.created_at if dataset is not None else _now()
        version_id = uuid4()
        version_created_at = _now()
        object_key = _build_object_key(
            project_id=project_id,
            dataset_id=dataset_id,
            dataset_created_at=dataset_created_at,
            version_id=version_id,
            version_created_at=version_created_at,
            file_name=payload.file_name,
        )
        presigned = build_presigned_upload(
            bucket=payload.bucket,
            object_key=object_key,
            browser_endpoint_url=browser_endpoint_url,
        )
        return PresignUploadResponse(**presigned)
