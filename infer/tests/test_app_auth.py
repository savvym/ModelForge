import importlib
import sys

import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError

from nta_infer_agent.config import AgentSettings, get_settings


def test_infer_agent_token_is_required(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("INFER_AGENT_TOKEN", raising=False)

    with pytest.raises(ValidationError, match="INFER_AGENT_TOKEN"):
        AgentSettings(_env_file=None)


def test_infer_agent_token_must_not_be_empty() -> None:
    with pytest.raises(ValidationError, match="must not be empty"):
        AgentSettings(INFER_AGENT_TOKEN="   ", _env_file=None)

    settings = AgentSettings(INFER_AGENT_TOKEN=" test-token ", _env_file=None)
    assert settings.agent_token.get_secret_value() == "test-token"


def test_all_http_urls_require_bearer_token(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("INFER_AGENT_TOKEN", "test-token")
    get_settings.cache_clear()
    sys.modules.pop("nta_infer_agent.api.app", None)
    app_module = importlib.import_module("nta_infer_agent.api.app")
    client = TestClient(app_module.create_app())

    unauthorized = client.get("/docs")
    assert unauthorized.status_code == 401
    assert unauthorized.json() == {"detail": "Invalid infer-agent token"}

    assert client.get("/openapi.json").status_code == 401
    assert client.get("/not-found").status_code == 401

    headers = {"Authorization": "Bearer test-token"}
    assert client.get("/docs", headers=headers).status_code == 200
    assert client.get("/openapi.json", headers=headers).status_code == 200
    assert client.get("/not-found", headers=headers).status_code == 404
