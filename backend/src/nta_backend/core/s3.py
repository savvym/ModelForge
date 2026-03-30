import boto3
from botocore.client import Config

from nta_backend.core.config import get_settings

_s3_clients: dict[str, object] = {}


def _get_cached_s3_client(endpoint_url: str):
    client = _s3_clients.get(endpoint_url)
    if client is None:
        settings = get_settings()
        client = boto3.client(
            "s3",
            endpoint_url=endpoint_url,
            region_name=settings.s3_region,
            aws_access_key_id=settings.s3_access_key_id,
            aws_secret_access_key=settings.s3_secret_access_key.get_secret_value(),
            config=Config(
                signature_version="s3v4",
                s3={"addressing_style": "path"},
                connect_timeout=1,
                read_timeout=2,
                retries={"max_attempts": 0},
            ),
        )
        _s3_clients[endpoint_url] = client
    return client


def get_s3_client():
    return _get_cached_s3_client(get_settings().s3_endpoint_url)


def get_s3_browser_client(browser_endpoint_url: str | None = None):
    settings = get_settings()
    return _get_cached_s3_client(
        browser_endpoint_url or settings.s3_browser_endpoint_url or settings.s3_endpoint_url
    )


def build_presigned_upload(
    bucket: str,
    object_key: str,
    expires_in: int = 900,
    content_type: str | None = None,
    browser_endpoint_url: str | None = None,
) -> dict[str, str | int | dict[str, str]]:
    client = get_s3_browser_client(browser_endpoint_url)
    params = {"Bucket": bucket, "Key": object_key}
    headers: dict[str, str] = {}
    if content_type:
        params["ContentType"] = content_type
        headers["Content-Type"] = content_type
    url = client.generate_presigned_url(
        ClientMethod="put_object",
        Params=params,
        ExpiresIn=expires_in,
    )
    return {
        "bucket": bucket,
        "object_key": object_key,
        "url": url,
        "expires_in": expires_in,
        "method": "PUT",
        "headers": headers,
    }
