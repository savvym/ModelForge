from __future__ import annotations

import asyncio
import logging
import mimetypes
from typing import Any

from botocore.exceptions import BotoCoreError, ClientError

from nta_backend.core.db import SessionLocal
from nta_backend.core.gitea_client import encode_base64
from nta_backend.core.training_cos import (
    TrainingCosObjectBody,
    get_training_cos_object,
    list_training_cos_objects,
)
from nta_backend.schemas.training_cos import (
    TrainingCosEntry,
    TrainingCosListResponse,
    TrainingCosPreviewResponse,
    TrainingCosStatus,
)
from nta_backend.services.system_config_service import (
    DEFAULT_TRAINING_COS_TARGET_PREFIX,
    load_training_cos_config,
)

logger = logging.getLogger(__name__)

INLINE_PREVIEW_MAX_BYTES = 1 * 1024 * 1024  # 1 MiB
TEXT_PREVIEW_TAIL = "…"
TEXT_MIME_PREFIXES = ("text/",)
TEXT_MIME_EXACT = {
    "application/json",
    "application/x-ndjson",
    "application/jsonl",
    "application/xml",
    "application/yaml",
    "application/x-yaml",
    "application/javascript",
    "application/x-sh",
    "application/x-python",
}


class TrainingCosUnavailable(RuntimeError):
    """Raised when the training COS settings are missing or marked disabled."""

    def __init__(self, message: str, *, configured: bool) -> None:
        super().__init__(message)
        self.configured = configured


class TrainingCosUpstreamError(RuntimeError):
    """Raised when boto3 returns an error talking to COS."""

    def __init__(self, message: str, *, status_code: int | None = None) -> None:
        super().__init__(message)
        self.status_code = status_code


async def _load_config() -> dict[str, Any]:
    async with SessionLocal() as session:
        return await load_training_cos_config(session)


def _is_text_like(mime: str | None) -> bool:
    if not mime:
        return False
    if mime in TEXT_MIME_EXACT:
        return True
    return any(mime.startswith(prefix) for prefix in TEXT_MIME_PREFIXES)


def _guess_mime(name: str) -> str | None:
    mime, _ = mimetypes.guess_type(name)
    return mime


def _normalize_input_prefix(prefix: str | None) -> str:
    cleaned = (prefix or "").strip().lstrip("/")
    if not cleaned:
        return ""
    return cleaned if cleaned.endswith("/") else f"{cleaned}/"


def _parent_prefix(prefix: str) -> str | None:
    cleaned = prefix.rstrip("/")
    if not cleaned:
        return None
    parts = cleaned.split("/")
    if len(parts) == 1:
        return ""
    return "/".join(parts[:-1]) + "/"


def _status_from_config(config: dict[str, Any]) -> TrainingCosStatus:
    bucket = (config.get("bucket") or "").strip() or None
    endpoint = (config.get("endpoint") or "").strip() or None
    target_prefix = (config.get("target_prefix") or DEFAULT_TRAINING_COS_TARGET_PREFIX).strip() or None
    secret_id_present = bool(config.get("secret_id"))
    secret_key_present = bool(config.get("secret_key"))
    configured = bool(bucket and endpoint and secret_id_present and secret_key_present)
    return TrainingCosStatus(
        enabled=bool(config.get("enabled")),
        configured=configured,
        bucket=bucket,
        bucket_alias=(config.get("bucket_alias") or "").strip() or None,
        region=(config.get("region") or "").strip() or None,
        endpoint=endpoint,
        target_prefix=target_prefix,
        addressing_style=(config.get("addressing_style") or "virtual").strip() or "virtual",
    )


def _ensure_usable(status: TrainingCosStatus) -> None:
    if not status.enabled:
        raise TrainingCosUnavailable(
            "训练环境 COS 未启用，请在系统配置中启用。",
            configured=status.configured,
        )
    if not status.configured:
        raise TrainingCosUnavailable(
            "训练环境 COS 配置不完整，请在系统配置中补全 endpoint / bucket / 凭据。",
            configured=False,
        )


def _wrap_boto_error(exc: Exception) -> TrainingCosUpstreamError:
    if isinstance(exc, ClientError):
        meta = exc.response.get("ResponseMetadata") or {}
        status_code = meta.get("HTTPStatusCode")
        error_info = exc.response.get("Error") or {}
        message = error_info.get("Message") or str(exc)
        return TrainingCosUpstreamError(message, status_code=int(status_code) if status_code else None)
    if isinstance(exc, BotoCoreError):
        return TrainingCosUpstreamError(str(exc))
    return TrainingCosUpstreamError(str(exc))


