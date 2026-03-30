from __future__ import annotations

import json
import re
from collections.abc import AsyncIterator
from datetime import UTC, datetime
from time import perf_counter
from typing import Any
from uuid import UUID

import httpx
from sqlalchemy import delete, func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from nta_backend.core.db import SessionLocal
from nta_backend.core.project_context import (
    ensure_default_project,
    resolve_active_project_id,
)
from nta_backend.models.modeling import Model, ModelProvider
from nta_backend.schemas.model_registry import (
    ModelProviderCreate,
    ModelProviderSummary,
    ModelProviderSyncResult,
    ModelProviderUpdate,
    RegistryModelChatRequest,
    RegistryModelChatResponse,
    RegistryModelCreate,
    RegistryModelSummary,
    RegistryModelTestRequest,
    RegistryModelTestResponse,
    RegistryModelUpdate,
)


def _now() -> datetime:
    return datetime.now(UTC)


def _normalize_base_url(value: str) -> str:
    normalized = value.strip().rstrip("/")
    if normalized.endswith("/models"):
        return normalized[: -len("/models")]
    return normalized


def _normalize_model_token(token: str) -> str:
    lowered = token.lower()

    exact_map = {
        "gpt": "GPT",
        "bge": "BGE",
        "glm": "GLM",
        "asr": "ASR",
        "tts": "TTS",
        "zh": "ZH",
        "en": "EN",
        "cn": "CN",
        "vl": "VL",
    }
    if lowered in exact_map:
        return exact_map[lowered]

    title_map = {
        "claude": "Claude",
        "opus": "Opus",
        "sonnet": "Sonnet",
        "haiku": "Haiku",
        "codex": "Codex",
        "spark": "Spark",
        "mini": "Mini",
        "max": "Max",
        "turbo": "Turbo",
        "large": "Large",
        "medium": "Medium",
        "small": "Small",
        "video": "Video",
        "image": "Image",
        "audio": "Audio",
        "embedding": "Embedding",
        "embeddings": "Embeddings",
        "vector": "Vector",
        "reranker": "Reranker",
        "chat": "Chat",
        "text": "Text",
        "vision": "Vision",
        "arc": "Arc",
        "deprecated": "Deprecated",
        "deepseek": "DeepSeek",
        "qwen": "Qwen",
        "gemini": "Gemini",
        "llama": "Llama",
        "mistral": "Mistral",
        "doubao": "Doubao",
        "hunyuan": "Hunyuan",
        "kimi": "Kimi",
        "instruct": "Instruct",
        "reasoning": "Reasoning",
        "pro": "Pro",
        "flash": "Flash",
        "nano": "Nano",
    }
    if lowered in title_map:
        return title_map[lowered]

    if re.fullmatch(r"o\d+(?:\.\d+)?", lowered):
        return lowered

    if re.fullmatch(r"\d+[a-z]", lowered):
        return f"{lowered[:-1]}{lowered[-1].upper()}"

    if re.fullmatch(r"v\d+(?:\.\d+)?", lowered):
        return f"V{lowered[1:]}"

    if lowered.isdigit():
        return lowered

    return token[:1].upper() + token[1:]


def _format_model_code(model_code: str) -> str:
    normalized = model_code.strip().replace("_", "-")
    if not normalized:
        return model_code

    raw_tokens = [token for token in normalized.split("-") if token]
    tokens: list[str] = []
    index = 0

    while index < len(raw_tokens):
        current = raw_tokens[index]
        next_token = raw_tokens[index + 1] if index + 1 < len(raw_tokens) else None

        if (
            next_token
            and current.isdigit()
            and next_token.isdigit()
            and len(current) <= 2
            and len(next_token) <= 2
        ):
            tokens.append(f"{current}.{next_token}")
            index += 2
            continue

        tokens.append(_normalize_model_token(current))
        index += 1

    if len(tokens) >= 2 and tokens[0] == "GPT" and re.fullmatch(r"\d+(?:\.\d+)?", tokens[1]):
        return " ".join([f"{tokens[0]}-{tokens[1]}", *tokens[2:]])

    return " ".join(tokens)


def _provider_model_display_name(remote_model: dict[str, Any], model_code: str) -> str:
    for key in ("display_name", "displayName", "name"):
        value = remote_model.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()
    return _format_model_code(model_code)


def _serialize_model_name(model: Model) -> str:
    if model.is_provider_managed and isinstance(model.capabilities_json, dict):
        for key in ("display_name", "displayName", "name"):
            value = model.capabilities_json.get(key)
            if isinstance(value, str) and value.strip():
                return value.strip()

    if model.is_provider_managed and model.model_code:
        return _format_model_code(model.model_code)

    return model.name


