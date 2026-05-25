from __future__ import annotations

import json
import re
from collections.abc import AsyncIterator
from datetime import UTC, datetime
from time import perf_counter
from typing import Any
from urllib.parse import quote
from uuid import UUID, uuid4

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
    RegistryModelDeploymentHints,
    RegistryModelHuggingFaceImport,
    RegistryModelHuggingFaceRevisionRequest,
    RegistryModelHuggingFaceRevisionResult,
    RegistryModelHuggingFaceSearchRequest,
    RegistryModelHuggingFaceSearchResult,
    RegistryModelObjectStorageImport,
    RegistryModelSummary,
    RegistryModelTestRequest,
    RegistryModelTestResponse,
    RegistryModelUpdate,
)
from nta_backend.services.system_config_service import load_system_huggingface_config

OBJECT_STORAGE_IMPORT_SOURCE = "object-storage-import"
HUGGINGFACE_IMPORT_SOURCE = "huggingface-import"
MAX_TENSOR_PARALLEL_HINT = 64


def _now() -> datetime:
    return datetime.now(UTC)


def _normalize_base_url(value: str) -> str:
    normalized = value.strip().rstrip("/")
    if normalized.endswith("/models"):
        return normalized[: -len("/models")]
    return normalized


def _normalize_api_format(value: str | None) -> str:
    normalized = (value or "").strip().lower()
    if normalized in {"responses", "openai-responses"}:
        return "responses"
    if normalized in {"google", "google-genai", "google-generativeai"}:
        return "google"
    return "chat-completions"


def _provider_type_for_api_format(api_format: str) -> str:
    if _normalize_api_format(api_format) == "google":
        return "google-generativeai"
    return "openai-compatible"


def _normalize_google_model_code(model_code: str) -> str:
    normalized = model_code.strip()
    if normalized.startswith("models/"):
        return normalized.removeprefix("models/")
    return normalized


def _normalize_google_request_url(base_url: str, model_code: str, *, stream: bool = False) -> str:
    normalized_base_url = _normalize_base_url(base_url)
    action = "streamGenerateContent?alt=sse" if stream else "generateContent"
    return f"{normalized_base_url}/models/{_normalize_google_model_code(model_code)}:{action}"


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


def _parse_object_storage_uri(source_uri: str) -> dict[str, str]:
    normalized = source_uri.strip()
    match = re.fullmatch(
        r"(?P<scheme>s3|cos)://(?P<bucket>[^/\s]+)/(?P<key>.+)",
        normalized,
        re.IGNORECASE,
    )
    if not match:
        raise ValueError("请输入有效的 s3://bucket/key 或 cos://bucket/key 对象存储路径。")

    scheme = match.group("scheme").lower()
    bucket = match.group("bucket").strip()
    object_key = match.group("key").strip().lstrip("/")
    if not bucket or not object_key:
        raise ValueError("对象存储路径需要包含 bucket 和对象 key。")

    return {
        "source_type": "cos" if scheme == "cos" else "object-storage",
        "source_uri": f"{scheme}://{bucket}/{object_key}",
        "bucket": bucket,
        "object_key": object_key,
    }


def _normalize_safetensors_import_target(parsed_uri: dict[str, str]) -> dict[str, str]:
    object_key = parsed_uri["object_key"]
    leaf_name = object_key.rstrip("/").rsplit("/", maxsplit=1)[-1]
    is_safetensors_file = leaf_name.lower().endswith(".safetensors")
    unsupported_file_suffixes = (
        ".bin",
        ".ckpt",
        ".gguf",
        ".gz",
        ".json",
        ".onnx",
        ".pt",
        ".pth",
        ".tar",
        ".txt",
        ".zip",
    )
    looks_like_directory = object_key.endswith("/") or (
        not is_safetensors_file and not leaf_name.lower().endswith(unsupported_file_suffixes)
    )

    if not is_safetensors_file and not looks_like_directory:
        raise ValueError(
            "当前仅支持导入 safetensors 模型文件或包含 safetensors checkpoint 的模型目录。"
        )

    normalized_key = object_key
    if looks_like_directory and not object_key.endswith("/"):
        normalized_key = f"{object_key}/"

    scheme = "cos" if parsed_uri["source_type"] == "cos" else "s3"
    return {
        **parsed_uri,
        "source_uri": f"{scheme}://{parsed_uri['bucket']}/{normalized_key}",
        "object_key": normalized_key,
        "target_type": "file" if is_safetensors_file else "directory",
    }


def _build_imported_model_code(name: str, prefix: str = "cos") -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", name.strip().lower()).strip("-")
    normalized_slug = slug[:72].strip("-") or "model"
    return f"{prefix}-{normalized_slug}-{uuid4().hex[:8]}"


def _strip_optional_text(value: str | None) -> str | None:
    if value is None:
        return None
    stripped = value.strip()
    return stripped or None


