from __future__ import annotations

import importlib.util
import sys
import types
from dataclasses import dataclass
from pathlib import Path


def _load_target_module():
    @dataclass
    class ChatMessage:
        role: str
        content: str

        def model_dump(self) -> dict[str, str]:
            return {"role": self.role, "content": self.content}

    @dataclass
    class Sample:
        id: str
        input: str | list[ChatMessage]

    @dataclass
    class ModelUsage:
        input_tokens: int | None = None
        output_tokens: int | None = None
        total_tokens: int | None = None

    @dataclass
    class ModelOutput:
        sample_id: str
        text: str = ""
        usage: ModelUsage | None = None
        raw: dict[str, object] | None = None
        error: str | None = None

    class ModelAPI:
        def __init__(self, *, model_id: str, **kwargs: object):
            self.model_id = model_id

    def register_model(_name: str):
        def decorator(cls):
            return cls

        return decorator

    def _register_module(name: str, **attrs: object) -> None:
        module = types.ModuleType(name)
        for key, value in attrs.items():
            setattr(module, key, value)
        sys.modules[name] = module

    _register_module("nta_backend")
    _register_module("nta_backend.eval_core")
    _register_module("nta_backend.eval_core.api")
    _register_module(
        "nta_backend.eval_core.api.dataset",
        ChatMessage=ChatMessage,
        Sample=Sample,
    )
    _register_module(
        "nta_backend.eval_core.api.model",
        ModelAPI=ModelAPI,
        ModelOutput=ModelOutput,
        ModelUsage=ModelUsage,
    )
    _register_module(
        "nta_backend.eval_core.api.registry",
        register_model=register_model,
    )

    module_path = (
        Path(__file__).resolve().parents[2]
        / "src"
        / "nta_backend"
        / "eval_core"
        / "models"
        / "openai_compatible.py"
    )
    spec = importlib.util.spec_from_file_location("test_openai_compatible_module", module_path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module, ChatMessage


TARGET_MODULE, CHAT_MESSAGE = _load_target_module()


def test_call_openai_compatible_chat_supports_google_format(monkeypatch) -> None:
    captured: dict[str, object] = {}

    class _FakeResponse:
        def raise_for_status(self) -> None:
            return None

        def json(self) -> dict[str, object]:
            return {
                "candidates": [
                    {
                        "content": {
                            "parts": [{"text": "Google format is working."}],
                        }
                    }
                ],
                "usageMetadata": {
                    "promptTokenCount": 11,
                    "candidatesTokenCount": 7,
                    "totalTokenCount": 18,
                },
            }

    def fake_post(url: str, *, headers: dict[str, str], json: dict[str, object], timeout: float):
        captured["url"] = url
        captured["headers"] = headers
        captured["json"] = json
        captured["timeout"] = timeout
        return _FakeResponse()

    monkeypatch.setattr(TARGET_MODULE.httpx, "post", fake_post)

    output = TARGET_MODULE.call_openai_compatible_chat(
        sample_id="sample-1",
        api_url="https://generativelanguage.googleapis.com/v1beta",
        api_key="google-api-key",
        model_name="models/gemini-2.5-flash",
        messages=[
            CHAT_MESSAGE(role="system", content="You are concise."),
            CHAT_MESSAGE(role="user", content="Say hello."),
        ],
        api_format="google",
        timeout_s=30.0,
        temperature=0.2,
        max_tokens=64,
    )

    assert captured["url"] == (
        "https://generativelanguage.googleapis.com/v1beta/models/"
        "gemini-2.5-flash:generateContent"
    )
    assert captured["headers"] == {
        "Content-Type": "application/json",
        "x-goog-api-key": "google-api-key",
    }
    assert captured["json"] == {
        "contents": [{"role": "user", "parts": [{"text": "Say hello."}]}],
        "generationConfig": {"temperature": 0.2, "maxOutputTokens": 64},
        "systemInstruction": {"parts": [{"text": "You are concise."}]},
    }
    assert captured["timeout"] == 30.0
    assert output.text == "Google format is working."
    assert output.usage is not None
    assert output.usage.input_tokens == 11
    assert output.usage.output_tokens == 7
    assert output.usage.total_tokens == 18
