from __future__ import annotations

import re
from datetime import UTC, datetime
from typing import Any
from uuid import UUID

import httpx
from sqlalchemy import select

from nta_backend.core.auth_context import get_current_user_id
from nta_backend.core.config import get_settings
from nta_backend.core.db import SessionLocal
from nta_backend.core.project_context import resolve_active_project_id
from nta_backend.models.modeling import Endpoint, Model
from nta_backend.schemas.model_deployment import (
    AgentDeploymentSpec,
    AgentDeploymentStatus,
    DeployModelRequest,
    EngineSpec,
    HuggingFaceSource,
    ModelBinding,
    ModelDeploymentEvent,
    ModelDeploymentSummary,
    ModelSource,
    ObjectStorageCredentials,
    ObjectStorageSource,
)
from nta_backend.services.system_config_service import load_system_huggingface_config

DEPLOYMENT_ENDPOINT_TYPE = "infer-agent-vllm"
DEFAULT_HUGGINGFACE_ALLOW_PATTERNS = [
    "*.json",
    "*.model",
    "*.py",
    "*.safetensors",
    "*.txt",
    "merges.txt",
    "tokenizer*",
    "vocab.*",
]


def _now() -> datetime:
    return datetime.now(UTC)


def _deployment_config(endpoint: Endpoint) -> dict[str, Any]:
    return endpoint.config_json if isinstance(endpoint.config_json, dict) else {}


def _agent_headers() -> dict[str, str]:
    settings = get_settings()
    if settings.infer_agent_token is None:
        return {}
    return {"Authorization": f"Bearer {settings.infer_agent_token.get_secret_value()}"}


def _agent_base_url() -> str:
    settings = get_settings()
    if not settings.infer_agent_base_url:
        raise ValueError("请先配置 INFER_AGENT_BASE_URL，指向 H20 机器上的 infer-agent。")
    return settings.infer_agent_base_url.rstrip("/")


def _normalize_served_name(value: str) -> str:
    normalized = re.sub(r"[^a-zA-Z0-9_.-]+", "-", value.strip()).strip("-")
    return normalized or "model"


def _parse_gpu_ids(raw: str) -> list[int]:
    return [int(item.strip()) for item in raw.split(",") if item.strip()]


def _read_object_storage_import(model: Model) -> dict[str, str]:
    if not isinstance(model.capabilities_json, dict):
        return {}
    metadata = model.capabilities_json.get("object_storage_import")
    if not isinstance(metadata, dict):
        return {}
    return {key: value for key, value in metadata.items() if isinstance(value, str)}


def _read_huggingface_import(model: Model) -> dict[str, str]:
    if not isinstance(model.capabilities_json, dict):
        return {}
    metadata = model.capabilities_json.get("huggingface_import")
    if not isinstance(metadata, dict):
        return {}
    return {key: value for key, value in metadata.items() if isinstance(value, str)}


def _redact_spec(spec: AgentDeploymentSpec) -> dict[str, Any]:
    secret_keys = {"secret_access_key", "session_token", "token", "api_key"}

    def redact(value: Any, key: str | None = None) -> Any:
        if key in secret_keys and value is not None:
            return "********"
        if isinstance(value, dict):
            return {
                str(item_key): redact(item_value, str(item_key))
                for item_key, item_value in value.items()
            }
        if isinstance(value, list):
            return [redact(item) for item in value]
        return value

    return redact(spec.model_dump(mode="json"))


def _serialize_deployment(
    endpoint: Endpoint,
    model_name: str | None = None,
) -> ModelDeploymentSummary:
    config = _deployment_config(endpoint)
    agent_status = (
        config.get("agent_status") if isinstance(config.get("agent_status"), dict) else {}
    )
    spec = config.get("spec") if isinstance(config.get("spec"), dict) else {}
    model = spec.get("model") if isinstance(spec.get("model"), dict) else {}
    return ModelDeploymentSummary(
        id=endpoint.id,
        name=endpoint.name,
        model_id=endpoint.model_id,
        model_name=model_name,
        status=endpoint.status,
        endpoint_url=agent_status.get("endpoint") or config.get("endpoint_url"),
        agent_base_url=config.get("agent_base_url"),
        served_model_name=model.get("served_name"),
        generation=int(config.get("generation") or agent_status.get("generation") or 0),
        phase=agent_status.get("phase"),
        progress=int(agent_status.get("progress") or 0),
        last_event=agent_status.get("last_event"),
        error_message=(
            agent_status.get("error", {}).get("message")
            if isinstance(agent_status.get("error"), dict)
            else None
        ),
        created_at=endpoint.created_at,
        updated_at=endpoint.updated_at,
    )


