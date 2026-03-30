from __future__ import annotations

from typing import Any

import httpx

from nta_backend.eval_core.api.dataset import ChatMessage, Sample
from nta_backend.eval_core.api.model import ModelAPI, ModelOutput, ModelUsage
from nta_backend.eval_core.api.registry import register_model


def call_openai_compatible_chat(
    *,
    sample_id: str,
    api_url: str,
    api_key: str | None,
    model_name: str,
    messages: list[ChatMessage] | list[dict[str, str]],
    api_format: str = "chat-completions",
    timeout_s: float = 180.0,
    temperature: float = 0.0,
    max_tokens: int | None = None,
) -> ModelOutput:
    normalized_api_format = _normalize_api_format(api_format)
    serialized_messages = [_serialize_message(message) for message in messages]
    payload = _build_request_payload(
        model_name=model_name,
        messages=serialized_messages,
        api_format=normalized_api_format,
        temperature=temperature,
        max_tokens=max_tokens,
    )

    headers = {"Content-Type": "application/json"}
    if api_key:
        headers["Authorization"] = f"Bearer {api_key}"

    try:
        response = httpx.post(
            _normalize_request_url(api_url, normalized_api_format),
            headers=headers,
            json=payload,
            timeout=timeout_s,
        )
        response.raise_for_status()
        body = response.json()
    except Exception as exc:
        return ModelOutput(sample_id=sample_id, error=str(exc))

    text = _extract_output_text(body, normalized_api_format)
    usage = _extract_usage(body.get("usage"), normalized_api_format)
    return ModelOutput(
        sample_id=sample_id,
        text=text,
        usage=usage,
        raw=body,
    )


@register_model("openai_compatible")
class OpenAICompatibleModel(ModelAPI):
    def __init__(
        self,
        *,
        model_id: str,
        api_url: str,
        api_key: str | None = None,
        api_format: str = "chat-completions",
        timeout_s: float = 180.0,
        temperature: float = 0.0,
        max_tokens: int | None = None,
        **kwargs: object,
    ):
        super().__init__(model_id=model_id, **kwargs)
        self.api_url = api_url
        self.api_key = api_key
        self.api_format = api_format
        self.timeout_s = timeout_s
        self.temperature = temperature
        self.max_tokens = max_tokens

    def generate(self, sample: Sample) -> ModelOutput:
        return call_openai_compatible_chat(
            sample_id=sample.id,
            api_url=self.api_url,
            api_key=self.api_key,
            model_name=self.model_id,
            messages=_messages_from_sample_input(sample.input),
            api_format=self.api_format,
            timeout_s=self.timeout_s,
            temperature=self.temperature,
            max_tokens=self.max_tokens,
        )


def _messages_from_sample_input(
    value: str | list[ChatMessage],
) -> list[ChatMessage]:
    if isinstance(value, str):
        return [ChatMessage(role="user", content=value)]
    return value


def _serialize_message(message: ChatMessage | dict[str, str]) -> dict[str, str]:
    if isinstance(message, ChatMessage):
        return message.model_dump()
    return {"role": str(message["role"]), "content": str(message["content"])}


def _normalize_request_url(api_url: str, api_format: str) -> str:
    if api_format == "responses":
        return _normalize_responses_url(api_url)
    return _normalize_chat_completions_url(api_url)


def _normalize_chat_completions_url(api_url: str) -> str:
    normalized = api_url.strip().rstrip("/")
    if normalized.endswith("/chat/completions"):
        return normalized
    if normalized.endswith("/v1"):
        return f"{normalized}/chat/completions"
    return f"{normalized}/v1/chat/completions"


def _normalize_responses_url(api_url: str) -> str:
    normalized = api_url.strip().rstrip("/")
    if normalized.endswith("/responses"):
        return normalized
    if normalized.endswith("/v1"):
        return f"{normalized}/responses"
    return f"{normalized}/v1/responses"


def _normalize_api_format(value: str | None) -> str:
    if value == "responses":
        return "responses"
    return "chat-completions"


def _build_request_payload(
    *,
    model_name: str,
    messages: list[dict[str, str]],
    api_format: str,
    temperature: float,
    max_tokens: int | None,
) -> dict[str, Any]:
    if api_format == "responses":
        payload: dict[str, Any] = {
            "model": model_name,
            "input": _responses_input_from_messages(messages),
        }
        if max_tokens is not None:
            payload["max_output_tokens"] = max_tokens
        return payload

    payload = {
        "model": model_name,
        "messages": messages,
        "temperature": temperature,
    }
    if max_tokens is not None:
        payload["max_tokens"] = max_tokens
    return payload


def _extract_output_text(payload: dict[str, Any], api_format: str) -> str:
    if api_format == "responses":
        return _extract_responses_text(payload)
    return _extract_chat_completions_text(payload)


def _extract_chat_completions_text(payload: dict[str, Any]) -> str:
    choices = payload.get("choices")
    if not isinstance(choices, list) or not choices:
        return ""
    first = choices[0] or {}
    message = first.get("message") or {}
    content = message.get("content")
    if isinstance(content, str):
        return content.strip()
    if isinstance(content, list):
        parts = []
        for item in content:
            if isinstance(item, dict) and isinstance(item.get("text"), str):
                parts.append(item["text"])
        return "\n".join(parts).strip()
    return ""


def _extract_responses_text(payload: dict[str, Any]) -> str:
    text = _extract_text(payload.get("output_text"))
    if text:
        return text

    output = payload.get("output")
    if not isinstance(output, list):
        return ""

    parts: list[str] = []
    for item in output:
        if not isinstance(item, dict):
            continue
        content = item.get("content")
        if not isinstance(content, list):
            continue
        for part in content:
            if not isinstance(part, dict):
                continue
            text = _extract_text(part.get("text"))
            if text:
                parts.append(text)
    return "\n".join(parts).strip()


def _extract_usage(payload: Any, api_format: str) -> ModelUsage | None:
    if not isinstance(payload, dict):
        return None
    input_key = "input_tokens" if api_format == "responses" else "prompt_tokens"
    output_key = "output_tokens" if api_format == "responses" else "completion_tokens"
    return ModelUsage(
        input_tokens=_as_int(payload.get(input_key)),
        output_tokens=_as_int(payload.get(output_key)),
        total_tokens=_as_int(payload.get("total_tokens")),
    )


def _responses_input_from_messages(messages: list[dict[str, str]]) -> str:
    parts: list[str] = []
    for message in messages:
        role = message["role"]
        content = message["content"].strip()
        if not content:
            continue
        prefix = "System"
        if role == "user":
            prefix = "User"
        elif role == "assistant":
            prefix = "Assistant"
        parts.append(f"{prefix}: {content}")
    parts.append("Assistant:")
    return "\n\n".join(parts)


def _extract_text(value: Any) -> str | None:
    if isinstance(value, str):
        text = value.strip()
        return text or None
    if isinstance(value, dict):
        for key in ("text", "content", "value"):
            text = _extract_text(value.get(key))
            if text:
                return text
    if isinstance(value, list):
        parts = []
        for item in value:
            text = _extract_text(item)
            if text:
                parts.append(text)
        joined = "\n".join(parts).strip()
        return joined or None
    return None


def _as_int(value: Any) -> int | None:
    if isinstance(value, int):
        return value
    return None
