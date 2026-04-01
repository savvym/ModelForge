import importlib.util
import sys
import types
from pathlib import Path
from types import SimpleNamespace

import pytest


def _load_target_module():
    async def _noop(*args, **kwargs):
        return None

    def _register_module(name: str, **attrs: object) -> None:
        module = types.ModuleType(name)
        for key, value in attrs.items():
            setattr(module, key, value)
        sys.modules[name] = module

    _register_module("nta_backend")
    _register_module("nta_backend.core")
    _register_module("nta_backend.core.db", SessionLocal=object())
    _register_module(
        "nta_backend.core.project_context",
        ensure_default_project=_noop,
        resolve_active_project_id=_noop,
    )
    _register_module("nta_backend.models")
    _register_module(
        "nta_backend.models.modeling",
        Model=type("Model", (), {}),
        ModelProvider=type("ModelProvider", (), {}),
    )
    _register_module("nta_backend.schemas")
    _register_module(
        "nta_backend.schemas.model_registry",
        ModelProviderCreate=type("ModelProviderCreate", (), {}),
        ModelProviderSummary=type("ModelProviderSummary", (), {}),
        ModelProviderSyncResult=type("ModelProviderSyncResult", (), {}),
        ModelProviderUpdate=type("ModelProviderUpdate", (), {}),
        RegistryModelChatRequest=type("RegistryModelChatRequest", (), {}),
        RegistryModelChatResponse=type("RegistryModelChatResponse", (), {}),
        RegistryModelCreate=type("RegistryModelCreate", (), {}),
        RegistryModelSummary=type("RegistryModelSummary", (), {}),
        RegistryModelTestRequest=type("RegistryModelTestRequest", (), {}),
        RegistryModelTestResponse=type("RegistryModelTestResponse", (), {}),
        RegistryModelUpdate=type("RegistryModelUpdate", (), {}),
    )

    module_path = (
        Path(__file__).resolve().parents[1]
        / "src"
        / "nta_backend"
        / "services"
        / "model_registry_service.py"
    )
    spec = importlib.util.spec_from_file_location("test_model_registry_service_module", module_path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


TARGET_MODULE = _load_target_module()


@pytest.mark.parametrize(
    ("raw_value", "expected"),
    [
        ("https://provider.example.com/v1/", "https://provider.example.com/v1"),
        ("https://provider.example.com/v1/models", "https://provider.example.com/v1"),
        (" https://provider.example.com/v1/models/ ", "https://provider.example.com/v1"),
        ("http://127.0.0.1:8000/v1", "http://127.0.0.1:8000/v1"),
        ("file:///etc/passwd", "file:///etc/passwd"),
    ],
)
def test_normalize_base_url(raw_value: str, expected: str) -> None:
    assert TARGET_MODULE._normalize_base_url(raw_value) == expected


@pytest.mark.parametrize(
    ("raw_value", "expected"),
    [
        ("responses", "responses"),
        ("openai-responses", "responses"),
        ("google", "google"),
        ("google-genai", "google"),
        ("google-generativeai", "google"),
        ("chat-completions", "chat-completions"),
        ("anything-else", "chat-completions"),
    ],
)
def test_normalize_api_format(raw_value: str, expected: str) -> None:
    assert TARGET_MODULE._normalize_api_format(raw_value) == expected


def test_provider_type_for_google_api_format() -> None:
    assert TARGET_MODULE._provider_type_for_api_format("google") == "google-generativeai"
    assert TARGET_MODULE._provider_type_for_api_format("chat-completions") == "openai-compatible"


def test_provider_request_headers_for_google() -> None:
    provider = SimpleNamespace(
        api_format="google",
        api_key="test-key",
        organization="org-123",
        headers_json={"x-extra-header": "demo"},
    )

    headers = TARGET_MODULE._provider_request_headers(provider)

    assert headers["x-goog-api-key"] == "test-key"
    assert headers["x-extra-header"] == "demo"
    assert "Authorization" not in headers
    assert "OpenAI-Organization" not in headers


def test_google_remote_models_normalizes_model_code() -> None:
    models = [
        {"name": "models/gemini-2.5-flash", "displayName": "Gemini 2.5 Flash"},
        {"name": "models/text-embedding-004"},
    ]

    normalized = TARGET_MODULE._google_remote_models(models)

    assert normalized == [
        {
            "name": "Gemini 2.5 Flash",
            "displayName": "Gemini 2.5 Flash",
            "id": "gemini-2.5-flash",
            "google_name": "models/gemini-2.5-flash",
        },
        {
            "name": "text-embedding-004",
            "id": "text-embedding-004",
            "google_name": "models/text-embedding-004",
        },
    ]


def test_google_payload_from_messages_uses_system_instruction() -> None:
    payload = TARGET_MODULE._google_payload_from_messages(
        [
            {"role": "system", "content": "You are precise."},
            {"role": "user", "content": "Explain VPC peering."},
            {"role": "assistant", "content": "Sure."},
        ],
        max_output_tokens=256,
        temperature=0.3,
        parameters={"top_p": 0.8, "stop": ["STOP"]},
    )

    assert payload["systemInstruction"] == {
        "parts": [{"text": "You are precise."}]
    }
    assert payload["contents"] == [
        {"role": "user", "parts": [{"text": "Explain VPC peering."}]},
        {"role": "model", "parts": [{"text": "Sure."}]},
    ]
    assert payload["generationConfig"] == {
        "maxOutputTokens": 256,
        "temperature": 0.3,
        "topP": 0.8,
        "stopSequences": ["STOP"],
    }
