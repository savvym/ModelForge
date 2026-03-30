from __future__ import annotations

import shutil
from dataclasses import dataclass
from datetime import UTC, datetime
from hashlib import md5
from pathlib import Path, PurePosixPath

from nta_backend.core.config import get_settings
from nta_backend.core.s3 import get_s3_client

LOCAL_OBJECT_STORE_ROOT = Path(__file__).resolve().parents[4] / ".data" / "object-store"
OBJECT_STORE_SEARCH_MAX_RESULTS = 500


@dataclass
class ObjectPayload:
    body: bytes
    content_type: str | None
    size_bytes: int
    etag: str | None = None


def _local_path(bucket: str, object_key: str) -> Path:
    return LOCAL_OBJECT_STORE_ROOT / bucket / object_key


def _local_fallback_enabled() -> bool:
    return get_settings().s3_local_fallback_enabled


def put_object_bytes(
    bucket: str, object_key: str, body: bytes, content_type: str | None = None
) -> ObjectPayload:
    etag = md5(body, usedforsecurity=False).hexdigest()
    should_write_local_fallback = False

    try:
        client = get_s3_client()
        client.put_object(
            Bucket=bucket,
            Key=object_key,
            Body=body,
            ContentType=content_type or "application/octet-stream",
        )
    except Exception:
        if not _local_fallback_enabled():
            raise
        should_write_local_fallback = True
    else:
        return ObjectPayload(
            body=body,
            content_type=content_type,
            size_bytes=len(body),
            etag=etag,
        )

    if should_write_local_fallback:
        local_path = _local_path(bucket, object_key)
        local_path.parent.mkdir(parents=True, exist_ok=True)
        local_path.write_bytes(body)

    return ObjectPayload(
        body=body,
        content_type=content_type,
        size_bytes=len(body),
        etag=etag,
    )


def create_object_prefix(bucket: str, prefix: str) -> None:
    normalized_prefix = normalize_object_prefix(prefix)
    if not normalized_prefix:
        raise ValueError("对象目录不能为空")

    try:
        client = get_s3_client()
        client.put_object(
            Bucket=bucket,
            Key=normalized_prefix,
            Body=b"",
            ContentType="application/x-directory",
        )
    except Exception:
        if not _local_fallback_enabled():
            raise
    else:
        return

    local_path = _local_path(bucket, normalized_prefix.rstrip("/"))
    local_path.mkdir(parents=True, exist_ok=True)


def get_object_bytes(bucket: str, object_key: str) -> ObjectPayload:
    try:
        client = get_s3_client()
        response = client.get_object(Bucket=bucket, Key=object_key)
        body = response["Body"].read()
        return ObjectPayload(
            body=body,
            content_type=response.get("ContentType"),
            size_bytes=len(body),
            etag=response.get("ETag"),
        )
    except Exception:
        if not _local_fallback_enabled():
            raise

    local_path = _local_path(bucket, object_key)
    if not local_path.exists():
        raise FileNotFoundError(object_key)

    body = local_path.read_bytes()
    return ObjectPayload(
        body=body,
        content_type=None,
        size_bytes=len(body),
        etag=md5(body, usedforsecurity=False).hexdigest(),
    )


def delete_object(bucket: str, object_key: str) -> None:
    try:
        client = get_s3_client()
        client.delete_object(Bucket=bucket, Key=object_key)
    except Exception:
        if not _local_fallback_enabled():
            raise

    local_path = _local_path(bucket, object_key)
    if local_path.exists():
        local_path.unlink()


def delete_object_prefix(bucket: str, prefix: str) -> None:
    normalized_prefix = normalize_object_prefix(prefix)

    try:
        client = get_s3_client()
        continuation_token: str | None = None
        while True:
            payload = {
                "Bucket": bucket,
                "Prefix": normalized_prefix,
                "MaxKeys": 500,
            }
            if continuation_token:
                payload["ContinuationToken"] = continuation_token

            response = client.list_objects_v2(**payload)
            objects = response.get("Contents", [])
            if objects:
                client.delete_objects(
                    Bucket=bucket,
                    Delete={
                        "Objects": [{"Key": item["Key"]} for item in objects if item.get("Key")],
                        "Quiet": True,
                    },
                )

            if not response.get("IsTruncated"):
                break
            continuation_token = response.get("NextContinuationToken")
    except Exception:
        if not _local_fallback_enabled():
            raise

    local_path = _local_path(bucket, normalized_prefix.rstrip("/"))
    if local_path.exists():
        if local_path.is_dir():
            shutil.rmtree(local_path)
        else:
            local_path.unlink()


def list_object_store_buckets() -> list[str]:
    settings = get_settings()
    configured = [
        settings.s3_bucket_dataset_raw,
        settings.s3_bucket_dataset_processed,
        settings.s3_bucket_eval_artifacts,
        settings.s3_bucket_batch_artifacts,
        settings.s3_bucket_exports,
        settings.s3_bucket_tmp,
    ]
    local = (
        [item.name for item in LOCAL_OBJECT_STORE_ROOT.iterdir() if item.is_dir()]
        if _local_fallback_enabled() and LOCAL_OBJECT_STORE_ROOT.exists()
        else []
    )

    ordered: list[str] = []
    seen: set[str] = set()
    for bucket in [*configured, *local]:
        if bucket and bucket not in seen:
            ordered.append(bucket)
            seen.add(bucket)
    return ordered


def normalize_object_prefix(prefix: str | None) -> str:
    if not prefix:
        return ""

    normalized = prefix.strip().lstrip("/")
    if not normalized:
        return ""

    return normalized if normalized.endswith("/") else f"{normalized}/"


