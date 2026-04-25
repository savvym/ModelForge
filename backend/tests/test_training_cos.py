from __future__ import annotations

from nta_backend.core import training_cos


def test_build_training_cos_endpoint_url() -> None:
    assert (
        training_cos.build_training_cos_endpoint_url(
            {"protocol": "http", "endpoint": "cos.ap-guangzhou.myqcloud.com"}
        )
        == "http://cos.ap-guangzhou.myqcloud.com"
    )
    assert (
        training_cos.build_training_cos_endpoint_url(
            {"protocol": "https", "endpoint": "http://cos.ap-guangzhou.myqcloud.com/"}
        )
        == "http://cos.ap-guangzhou.myqcloud.com"
    )


def test_build_training_cos_uri() -> None:
    assert (
        training_cos.build_training_cos_uri(
            {"bucket": "nta-1300272946"},
            "/training/datasets/demo.jsonl",
        )
        == "cos://nta-1300272946/training/datasets/demo.jsonl"
    )


def test_put_training_cos_object_builds_tencent_cos_client(monkeypatch) -> None:
    calls: dict[str, object] = {}

    class FakeClient:
        def put_object(self, **kwargs):
            calls["put_object"] = kwargs
            return {"ETag": '"etag"'}

    def fake_boto3_client(service_name: str, **kwargs):
        calls["service_name"] = service_name
        calls["client_kwargs"] = kwargs
        return FakeClient()

    monkeypatch.setattr(training_cos.boto3, "client", fake_boto3_client)

    result = training_cos.put_training_cos_object(
        {
            "protocol": "http",
            "endpoint": "cos.ap-guangzhou.myqcloud.com",
            "bucket": "nta-1300272946",
            "secret_id": "AKIDxxxx",
            "secret_key": "secret",
        },
        object_key="/training/datasets/demo.jsonl",
        body=b"{}\n",
        content_type="application/x-ndjson",
    )

    assert result.object_key == "training/datasets/demo.jsonl"
    assert calls["service_name"] == "s3"
    client_kwargs = calls["client_kwargs"]
    assert client_kwargs["endpoint_url"] == "http://cos.ap-guangzhou.myqcloud.com"
    assert client_kwargs["region_name"] == "ap-guangzhou"
    assert client_kwargs["aws_access_key_id"] == "AKIDxxxx"
    assert calls["put_object"] == {
        "Bucket": "nta-1300272946",
        "Key": "training/datasets/demo.jsonl",
        "Body": b"{}\n",
        "ContentType": "application/x-ndjson",
    }
