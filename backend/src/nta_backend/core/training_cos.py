from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any
from urllib.parse import urlparse, urlunparse

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
    host_overrides = parse_training_cos_hosts(config)

    client = boto3.client(
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
    if host_overrides:
        client.meta.events.register(
            "before-send.s3",
            lambda request, **_: apply_training_cos_host_overrides(request, host_overrides),
            unique_id="training-cos-host-overrides",
        )
    return client


def parse_training_cos_hosts(config: Mapping[str, object]) -> dict[str, str]:
    raw_hosts = config.get("hosts")
    if isinstance(raw_hosts, Mapping):
        return {
            normalized_host: _normalize_host_override_target(str(target_value))
            for host_value, target_value in raw_hosts.items()
            if (normalized_host := _normalize_hostname(str(host_value)))
            and _normalize_host_override_target(str(target_value))
        }
    if not isinstance(raw_hosts, str):
        return {}

    host_overrides: dict[str, str] = {}
    for raw_line in raw_hosts.splitlines():
        line = raw_line.split("#", 1)[0].strip()
        if not line:
            continue
        if "=" in line and len(line.split()) == 1:
            host_value, target_value = line.split("=", 1)
            host = _normalize_hostname(host_value)
            target = _normalize_host_override_target(target_value)
            if host and target:
                host_overrides[host] = target
            continue

        parts = line.split()
        if len(parts) < 2:
            continue
        target = _normalize_host_override_target(parts[0])
        if not target:
            continue
        for host_value in parts[1:]:
            host = _normalize_hostname(host_value)
            if host:
                host_overrides[host] = target
    return host_overrides


def apply_training_cos_host_overrides(request: Any, host_overrides: Mapping[str, str]) -> None:
    parsed = urlparse(str(request.url))
    request_host = parsed.hostname
    if not request_host:
        return

    target_host = _resolve_training_cos_host_override(request_host, host_overrides)
    if not target_host:
        return

    original_netloc = parsed.netloc
    next_netloc = _build_host_override_netloc(target_host, parsed.port)
    request.url = urlunparse(parsed._replace(netloc=next_netloc))
    request.headers["Host"] = original_netloc


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


def _normalize_hostname(value: str) -> str | None:
    text = value.strip().rstrip("/")
    if not text:
        return None
    parsed = urlparse(text if "://" in text else f"//{text}")
    host = parsed.hostname or text
    return host.strip().rstrip(".").lower() or None


def _normalize_host_override_target(value: str) -> str | None:
    text = value.strip().rstrip("/")
    if not text:
        return None
    if "://" in text:
        parsed = urlparse(text)
        return parsed.netloc or None
    return text


def _resolve_training_cos_host_override(host: str, host_overrides: Mapping[str, str]) -> str | None:
    normalized_host = _normalize_hostname(host)
    if not normalized_host:
        return None

    return host_overrides.get(normalized_host)


def _build_host_override_netloc(target_host: str, fallback_port: int | None) -> str:
    parsed = urlparse(f"//{target_host}")
    host = parsed.hostname or target_host
    try:
        port = parsed.port or fallback_port
    except ValueError:
        port = fallback_port
    if ":" in host and not host.startswith("["):
        host = f"[{host}]"
    return f"{host}:{port}" if port else host


def _infer_region_from_endpoint(endpoint_url: str) -> str | None:
    parsed = urlparse(endpoint_url if "://" in endpoint_url else f"https://{endpoint_url}")
    host = parsed.netloc or parsed.path
    for segment in host.split("."):
        if segment.startswith("ap-") or segment.startswith("na-") or segment.startswith("eu-"):
            return segment
    return None