def get_parent_prefix(prefix: str) -> str | None:
    normalized = normalize_object_prefix(prefix)
    if not normalized:
        return None

    parent = PurePosixPath(normalized.rstrip("/")).parent.as_posix()
    if parent in ("", "."):
        return None
    return f"{parent}/"


def list_object_store_entries(bucket: str, prefix: str | None = None) -> dict[str, object]:
    buckets = list_object_store_buckets()
    if bucket not in buckets:
        raise ValueError("对象存储桶不存在")

    normalized_prefix = normalize_object_prefix(prefix)

    try:
        client = get_s3_client()
        response = client.list_objects_v2(
            Bucket=bucket,
            Prefix=normalized_prefix,
            Delimiter="/",
            MaxKeys=500,
        )

        prefixes = [
            {
                "name": PurePosixPath(item["Prefix"].rstrip("/")).name,
                "prefix": item["Prefix"],
            }
            for item in response.get("CommonPrefixes", [])
            if item.get("Prefix")
        ]
        objects = [
            {
                "key": item["Key"],
                "name": PurePosixPath(item["Key"]).name,
                "size_bytes": item.get("Size", 0),
                "last_modified": item.get("LastModified"),
            }
            for item in response.get("Contents", [])
            if item.get("Key") and item["Key"] != normalized_prefix
        ]
    except Exception:
        if not _local_fallback_enabled():
            raise
        base_dir = LOCAL_OBJECT_STORE_ROOT / bucket
        target_dir = base_dir / normalized_prefix.rstrip("/") if normalized_prefix else base_dir
        prefixes = []
        objects = []
        if target_dir.exists():
            for item in sorted(
                target_dir.iterdir(),
                key=lambda entry: (not entry.is_dir(), entry.name.lower()),
            ):
                relative_path = item.relative_to(base_dir).as_posix()
                if item.is_dir():
                    prefixes.append(
                        {
                            "name": item.name,
                            "prefix": f"{relative_path}/",
                        }
                    )
                else:
                    stats = item.stat()
                    objects.append(
                        {
                            "key": relative_path,
                            "name": item.name,
                            "size_bytes": stats.st_size,
                            "last_modified": datetime.fromtimestamp(
                                stats.st_mtime, tz=UTC
                            ),
                        }
                    )

    return {
        "bucket": bucket,
        "prefix": normalized_prefix,
        "parent_prefix": get_parent_prefix(normalized_prefix),
        "search_query": None,
        "buckets": buckets,
        "prefixes": prefixes,
        "objects": objects,
    }


def search_object_store_entries(
    bucket: str,
    query: str,
    prefix: str | None = None,
) -> dict[str, object]:
    buckets = list_object_store_buckets()
    if bucket not in buckets:
        raise ValueError("对象存储桶不存在")

    normalized_prefix = normalize_object_prefix(prefix)
    normalized_query = query.strip().lower()
    if not normalized_query:
        return list_object_store_entries(bucket, normalized_prefix)

    objects: list[dict[str, object]] = []

    try:
        client = get_s3_client()
        continuation_token: str | None = None
        while True:
            payload: dict[str, object] = {
                "Bucket": bucket,
                "MaxKeys": OBJECT_STORE_SEARCH_MAX_RESULTS,
            }
            if continuation_token:
                payload["ContinuationToken"] = continuation_token

            response = client.list_objects_v2(**payload)
            for item in response.get("Contents", []):
                object_key = item.get("Key")
                if not object_key or object_key.endswith("/"):
                    continue
                if normalized_prefix and not object_key.startswith(normalized_prefix):
                    continue

                object_name = PurePosixPath(object_key).name
                if (
                    normalized_query not in object_key.lower()
                    and normalized_query not in object_name.lower()
                ):
                    continue

                objects.append(
                    {
                        "key": object_key,
                        "name": object_name,
                        "size_bytes": item.get("Size", 0),
                        "last_modified": item.get("LastModified"),
                    }
                )
                if len(objects) >= OBJECT_STORE_SEARCH_MAX_RESULTS:
                    break

            if len(objects) >= OBJECT_STORE_SEARCH_MAX_RESULTS or not response.get("IsTruncated"):
                break
            continuation_token = response.get("NextContinuationToken")
    except Exception:
        if not _local_fallback_enabled():
            raise

        base_dir = LOCAL_OBJECT_STORE_ROOT / bucket
        if base_dir.exists():
            for item in sorted(
                base_dir.rglob("*"),
                key=lambda entry: entry.as_posix().lower(),
            ):
                if not item.is_file():
                    continue
                relative_path = item.relative_to(base_dir).as_posix()
                if normalized_prefix and not relative_path.startswith(normalized_prefix):
                    continue
                object_name = item.name
                if (
                    normalized_query not in relative_path.lower()
                    and normalized_query not in object_name.lower()
                ):
                    continue

                stats = item.stat()
                objects.append(
                    {
                        "key": relative_path,
                        "name": object_name,
                        "size_bytes": stats.st_size,
                        "last_modified": datetime.fromtimestamp(stats.st_mtime, tz=UTC),
                    }
                )
                if len(objects) >= OBJECT_STORE_SEARCH_MAX_RESULTS:
                    break

    return {
        "bucket": bucket,
        "prefix": normalized_prefix,
        "parent_prefix": get_parent_prefix(normalized_prefix),
        "search_query": query.strip(),
        "buckets": buckets,
        "prefixes": [],
        "objects": objects,
    }