def _serialize_provider(provider: ModelProvider, model_count: int) -> ModelProviderSummary:
    return ModelProviderSummary(
        id=provider.id,
        name=provider.name,
        provider_type=provider.provider_type,
        adapter=provider.adapter,
        api_format=provider.api_format,
        base_url=provider.base_url,
        organization=provider.organization,
        description=provider.description,
        status=provider.status,
        has_api_key=bool(provider.api_key),
        model_count=model_count,
        last_synced_at=provider.last_synced_at,
        created_at=provider.created_at,
        updated_at=provider.updated_at,
    )


def _serialize_model(model: Model, provider_name: str | None) -> RegistryModelSummary:
    return RegistryModelSummary(
        id=model.id,
        name=_serialize_model_name(model),
        model_code=model.model_code,
        vendor=model.vendor,
        source=model.source,
        api_format=model.api_format,
        category=model.category,
        description=model.description,
        status=model.status,
        provider_id=model.provider_id,
        provider_name=provider_name,
        is_provider_managed=model.is_provider_managed,
        last_synced_at=model.last_synced_at,
        created_at=model.created_at,
        updated_at=model.updated_at,
    )


async def _get_provider_or_raise(
    session: AsyncSession,
    provider_id: UUID,
    project_id: UUID,
) -> ModelProvider:
    row = await session.execute(
        select(ModelProvider).where(
            ModelProvider.id == provider_id,
            ModelProvider.project_id == project_id,
        )
    )
    provider = row.scalar_one_or_none()
    if provider is None:
        raise KeyError(str(provider_id))
    return provider


async def _get_model_or_raise(
    session: AsyncSession,
    model_id: UUID,
    project_id: UUID,
) -> Model:
    row = await session.execute(
        select(Model).where(
            Model.id == model_id,
            Model.project_id == project_id,
        )
    )
    model = row.scalar_one_or_none()
    if model is None:
        raise KeyError(str(model_id))
    return model


async def _fetch_provider_models(provider: ModelProvider) -> list[dict[str, Any]]:
    headers = _provider_request_headers(provider)
    url = f"{_normalize_base_url(provider.base_url)}/models"
    async with httpx.AsyncClient(timeout=20.0) as client:
        response = await client.get(url, headers=headers)
        response.raise_for_status()
        payload = response.json()

    data = payload.get("data")
    if not isinstance(data, list):
        raise ValueError("Provider `/models` response is invalid")

    return [item for item in data if isinstance(item, dict) and item.get("id")]


def _provider_request_headers(provider: ModelProvider) -> dict[str, str]:
    headers: dict[str, str] = {"Accept": "application/json"}
    if provider.api_key:
        headers["Authorization"] = f"Bearer {provider.api_key}"
    if provider.organization:
        headers["OpenAI-Organization"] = provider.organization
    if provider.headers_json:
        headers.update(
            {
                str(key): str(value)
                for key, value in provider.headers_json.items()
                if value is not None
            }
        )
    return headers


def _extract_text(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, str):
        return value.strip()
    if isinstance(value, list):
        parts = [_extract_text(item) for item in value]
        return "\n".join(part for part in parts if part)
    if isinstance(value, dict):
        if isinstance(value.get("output_text"), str):
            return value["output_text"].strip()
        if isinstance(value.get("text"), str):
            return value["text"].strip()
        for key in ("content", "output", "message"):
            extracted = _extract_text(value.get(key))
            if extracted:
                return extracted
        return ""
    return ""


def _extract_chat_completion_text(payload: dict[str, Any]) -> str:
    choices = payload.get("choices")
    if not isinstance(choices, list) or not choices:
        raise ValueError("Provider chat completion response is invalid")
    message = choices[0].get("message") if isinstance(choices[0], dict) else None
    text = _extract_text(message)
    if not text:
        raise ValueError("Provider chat completion response did not include message content")
    return text


def _extract_responses_text(payload: dict[str, Any]) -> str:
    text = _extract_text(payload.get("output_text"))
    if text:
        return text
    text = _extract_text(payload.get("output"))
    if text:
        return text
    raise ValueError("Provider responses API response did not include output text")


def _extract_responses_reasoning_text(payload: dict[str, Any]) -> str | None:
    output = payload.get("output")
    if not isinstance(output, list):
        return None

    chunks: list[str] = []

    for item in output:
        if not isinstance(item, dict) or item.get("type") != "reasoning":
            continue

        summary = item.get("summary")
        if isinstance(summary, list):
            for part in summary:
                if not isinstance(part, dict):
                    continue
                text = _extract_text(part.get("text"))
                if text:
                    chunks.append(text)
                    continue

                text = _extract_text(part.get("summary_text"))
                if text:
                    chunks.append(text)

    joined = "\n\n".join(chunk for chunk in chunks if chunk).strip()
    return joined or None