def _object_storage_import_metadata(model: Model) -> dict[str, str | None]:
    if not isinstance(model.capabilities_json, dict):
        return {}

    metadata = model.capabilities_json.get("object_storage_import")
    if not isinstance(metadata, dict):
        return {}

    def read_text(key: str) -> str | None:
        value = metadata.get(key)
        return value if isinstance(value, str) else None

    return {
        "source_type": read_text("source_type"),
        "source_uri": read_text("source_uri"),
        "bucket": read_text("bucket"),
        "object_key": read_text("object_key"),
    }


def _parse_huggingface_repo_id(raw_repo_id: str) -> tuple[str, str | None]:
    value = raw_repo_id.strip()
    revision: str | None = None

    if value.startswith("hf://"):
        value = value.removeprefix("hf://")
    elif value.startswith("https://huggingface.co/") or value.startswith("http://huggingface.co/"):
        value = value.split("huggingface.co/", maxsplit=1)[1]

    parts = [part for part in value.strip("/").split("/") if part]
    if "tree" in parts:
        tree_index = parts.index("tree")
        revision_parts = parts[tree_index + 1 :]
        parts = parts[:tree_index]
        revision = "/".join(revision_parts) if revision_parts else None

    if len(parts) not in {1, 2}:
        raise ValueError("请输入有效的 Hugging Face Repo ID，例如 Qwen/Qwen2.5-7B-Instruct。")

    repo_id = "/".join(parts)
    if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_.-]*(/[A-Za-z0-9][A-Za-z0-9_.-]*)?", repo_id):
        raise ValueError(
            "Hugging Face Repo ID 只能包含字母、数字、点、下划线、连字符和一个命名空间斜杠。"
        )

    return repo_id, revision


def _huggingface_source_uri(repo_id: str, revision: str) -> str:
    return f"hf://{repo_id}@{revision}"


def _huggingface_endpoint_url(endpoint_url: str | None = None) -> str:
    return (endpoint_url or "https://huggingface.co").rstrip("/")


