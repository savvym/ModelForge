from __future__ import annotations

from datetime import UTC, datetime
from mimetypes import guess_type
from pathlib import PurePosixPath
from uuid import UUID

from fastapi import UploadFile

from nta_backend.core.config import get_settings
from nta_backend.core.object_store import (
    create_object_prefix,
    delete_object,
    delete_object_prefix,
    get_object_bytes,
    list_object_store_buckets,
    normalize_object_prefix,
    put_object_bytes,
)
from nta_backend.core.s3 import build_presigned_upload
from nta_backend.core.storage_layout import (
    build_project_files_prefix,
    build_project_prefix,
    build_scoped_object_key,
    is_project_scoped_key,
    is_project_scoped_prefix,
)
from nta_backend.schemas.object_store import (
    ObjectStoreDirectUploadInitRequest,
    ObjectStoreDirectUploadInitResponse,
    ObjectStoreFolderResponse,
    ObjectStoreObjectPreviewResponse,
    ObjectStoreObjectTextUpdateRequest,
    ObjectStoreUploadResponse,
)

DIRECT_UPLOAD_EXPIRES_IN_SECONDS = 900
PREVIEW_LIMIT_BYTES = 100 * 1024
TEXT_PREVIEW_EXTENSIONS = {
    "css",
    "csv",
    "html",
    "htm",
    "js",
    "json",
    "jsonl",
    "jsx",
    "log",
    "md",
    "py",
    "sh",
    "sql",
    "ts",
    "tsx",
    "txt",
    "xml",
    "yaml",
    "yml",
}
TEXT_PREVIEW_CONTENT_TYPES = {
    "application/javascript",
    "application/json",
    "application/sql",
    "application/x-ndjson",
    "application/xml",
    "application/x-yaml",
    "text/csv",
}


def _ensure_bucket_exists(bucket: str) -> None:
    if bucket not in list_object_store_buckets():
        raise ValueError("对象存储桶不存在")


def _normalize_folder_name(name: str) -> str:
    normalized = name.strip().strip("/")
    if not normalized:
        raise ValueError("文件夹名称不能为空")
    if normalized in {".", ".."} or "/" in normalized:
        raise ValueError("文件夹名称不合法")
    return normalized


def _resolve_scoped_prefix(
    *,
    project_id: UUID,
    prefix: str | None = None,
    default_domain: str = "files",
) -> str:
    normalized_prefix = normalize_object_prefix(prefix)
    if not normalized_prefix:
        if default_domain == "files":
            return build_project_files_prefix(project_id)
        return f"{build_project_prefix(project_id)}{default_domain.strip('/')}/"

    if not is_project_scoped_prefix(project_id, normalized_prefix):
        raise ValueError("对象目录超出当前项目范围")
    return normalized_prefix


def _assert_project_object_key(project_id: UUID, object_key: str) -> str:
    normalized_key = object_key.strip().replace("\\", "/").lstrip("/")
    if not normalized_key:
        raise ValueError("对象路径不能为空")
    if not is_project_scoped_key(project_id, normalized_key):
        raise ValueError("对象路径超出当前项目范围")
    return normalized_key


def _assert_project_prefix(project_id: UUID, prefix: str) -> str:
    normalized_prefix = normalize_object_prefix(prefix)
    if not normalized_prefix:
        raise ValueError("目录路径不能为空")
    if not is_project_scoped_prefix(project_id, normalized_prefix):
        raise ValueError("对象目录超出当前项目范围")
    return normalized_prefix


def _guess_object_content_type(
    object_key: str,
    stored_content_type: str | None = None,
) -> str | None:
    lower_name = PurePosixPath(object_key).name.lower()
    if lower_name.endswith(".jsonl"):
        return "application/x-ndjson"
    if lower_name.endswith(".md"):
        return "text/markdown"

    if stored_content_type and stored_content_type != "application/octet-stream":
        return stored_content_type

    guessed, _ = guess_type(PurePosixPath(object_key).name)
    return guessed or stored_content_type