def _extract_chat_completion_reasoning_text(payload: dict[str, Any]) -> str | None:
    choices = payload.get("choices")
    if not isinstance(choices, list) or not choices:
        return None

    message = choices[0].get("message") if isinstance(choices[0], dict) else None
    if not isinstance(message, dict):
        return None

    for key in ("reasoning_content", "reasoning", "reasoning_text"):
        text = _extract_text(message.get(key))
        if text:
            return text

    content = message.get("content")
    if isinstance(content, list):
        chunks: list[str] = []
        for part in content:
            if not isinstance(part, dict):
                continue
            if part.get("type") not in {"reasoning", "reasoning_text", "summary_text"}:
                continue
            text = _extract_text(part.get("text"))
            if text:
                chunks.append(text)
        joined = "\n\n".join(chunk for chunk in chunks if chunk).strip()
        if joined:
            return joined

    return None


def _extract_usage_tokens(payload: dict[str, Any]) -> tuple[int | None, int | None, int | None]:
    usage = payload.get("usage")
    if not isinstance(usage, dict):
        return None, None, None

    input_tokens = usage.get("input_tokens") or usage.get("prompt_tokens")
    output_tokens = usage.get("output_tokens") or usage.get("completion_tokens")
    total_tokens = usage.get("total_tokens")

    return (
        int(input_tokens) if isinstance(input_tokens, int | float) else None,
        int(output_tokens) if isinstance(output_tokens, int | float) else None,
        int(total_tokens) if isinstance(total_tokens, int | float) else None,
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


def _map_reasoning_effort(reasoning_depth: str | None) -> str | None:
    if reasoning_depth in {"关闭", "off", "none"}:
        return "none"
    if reasoning_depth in {"中", "medium"}:
        return "medium"
    if reasoning_depth in {"高", "high"}:
        return "high"
    return None


def _merge_generation_parameters(
    request_body: dict[str, Any],
    parameters: dict[str, Any] | None,
    *,
    api_format: str,
) -> dict[str, Any]:
    if not parameters:
        return request_body

    merged = dict(request_body)
    if api_format == "responses":
        field_map = {
            "temperature": "temperature",
            "top_p": "top_p",
            "frequency_penalty": "frequency_penalty",
            "stop": "stop",
            "max_tokens": "max_output_tokens",
            "max_output_tokens": "max_output_tokens",
        }
    else:
        field_map = {
            "temperature": "temperature",
            "top_p": "top_p",
            "frequency_penalty": "frequency_penalty",
            "stop": "stop",
            "logprobs": "logprobs",
            "top_logprobs": "top_logprobs",
            "max_tokens": "max_tokens",
        }

    for source_key, target_key in field_map.items():
        value = parameters.get(source_key)
        if value is not None:
            merged[target_key] = value
    return merged


def _sse_payload(payload: dict[str, Any]) -> str:
    return f"data: {json.dumps(payload, ensure_ascii=False)}\n\n"


async def _iter_sse_events(response: httpx.Response) -> AsyncIterator[tuple[str | None, str]]:
    event_name: str | None = None
    data_lines: list[str] = []

    async for raw_line in response.aiter_lines():
        line = raw_line.rstrip("\r")
        if not line:
            if data_lines:
                yield event_name, "\n".join(data_lines)
                event_name = None
                data_lines = []
            continue

        if line.startswith(":"):
            continue
        if line.startswith("event:"):
            event_name = line[6:].strip()
            continue
        if line.startswith("data:"):
            data_lines.append(line[5:].lstrip())

    if data_lines:
        yield event_name, "\n".join(data_lines)


class ModelRegistryService:
    async def get_model(self, model_id: UUID) -> RegistryModelSummary:
        async with SessionLocal() as session:
            await ensure_default_project(session)
            project_id = await resolve_active_project_id(session)
            model = await _get_model_or_raise(session, model_id, project_id)

            provider_name = None
            if model.provider_id is not None:
                provider = await session.get(ModelProvider, model.provider_id)
                provider_name = provider.name if provider is not None else None

            return _serialize_model(model, provider_name)

    async def get_provider(self, provider_id: UUID) -> ModelProviderSummary:
        async with SessionLocal() as session:
            await ensure_default_project(session)
            project_id = await resolve_active_project_id(session)
            provider = await _get_provider_or_raise(session, provider_id, project_id)
            count_row = await session.execute(
                select(func.count(Model.id)).where(
                    Model.project_id == project_id,
                    Model.provider_id == provider.id,
                    Model.status != "deleted",
                )
            )
            return _serialize_provider(provider, count_row.scalar_one())

    async def list_providers(self) -> list[ModelProviderSummary]:
        async with SessionLocal() as session:
            await ensure_default_project(session)
            project_id = await resolve_active_project_id(session)
            rows = await session.execute(
                select(ModelProvider)
                .where(
                    ModelProvider.project_id == project_id,
                )
                .order_by(ModelProvider.updated_at.desc(), ModelProvider.name.asc())
            )
            providers = rows.scalars().all()

            count_rows = await session.execute(
                select(Model.provider_id, func.count(Model.id))
                .where(
                    Model.project_id == project_id,
                    Model.status != "deleted",
                    Model.provider_id.is_not(None),
                )
                .group_by(Model.provider_id)
            )
            count_map = {provider_id: count for provider_id, count in count_rows.all()}
            return [
                _serialize_provider(provider, count_map.get(provider.id, 0))
                for provider in providers
                if provider.status != "deleted"
            ]

    async def create_provider(self, payload: ModelProviderCreate) -> ModelProviderSummary:
        async with SessionLocal() as session:
            await ensure_default_project(session)
            project_id = await resolve_active_project_id(session)
            provider = ModelProvider(
                project_id=project_id,
                name=payload.name.strip(),
                provider_type=payload.provider_type,
                adapter=payload.adapter,
                api_format=payload.api_format,
                base_url=_normalize_base_url(payload.base_url),
                api_key=payload.api_key.strip() if payload.api_key else None,
                organization=payload.organization.strip() if payload.organization else None,
                description=payload.description.strip() if payload.description else None,
                status="active",
            )
            session.add(provider)
            try:
                await session.commit()
            except IntegrityError as exc:
                await session.rollback()
                raise ValueError("Provider 名称已存在，请更换后重试。") from exc
            await session.refresh(provider)
            return _serialize_provider(provider, 0)

    async def update_provider(
        self, provider_id: UUID, payload: ModelProviderUpdate
    ) -> ModelProviderSummary:
        async with SessionLocal() as session:
            project_id = await resolve_active_project_id(session)
            provider = await _get_provider_or_raise(session, provider_id, project_id)
            changes = payload.model_dump(exclude_unset=True)
            if "name" in changes and changes["name"] is not None:
                provider.name = changes["name"].strip()
            if "api_format" in changes and changes["api_format"] is not None:
                provider.api_format = changes["api_format"]
            if "base_url" in changes and changes["base_url"] is not None:
                provider.base_url = _normalize_base_url(changes["base_url"])
            if "api_key" in changes:
                provider.api_key = (
                    changes["api_key"].strip()
                    if isinstance(changes["api_key"], str) and changes["api_key"].strip()
                    else None
                )
            if "organization" in changes:
                provider.organization = (
                    changes["organization"].strip()
                    if isinstance(changes["organization"], str)
                    else None
                ) or None
            if "status" in changes and changes["status"] is not None:
                provider.status = changes["status"]
            if "description" in changes:
                provider.description = (
                    changes["description"].strip()
                    if isinstance(changes["description"], str)
                    else None
                ) or None
            try:
                await session.commit()
            except IntegrityError as exc:
                await session.rollback()
                raise ValueError("Provider 名称已存在，请更换后重试。") from exc
            await session.refresh(provider)

            count_row = await session.execute(
                select(func.count(Model.id)).where(
                    Model.project_id == project_id,
                    Model.provider_id == provider.id,
                    Model.status != "deleted",
                )
            )
            return _serialize_provider(provider, count_row.scalar_one())

    async def delete_provider(self, provider_id: UUID) -> None:
        async with SessionLocal() as session:
            project_id = await resolve_active_project_id(session)
            provider = await _get_provider_or_raise(session, provider_id, project_id)
            await session.execute(
                delete(Model).where(
                    Model.project_id == project_id,
                    Model.provider_id == provider.id,
                )
            )
            await session.delete(provider)
            await session.commit()

    async def sync_provider_models(self, provider_id: UUID) -> ModelProviderSyncResult:
        async with SessionLocal() as session:
            project_id = await resolve_active_project_id(session)
            provider = await _get_provider_or_raise(session, provider_id, project_id)
            remote_models = await _fetch_provider_models(provider)
            now = _now()

            rows = await session.execute(
                select(Model).where(
                    Model.project_id == project_id,
                    Model.provider_id == provider.id,
                )
            )
            existing_models = rows.scalars().all()
            existing_by_code = {
                model.model_code: model for model in existing_models if model.model_code
            }

            created_count = 0
            updated_count = 0
            seen_codes: set[str] = set()

            for remote_model in remote_models:
                model_code = str(remote_model["id"]).strip()
                seen_codes.add(model_code)
                capabilities = {
                    key: value
                    for key, value in remote_model.items()
                    if key != "id"
                }

                existing = existing_by_code.get(model_code)
                if existing is None:
                    session.add(
                        Model(
                            project_id=project_id,
                            provider_id=provider.id,
                            name=_provider_model_display_name(remote_model, model_code),
                            model_code=model_code,
                            vendor=provider.name,
                            source="provider-sync",
                            api_format=provider.api_format,
                            category="chat-model",
                            description=f"Synced from {provider.name}",
                            capabilities_json=capabilities,
                            is_provider_managed=True,
                            last_synced_at=now,
                            status="active",
                        )
                    )
                    created_count += 1
                    continue

                existing.name = _provider_model_display_name(remote_model, model_code)
                existing.vendor = provider.name
                existing.source = "provider-sync"
                existing.api_format = provider.api_format
                existing.category = existing.category or "chat-model"
                existing.description = existing.description or f"Synced from {provider.name}"
                existing.capabilities_json = capabilities
                existing.is_provider_managed = True
                existing.last_synced_at = now
                if existing.status == "deleted":
                    existing.status = "active"
                updated_count += 1

            for existing in existing_models:
                if existing.model_code and existing.model_code not in seen_codes:
                    existing.status = "inactive"
                    existing.last_synced_at = now

            provider.last_synced_at = now
            await session.commit()
            await session.refresh(provider)

            return ModelProviderSyncResult(
                provider_id=provider.id,
                provider_name=provider.name,
                synced_count=len(seen_codes),
                created_count=created_count,
                updated_count=updated_count,
                last_synced_at=provider.last_synced_at or now,
            )

    async def list_models(self) -> list[RegistryModelSummary]:
        async with SessionLocal() as session:
            await ensure_default_project(session)
            project_id = await resolve_active_project_id(session)
            rows = await session.execute(
                select(Model, ModelProvider.name)
                .outerjoin(ModelProvider, Model.provider_id == ModelProvider.id)
                .where(
                    Model.project_id == project_id,
                    Model.status != "deleted",
                )
                .order_by(Model.updated_at.desc(), Model.name.asc())
            )
            return [_serialize_model(model, provider_name) for model, provider_name in rows.all()]

    async def create_model(self, payload: RegistryModelCreate) -> RegistryModelSummary:
        async with SessionLocal() as session:
            await ensure_default_project(session)
            project_id = await resolve_active_project_id(session)
            provider_name: str | None = None
            if payload.provider_id is not None:
                provider = await _get_provider_or_raise(session, payload.provider_id, project_id)
                provider_name = provider.name

            model = Model(
                project_id=project_id,
                provider_id=payload.provider_id,
                name=payload.name.strip(),
                model_code=payload.model_code.strip(),
                vendor=(payload.vendor.strip() if payload.vendor else None) or provider_name,
                source=payload.source,
                api_format=payload.api_format,
                category=payload.category.strip() if payload.category else None,
                description=payload.description.strip() if payload.description else None,
                is_provider_managed=False,
                status="active",
            )
            session.add(model)
            try:
                await session.commit()
            except IntegrityError as exc:
                await session.rollback()
                raise ValueError("模型 ID 已存在，请检查 Provider 和模型编码。") from exc
            await session.refresh(model)
            return _serialize_model(model, provider_name)

    async def update_model(
        self, model_id: UUID, payload: RegistryModelUpdate
    ) -> RegistryModelSummary:
        async with SessionLocal() as session:
            project_id = await resolve_active_project_id(session)
            model = await _get_model_or_raise(session, model_id, project_id)
            changes = payload.model_dump(exclude_unset=True)
            provider_name = None

            if "provider_id" in changes:
                provider_id = changes["provider_id"]
                if provider_id is not None:
                    provider = await _get_provider_or_raise(session, provider_id, project_id)
                    provider_name = provider.name
                model.provider_id = provider_id
            elif model.provider_id is not None:
                provider = await session.get(ModelProvider, model.provider_id)
                provider_name = provider.name if provider is not None else None

            if "name" in changes and changes["name"] is not None:
                model.name = changes["name"].strip()
            if "model_code" in changes and changes["model_code"] is not None:
                model.model_code = changes["model_code"].strip()
            if "vendor" in changes:
                model.vendor = (
                    changes["vendor"].strip()
                    if isinstance(changes["vendor"], str)
                    else None
                ) or provider_name
            elif "provider_id" in changes:
                model.vendor = provider_name
            if "api_format" in changes and changes["api_format"] is not None:
                model.api_format = changes["api_format"]
            if "category" in changes:
                model.category = (
                    changes["category"].strip()
                    if isinstance(changes["category"], str)
                    else None
                ) or None
            if "status" in changes and changes["status"] is not None:
                model.status = changes["status"]
            if "description" in changes:
                model.description = (
                    changes["description"].strip()
                    if isinstance(changes["description"], str)
                    else None
                ) or None
            try:
                await session.commit()
            except IntegrityError as exc:
                await session.rollback()
                raise ValueError("模型 ID 已存在，请检查 Provider 和模型编码。") from exc
            await session.refresh(model)

            if model.provider_id is not None:
                provider = await session.get(ModelProvider, model.provider_id)
                provider_name = provider.name if provider is not None else None
            return _serialize_model(model, provider_name)

    async def delete_model(self, model_id: UUID) -> None:
        async with SessionLocal() as session:
            project_id = await resolve_active_project_id(session)
            model = await _get_model_or_raise(session, model_id, project_id)
            await session.delete(model)
            await session.commit()

    async def test_model(
        self, model_id: UUID, payload: RegistryModelTestRequest
    ) -> RegistryModelTestResponse:
        async with SessionLocal() as session:
            project_id = await resolve_active_project_id(session)
            model = await _get_model_or_raise(session, model_id, project_id)
            if not model.provider_id:
                raise ValueError("当前模型没有关联 Provider，暂不支持直接测试。")

            provider = await _get_provider_or_raise(session, model.provider_id, project_id)
            model_code = (model.model_code or "").strip()
            if not model_code:
                raise ValueError("当前模型缺少模型 ID，无法发起测试。")

            api_format = (model.api_format or provider.api_format or "chat-completions").strip()
            base_url = _normalize_base_url(provider.base_url)
            headers = _provider_request_headers(provider)
            headers["Content-Type"] = "application/json"

            if api_format == "responses":
                url = f"{base_url}/responses"
                request_body = {
                    "model": model_code,
                    "input": payload.prompt.strip(),
                    "max_output_tokens": 256,
                }
            else:
                url = f"{base_url}/chat/completions"
                request_body = {
                    "model": model_code,
                    "messages": [
                        {
                            "role": "system",
                            "content": "You are running a connectivity smoke test. Reply briefly."
                        },
                        {
                            "role": "user",
                            "content": payload.prompt.strip(),
                        },
                    ],
                    "temperature": 0.2,
                    "max_tokens": 256,
                }

            start = perf_counter()
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.post(url, headers=headers, json=request_body)
                response.raise_for_status()
                response_payload = response.json()
            latency_ms = int((perf_counter() - start) * 1000)

            if api_format == "responses":
                output_text = _extract_responses_text(response_payload)
            else:
                output_text = _extract_chat_completion_text(response_payload)

            return RegistryModelTestResponse(
                model_id=model.id,
                model_name=model.name,
                model_code=model_code,
                provider_id=provider.id,
                provider_name=provider.name,
                api_format=api_format,
                prompt=payload.prompt.strip(),
                output_text=output_text,
                latency_ms=latency_ms,
                request_id=response.headers.get("x-request-id")
                or response.headers.get("request-id")
                or response_payload.get("id"),
            )

    async def chat_model(
        self, model_id: UUID, payload: RegistryModelChatRequest
    ) -> RegistryModelChatResponse:
        async with SessionLocal() as session:
            project_id = await resolve_active_project_id(session)
            model = await _get_model_or_raise(session, model_id, project_id)
            if not model.provider_id:
                raise ValueError("当前模型没有关联 Provider，暂不支持对话。")

            provider = await _get_provider_or_raise(session, model.provider_id, project_id)
            model_code = (model.model_code or "").strip()
            if not model_code:
                raise ValueError("当前模型缺少模型 ID，无法发起对话。")

            messages = [
                {
                    "role": message.role,
                    "content": message.content.strip(),
                }
                for message in payload.messages
                if message.content.strip()
            ]
            if not messages:
                raise ValueError("请输入至少一条有效消息。")

            api_format = (model.api_format or provider.api_format or "chat-completions").strip()
            base_url = _normalize_base_url(provider.base_url)
            headers = _provider_request_headers(provider)
            headers["Content-Type"] = "application/json"

            reasoning_effort = _map_reasoning_effort(payload.reasoning_depth)

            if api_format == "responses":
                url = f"{base_url}/responses"
                request_body = {
                    "model": model_code,
                    "input": _responses_input_from_messages(messages),
                    "max_output_tokens": 2048,
                }
                if reasoning_effort and reasoning_effort != "none":
                    request_body["reasoning"] = {
                        "effort": reasoning_effort,
                        "summary": "auto",
                    }
                request_body = _merge_generation_parameters(
                    request_body,
                    payload.parameters,
                    api_format=api_format,
                )
            else:
                url = f"{base_url}/chat/completions"
                request_body = {
                    "model": model_code,
                    "messages": messages,
                    "temperature": 0.6,
                    "max_tokens": 2048,
                }
                if reasoning_effort and reasoning_effort != "none":
                    request_body["reasoning_effort"] = reasoning_effort
                request_body = _merge_generation_parameters(
                    request_body,
                    payload.parameters,
                    api_format=api_format,
                )

            start = perf_counter()
            async with httpx.AsyncClient(timeout=60.0) as client:
                response = await client.post(url, headers=headers, json=request_body)
                response.raise_for_status()
                response_payload = response.json()
            latency_ms = int((perf_counter() - start) * 1000)

            if api_format == "responses":
                output_text = _extract_responses_text(response_payload)
                reasoning_text = _extract_responses_reasoning_text(response_payload)
            else:
                output_text = _extract_chat_completion_text(response_payload)
                reasoning_text = _extract_chat_completion_reasoning_text(response_payload)

            input_tokens, output_tokens, total_tokens = _extract_usage_tokens(response_payload)

            return RegistryModelChatResponse(
                model_id=model.id,
                model_name=_serialize_model_name(model),
                model_code=model_code,
                provider_id=provider.id,
                provider_name=provider.name,
                api_format=api_format,
                output_text=output_text,
                reasoning_text=reasoning_text,
                latency_ms=latency_ms,
                request_id=response.headers.get("x-request-id")
                or response.headers.get("request-id")
                or response_payload.get("id"),
                input_tokens=input_tokens,
                output_tokens=output_tokens,
                total_tokens=total_tokens,
            )

    async def stream_chat_model(
        self, model_id: UUID, payload: RegistryModelChatRequest
    ) -> AsyncIterator[str]:
        async with SessionLocal() as session:
            project_id = await resolve_active_project_id(session)
            model = await _get_model_or_raise(session, model_id, project_id)
            if not model.provider_id:
                raise ValueError("当前模型没有关联 Provider，暂不支持对话。")

            provider = await _get_provider_or_raise(session, model.provider_id, project_id)
            model_code = (model.model_code or "").strip()
            if not model_code:
                raise ValueError("当前模型缺少模型 ID，无法发起对话。")

            messages = [
                {
                    "role": message.role,
                    "content": message.content.strip(),
                }
                for message in payload.messages
                if message.content.strip()
            ]
            if not messages:
                raise ValueError("请输入至少一条有效消息。")

            api_format = (model.api_format or provider.api_format or "chat-completions").strip()
            base_url = _normalize_base_url(provider.base_url)
            headers = _provider_request_headers(provider)
            headers["Content-Type"] = "application/json"
            reasoning_effort = _map_reasoning_effort(payload.reasoning_depth)
            model_name = _serialize_model_name(model)
            provider_name = provider.name
            provider_id = provider.id

        async def generator() -> AsyncIterator[str]:
            start_time = perf_counter()
            yielded_reasoning = False

            yield _sse_payload(
                {
                    "type": "start",
                    "model_name": model_name,
                    "model_code": model_code,
                    "provider_id": str(provider_id),
                    "provider_name": provider_name,
                    "api_format": api_format,
                    "reasoning_depth": payload.reasoning_depth,
                }
            )

            try:
                if api_format == "responses":
                    url = f"{base_url}/responses"
                    request_body: dict[str, Any] = {
                        "model": model_code,
                        "input": _responses_input_from_messages(messages),
                        "stream": True,
                        "max_output_tokens": 2048,
                    }
                    if reasoning_effort and reasoning_effort != "none":
                        request_body["reasoning"] = {
                            "effort": reasoning_effort,
                            "summary": "auto",
                        }
                    request_body = _merge_generation_parameters(
                        request_body,
                        payload.parameters,
                        api_format=api_format,
                    )
                else:
                    url = f"{base_url}/chat/completions"
                    request_body = {
                        "model": model_code,
                        "messages": messages,
                        "stream": True,
                        "stream_options": {"include_usage": True},
                        "temperature": 0.6,
                        "max_tokens": 2048,
                    }
                    if reasoning_effort and reasoning_effort != "none":
                        request_body["reasoning_effort"] = reasoning_effort
                    request_body = _merge_generation_parameters(
                        request_body,
                        payload.parameters,
                        api_format=api_format,
                    )

                async with httpx.AsyncClient(timeout=None) as client:
                    async with client.stream(
                        "POST", url, headers=headers, json=request_body
                    ) as response:
                        request_id = response.headers.get(
                            "x-request-id"
                        ) or response.headers.get("request-id")

                        if response.status_code >= 400:
                            sync_response = await self.chat_model(model_id, payload)
                            if sync_response.reasoning_text:
                                yielded_reasoning = True
                                yield _sse_payload(
                                    {
                                        "type": "reasoning_delta",
                                        "delta": sync_response.reasoning_text,
                                    }
                                )
                            yield _sse_payload(
                                {
                                    "type": "text_delta",
                                    "delta": sync_response.output_text,
                                }
                            )
                            yield _sse_payload(
                                {
                                    "type": "done",
                                    "latency_ms": sync_response.latency_ms,
                                    "request_id": sync_response.request_id,
                                    "input_tokens": sync_response.input_tokens,
                                    "output_tokens": sync_response.output_tokens,
                                    "total_tokens": sync_response.total_tokens,
                                    "reasoning_available": yielded_reasoning,
                                    "streaming_mode": "fallback",
                                }
                            )
                            return

                        usage_input_tokens: int | None = None
                        usage_output_tokens: int | None = None
                        usage_total_tokens: int | None = None

                        async for event_name, raw_data in _iter_sse_events(response):
                            if raw_data == "[DONE]":
                                break

                            payload_data = json.loads(raw_data)
                            payload_type = str(payload_data.get("type") or event_name or "")

                            if api_format == "responses":
                                if payload_type == "response.output_text.delta":
                                    delta = payload_data.get("delta")
                                    if isinstance(delta, str) and delta:
                                        yield _sse_payload(
                                            {
                                                "type": "text_delta",
                                                "delta": delta,
                                            }
                                        )
                                elif (
                                    "reasoning" in payload_type
                                    and payload_type.endswith(".delta")
                                ):
                                    delta = payload_data.get("delta")
                                    if isinstance(delta, str) and delta:
                                        yielded_reasoning = True
                                        yield _sse_payload(
                                            {
                                                "type": "reasoning_delta",
                                                "delta": delta,
                                            }
                                        )
                                elif payload_type == "response.completed":
                                    completed_response = payload_data.get("response")
                                    if isinstance(completed_response, dict):
                                        request_id = request_id or completed_response.get("id")
                                        (
                                            usage_input_tokens,
                                            usage_output_tokens,
                                            usage_total_tokens,
                                        ) = _extract_usage_tokens(completed_response)
                                        if not yielded_reasoning:
                                            reasoning_text = (
                                                _extract_responses_reasoning_text(
                                                    completed_response
                                                )
                                            )
                                            if reasoning_text:
                                                yielded_reasoning = True
                                                yield _sse_payload(
                                                    {
                                                        "type": "reasoning_delta",
                                                        "delta": reasoning_text,
                                                    }
                                                )
                            else:
                                choices = payload_data.get("choices")
                                if isinstance(choices, list) and choices:
                                    choice = choices[0] if isinstance(choices[0], dict) else {}
                                    delta_data = (
                                        choice.get("delta")
                                        if isinstance(choice, dict)
                                        else {}
                                    )
                                    if isinstance(delta_data, dict):
                                        content = delta_data.get("content")
                                        if isinstance(content, str) and content:
                                            yield _sse_payload(
                                                {
                                                    "type": "text_delta",
                                                    "delta": content,
                                                }
                                            )
                                        reasoning_delta = (
                                            _extract_text(delta_data.get("reasoning_content"))
                                            or _extract_text(delta_data.get("reasoning"))
                                            or _extract_text(delta_data.get("reasoning_text"))
                                        )
                                        if reasoning_delta:
                                            yielded_reasoning = True
                                            yield _sse_payload(
                                                {
                                                    "type": "reasoning_delta",
                                                    "delta": reasoning_delta,
                                                }
                                            )

                                (
                                    usage_input_tokens,
                                    usage_output_tokens,
                                    usage_total_tokens,
                                ) = _extract_usage_tokens(payload_data)

                        yield _sse_payload(
                            {
                                "type": "done",
                                "latency_ms": int((perf_counter() - start_time) * 1000),
                                "request_id": request_id,
                                "input_tokens": usage_input_tokens,
                                "output_tokens": usage_output_tokens,
                                "total_tokens": usage_total_tokens,
                                "reasoning_available": yielded_reasoning,
                                "streaming_mode": "upstream",
                            }
                        )
            except Exception as exc:
                yield _sse_payload({"type": "error", "message": str(exc)})

        return generator()
