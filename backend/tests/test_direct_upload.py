import json
from types import SimpleNamespace

from nta_backend.core import direct_upload
from nta_backend.core.config import get_settings


def test_build_direct_upload_response_uses_cos_sts(monkeypatch) -> None:
    captured: dict[str, object] = {}

    class FakeStsClient:
        def GetFederationToken(self, request):
            captured["request"] = json.loads(request.to_json_string())
            return SimpleNamespace(
                Credentials=SimpleNamespace(
                    TmpSecretId="tmp-secret-id",
                    TmpSecretKey="tmp-secret-key",
                    Token="tmp-session-token",
                ),
                ExpiredTime=1_800_000_000,
            )

    monkeypatch.setenv("S3_ENDPOINT_URL", "https://cos-internal.ap-chengdu.tencentcos.cn")
    monkeypatch.setenv("S3_BROWSER_ENDPOINT_URL", "https://cos-internal.ap-chengdu.tencentcos.cn")
    monkeypatch.setenv("S3_REGION", "ap-chengdu")
    monkeypatch.setenv("S3_ACCESS_KEY_ID", "secret-id")
    monkeypatch.setenv("S3_SECRET_ACCESS_KEY", "secret-key")
    monkeypatch.setenv("S3_BUCKET_MAIN", "zhhdzhang-cos-1257943044")
    monkeypatch.setenv("S3_DIRECT_UPLOAD_MODE", "cos-sts")
    monkeypatch.setenv("S3_STS_DURATION_SECONDS", "1800")
    monkeypatch.setattr(direct_upload, "_get_sts_client", lambda: FakeStsClient())

    get_settings.cache_clear()
    try:
        response = direct_upload.build_direct_upload_response(
            bucket="zhhdzhang-cos-1257943044",
            object_key="nta-dev/projects/proj-1/files/demo.txt",
            file_name="demo.txt",
            file_size=3,
            content_type="text/plain",
            browser_endpoint_url="https://cos-internal.ap-chengdu.tencentcos.cn",
        )
    finally:
        get_settings.cache_clear()

    assert response.provider == "cos-sts"
    assert response.region == "ap-chengdu"
    assert response.domain == "{Bucket}.cos-internal.ap-chengdu.tencentcos.cn"
    assert response.protocol == "https:"
    assert response.sts is not None
    assert response.sts.tmp_secret_id == "tmp-secret-id"
    assert response.sts.tmp_secret_key == "tmp-secret-key"
    assert response.sts.session_token == "tmp-session-token"
    assert response.sts.start_time <= response.sts.expired_time
    assert response.sts.expired_time == 1_800_000_000
    assert captured["request"] == {
        "Name": "ntaupload",
        "Policy": json.dumps(
            {
                "version": "2.0",
                "statement": [
                    {
                        "effect": "allow",
                        "action": direct_upload.COS_STS_ACTIONS,
                        "resource": [
                            "qcs::cos:ap-chengdu:uid/1257943044:zhhdzhang-cos-1257943044/nta-dev/projects/proj-1/files/demo.txt"
                        ],
                    }
                ],
            }
        ),
        "DurationSeconds": 1800,
    }


def test_build_direct_upload_response_falls_back_to_presigned(monkeypatch) -> None:
    monkeypatch.setenv("S3_ENDPOINT_URL", "http://127.0.0.1:8081")
    monkeypatch.setenv("S3_BROWSER_ENDPOINT_URL", "http://127.0.0.1:8081")
    monkeypatch.setenv("S3_DIRECT_UPLOAD_MODE", "presigned")
    monkeypatch.setenv("S3_STS_DURATION_SECONDS", "1200")
    monkeypatch.setattr(
        direct_upload,
        "build_presigned_upload",
        lambda **kwargs: {
            "bucket": kwargs["bucket"],
            "object_key": kwargs["object_key"],
            "url": "http://127.0.0.1:8081/upload",
            "expires_in": kwargs["expires_in"],
            "method": "PUT",
            "headers": {"Content-Type": "text/plain"},
        },
    )

    get_settings.cache_clear()
    try:
        response = direct_upload.build_direct_upload_response(
            bucket="nta-default",
            object_key="nta-dev/projects/proj-1/files/demo.txt",
            file_name="demo.txt",
            file_size=3,
            content_type="text/plain",
        )
    finally:
        get_settings.cache_clear()

    assert response.provider == "presigned"
    assert response.url == "http://127.0.0.1:8081/upload"
    assert response.method == "PUT"
    assert response.headers == {"Content-Type": "text/plain"}
    assert response.expires_in == 1200


def test_get_sts_client_uses_configured_region(monkeypatch) -> None:
    captured: dict[str, object] = {}

    class FakeStsClient:
        def __init__(self, cred, region, profile):
            captured["cred"] = cred
            captured["region"] = region
            captured["profile"] = profile

    monkeypatch.setenv("S3_REGION", "ap-chengdu")
    monkeypatch.setenv("S3_ACCESS_KEY_ID", "secret-id")
    monkeypatch.setenv("S3_SECRET_ACCESS_KEY", "secret-key")
    monkeypatch.setattr(direct_upload.sts_client, "StsClient", FakeStsClient)

    get_settings.cache_clear()
    direct_upload._get_sts_client.cache_clear()
    try:
        direct_upload._get_sts_client()
    finally:
        direct_upload._get_sts_client.cache_clear()
        get_settings.cache_clear()

    assert captured["region"] == "ap-chengdu"