def _resolve_preview_kind(object_key: str, content_type: str | None) -> str:
    lower_name = PurePosixPath(object_key).name.lower()
    extension = lower_name.rsplit(".", 1)[-1] if "." in lower_name else ""
    normalized_content_type = (content_type or "").lower()

    if normalized_content_type == "application/pdf" or extension == "pdf":
        return "pdf"
    if normalized_content_type.startswith("image/"):
        return "image"
    if (
        normalized_content_type.startswith("text/")
        or normalized_content_type in TEXT_PREVIEW_CONTENT_TYPES
        or extension in TEXT_PREVIEW_EXTENSIONS
    ):
        return "text"
    return "unsupported"


class ObjectStoreService:
    def initiate_direct_upload(
        self,
        *,
        project_id: UUID,
        payload: ObjectStoreDirectUploadInitRequest,
        browser_endpoint_url: str | None = None,
    ) -> ObjectStoreDirectUploadInitResponse:
        target_bucket = payload.bucket or get_settings().s3_bucket_dataset_raw
        _ensure_bucket_exists(target_bucket)
        if payload.file_size <= 0:
            raise ValueError("请选择待上传的文件")

        scoped_prefix = _resolve_scoped_prefix(
            project_id=project_id,
            prefix=payload.prefix,
            default_domain="files",
        )
        object_key = build_scoped_object_key(
            scoped_prefix,
            payload.file_name,
            payload.relative_path,
        )
        presigned = build_presigned_upload(
            target_bucket,
            object_key,
            expires_in=DIRECT_UPLOAD_EXPIRES_IN_SECONDS,
            content_type=payload.content_type,
            browser_endpoint_url=browser_endpoint_url,
        )
        return ObjectStoreDirectUploadInitResponse(
            bucket=target_bucket,
            object_key=object_key,
            uri=f"s3://{target_bucket}/{object_key}",
            file_name=PurePosixPath(object_key).name,
            size_bytes=payload.file_size,
            content_type=payload.content_type,
            expires_in=DIRECT_UPLOAD_EXPIRES_IN_SECONDS,
            method=str(presigned["method"]),
            headers=dict(presigned["headers"]),
            url=str(presigned["url"]),
        )

    async def upload_project_file(
        self,
        *,
        project_id: UUID,
        upload_file: UploadFile,
        bucket: str | None = None,
        prefix: str | None = None,
        relative_path: str | None = None,
    ) -> ObjectStoreUploadResponse:
        target_bucket = bucket or get_settings().s3_bucket_dataset_raw
        _ensure_bucket_exists(target_bucket)

        body = await upload_file.read()
        if not body:
            raise ValueError("请选择待上传的文件")

        scoped_prefix = _resolve_scoped_prefix(
            project_id=project_id,
            prefix=prefix,
            default_domain="files",
        )
        object_key = build_scoped_object_key(
            scoped_prefix,
            upload_file.filename or "upload.bin",
            relative_path,
        )
        payload = put_object_bytes(
            target_bucket,
            object_key,
            body,
            content_type=upload_file.content_type or "application/octet-stream",
        )
        now = datetime.now(tz=UTC)
        return ObjectStoreUploadResponse(
            bucket=target_bucket,
            object_key=object_key,
            uri=f"s3://{target_bucket}/{object_key}",
            file_name=PurePosixPath(object_key).name,
            size_bytes=payload.size_bytes,
            content_type=payload.content_type,
            last_modified=now,
        )

    def create_folder(
        self,
        *,
        project_id: UUID,
        bucket: str | None = None,
        prefix: str | None = None,
        name: str,
    ) -> ObjectStoreFolderResponse:
        target_bucket = bucket or get_settings().s3_bucket_dataset_raw
        _ensure_bucket_exists(target_bucket)

        scoped_prefix = _resolve_scoped_prefix(
            project_id=project_id,
            prefix=prefix,
            default_domain="files",
        )
        folder_prefix = f"{scoped_prefix}{_normalize_folder_name(name)}/"
        create_object_prefix(target_bucket, folder_prefix)
        return ObjectStoreFolderResponse(
            bucket=target_bucket,
            prefix=folder_prefix,
            name=_normalize_folder_name(name),
            uri=f"s3://{target_bucket}/{folder_prefix}",
        )

    def delete_object(self, *, project_id: UUID, bucket: str, object_key: str) -> None:
        _ensure_bucket_exists(bucket)
        normalized_key = _assert_project_object_key(project_id, object_key)
        delete_object(bucket, normalized_key)

    def delete_prefix(self, *, project_id: UUID, bucket: str, prefix: str) -> None:
        _ensure_bucket_exists(bucket)
        normalized_prefix = _assert_project_prefix(project_id, prefix)
        if normalized_prefix == build_project_prefix(project_id):
            raise ValueError("根目录不允许删除")
        delete_object_prefix(bucket, normalized_prefix)

    def download_object(
        self,
        *,
        project_id: UUID,
        bucket: str,
        object_key: str,
    ) -> tuple[str, bytes, str | None]:
        _ensure_bucket_exists(bucket)
        normalized_key = _assert_project_object_key(project_id, object_key)

        payload = get_object_bytes(bucket, normalized_key)
        content_type = _guess_object_content_type(normalized_key, payload.content_type)
        return (
            PurePosixPath(normalized_key).name or "download.bin",
            payload.body,
            content_type,
        )

    def preview_object(
        self,
        *,
        project_id: UUID,
        bucket: str,
        object_key: str,
    ) -> ObjectStoreObjectPreviewResponse:
        _ensure_bucket_exists(bucket)
        normalized_key = _assert_project_object_key(project_id, object_key)

        file_name = PurePosixPath(normalized_key).name or "preview.bin"
        content_type = _guess_object_content_type(normalized_key)
        preview_kind = _resolve_preview_kind(normalized_key, content_type)

        if preview_kind != "text":
            return ObjectStoreObjectPreviewResponse(
                bucket=bucket,
                object_key=normalized_key,
                file_name=file_name,
                preview_kind=preview_kind,
                content_type=content_type,
            )

        payload = get_object_bytes(bucket, normalized_key)
        resolved_content_type = _guess_object_content_type(normalized_key, payload.content_type)
        preview_bytes = payload.body[:PREVIEW_LIMIT_BYTES]
        return ObjectStoreObjectPreviewResponse(
            bucket=bucket,
            object_key=normalized_key,
            file_name=file_name,
            preview_kind="text",
            content_type=resolved_content_type,
            content=preview_bytes.decode("utf-8", errors="replace"),
            truncated=payload.size_bytes > PREVIEW_LIMIT_BYTES,
            content_bytes=payload.size_bytes,
        )

    def update_text_object(
        self,
        *,
        project_id: UUID,
        payload: ObjectStoreObjectTextUpdateRequest,
    ) -> ObjectStoreUploadResponse:
        _ensure_bucket_exists(payload.bucket)
        normalized_key = _assert_project_object_key(project_id, payload.object_key)

        content_type = _guess_object_content_type(normalized_key, payload.content_type)
        preview_kind = _resolve_preview_kind(normalized_key, content_type)
        if preview_kind != "text":
            raise ValueError("当前对象不支持文本编辑")

        body = payload.content.encode("utf-8")
        stored_payload = put_object_bytes(
            payload.bucket,
            normalized_key,
            body,
            content_type=content_type or "text/plain; charset=utf-8",
        )
        now = datetime.now(tz=UTC)
        return ObjectStoreUploadResponse(
            bucket=payload.bucket,
            object_key=normalized_key,
            uri=f"s3://{payload.bucket}/{normalized_key}",
            file_name=PurePosixPath(normalized_key).name or "document.txt",
            size_bytes=stored_payload.size_bytes,
            content_type=content_type,
            last_modified=now,
        )
