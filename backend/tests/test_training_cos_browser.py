from __future__ import annotations

import base64
from datetime import datetime, timezone
from io import BytesIO

import pytest

from nta_backend.core import training_cos
from nta_backend.services import training_cos_browser_service as svc


BASE_CONFIG = {
    "enabled": True,
    "protocol": "http",
    "endpoint": "cos.ap-guangzhou.myqcloud.com",
    "bucket": "nta-1300272946",
    "secret_id": "AKIDxxxx",
    "secret_key": "secret",
}


class FakeClient:
    def __init__(self, calls: dict, responses: dict):
        self.calls = calls
        self.responses = responses

    def list_objects_v2(self, **kwargs):
        self.calls.setdefault("list", []).append(kwargs)
        return self.responses["list"]

    def get_object(self, **kwargs):
        self.calls.setdefault("get", []).append(kwargs)
        return self.responses["get"]


def _install_fake_client(monkeypatch, responses):
    calls: dict = {}

    def fake_boto3_client(service_name, **kwargs):
        calls["service_name"] = service_name
        calls["client_kwargs"] = kwargs
        return FakeClient(calls, responses)

    monkeypatch.setattr(training_cos.boto3, "client", fake_boto3_client)
    return calls


def test_list_training_cos_objects_normalizes_prefix_and_parses_response(monkeypatch):
    responses = {
        "list": {
            "Prefix": "training/datasets/",
            "Delimiter": "/",
            "IsTruncated": True,
            "NextContinuationToken": "tok-next",
            "CommonPrefixes": [{"Prefix": "training/datasets/v1/"}],
            "Contents": [
                {
                    "Key": "training/datasets/demo.jsonl",
                    "Size": 12,
                    "LastModified": datetime(2026, 5, 19, 10, tzinfo=timezone.utc),
                    "ETag": '"abc"',
                },
                {"Key": "training/datasets/", "Size": 0},  # placeholder, should skip
            ],
        }
    }
    calls = _install_fake_client(monkeypatch, responses)

    result = training_cos.list_training_cos_objects(
        BASE_CONFIG,
        prefix="training/datasets",
        delimiter="/",
        max_keys=50,
        continuation_token="prev",
    )

    list_call = calls["list"][0]
    assert list_call["Bucket"] == "nta-1300272946"
    assert list_call["Prefix"] == "training/datasets/"  # appended trailing slash
    assert list_call["Delimiter"] == "/"
    assert list_call["MaxKeys"] == 50
    assert list_call["ContinuationToken"] == "prev"

    assert result.prefix == "training/datasets/"
    assert result.folders == ["training/datasets/v1/"]
    assert len(result.files) == 1
    assert result.files[0].key == "training/datasets/demo.jsonl"
    assert result.files[0].size == 12
    assert result.next_token == "tok-next"
    assert result.truncated is True


def test_get_training_cos_object_returns_typed_body(monkeypatch):
    responses = {
        "get": {
            "Body": BytesIO(b"hello world"),
            "ContentType": "text/plain",
            "ContentLength": 11,
            "ETag": '"etag-1"',
            "LastModified": datetime(2026, 5, 19, 11, tzinfo=timezone.utc),
        }
    }
    calls = _install_fake_client(monkeypatch, responses)

    result = training_cos.get_training_cos_object(BASE_CONFIG, object_key="/training/demo.txt")

    assert calls["get"][0] == {"Bucket": "nta-1300272946", "Key": "training/demo.txt"}
    assert result.object_key == "training/demo.txt"
    assert result.body == b"hello world"
    assert result.content_type == "text/plain"
    assert result.size == 11
    assert result.etag == '"etag-1"'
    assert result.last_modified is not None


def test_status_reports_configured_when_required_fields_present(monkeypatch):
    async def fake_load():
        return dict(BASE_CONFIG)

    monkeypatch.setattr(svc, "_load_config", fake_load)
    service = svc.TrainingCosBrowserService()

    import asyncio

    status = asyncio.run(service.get_status())
    assert status.configured is True
    assert status.enabled is True
    assert status.bucket == "nta-1300272946"


def test_status_marks_missing_credentials_as_not_configured(monkeypatch):
    async def fake_load():
        return {**BASE_CONFIG, "secret_key": ""}

    monkeypatch.setattr(svc, "_load_config", fake_load)
    service = svc.TrainingCosBrowserService()

    import asyncio

    status = asyncio.run(service.get_status())
    assert status.configured is False


def test_list_entries_raises_when_disabled(monkeypatch):
    async def fake_load():
        return {**BASE_CONFIG, "enabled": False}

    monkeypatch.setattr(svc, "_load_config", fake_load)
    service = svc.TrainingCosBrowserService()

    import asyncio

    with pytest.raises(svc.TrainingCosUnavailable):
        asyncio.run(service.list_entries(prefix=""))


def test_preview_text_object_inlines_utf8_content():
    body = training_cos.TrainingCosObjectBody(
        object_key="training/notes/readme.md",
        body=b"# Hello\nworld",
        content_type="text/markdown",
        size=13,
        etag='"abc"',
        last_modified="2026-05-19T10:00:00+00:00",
    )
    preview = svc._preview_from_body(body, download_url="/api/v1/training-cos/object/raw?key=x")
    assert preview.encoding == "utf8"
    assert preview.content == "# Hello\nworld"
    assert preview.is_binary is False
    assert preview.truncated is False


def test_preview_large_text_object_is_truncated_with_tail_marker():
    big_text = ("a" * (svc.INLINE_PREVIEW_MAX_BYTES + 16)).encode("utf-8")
    body = training_cos.TrainingCosObjectBody(
        object_key="training/notes/big.log",
        body=big_text,
        content_type="text/plain",
        size=len(big_text),
        etag=None,
        last_modified=None,
    )
    preview = svc._preview_from_body(body, download_url="/x")
    assert preview.truncated is True
    assert preview.encoding == "utf8"
    assert preview.content is not None and preview.content.endswith(svc.TEXT_PREVIEW_TAIL)


def test_preview_small_image_returns_base64_payload():
    raw = b"\x89PNG fake bytes"
    body = training_cos.TrainingCosObjectBody(
        object_key="training/img/logo.png",
        body=raw,
        content_type="image/png",
        size=len(raw),
        etag=None,
        last_modified=None,
    )
    preview = svc._preview_from_body(body, download_url="/x")
    assert preview.encoding == "base64"
    assert preview.content == base64.b64encode(raw).decode("ascii")
    assert preview.is_binary is False


def test_preview_large_binary_falls_back_to_download_only():
    raw = b"\x00" * (svc.INLINE_PREVIEW_MAX_BYTES + 1)
    body = training_cos.TrainingCosObjectBody(
        object_key="training/big.zip",
        body=raw,
        content_type="application/zip",
        size=len(raw),
        etag=None,
        last_modified=None,
    )
    preview = svc._preview_from_body(body, download_url="/x")
    assert preview.content is None
    assert preview.is_binary is True
    assert preview.truncated is True
