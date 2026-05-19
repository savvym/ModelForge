import boto3

from nta_backend.core.config import get_settings
from nta_backend.core import s3 as s3_module


def test_get_s3_client_uses_configured_addressing_style(monkeypatch) -> None:
    captured: dict[str, object] = {}

    def fake_boto3_client(service_name: str, **kwargs):
        captured["service_name"] = service_name
        captured["kwargs"] = kwargs
        return object()

    monkeypatch.setattr(boto3, "client", fake_boto3_client)
    monkeypatch.setenv("S3_ENDPOINT_URL", "https://cos.ap-shanghai.myqcloud.com")
    monkeypatch.setenv("S3_REGION", "ap-shanghai")
    monkeypatch.setenv("S3_ADDRESSING_STYLE", "virtual")
    monkeypatch.setenv("S3_ACCESS_KEY_ID", "secret-id")
    monkeypatch.setenv("S3_SECRET_ACCESS_KEY", "secret-key")

    get_settings.cache_clear()
    s3_module._s3_clients.clear()
    try:
        s3_module.get_s3_client()
    finally:
        s3_module._s3_clients.clear()
        get_settings.cache_clear()

    assert captured["service_name"] == "s3"
    config = captured["kwargs"]["config"]
    assert config.s3["addressing_style"] == "virtual"


def test_get_s3_client_uses_configured_timeouts(monkeypatch) -> None:
    captured: dict[str, object] = {}

    def fake_boto3_client(service_name: str, **kwargs):
        captured["service_name"] = service_name
        captured["kwargs"] = kwargs
        return object()

    monkeypatch.setattr(boto3, "client", fake_boto3_client)
    monkeypatch.setenv("S3_CONNECT_TIMEOUT_SECONDS", "7")
    monkeypatch.setenv("S3_READ_TIMEOUT_SECONDS", "90")
    monkeypatch.setenv("S3_MAX_ATTEMPTS", "3")

    get_settings.cache_clear()
    s3_module._s3_clients.clear()
    try:
        s3_module.get_s3_client()
    finally:
        s3_module._s3_clients.clear()
        get_settings.cache_clear()

    assert captured["service_name"] == "s3"
    config = captured["kwargs"]["config"]
    assert config.connect_timeout == 7
    assert config.read_timeout == 90
    assert config.retries["max_attempts"] == 3