class TrainingCosBrowserService:
    async def get_status(self) -> TrainingCosStatus:
        return _status_from_config(await _load_config())

    async def list_entries(
        self,
        *,
        prefix: str | None = None,
        continuation_token: str | None = None,
        page_size: int = 200,
    ) -> TrainingCosListResponse:
        config = await _load_config()
        status = _status_from_config(config)
        _ensure_usable(status)
        normalized = _normalize_input_prefix(prefix)
        try:
            result = await asyncio.to_thread(
                list_training_cos_objects,
                config,
                prefix=normalized,
                delimiter="/",
                max_keys=max(1, min(int(page_size), 1000)),
                continuation_token=continuation_token,
            )
        except (ClientError, BotoCoreError) as exc:
            logger.warning("Training COS list failed at prefix=%s: %s", normalized, exc)
            raise _wrap_boto_error(exc) from exc

        entries: list[TrainingCosEntry] = []
        for folder in result.folders:
            name = folder[len(result.prefix):].rstrip("/") if folder.startswith(result.prefix) else folder.rstrip("/")
            entries.append(
                TrainingCosEntry(
                    type="dir",
                    name=name,
                    key=folder,
                )
            )
        for entry in result.files:
            entries.append(
                TrainingCosEntry(
                    type="file",
                    name=entry.name.rstrip("/") or entry.key.split("/")[-1],
                    key=entry.key,
                    size=entry.size,
                    last_modified=entry.last_modified,
                    etag=entry.etag,
                )
            )

        return TrainingCosListResponse(
            prefix=result.prefix,
            parent_prefix=_parent_prefix(result.prefix),
            entries=entries,
            next_token=result.next_token,
            truncated=result.truncated,
        )

    async def preview_object(
        self,
        *,
        key: str,
        download_url: str,
    ) -> TrainingCosPreviewResponse:
        config = await _load_config()
        status = _status_from_config(config)
        _ensure_usable(status)
        try:
            body = await asyncio.to_thread(get_training_cos_object, config, object_key=key)
        except (ClientError, BotoCoreError) as exc:
            logger.warning("Training COS get failed for key=%s: %s", key, exc)
            raise _wrap_boto_error(exc) from exc
        return _preview_from_body(body, download_url=download_url)

    async def download_object(self, *, key: str) -> TrainingCosObjectBody:
        config = await _load_config()
        status = _status_from_config(config)
        _ensure_usable(status)
        try:
            return await asyncio.to_thread(get_training_cos_object, config, object_key=key)
        except (ClientError, BotoCoreError) as exc:
            logger.warning("Training COS get failed for key=%s: %s", key, exc)
            raise _wrap_boto_error(exc) from exc


def _preview_from_body(
    body: TrainingCosObjectBody,
    *,
    download_url: str,
) -> TrainingCosPreviewResponse:
    name = body.object_key.split("/")[-1]
    mime = body.content_type if body.content_type and body.content_type != "application/octet-stream" else _guess_mime(name)
    is_text = _is_text_like(mime)
    truncated = body.size > INLINE_PREVIEW_MAX_BYTES
    payload = body.body[:INLINE_PREVIEW_MAX_BYTES] if truncated else body.body

    encoding: str | None = None
    content: str | None = None
    is_binary = False

    if is_text:
        try:
            content = payload.decode("utf-8")
            if truncated:
                content = content + "\n" + TEXT_PREVIEW_TAIL
            encoding = "utf8"
        except UnicodeDecodeError:
            is_binary = True
    else:
        # Inline tiny binaries (images small enough) base64; otherwise leave content=None.
        if not truncated and len(payload) <= INLINE_PREVIEW_MAX_BYTES and (mime or "").startswith("image/"):
            encoding = "base64"
            content = encode_base64(payload)
        else:
            is_binary = True

    return TrainingCosPreviewResponse(
        key=body.object_key,
        name=name,
        size=body.size,
        mime_type=mime,
        is_binary=is_binary and not content,
        encoding=encoding,
        content=content,
        download_url=download_url,
        last_modified=body.last_modified,
        etag=body.etag,
        truncated=truncated,
    )