def _huggingface_headers(token: str | None, *, accept_json: bool = True) -> dict[str, str]:
    headers = {"Accept": "application/json" if accept_json else "*/*"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    return headers


def _huggingface_error_message(response: httpx.Response) -> str:
    try:
        payload = response.json()
    except ValueError:
        return response.text.strip()

    if isinstance(payload, dict):
        for key in ("error", "message"):
            value = payload.get(key)
            if isinstance(value, str) and value.strip():
                return value.strip()
    return response.text.strip()


def _raise_huggingface_access_error(response: httpx.Response, *, has_token: bool) -> None:
    detail = _huggingface_error_message(response)
    suffix = f" Hugging Face 返回：{detail}" if detail else ""

    if response.status_code in {401, 403}:
        if has_token:
            raise ValueError(
                "HF Token 无效、已过期，或没有权限访问该模型；如果是 gated model，"
                f"请先在 Hugging Face 接受模型协议。{suffix}"
            )
        raise ValueError(f"未录入 HF Token 时只能录入公开模型；当前模型无法匿名访问。{suffix}")

    if response.status_code == 404:
        if has_token:
            raise ValueError(f"模型不存在，或当前 HF Token 对该模型不可见。{suffix}")
        raise ValueError(
            f"模型不存在，或它不是公开模型。未录入 HF Token 时只能录入公开模型。{suffix}"
        )

    raise ValueError(f"Hugging Face 权限校验失败：HTTP {response.status_code}。{suffix}")


async def _verify_huggingface_access(
    *,
    repo_id: str,
    revision: str,
    token: str | None,
    endpoint_url: str | None = None,
    require_adapter_config: bool = False,
) -> list[str]:
    endpoint_url = _huggingface_endpoint_url(endpoint_url)
    encoded_repo_id = quote(repo_id, safe="/")
    encoded_revision = quote(revision, safe="")
    api_url = f"{endpoint_url}/api/models/{encoded_repo_id}/revision/{encoded_revision}"

    async with httpx.AsyncClient(timeout=20.0, follow_redirects=False) as client:
        response = await client.get(
            api_url,
            headers=_huggingface_headers(token),
        )
        if response.status_code >= 400:
            _raise_huggingface_access_error(response, has_token=bool(token))

        payload = response.json()
        siblings = payload.get("siblings") if isinstance(payload, dict) else None
        if not isinstance(siblings, list):
            raise ValueError("Hugging Face 模型元信息缺少文件列表，无法确认模型格式。")

        safetensor_files = sorted(
            item["rfilename"]
            for item in siblings
            if isinstance(item, dict)
            and isinstance(item.get("rfilename"), str)
            and item["rfilename"].lower().endswith(".safetensors")
        )
        if not safetensor_files:
            raise ValueError("该 Hugging Face 仓库未找到 safetensors 权重文件。")
        if require_adapter_config and not any(
            isinstance(item, dict)
            and str(item.get("rfilename") or "").lower() == "adapter_config.json"
            for item in siblings
        ):
            raise ValueError("LoRA adapter 仓库需要包含 adapter_config.json。")

        sample_file = quote(safetensor_files[0], safe="/")
        resolve_url = f"{endpoint_url}/{encoded_repo_id}/resolve/{encoded_revision}/{sample_file}"
        access_response = await client.head(
            resolve_url,
            headers=_huggingface_headers(token, accept_json=False),
        )
        if access_response.status_code == 405:
            access_response = await client.get(
                resolve_url,
                headers={
                    **_huggingface_headers(token, accept_json=False),
                    "Range": "bytes=0-0",
                },
            )
        if access_response.status_code not in {200, 206, 302, 303, 307, 308}:
            _raise_huggingface_access_error(access_response, has_token=bool(token))

        return safetensor_files


def _int_or_none(value: Any) -> int | None:
    if isinstance(value, bool):
        return None
    if isinstance(value, int | float):
        return int(value)
    if isinstance(value, str) and value.strip().isdigit():
        return int(value.strip())
    return None


def _positive_int_or_none(value: Any) -> int | None:
    parsed = _int_or_none(value)
    return parsed if parsed is not None and parsed > 0 else None


def _str_or_none(value: Any) -> str | None:
    if isinstance(value, str) and value.strip():
        return value.strip()
    return None


def _string_list(value: Any) -> list[str]:
    if isinstance(value, str) and value.strip():
        return [value.strip()]
    if not isinstance(value, list):
        return []
    return [item.strip() for item in value if isinstance(item, str) and item.strip()]


def _model_config_text_section(config: dict[str, Any]) -> dict[str, Any]:
    if _positive_int_or_none(config.get("num_attention_heads") or config.get("n_head")):
        return config
    for key in ("text_config", "llm_config", "language_config"):
        nested = config.get(key)
        if isinstance(nested, dict) and _positive_int_or_none(
            nested.get("num_attention_heads") or nested.get("n_head")
        ):
            return nested
    return config


def _first_positive_int(config: dict[str, Any], keys: tuple[str, ...]) -> int | None:
    for key in keys:
        value = _positive_int_or_none(config.get(key))
        if value is not None:
            return value
    return None


def _tensor_parallel_options(*values: int | None) -> list[int]:
    divisibility_values = [value for value in values if value is not None and value > 0]
    if not divisibility_values:
        return []
    upper_bound = min(min(divisibility_values), MAX_TENSOR_PARALLEL_HINT)
    return [
        candidate
        for candidate in range(1, upper_bound + 1)
        if all(value % candidate == 0 for value in divisibility_values)
    ]


def _model_config_deployment_hints(config: dict[str, Any]) -> RegistryModelDeploymentHints:
    text_config = _model_config_text_section(config)
    num_attention_heads = _first_positive_int(
        text_config,
        ("num_attention_heads", "n_head", "num_heads", "n_heads"),
    )
    num_key_value_heads = _first_positive_int(
        text_config,
        ("num_key_value_heads", "num_kv_heads", "n_kv_heads"),
    )
    vocab_size = _first_positive_int(
        text_config,
        ("vocab_size", "padded_vocab_size"),
    )
    max_model_len = _first_positive_int(
        text_config,
        (
            "max_model_len",
            "max_position_embeddings",
            "model_max_length",
            "seq_length",
            "n_positions",
        ),
    )
    return RegistryModelDeploymentHints(
        model_type=_str_or_none(text_config.get("model_type") or config.get("model_type")),
        architectures=_string_list(config.get("architectures") or text_config.get("architectures")),
        num_attention_heads=num_attention_heads,
        num_key_value_heads=num_key_value_heads,
        vocab_size=vocab_size,
        max_model_len=max_model_len,
        tensor_parallel_size_options=_tensor_parallel_options(num_attention_heads, vocab_size),
    )


async def _fetch_huggingface_model_config(
    *,
    repo_id: str,
    revision: str,
    token: str | None,
    endpoint_url: str | None = None,
) -> dict[str, Any]:
    endpoint_url = _huggingface_endpoint_url(endpoint_url)
    encoded_repo_id = quote(repo_id, safe="/")
    encoded_revision = quote(revision, safe="")
    config_url = f"{endpoint_url}/{encoded_repo_id}/resolve/{encoded_revision}/config.json"
    async with httpx.AsyncClient(timeout=20.0, follow_redirects=True) as client:
        response = await client.get(
            config_url,
            headers=_huggingface_headers(token, accept_json=False),
        )
        if response.status_code >= 400:
            _raise_huggingface_access_error(response, has_token=bool(token))
        try:
            payload = response.json()
        except json.JSONDecodeError as exc:
            raise ValueError(
                "Hugging Face config.json 不是有效 JSON，无法计算 TP 可选值。"
            ) from exc
    if not isinstance(payload, dict):
        raise ValueError("Hugging Face config.json 响应格式不正确，无法计算 TP 可选值。")
    return payload


def _read_object_storage_model_config(parsed_uri: dict[str, str]) -> dict[str, Any] | None:
    object_key = parsed_uri["object_key"]
    if parsed_uri.get("target_type") == "directory":
        config_key = f"{object_key.rstrip('/')}/config.json"
    else:
        parent = object_key.rsplit("/", maxsplit=1)[0] if "/" in object_key else ""
        config_key = f"{parent}/config.json" if parent else "config.json"

    try:
        from nta_backend.core.object_store import get_object_bytes

        payload = get_object_bytes(parsed_uri["bucket"], config_key)
    except FileNotFoundError:
        return None
    except Exception:
        return None

    try:
        decoded = payload.body.decode("utf-8")
        config = json.loads(decoded)
    except (UnicodeDecodeError, json.JSONDecodeError):
        return None
    return config if isinstance(config, dict) else None


def _deployment_hints_from_import_metadata(model: Model) -> RegistryModelDeploymentHints | None:
    if not isinstance(model.capabilities_json, dict):
        return None
    for metadata_key in ("huggingface_import", "object_storage_import"):
        metadata = model.capabilities_json.get(metadata_key)
        if not isinstance(metadata, dict):
            continue
        hints_payload = metadata.get("deployment_hints")
        if not isinstance(hints_payload, dict):
            continue
        try:
            return RegistryModelDeploymentHints.model_validate(hints_payload)
        except ValueError:
            continue
    return None


def _artifact_type_from_import_metadata(model: Model) -> str | None:
    if not isinstance(model.capabilities_json, dict):
        return None
    for metadata_key in ("huggingface_import", "object_storage_import"):
        metadata = model.capabilities_json.get(metadata_key)
        if not isinstance(metadata, dict):
            continue
        artifact_type = metadata.get("artifact_type")
        if isinstance(artifact_type, str) and artifact_type.strip():
            return artifact_type.strip()
    return None


def _is_huggingface_gated(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        return value.strip().lower() not in {"", "false", "none", "no"}
    return bool(value)


def _huggingface_revision_results(
    payload: dict[str, Any],
) -> list[RegistryModelHuggingFaceRevisionResult]:
    result: list[RegistryModelHuggingFaceRevisionResult] = []
    seen: set[str] = set()
    collections = (
        ("branches", "branch"),
        ("tags", "tag"),
        ("converts", "convert"),
    )
    for payload_key, kind in collections:
        items = payload.get(payload_key)
        if not isinstance(items, list):
            continue
        for item in items:
            if not isinstance(item, dict):
                continue
            name = _str_or_none(item.get("name"))
            if not name or name in seen:
                continue
            seen.add(name)
            result.append(
                RegistryModelHuggingFaceRevisionResult(
                    name=name,
                    kind=kind,
                    ref=_str_or_none(item.get("ref")),
                    target_commit=_str_or_none(item.get("targetCommit")),
                )
            )
    return result


def _huggingface_import_metadata(model: Model) -> dict[str, str | None]:
    if not isinstance(model.capabilities_json, dict):
        return {}

    metadata = model.capabilities_json.get("huggingface_import")
    if not isinstance(metadata, dict):
        return {}

    def read_text(key: str) -> str | None:
        value = metadata.get(key)
        return value if isinstance(value, str) else None

    return {
        "source_type": read_text("source_type"),
        "source_uri": read_text("source_uri"),
        "repo_id": read_text("repo_id"),
        "revision": read_text("revision"),
    }


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
    import_metadata = _object_storage_import_metadata(model)
    huggingface_metadata = _huggingface_import_metadata(model)
    return RegistryModelSummary(
        id=model.id,
        name=_serialize_model_name(model),
        model_code=model.model_code,
        vendor=model.vendor,
        source=model.source,
        api_format=model.api_format,
        base_model=model.base_model,
        category=model.category,
        description=model.description,
        import_source_type=import_metadata.get("source_type")
        or huggingface_metadata.get("source_type"),
        import_source_uri=import_metadata.get("source_uri")
        or huggingface_metadata.get("source_uri"),
        import_bucket=import_metadata.get("bucket"),
        import_object_key=import_metadata.get("object_key"),
        import_repo_id=huggingface_metadata.get("repo_id"),
        import_revision=huggingface_metadata.get("revision"),
        artifact_type=_artifact_type_from_import_metadata(model),
        deployment_hints=_deployment_hints_from_import_metadata(model),
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
    api_format = _normalize_api_format(provider.api_format)
    remote_models: list[dict[str, Any]] = []
    page_token: str | None = None

    async with httpx.AsyncClient(timeout=20.0) as client:
        while True:
            params = {"pageToken": page_token} if api_format == "google" and page_token else None
            response = await client.get(url, headers=headers, params=params)
            response.raise_for_status()
            payload = response.json()

            if api_format == "google":
                models = payload.get("models")
                if not isinstance(models, list):
                    raise ValueError("Google `/models` response is invalid")
                remote_models.extend(_google_remote_models(models))
                page_token = payload.get("nextPageToken")
                if not isinstance(page_token, str) or not page_token:
                    break
                continue

            data = payload.get("data")
            if not isinstance(data, list):
                raise ValueError("Provider `/models` response is invalid")
            remote_models.extend(
                item for item in data if isinstance(item, dict) and item.get("id")
            )
            break

    return remote_models


def _provider_request_headers(provider: ModelProvider) -> dict[str, str]:
    headers: dict[str, str] = {"Accept": "application/json"}
    normalized_api_format = _normalize_api_format(provider.api_format)
    if provider.api_key:
        if normalized_api_format == "google":
            headers["x-goog-api-key"] = provider.api_key
        else:
            headers["Authorization"] = f"Bearer {provider.api_key}"
    if provider.organization and normalized_api_format != "google":
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


def _google_remote_models(models: list[dict[str, Any]]) -> list[dict[str, Any]]:
    normalized_models: list[dict[str, Any]] = []
    for model in models:
        raw_name = model.get("name")
        if not isinstance(raw_name, str) or not raw_name.strip():
            continue
        model_code = _normalize_google_model_code(raw_name)
        if not model_code:
            continue
        normalized_models.append(
            {
                **model,
                "id": model_code,
                "name": model.get("displayName") or model_code,
                "google_name": raw_name,
            }
        )
    return normalized_models


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


def _extract_google_text(payload: dict[str, Any]) -> str:
    candidates = payload.get("candidates")
    if not isinstance(candidates, list) or not candidates:
        raise ValueError("Google generateContent response is invalid")

    content = candidates[0].get("content") if isinstance(candidates[0], dict) else None
    if not isinstance(content, dict):
        raise ValueError("Google generateContent response did not include content")

    parts = content.get("parts")
    if not isinstance(parts, list):
        raise ValueError("Google generateContent response did not include parts")

    chunks: list[str] = []
    for part in parts:
        if not isinstance(part, dict):
            continue
        text = _extract_text(part.get("text"))
        if text:
            chunks.append(text)

    joined = "\n".join(chunk for chunk in chunks if chunk).strip()
    if not joined:
        raise ValueError("Google generateContent response did not include text output")
    return joined


def _extract_google_stream_text(payload: dict[str, Any]) -> str | None:
    candidates = payload.get("candidates")
    if not isinstance(candidates, list) or not candidates:
        return None

    content = candidates[0].get("content") if isinstance(candidates[0], dict) else None
    if not isinstance(content, dict):
        return None

    parts = content.get("parts")
    if not isinstance(parts, list):
        return None

    chunks: list[str] = []
    for part in parts:
        if not isinstance(part, dict):
            continue
        text = _extract_text(part.get("text"))
        if text:
            chunks.append(text)
    joined = "\n".join(chunk for chunk in chunks if chunk).strip()
    return joined or None


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


def _extract_google_reasoning_text(payload: dict[str, Any]) -> str | None:
    candidates = payload.get("candidates")
    if not isinstance(candidates, list) or not candidates:
        return None

    content = candidates[0].get("content") if isinstance(candidates[0], dict) else None
    if not isinstance(content, dict):
        return None

    parts = content.get("parts")
    if not isinstance(parts, list):
        return None

    chunks: list[str] = []
    for part in parts:
        if not isinstance(part, dict):
            continue
        if part.get("thought") is True:
            thought_text = _extract_text(part.get("text"))
            if thought_text:
                chunks.append(thought_text)

    joined = "\n\n".join(chunk for chunk in chunks if chunk).strip()
    return joined or None


def _extract_usage_tokens(payload: dict[str, Any]) -> tuple[int | None, int | None, int | None]:
    usage = payload.get("usage")
    usage_metadata = payload.get("usageMetadata")
    if isinstance(usage, dict):
        input_tokens = usage.get("input_tokens") or usage.get("prompt_tokens")
        output_tokens = usage.get("output_tokens") or usage.get("completion_tokens")
        total_tokens = usage.get("total_tokens")
    elif isinstance(usage_metadata, dict):
        input_tokens = usage_metadata.get("promptTokenCount")
        output_tokens = usage_metadata.get("candidatesTokenCount")
        total_tokens = usage_metadata.get("totalTokenCount")
    else:
        return None, None, None

    return (
        int(input_tokens) if isinstance(input_tokens, int | float) else None,
        int(output_tokens) if isinstance(output_tokens, int | float) else None,
        int(total_tokens) if isinstance(total_tokens, int | float) else None,
    )


def _google_payload_from_messages(
    messages: list[dict[str, str]],
    *,
    max_output_tokens: int,
    temperature: float | None = None,
    parameters: dict[str, Any] | None = None,
) -> dict[str, Any]:
    system_messages: list[str] = []
    contents: list[dict[str, Any]] = []

    for message in messages:
        role = message["role"]
        content = message["content"].strip()
        if not content:
            continue
        if role == "system":
            system_messages.append(content)
            continue
        contents.append(
            {
                "role": "model" if role == "assistant" else "user",
                "parts": [{"text": content}],
            }
        )

    if not contents:
        raise ValueError("Google generateContent 请求至少需要一条 user/assistant 消息。")

    payload: dict[str, Any] = {
        "contents": contents,
        "generationConfig": {
            "maxOutputTokens": max_output_tokens,
        },
    }
    if temperature is not None:
        payload["generationConfig"]["temperature"] = temperature
    if system_messages:
        payload["systemInstruction"] = {
            "parts": [{"text": "\n\n".join(system_messages)}]
        }

    return _merge_generation_parameters(
        payload,
        parameters,
        api_format="google",
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
    normalized_api_format = _normalize_api_format(api_format)
    if normalized_api_format == "responses":
        field_map = {
            "temperature": "temperature",
            "top_p": "top_p",
            "frequency_penalty": "frequency_penalty",
            "stop": "stop",
            "max_tokens": "max_output_tokens",
            "max_output_tokens": "max_output_tokens",
        }
    elif normalized_api_format == "google":
        field_map = {
            "temperature": "temperature",
            "top_p": "topP",
            "stop": "stopSequences",
            "max_tokens": "maxOutputTokens",
            "max_output_tokens": "maxOutputTokens",
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
            if normalized_api_format == "google":
                generation_config = dict(merged.get("generationConfig") or {})
                generation_config[target_key] = value
                merged["generationConfig"] = generation_config
            else:
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
                provider_type=_provider_type_for_api_format(payload.api_format),
                adapter=payload.adapter,
                api_format=_normalize_api_format(payload.api_format),
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
                provider.api_format = _normalize_api_format(changes["api_format"])
                provider.provider_type = _provider_type_for_api_format(provider.api_format)
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
                api_format=_normalize_api_format(payload.api_format),
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

    async def search_huggingface_models(
        self, payload: RegistryModelHuggingFaceSearchRequest
    ) -> list[RegistryModelHuggingFaceSearchResult]:
        query = payload.query.strip()
        explicit_token = _strip_optional_text(payload.hf_token)
        async with SessionLocal() as session:
            hf_config = await load_system_huggingface_config(session)
        token = explicit_token or hf_config.get("token")
        endpoint_url = hf_config.get("endpoint_url")
        params = {
            "search": query,
            "limit": str(min(payload.limit * 3, 50)),
            "sort": "downloads",
            "direction": "-1",
            "full": "false",
        }
        async with httpx.AsyncClient(timeout=20.0) as client:
            response = await client.get(
                f"{_huggingface_endpoint_url(endpoint_url)}/api/models",
                headers=_huggingface_headers(token),
                params=params,
            )
            if response.status_code >= 400:
                _raise_huggingface_access_error(response, has_token=bool(token))
            payload_json = response.json()

        if not isinstance(payload_json, list):
            raise ValueError("Hugging Face 搜索响应格式不正确。")

        results: list[RegistryModelHuggingFaceSearchResult] = []
        seen_repo_ids: set[str] = set()
        for item in payload_json:
            if not isinstance(item, dict):
                continue
            repo_id = _str_or_none(item.get("id") or item.get("modelId"))
            if not repo_id or repo_id in seen_repo_ids:
                continue
            seen_repo_ids.add(repo_id)

            tags = [tag for tag in item.get("tags", []) if isinstance(tag, str) and tag.strip()][
                :12
            ]
            if "safetensors" not in {tag.lower() for tag in tags}:
                continue
            results.append(
                RegistryModelHuggingFaceSearchResult(
                    repo_id=repo_id,
                    author=_str_or_none(item.get("author")),
                    pipeline_tag=_str_or_none(item.get("pipeline_tag")),
                    library_name=_str_or_none(item.get("library_name")),
                    downloads=_int_or_none(item.get("downloads")),
                    likes=_int_or_none(item.get("likes")),
                    is_private=bool(item.get("private")),
                    is_gated=_is_huggingface_gated(item.get("gated")),
                    tags=tags,
                    last_modified=_str_or_none(item.get("lastModified")),
                )
            )
            if len(results) >= payload.limit:
                break

        return results

    async def list_huggingface_revisions(
        self, payload: RegistryModelHuggingFaceRevisionRequest
    ) -> list[RegistryModelHuggingFaceRevisionResult]:
        repo_id, _ = _parse_huggingface_repo_id(payload.repo_id)
        async with SessionLocal() as session:
            hf_config = await load_system_huggingface_config(session)
        token = hf_config.get("token")
        endpoint_url = _huggingface_endpoint_url(hf_config.get("endpoint_url"))
        encoded_repo_id = quote(repo_id, safe="/")
        async with httpx.AsyncClient(timeout=20.0) as client:
            response = await client.get(
                f"{endpoint_url}/api/models/{encoded_repo_id}/refs",
                headers=_huggingface_headers(token),
            )
            if response.status_code >= 400:
                _raise_huggingface_access_error(response, has_token=bool(token))
            payload_json = response.json()

        if not isinstance(payload_json, dict):
            raise ValueError("Hugging Face Revision 响应格式不正确。")

        revisions = _huggingface_revision_results(payload_json)
        if not revisions:
            raise ValueError("该 Hugging Face 仓库没有可用 Revision。")
        return revisions

    async def refresh_model_deployment_hints(self, model_id: UUID) -> RegistryModelSummary:
        async with SessionLocal() as session:
            await ensure_default_project(session)
            project_id = await resolve_active_project_id(session)
            model = await _get_model_or_raise(session, model_id, project_id)
            capabilities = dict(model.capabilities_json or {})

            huggingface_metadata = capabilities.get("huggingface_import")
            if isinstance(huggingface_metadata, dict):
                hf_config = await load_system_huggingface_config(session)
                token = _str_or_none(huggingface_metadata.get("token")) or hf_config.get("token")
                endpoint_url = hf_config.get("endpoint_url")
                repo_id = _str_or_none(huggingface_metadata.get("repo_id"))
                revision = _str_or_none(huggingface_metadata.get("revision")) or "main"
                if not repo_id:
                    raise ValueError("Hugging Face 模型缺少 repo_id，无法读取 config.json。")
                config = await _fetch_huggingface_model_config(
                    repo_id=repo_id,
                    revision=revision,
                    token=token,
                    endpoint_url=endpoint_url,
                )
                updated_metadata = dict(huggingface_metadata)
                updated_metadata["deployment_hints"] = _model_config_deployment_hints(
                    config
                ).model_dump(exclude_none=True)
                capabilities["huggingface_import"] = updated_metadata
            else:
                object_storage_metadata = capabilities.get("object_storage_import")
                if not isinstance(object_storage_metadata, dict):
                    raise ValueError("只有 Hugging Face 或对象存储导入模型支持读取 config.json。")
                config = _read_object_storage_model_config(
                    {key: str(value) for key, value in object_storage_metadata.items()}
                )
                if config is None:
                    raise ValueError("对象存储模型目录未找到可读取的 config.json。")
                updated_metadata = dict(object_storage_metadata)
                updated_metadata["deployment_hints"] = _model_config_deployment_hints(
                    config
                ).model_dump(exclude_none=True)
                capabilities["object_storage_import"] = updated_metadata

            model.capabilities_json = capabilities
            await session.commit()
            await session.refresh(model)
            provider_name = None
            if model.provider_id is not None:
                provider = await session.get(ModelProvider, model.provider_id)
                provider_name = provider.name if provider else None
            return _serialize_model(model, provider_name)

    async def import_model_from_object_storage(
        self, payload: RegistryModelObjectStorageImport
    ) -> RegistryModelSummary:
        parsed_uri = _normalize_safetensors_import_target(
            _parse_object_storage_uri(payload.source_uri)
        )
        model_code = _build_imported_model_code(payload.name)
        imported_at = _now()
        is_lora_adapter = payload.artifact_type == "lora_adapter"
        model_config = None if is_lora_adapter else _read_object_storage_model_config(parsed_uri)
        deployment_hints = (
            _model_config_deployment_hints(model_config).model_dump(exclude_none=True)
            if model_config is not None
            else None
        )

        async with SessionLocal() as session:
            await ensure_default_project(session)
            project_id = await resolve_active_project_id(session)

            model = Model(
                project_id=project_id,
                provider_id=None,
                name=payload.name.strip(),
                model_code=model_code,
                vendor="对象存储",
                source=OBJECT_STORAGE_IMPORT_SOURCE,
                api_format=None,
                base_model=payload.base_model.strip(),
                category="文本生成",
                description=_strip_optional_text(payload.description),
                capabilities_json={
                    "object_storage_import": {
                        **parsed_uri,
                        "artifact_type": payload.artifact_type,
                        "artifact_format": "safetensors",
                        **(
                            {"deployment_hints": deployment_hints}
                            if deployment_hints is not None
                            else {}
                        ),
                        "imported_at": imported_at.isoformat(),
                    }
                },
                is_provider_managed=False,
                status="active",
            )
            session.add(model)
            try:
                await session.commit()
            except IntegrityError as exc:
                await session.rollback()
                raise ValueError("模型 ID 已存在，请更换后重试。") from exc
            await session.refresh(model)
            return _serialize_model(model, None)

    async def import_model_from_huggingface(
        self, payload: RegistryModelHuggingFaceImport
    ) -> RegistryModelSummary:
        repo_id, revision_from_uri = _parse_huggingface_repo_id(payload.repo_id)
        revision = (payload.revision or revision_from_uri or "main").strip() or "main"
        explicit_hf_token = _strip_optional_text(payload.hf_token)
        model_code = _build_imported_model_code(payload.name, prefix="hf")
        imported_at = _now()

        async with SessionLocal() as session:
            await ensure_default_project(session)
            project_id = await resolve_active_project_id(session)
            hf_config = await load_system_huggingface_config(session)
            inherited_hf_token = hf_config.get("token")
            endpoint_url = hf_config.get("endpoint_url")
            hf_token = explicit_hf_token or inherited_hf_token
            safetensor_files = await _verify_huggingface_access(
                repo_id=repo_id,
                revision=revision,
                token=hf_token,
                endpoint_url=endpoint_url,
                require_adapter_config=payload.artifact_type == "lora_adapter",
            )
            deployment_hints = None
            if payload.artifact_type != "lora_adapter":
                model_config = await _fetch_huggingface_model_config(
                    repo_id=repo_id,
                    revision=revision,
                    token=hf_token,
                    endpoint_url=endpoint_url,
                )
                deployment_hints = _model_config_deployment_hints(model_config).model_dump(
                    exclude_none=True
                )

            model = Model(
                project_id=project_id,
                provider_id=None,
                name=payload.name.strip(),
                model_code=model_code,
                vendor="Hugging Face",
                source=HUGGINGFACE_IMPORT_SOURCE,
                api_format=None,
                base_model=payload.base_model.strip(),
                category="文本生成",
                description=_strip_optional_text(payload.description),
                capabilities_json={
                    "huggingface_import": {
                        "source_type": "huggingface",
                        "source_uri": _huggingface_source_uri(repo_id, revision),
                        "repo_id": repo_id,
                        "revision": revision,
                        "repo_type": "model",
                        "artifact_type": payload.artifact_type,
                        "artifact_format": "safetensors",
                        "safetensors_count": str(len(safetensor_files)),
                        **(
                            {"deployment_hints": deployment_hints}
                            if deployment_hints is not None
                            else {}
                        ),
                        **({"token": explicit_hf_token} if explicit_hf_token else {}),
                        **(
                            {"token_source": "system"}
                            if not explicit_hf_token and inherited_hf_token
                            else {}
                        ),
                        "imported_at": imported_at.isoformat(),
                    }
                },
                is_provider_managed=False,
                status="active",
            )
            session.add(model)
            try:
                await session.commit()
            except IntegrityError as exc:
                await session.rollback()
                raise ValueError("模型 ID 已存在，请更换后重试。") from exc
            await session.refresh(model)
            return _serialize_model(model, None)

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
                    changes["vendor"].strip() if isinstance(changes["vendor"], str) else None
                ) or provider_name
            elif "provider_id" in changes:
                model.vendor = provider_name
            if "api_format" in changes and changes["api_format"] is not None:
                model.api_format = _normalize_api_format(changes["api_format"])
            if "category" in changes:
                model.category = (
                    changes["category"].strip() if isinstance(changes["category"], str) else None
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

            api_format = _normalize_api_format(
                model.api_format or provider.api_format or "chat-completions"
            )
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
            elif api_format == "google":
                url = _normalize_google_request_url(base_url, model_code)
                request_body = _google_payload_from_messages(
                    [
                        {
                            "role": "system",
                            "content": "You are running a connectivity smoke test. Reply briefly.",
                        },
                        {
                            "role": "user",
                            "content": payload.prompt.strip(),
                        },
                    ],
                    max_output_tokens=256,
                    temperature=0.2,
                )
            else:
                url = f"{base_url}/chat/completions"
                request_body = {
                    "model": model_code,
                    "messages": [
                        {
                            "role": "system",
                            "content": "You are running a connectivity smoke test. Reply briefly.",
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
            elif api_format == "google":
                output_text = _extract_google_text(response_payload)
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

            api_format = _normalize_api_format(
                model.api_format or provider.api_format or "chat-completions"
            )
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
            elif api_format == "google":
                url = _normalize_google_request_url(base_url, model_code)
                request_body = _google_payload_from_messages(
                    messages,
                    max_output_tokens=2048,
                    temperature=0.6,
                    parameters=payload.parameters,
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
            elif api_format == "google":
                output_text = _extract_google_text(response_payload)
                reasoning_text = _extract_google_reasoning_text(response_payload)
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

            api_format = _normalize_api_format(
                model.api_format or provider.api_format or "chat-completions"
            )
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
                elif api_format == "google":
                    url = _normalize_google_request_url(base_url, model_code, stream=True)
                    request_body = _google_payload_from_messages(
                        messages,
                        max_output_tokens=2048,
                        temperature=0.6,
                        parameters=payload.parameters,
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
                        request_id = response.headers.get("x-request-id") or response.headers.get(
                            "request-id"
                        )

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
                                elif "reasoning" in payload_type and payload_type.endswith(
                                    ".delta"
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
                                            reasoning_text = _extract_responses_reasoning_text(
                                                completed_response
                                            )
                                            if reasoning_text:
                                                yielded_reasoning = True
                                                yield _sse_payload(
                                                    {
                                                        "type": "reasoning_delta",
                                                        "delta": reasoning_text,
                                                    }
                                                )
                            elif api_format == "google":
                                delta = _extract_google_stream_text(payload_data)
                                if delta:
                                    yield _sse_payload(
                                        {
                                            "type": "text_delta",
                                            "delta": delta,
                                        }
                                    )
                                reasoning_delta = _extract_google_reasoning_text(payload_data)
                                if reasoning_delta:
                                    yielded_reasoning = True
                                    yield _sse_payload(
                                        {
                                            "type": "reasoning_delta",
                                            "delta": reasoning_delta,
                                        }
                                    )
                            else:
                                choices = payload_data.get("choices")
                                if isinstance(choices, list) and choices:
                                    choice = choices[0] if isinstance(choices[0], dict) else {}
                                    delta_data = (
                                        choice.get("delta") if isinstance(choice, dict) else {}
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