class ModelDeploymentService:
    async def list_deployments(self) -> list[ModelDeploymentSummary]:
        async with SessionLocal() as session:
            project_id = await resolve_active_project_id(session)
            rows = await session.execute(
                select(Endpoint, Model.name)
                .join(Model, Endpoint.model_id == Model.id, isouter=True)
                .where(
                    Endpoint.project_id == project_id,
                    Endpoint.endpoint_type == DEPLOYMENT_ENDPOINT_TYPE,
                    Endpoint.status != "deleted",
                )
                .order_by(Endpoint.updated_at.desc())
            )
            return [
                _serialize_deployment(endpoint, model_name) for endpoint, model_name in rows.all()
            ]

    async def deploy_model(
        self,
        model_id: UUID,
        payload: DeployModelRequest,
    ) -> ModelDeploymentSummary:
        async with SessionLocal() as session:
            project_id = await resolve_active_project_id(session)
            model = await session.get(Model, model_id)
            if model is None or model.project_id != project_id:
                raise KeyError(str(model_id))

            hf_config = await load_system_huggingface_config(session)
            spec = self._build_spec(model, payload, system_huggingface_config=hf_config)
            redacted_spec = _redact_spec(spec)
            endpoint = Endpoint(
                project_id=project_id,
                name=payload.name or f"{model.name} 部署",
                endpoint_type=DEPLOYMENT_ENDPOINT_TYPE,
                model_id=model.id,
                purchase_type="local-h20",
                status="deploying",
                created_by=get_current_user_id(),
                config_json={
                    "agent_base_url": _agent_base_url(),
                    "generation": spec.generation,
                    "spec": redacted_spec,
                    "endpoint_url": None,
                    "created_at": _now().isoformat(),
                },
            )
            session.add(endpoint)
            await session.flush()

            current_agent_status = await self._get_agent_status()
            spec.deployment_id = str(endpoint.id)
            spec.generation = max(1, current_agent_status.generation + 1)
            endpoint.config_json = {
                **_deployment_config(endpoint),
                "generation": spec.generation,
                "spec": _redact_spec(spec),
            }
            await session.commit()
            await session.refresh(endpoint)

        agent_status = await self._put_agent_spec(spec)
        await self._save_agent_status(endpoint.id, agent_status)
        return await self.get_deployment(endpoint.id)

    async def get_deployment(self, deployment_id: UUID) -> ModelDeploymentSummary:
        async with SessionLocal() as session:
            project_id = await resolve_active_project_id(session)
            rows = await session.execute(
                select(Endpoint, Model.name)
                .join(Model, Endpoint.model_id == Model.id, isouter=True)
                .where(Endpoint.id == deployment_id, Endpoint.project_id == project_id)
            )
            row = rows.one_or_none()
            if row is None:
                raise KeyError(str(deployment_id))
            endpoint, model_name = row
            return _serialize_deployment(endpoint, model_name)

    async def refresh_deployment(self, deployment_id: UUID) -> ModelDeploymentSummary:
        async with SessionLocal() as session:
            project_id = await resolve_active_project_id(session)
            endpoint = await session.get(Endpoint, deployment_id)
            if endpoint is None or endpoint.project_id != project_id:
                raise KeyError(str(deployment_id))

        status = await self._get_agent_status()
        await self._save_agent_status(deployment_id, status)
        return await self.get_deployment(deployment_id)

    async def list_events(
        self,
        deployment_id: UUID,
        limit: int = 200,
    ) -> list[ModelDeploymentEvent]:
        async with httpx.AsyncClient(timeout=20.0) as client:
            response = await client.get(
                f"{_agent_base_url()}/v1/events/recent",
                headers=_agent_headers(),
                params={"deployment_id": str(deployment_id), "limit": limit},
            )
            response.raise_for_status()
            return [ModelDeploymentEvent.model_validate(item) for item in response.json()]

    async def stop_current(self) -> AgentDeploymentStatus:
        async with httpx.AsyncClient(timeout=20.0) as client:
            response = await client.delete(
                f"{_agent_base_url()}/v1/deployments/current",
                headers=_agent_headers(),
            )
            response.raise_for_status()
            return AgentDeploymentStatus.model_validate(response.json())

    def _build_spec(
        self,
        model: Model,
        payload: DeployModelRequest,
        *,
        system_huggingface_config: dict[str, str | None] | None = None,
    ) -> AgentDeploymentSpec:
        settings = get_settings()
        object_storage_metadata = _read_object_storage_import(model)
        huggingface_metadata = _read_huggingface_import(model)

        served_name = _normalize_served_name(
            payload.served_model_name or model.model_code or model.name
        )
        gpu_ids = payload.gpu_ids or _parse_gpu_ids(settings.infer_default_gpu_ids)
        tensor_parallel_size = (
            payload.tensor_parallel_size or settings.infer_default_tensor_parallel_size
        )
        model_source = self._build_model_source(
            object_storage_metadata=object_storage_metadata,
            huggingface_metadata=huggingface_metadata,
            system_huggingface_config=system_huggingface_config or {},
        )
        return AgentDeploymentSpec(
            deployment_id="pending",
            generation=1,
            model=ModelBinding(
                model_id=str(model.id),
                name=model.name,
                served_name=served_name,
                source=model_source,
            ),
            engine=EngineSpec(
                image=settings.infer_vllm_image,
                gpu_ids=gpu_ids,
                tensor_parallel_size=tensor_parallel_size,
                listen_port=settings.infer_default_listen_port,
                dtype=payload.dtype or settings.infer_default_dtype,
                gpu_memory_utilization=settings.infer_default_gpu_memory_utilization,
                max_model_len=payload.max_model_len or settings.infer_default_max_model_len,
            ),
        )

    def _build_model_source(
        self,
        *,
        object_storage_metadata: dict[str, str],
        huggingface_metadata: dict[str, str],
        system_huggingface_config: dict[str, str | None],
    ) -> ModelSource:
        settings = get_settings()
        repo_id = huggingface_metadata.get("repo_id")
        if repo_id:
            revision = huggingface_metadata.get("revision") or "main"
            uri = huggingface_metadata.get("source_uri") or f"hf://{repo_id}@{revision}"
            token = huggingface_metadata.get("token") or (
                system_huggingface_config.get("token")
                if system_huggingface_config.get("token")
                else None
            )
            endpoint_url = system_huggingface_config.get("endpoint_url")
            huggingface_source = HuggingFaceSource(
                repo_id=repo_id,
                revision=revision,
                repo_type=huggingface_metadata.get("repo_type") or "model",
                allow_patterns=DEFAULT_HUGGINGFACE_ALLOW_PATTERNS,
                token=token,
                endpoint_url=endpoint_url,
            )
            return ModelSource(
                type="huggingface",
                uri=uri,
                huggingface=huggingface_source,
            )

        source_uri = object_storage_metadata.get("source_uri")
        if source_uri:
            credentials = ObjectStorageCredentials(
                access_key_id=settings.s3_access_key_id,
                secret_access_key=settings.s3_secret_access_key.get_secret_value(),
            )
            object_source = ObjectStorageSource(
                uri=source_uri,
                endpoint_url=settings.infer_object_storage_endpoint_url or settings.s3_endpoint_url,
                region=settings.s3_region,
                addressing_style=settings.s3_addressing_style,
                credentials=credentials,
            )
            return ModelSource(
                type="object_storage",
                uri=source_uri,
                object_storage=object_source,
            )

        raise ValueError("当前模型缺少 Hugging Face 或对象存储导入路径，无法部署到 infer-agent。")

    async def _put_agent_spec(self, spec: AgentDeploymentSpec) -> AgentDeploymentStatus:
        async with httpx.AsyncClient(timeout=20.0) as client:
            response = await client.put(
                f"{_agent_base_url()}/v1/deployments/current",
                headers=_agent_headers(),
                json=spec.model_dump(mode="json"),
            )
            response.raise_for_status()
            return AgentDeploymentStatus.model_validate(response.json())

    async def _get_agent_status(self) -> AgentDeploymentStatus:
        async with httpx.AsyncClient(timeout=20.0) as client:
            response = await client.get(
                f"{_agent_base_url()}/v1/deployments/current",
                headers=_agent_headers(),
            )
            response.raise_for_status()
            return AgentDeploymentStatus.model_validate(response.json())

    async def _save_agent_status(
        self,
        deployment_id: UUID,
        agent_status: AgentDeploymentStatus,
    ) -> None:
        async with SessionLocal() as session:
            endpoint = await session.get(Endpoint, deployment_id)
            if endpoint is None:
                return
            config = _deployment_config(endpoint)
            endpoint.config_json = {
                **config,
                "agent_status": agent_status.model_dump(mode="json"),
                "endpoint_url": agent_status.endpoint,
                "updated_from_agent_at": _now().isoformat(),
            }
            if agent_status.phase == "ready":
                endpoint.status = "active"
            elif agent_status.phase == "error":
                endpoint.status = "failed"
            elif agent_status.phase == "stopped":
                endpoint.status = "stopped"
            else:
                endpoint.status = "deploying"
            await session.commit()
