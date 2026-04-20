from __future__ import annotations

import json
from datetime import UTC, datetime
from functools import lru_cache
from pathlib import PurePosixPath
from urllib.parse import urlparse

from tencentcloud.common import credential
from tencentcloud.common.profile.client_profile import ClientProfile
from tencentcloud.common.profile.http_profile import HttpProfile
from tencentcloud.sts.v20180813 import models, sts_client

from nta_backend.core.config import get_settings
from nta_backend.core.s3 import build_presigned_upload
from nta_backend.schemas.object_store import (
    ObjectStoreDirectUploadInitResponse,
    ObjectStoreDirectUploadStsCredentials,
)

COS_STS_ACTIONS = [
    "name/cos:PutObject",
    "name/cos:PostObject",
    "name/cos:InitiateMultipartUpload",
    "name/cos:ListMultipartUploads",
    "name/cos:ListParts",
    "name/cos:UploadPart",
    "name/cos:CompleteMultipartUpload",
    "name/cos:AbortMultipartUpload",
]
DIRECT_UPLOAD_STS_NAME = "ntaupload"
GENERIC_COS_HOST_PREFIXES = (
    "cos.",
    "cos-internal.",
    "cos.accelerate.",
    "cos-website.",
)


def build_direct_upload_response(
    *,
    bucket: str,
    object_key: str,
    file_name: str,
    file_size: int,
    content_type: str | None,
    browser_endpoint_url: str | None = None,
) -> ObjectStoreDirectUploadInitResponse:
    settings = get_settings()
    if settings.s3_resolved_direct_upload_mode == "cos-sts":
        return _build_cos_sts_direct_upload_response(
            bucket=bucket,
            object_key=object_key,
            file_name=file_name,
            file_size=file_size,
            content_type=content_type,
            browser_endpoint_url=browser_endpoint_url,
        )
    return _build_presigned_direct_upload_response(
        bucket=bucket,
        object_key=object_key,
        file_name=file_name,
        file_size=file_size,
        content_type=content_type,
        browser_endpoint_url=browser_endpoint_url,
    )


def _build_presigned_direct_upload_response(
    *,
    bucket: str,
    object_key: str,
    file_name: str,
    file_size: int,
    content_type: str | None,
    browser_endpoint_url: str | None = None,
) -> ObjectStoreDirectUploadInitResponse:
    settings = get_settings()
    presigned = build_presigned_upload(
        bucket=bucket,
        object_key=object_key,
        expires_in=settings.s3_sts_duration_seconds,
        content_type=content_type,
        browser_endpoint_url=browser_endpoint_url,
    )
    return ObjectStoreDirectUploadInitResponse(
        bucket=bucket,
        object_key=object_key,
        uri=f"s3://{bucket}/{object_key}",
        file_name=file_name,
        size_bytes=file_size,
        content_type=content_type,
        expires_in=settings.s3_sts_duration_seconds,
        provider="presigned",
        method=str(presigned["method"]),
        headers=dict(presigned["headers"]),
        url=str(presigned["url"]),
    )


def _build_cos_sts_direct_upload_response(
    *,
    bucket: str,
    object_key: str,
    file_name: str,
    file_size: int,
    content_type: str | None,
    browser_endpoint_url: str | None = None,
) -> ObjectStoreDirectUploadInitResponse:
    settings = get_settings()
    credentials_payload = _request_cos_sts_credentials(bucket=bucket, object_key=object_key)
    domain, protocol = _resolve_cos_request_domain(
        browser_endpoint_url or settings.s3_browser_endpoint_url,
        bucket=bucket,
    )
    return ObjectStoreDirectUploadInitResponse(
        bucket=bucket,
        object_key=object_key,
        uri=f"s3://{bucket}/{object_key}",
        file_name=file_name,
        size_bytes=file_size,
        content_type=content_type,
        expires_in=settings.s3_sts_duration_seconds,
        provider="cos-sts",
        region=settings.s3_region,
        domain=domain,
        protocol=protocol,
        sts=credentials_payload,
    )


def _request_cos_sts_credentials(
    *,
    bucket: str,
    object_key: str,
) -> ObjectStoreDirectUploadStsCredentials:
    settings = get_settings()
    request = models.GetFederationTokenRequest()
    request.from_json_string(
        json.dumps(
            {
                "Name": DIRECT_UPLOAD_STS_NAME,
                "Policy": _build_cos_sts_policy(bucket=bucket, object_key=object_key),
                "DurationSeconds": settings.s3_sts_duration_seconds,
            }
        )
    )
    response = _get_sts_client().GetFederationToken(request)
    if response.Credentials is None:
        raise ValueError("STS 未返回临时密钥")

    now = int(datetime.now(tz=UTC).timestamp())
    return ObjectStoreDirectUploadStsCredentials(
        tmp_secret_id=response.Credentials.TmpSecretId,
        tmp_secret_key=response.Credentials.TmpSecretKey,
        session_token=response.Credentials.Token,
        start_time=now,
        expired_time=int(response.ExpiredTime),
        scope_limit=True,
    )


@lru_cache(maxsize=1)
def _get_sts_client() -> sts_client.StsClient:
    settings = get_settings()
    cred = credential.Credential(
        settings.s3_access_key_id,
        settings.s3_secret_access_key.get_secret_value(),
    )
    http_profile = HttpProfile()
    http_profile.endpoint = "sts.tencentcloudapi.com"
    client_profile = ClientProfile()
    client_profile.httpProfile = http_profile
    return sts_client.StsClient(cred, settings.s3_region, client_profile)


def _build_cos_sts_policy(*, bucket: str, object_key: str) -> str:
    settings = get_settings()
    app_id = _extract_bucket_app_id(bucket)
    normalized_key = object_key.strip().lstrip("/")
    resource = f"qcs::cos:{settings.s3_region}:uid/{app_id}:{bucket}/{normalized_key}"
    return json.dumps(
        {
            "version": "2.0",
            "statement": [
                {
                    "effect": "allow",
                    "action": COS_STS_ACTIONS,
                    "resource": [resource],
                }
            ],
        }
    )


def _extract_bucket_app_id(bucket: str) -> str:
    bucket_name = PurePosixPath(bucket).name
    app_id = bucket_name.rsplit("-", 1)[-1]
    if not app_id.isdigit():
        raise ValueError("COS bucket 名称必须包含 APPID 后缀，例如 bucket-1250000000")
    return app_id


def _resolve_cos_request_domain(
    endpoint_url: str | None,
    *,
    bucket: str,
) -> tuple[str | None, str | None]:
    if not endpoint_url:
        return None, None

    parsed = urlparse(endpoint_url if "://" in endpoint_url else f"https://{endpoint_url}")
    host = parsed.netloc or parsed.path
    if not host:
        return None, None

    protocol = f"{parsed.scheme}:" if parsed.scheme else None
    lowered_host = host.lower()
    if "{bucket}" in lowered_host:
        return host, protocol
    if lowered_host.startswith(f"{bucket.lower()}."):
        return host, protocol
    if lowered_host.startswith(GENERIC_COS_HOST_PREFIXES):
        return f"{{Bucket}}.{host}", protocol
    return host, protocol
