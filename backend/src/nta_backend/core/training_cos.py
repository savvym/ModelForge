from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from urllib.parse import urlparse

import boto3
from botocore.client import Config


@dataclass(frozen=True)
class TrainingCosObjectResult:
    object_key: str
    etag: str | None


def build_training_cos_endpoint_url(config: Mapping[str, object]) -> str:
    endpoint = _read_text(config, "endpoint")
    if not endpoint:
        raise ValueError("训练环境 COS endpoint 未配置")
    if "://" in endpoint:
        return endpoint.rstrip("/")

    protocol = _read_text(config, "protocol") or "https"
    return f"{protocol}://{endpoint}".rstrip("/")


def build_training_cos_uri(config: Mapping[str, object], object_key: str) -> str:
    bucket = _read_required_text(config, "bucket", "训练环境 COS bucket 未配置")
    return f"cos://{bucket}/{object_key.lstrip('/')}"


def put_training_cos_object(
    config: Mapping[str, object],
    *,
    object_key: str,
    body: bytes,
    content_type: str | None = None,
) -> TrainingCosObjectResult:
    client = build_training_cos_client(config)
    bucket = _read_required_text(config, "bucket", "训练环境 COS bucket 未配置")
    response = client.put_object(
        Bucket=bucket,
        Key=object_key.lstrip("/"),
        Body=body,
        ContentType=content_type or "application/octet-stream",
    )
    return TrainingCosObjectResult(object_key=object_key.lstrip("/"), etag=response.get("ETag"))


def probe_training_cos(config: Mapping[str, object]) -> dict[str, object]:
    client = build_training_cos_client(config)
    bucket = _read_required_text(config, "bucket", "训练环境 COS bucket 未配置")
    prefix = (_read_text(config, "target_prefix") or "").strip().strip("/")
    response = client.list_objects_v2(Bucket=bucket, Prefix=prefix, MaxKeys=1)
    return {
        "bucket": bucket,
        "prefix": prefix,
        "object_count": response.get("KeyCount", 0),
    }


def build_training_cos_client(config: Mapping[str, object]):
    endpoint_url = build_training_cos_endpoint_url(config)
    region = _read_text(config, "region") or _infer_region_from_endpoint(endpoint_url)
    secret_id = _read_required_text(config, "secret_id", "训练环境 COS SecretId 未配置")
    secret_key = _read_required_text(config, "secret_key", "训练环境 COS SecretKey 未配置")
    session_token = _read_text(config, "session_token")
    addressing_style = _read_text(config, "addressing_style") or "virtual"

    return boto3.client(
        "s3",
        endpoint_url=endpoint_url,
        region_name=region or "ap-guangzhou",
        aws_access_key_id=secret_id,
        aws_secret_access_key=secret_key,
        aws_session_token=session_token,
        config=Config(
            signature_version="s3v4",
            s3={"addressing_style": addressing_style},
            connect_timeout=5,
            read_timeout=60,
            retries={"max_attempts": 1},
        ),
    )


def _read_required_text(config: Mapping[str, object], key: str, message: str) -> str:
    value = _read_text(config, key)
    if not value:
        raise ValueError(message)
    return value


def _read_text(config: Mapping[str, object], key: str) -> str | None:
    value = config.get(key)
    if isinstance(value, str):
        normalized = value.strip()
        return normalized or None
    return None


def _infer_region_from_endpoint(endpoint_url: str) -> str | None:
    parsed = urlparse(endpoint_url if "://" in endpoint_url else f"https://{endpoint_url}")
    host = parsed.netloc or parsed.path
    for segment in host.split("."):
        if segment.startswith("ap-") or segment.startswith("na-") or segment.startswith("eu-"):
            return segment
    return None
