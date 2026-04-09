from __future__ import annotations

from dataclasses import dataclass
from hashlib import md5
from pathlib import PurePosixPath

from nta_backend.core.config import get_settings
from nta_backend.core.s3 import get_s3_client

OBJECT_STORE_SEARCH_MAX_RESULTS = 500


@dataclass
class ObjectPayload:
    body: bytes
    content_type: str | None
    size_bytes: int
    etag: str | None = None


def put_object_bytes(
    bucket: str, object_key: str, body: bytes, content_type: str | None = None
) -> ObjectPayload:
    etag = md5(body, usedforsecurity=False).hexdigest()
    client = get_s3_client()
    client.put_object(
        Bucket=bucket,
        Key=object_key,
        Body=body,
        ContentType=content_type or "application/octet-stream",
    )

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

    client = get_s3_client()
    client.put_object(
        Bucket=bucket,
        Key=normalized_prefix,
        Body=b"",
        ContentType="application/x-directory",
    )


def get_object_bytes(bucket: str, object_key: str) -> ObjectPayload:
    client = get_s3_client()
    response = client.get_object(Bucket=bucket, Key=object_key)
    body = response["Body"].read()
    return ObjectPayload(
        body=body,
        content_type=response.get("ContentType"),
        size_bytes=len(body),
        etag=response.get("ETag"),
    )


def delete_object(bucket: str, object_key: str) -> None:
    client = get_s3_client()
    client.delete_object(Bucket=bucket, Key=object_key)


def delete_object_prefix(bucket: str, prefix: str) -> None:
    normalized_prefix = normalize_object_prefix(prefix)

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

    ordered: list[str] = []
    seen: set[str] = set()
    for bucket in configured:
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

    return {
        "bucket": bucket,
        "prefix": normalized_prefix,
        "parent_prefix": get_parent_prefix(normalized_prefix),
        "search_query": query.strip(),
        "buckets": buckets,
        "prefixes": [],
        "objects": objects,
    }
