from __future__ import annotations

from types import SimpleNamespace

from nta_backend.core import training_cos
from nta_backend.schemas.training_cos import TrainingCosHuggingFaceSyncCreateRequest
from nta_backend.services.training_cos_huggingface_sync_service import (
    JOB_NAME_PREFIX,
    MAX_JOB_NAME_LENGTH,
    _build_readme,
    _job_name,
)


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


def test_parse_training_cos_hosts_uses_hosts_file_format() -> None:
    assert training_cos.parse_training_cos_hosts(
        {
            "hosts": """
            # only training COS requests use this override
            21.0.81.61 nta-1300272946.cos.ap-guangzhou.myqcloud.com
            21.0.81.62 backup.cos.ap-guangzhou.myqcloud.com alias.cos.ap-guangzhou.myqcloud.com
            """
        }
    ) == {
        "nta-1300272946.cos.ap-guangzhou.myqcloud.com": "21.0.81.61",
        "backup.cos.ap-guangzhou.myqcloud.com": "21.0.81.62",
        "alias.cos.ap-guangzhou.myqcloud.com": "21.0.81.62",
    }


def test_training_cos_host_override_is_exact_match_only() -> None:
    request = SimpleNamespace(
        url="http://nta-1300272946.cos.ap-guangzhou.myqcloud.com/demo.jsonl",
        headers={},
    )

    training_cos.apply_training_cos_host_overrides(
        request,
        {"nta-1300272946.cos.ap-guangzhou.myqcloud.com": "21.0.81.61"},
    )

    assert request.url == "http://21.0.81.61/demo.jsonl"
    assert request.headers["Host"] == "nta-1300272946.cos.ap-guangzhou.myqcloud.com"

    unmatched_request = SimpleNamespace(
        url="http://other.cos.ap-guangzhou.myqcloud.com/demo.jsonl",
        headers={},
    )
    training_cos.apply_training_cos_host_overrides(
        unmatched_request,
        {"cos.ap-guangzhou.myqcloud.com": "21.0.81.61"},
    )

    assert unmatched_request.url == "http://other.cos.ap-guangzhou.myqcloud.com/demo.jsonl"
    assert unmatched_request.headers == {}


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


def test_huggingface_sync_job_name_is_capped_for_long_prefix() -> None:
    prefix = (
        "checkpoints/gemma4-31b-it-troubleshooting-sft-lora-8gpu/"
        "v0-20260525-232909/v0-20260525-232909/checkpoint-150/"
    )

    name = _job_name(prefix)

    assert name.startswith(f"{JOB_NAME_PREFIX}: ")
    assert len(name) <= MAX_JOB_NAME_LENGTH
    assert prefix.rstrip("/") not in name


def test_huggingface_sync_readme_skips_local_base_model_path() -> None:
    readme = _build_readme(
        TrainingCosHuggingFaceSyncCreateRequest(
            prefix="checkpoints/demo/",
            repo_id="SavvyM/demo-model",
            base_model="/data/data_cfs_turbo/nta-train/models/gemma-4-31b-it",
            tags=["text-generation"],
        )
    )

    assert "base_model:" not in readme
    assert "/data/data_cfs_turbo" not in readme
    assert "tags:" in readme


def test_huggingface_sync_readme_keeps_valid_base_model_url() -> None:
    readme = _build_readme(
        TrainingCosHuggingFaceSyncCreateRequest(
            prefix="checkpoints/demo/",
            repo_id="SavvyM/demo-model",
            base_model="https://huggingface.co/google/gemma-3-27b-it",
        )
    )

    assert "base_model:" in readme
    assert "- google/gemma-3-27b-it" in readme
