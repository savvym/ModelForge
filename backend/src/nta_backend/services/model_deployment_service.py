from __future__ import annotations

import re
from datetime import UTC, datetime
from typing import Any
from uuid import UUID

import httpx
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from nta_backend.core.auth_context import get_current_user_id
from nta_backend.core.config import get_settings
from nta_backend.core.db import SessionLocal
from nta_backend.core.project_context import resolve_active_project_id
from nta_backend.models.modeling import Endpoint, Model, ModelProvider
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
from nta_backend.schemas.model_registry import RegistryModelSummary
from nta_backend.services.inference_machine_service import (
    InferenceMachineRuntimeConfig,
    agent_headers,
    load_inference_machine_runtime,
    load_runtime_for_endpoint,
)
from nta_backend.services.system_config_service import load_system_huggingface_config

DEPLOYMENT_ENDPOINT_TYPE = "infer-agent-vllm"
LOCAL_DEPLOYMENT_PROVIDER_PREFIX = "infer-agent / "
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


def _normalize_served_name(value: str) -> str:
    normalized = re.sub(r"[^a-zA-Z0-9_.-]+", "-", value.strip()).strip("-")
    return normalized or "model"


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
    status_deployment_id = agent_status.get("deployment_id")
    is_superseded = bool(config.get("superseded_by"))
    if status_deployment_id and str(status_deployment_id) != str(endpoint.id):
        is_superseded = True
    phase = str(agent_status.get("phase") or "") if agent_status.get("phase") else None
    endpoint_url = agent_status.get("endpoint") or config.get("endpoint_url")
    progress = int(agent_status.get("progress") or 0)
    last_event = agent_status.get("last_event")
    if is_superseded:
        phase = "superseded"
        endpoint_url = None
        progress = 100
        last_event = config.get("superseded_reason") or "已被同一推理机器上的新部署替换"
    return ModelDeploymentSummary(
        id=endpoint.id,
        name=endpoint.name,
        model_id=endpoint.model_id,
        model_name=model_name,
        status=endpoint.status,
        endpoint_url=endpoint_url,
        machine_id=config.get("machine_id"),
        machine_name=config.get("machine_name"),
        experience_model_id=config.get("experience_model_id"),
        experience_provider_id=config.get("experience_provider_id"),
        agent_base_url=config.get("agent_base_url"),
        served_model_name=model.get("served_name"),
        generation=int(config.get("generation") or agent_status.get("generation") or 0),
        phase=phase,
        progress=progress,
        last_event=last_event,
        error_message=(
            agent_status.get("error", {}).get("message")
            if not is_superseded and isinstance(agent_status.get("error"), dict)
            else None
        ),
        created_at=endpoint.created_at,
        updated_at=endpoint.updated_at,
    )


def _deployment_machine_key(deployment: ModelDeploymentSummary) -> str | None:
    if deployment.machine_id is not None:
        return str(deployment.machine_id)
    return deployment.agent_base_url


def _normalize_machine_active_deployments(
    deployments: list[ModelDeploymentSummary],
) -> list[ModelDeploymentSummary]:
    latest_by_machine: dict[str, tuple[int, datetime, UUID]] = {}
    for deployment in deployments:
        if deployment.phase != "ready" and deployment.status != "active":
            continue
        machine_key = _deployment_machine_key(deployment)
        if not machine_key:
            continue
        current_latest = latest_by_machine.get(machine_key)
        if current_latest is None or (deployment.generation, deployment.updated_at) > (
            current_latest[0],
            current_latest[1],
        ):
            latest_by_machine[machine_key] = (
                deployment.generation,
                deployment.updated_at,
                deployment.id,
            )

    for deployment in deployments:
        machine_key = _deployment_machine_key(deployment)
        if not machine_key or machine_key not in latest_by_machine:
            continue
        latest_generation, latest_updated_at, latest_id = latest_by_machine[machine_key]
        if deployment.id == latest_id:
            continue
        if deployment.phase == "ready" or deployment.status == "active":
            if (deployment.generation, deployment.updated_at) <= (
                latest_generation,
                latest_updated_at,
            ):
                deployment.phase = "superseded"
                deployment.status = "stopped"
                deployment.endpoint_url = None
                deployment.progress = 100
                deployment.last_event = "已被同一推理机器上的新部署替换"
                deployment.error_message = None

    return deployments


def _local_provider_name(machine_name: str | None) -> str:
    suffix = (machine_name or "local").strip() or "local"
    return f"{LOCAL_DEPLOYMENT_PROVIDER_PREFIX}{suffix}"[:120]


def _serialize_registry_model(
    model: Model,
    provider_name: str | None,
) -> RegistryModelSummary:
    object_storage_metadata = _read_object_storage_import(model)
    huggingface_metadata = _read_huggingface_import(model)
    return RegistryModelSummary(
        id=model.id,
        name=model.name,
        model_code=model.model_code,
        vendor=model.vendor,
        source=model.source,
        api_format=model.api_format,
        base_model=model.base_model,
        category=model.category,
        description=model.description,
        import_source_type=object_storage_metadata.get("source_type")
        or huggingface_metadata.get("source_type"),
        import_source_uri=object_storage_metadata.get("source_uri")
        or huggingface_metadata.get("source_uri"),
        import_bucket=object_storage_metadata.get("bucket"),
        import_object_key=object_storage_metadata.get("object_key"),
        import_repo_id=huggingface_metadata.get("repo_id"),
        import_revision=huggingface_metadata.get("revision"),
        status=model.status,
        provider_id=model.provider_id,
        provider_name=provider_name,
        is_provider_managed=model.is_provider_managed,
        last_synced_at=model.last_synced_at,
        created_at=model.created_at,
        updated_at=model.updated_at,
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
            deployments = [
                _serialize_deployment(endpoint, model_name) for endpoint, model_name in rows.all()
            ]
            return _normalize_machine_active_deployments(deployments)

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
            machine = await load_inference_machine_runtime(
                session,
                project_id,
                payload.machine_id,
            )
            spec = self._build_spec(
                model,
                payload,
                inference_machine=machine,
                system_huggingface_config=hf_config,
            )
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
                    "machine_id": str(machine.id) if machine.id else None,
                    "machine_name": machine.name,
                    "agent_base_url": machine.agent_base_url,
                    "generation": spec.generation,
                    "spec": redacted_spec,
                    "endpoint_url": None,
                    "created_at": _now().isoformat(),
                },
            )
            session.add(endpoint)
            await session.flush()

            current_agent_status = await self._get_agent_status(machine)
            spec.deployment_id = str(endpoint.id)
            spec.generation = max(1, current_agent_status.generation + 1)
            endpoint.config_json = {
                **_deployment_config(endpoint),
                "generation": spec.generation,
                "spec": _redact_spec(spec),
            }
            await session.commit()
            await session.refresh(endpoint)

        agent_status = await self._put_agent_spec(spec, machine)
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
            machine = await load_runtime_for_endpoint(
                session,
                project_id,
                _deployment_config(endpoint),
            )

        status = await self._get_agent_status(machine)
        await self._save_agent_status(deployment_id, status)
        return await self.get_deployment(deployment_id)

    async def publish_to_experience(self, deployment_id: UUID) -> RegistryModelSummary:
        async with SessionLocal() as session:
            project_id = await resolve_active_project_id(session)
            rows = await session.execute(
                select(Endpoint, Model)
                .join(Model, Endpoint.model_id == Model.id, isouter=True)
                .where(
                    Endpoint.id == deployment_id,
                    Endpoint.project_id == project_id,
                    Endpoint.endpoint_type == DEPLOYMENT_ENDPOINT_TYPE,
                )
            )
            row = rows.one_or_none()
            if row is None:
                raise KeyError(str(deployment_id))
            endpoint, model = row
            if model is None:
                raise ValueError("部署任务没有关联模型，无法接入体验中心。")
            config = _deployment_config(endpoint)
            machine = await load_runtime_for_endpoint(session, project_id, config)

        agent_status = await self._get_agent_status(machine)
        await self._save_agent_status(deployment_id, agent_status)
        if agent_status.deployment_id and agent_status.deployment_id != str(deployment_id):
            raise ValueError("当前部署已被同一推理机器上的新部署替换，不能接入体验中心。")
        if agent_status.phase != "ready" or not agent_status.endpoint:
            raise ValueError("部署尚未可用，请等待 vLLM ready 后再接入体验中心。")

        async with SessionLocal() as session:
            project_id = await resolve_active_project_id(session)
            rows = await session.execute(
                select(Endpoint, Model)
                .join(Model, Endpoint.model_id == Model.id, isouter=True)
                .where(
                    Endpoint.id == deployment_id,
                    Endpoint.project_id == project_id,
                    Endpoint.endpoint_type == DEPLOYMENT_ENDPOINT_TYPE,
                )
            )
            row = rows.one_or_none()
            if row is None:
                raise KeyError(str(deployment_id))
            endpoint, model = row
            if model is None:
                raise ValueError("部署任务没有关联模型，无法接入体验中心。")

            config = _deployment_config(endpoint)
            spec = config.get("spec") if isinstance(config.get("spec"), dict) else {}
            spec_model = spec.get("model") if isinstance(spec.get("model"), dict) else {}
            served_model_name = str(
                spec_model.get("served_name") or model.model_code or model.name
            ).strip()
            if not served_model_name:
                raise ValueError("部署任务缺少 served model name。")

            provider_name = _local_provider_name(config.get("machine_name"))
            provider_rows = await session.execute(
                select(ModelProvider).where(
                    ModelProvider.project_id == project_id,
                    ModelProvider.name == provider_name,
                )
            )
            provider = provider_rows.scalar_one_or_none()
            if provider is None:
                provider = ModelProvider(
                    project_id=project_id,
                    name=provider_name,
                    provider_type="openai-compatible",
                    adapter="litellm",
                    api_format="chat-completions",
                    base_url=agent_status.endpoint.rstrip("/"),
                    api_key=None,
                    organization=None,
                    description=f"由 infer-agent 部署任务 {endpoint.name} 自动接入。",
                    headers_json=None,
                    status="active",
                    created_by=get_current_user_id(),
                )
                session.add(provider)
                await session.flush()
            else:
                provider.provider_type = "openai-compatible"
                provider.adapter = "litellm"
                provider.api_format = "chat-completions"
                provider.base_url = agent_status.endpoint.rstrip("/")
                provider.api_key = None
                provider.status = "active"
                provider.description = f"由 infer-agent 部署任务 {endpoint.name} 自动接入。"

            other_model_rows = await session.execute(
                select(Model).where(
                    Model.project_id == project_id,
                    Model.provider_id == provider.id,
                    Model.id != model.id,
                )
            )
            for previous_model in other_model_rows.scalars().all():
                previous_model.provider_id = None
                if previous_model.vendor == provider.name:
                    previous_model.vendor = None
                if isinstance(previous_model.capabilities_json, dict):
                    previous_model.capabilities_json = {
                        key: value
                        for key, value in previous_model.capabilities_json.items()
                        if key != "local_deployment_publish"
                    }

            capabilities = (
                model.capabilities_json if isinstance(model.capabilities_json, dict) else {}
            )
            model.provider_id = provider.id
            model.model_code = served_model_name
            model.vendor = provider.name
            model.api_format = "chat-completions"
            model.category = model.category or "chat-model"
            model.status = "active"
            model.capabilities_json = {
                **capabilities,
                "local_deployment_publish": {
                    "deployment_id": str(endpoint.id),
                    "provider_id": str(provider.id),
                    "endpoint_url": agent_status.endpoint,
                    "served_model_name": served_model_name,
                    "published_at": _now().isoformat(),
                },
            }
            endpoint.config_json = {
                **config,
                "experience_model_id": str(model.id),
                "experience_provider_id": str(provider.id),
                "endpoint_url": agent_status.endpoint,
                "published_at": _now().isoformat(),
            }

            try:
                await session.commit()
            except IntegrityError as exc:
                await session.rollback()
                raise ValueError("接入体验中心失败：Provider 或模型编码已存在。") from exc
            await session.refresh(model)
            return _serialize_registry_model(model, provider.name)

    async def list_events(
        self,
        deployment_id: UUID,
        limit: int = 200,
    ) -> list[ModelDeploymentEvent]:
        async with SessionLocal() as session:
            project_id = await resolve_active_project_id(session)
            endpoint = await session.get(Endpoint, deployment_id)
            if endpoint is None or endpoint.project_id != project_id:
                raise KeyError(str(deployment_id))
            machine = await load_runtime_for_endpoint(
                session,
                project_id,
                _deployment_config(endpoint),
            )

        async with httpx.AsyncClient(timeout=20.0) as client:
            response = await client.get(
                f"{machine.agent_base_url}/v1/events/recent",
                headers=agent_headers(machine),
                params={"deployment_id": str(deployment_id), "limit": limit},
            )
            response.raise_for_status()
            return [ModelDeploymentEvent.model_validate(item) for item in response.json()]

    async def stop_current(self, machine_id: UUID | None = None) -> AgentDeploymentStatus:
        async with SessionLocal() as session:
            project_id = await resolve_active_project_id(session)
            machine = await load_inference_machine_runtime(session, project_id, machine_id)

        async with httpx.AsyncClient(timeout=20.0) as client:
            response = await client.delete(
                f"{machine.agent_base_url}/v1/deployments/current",
                headers=agent_headers(machine),
            )
            response.raise_for_status()
            return AgentDeploymentStatus.model_validate(response.json())

    def _build_spec(
        self,
        model: Model,
        payload: DeployModelRequest,
        *,
        inference_machine: InferenceMachineRuntimeConfig,
        system_huggingface_config: dict[str, str | None] | None = None,
    ) -> AgentDeploymentSpec:
        object_storage_metadata = _read_object_storage_import(model)
        huggingface_metadata = _read_huggingface_import(model)

        served_name = _normalize_served_name(
            payload.served_model_name or model.model_code or model.name
        )
        gpu_ids = payload.gpu_ids or inference_machine.gpu_ids
        tensor_parallel_size = (
            payload.tensor_parallel_size or inference_machine.tensor_parallel_size
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
                image=inference_machine.vllm_image,
                gpu_ids=gpu_ids,
                tensor_parallel_size=tensor_parallel_size,
                listen_port=inference_machine.listen_port,
                dtype=payload.dtype or inference_machine.dtype,
                gpu_memory_utilization=inference_machine.gpu_memory_utilization,
                max_model_len=payload.max_model_len or inference_machine.max_model_len,
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

    async def _put_agent_spec(
        self,
        spec: AgentDeploymentSpec,
        machine: InferenceMachineRuntimeConfig,
    ) -> AgentDeploymentStatus:
        async with httpx.AsyncClient(timeout=20.0) as client:
            response = await client.put(
                f"{machine.agent_base_url}/v1/deployments/current",
                headers=agent_headers(machine),
                json=spec.model_dump(mode="json"),
            )
            response.raise_for_status()
            return AgentDeploymentStatus.model_validate(response.json())

    async def _get_agent_status(
        self,
        machine: InferenceMachineRuntimeConfig,
    ) -> AgentDeploymentStatus:
        async with httpx.AsyncClient(timeout=20.0) as client:
            response = await client.get(
                f"{machine.agent_base_url}/v1/deployments/current",
                headers=agent_headers(machine),
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
            if agent_status.deployment_id and agent_status.deployment_id != str(endpoint.id):
                endpoint.config_json = {
                    **config,
                    "last_observed_agent_status": agent_status.model_dump(mode="json"),
                    "superseded_by": agent_status.deployment_id,
                    "superseded_at": _now().isoformat(),
                    "superseded_reason": "已被同一推理机器上的新部署替换",
                    "endpoint_url": None,
                    "agent_status": {
                        **(
                            config.get("agent_status")
                            if isinstance(config.get("agent_status"), dict)
                            else {}
                        ),
                        "phase": "superseded",
                        "progress": 100,
                        "endpoint": None,
                        "last_event": "已被同一推理机器上的新部署替换",
                        "error": None,
                    },
                }
                endpoint.status = "stopped"
                await self._unpublish_deployment_model(session, config)
                await session.commit()
                return

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
            if agent_status.deployment_id == str(endpoint.id):
                await self._mark_sibling_deployments_superseded(session, endpoint)
            await session.commit()

    async def _mark_sibling_deployments_superseded(
        self,
        session: AsyncSession,
        active_endpoint: Endpoint,
    ) -> None:
        active_config = _deployment_config(active_endpoint)
        active_machine_id = active_config.get("machine_id")
        active_agent_base_url = active_config.get("agent_base_url")
        rows = await session.execute(
            select(Endpoint).where(
                Endpoint.project_id == active_endpoint.project_id,
                Endpoint.endpoint_type == DEPLOYMENT_ENDPOINT_TYPE,
                Endpoint.id != active_endpoint.id,
                Endpoint.status != "deleted",
            )
        )
        for endpoint in rows.scalars().all():
            config = _deployment_config(endpoint)
            is_same_machine = False
            if active_machine_id and config.get("machine_id") == active_machine_id:
                is_same_machine = True
            elif (
                not active_machine_id
                and active_agent_base_url
                and config.get("agent_base_url") == active_agent_base_url
            ):
                is_same_machine = True
            if not is_same_machine:
                continue
            endpoint.config_json = {
                **config,
                "superseded_by": str(active_endpoint.id),
                "superseded_at": _now().isoformat(),
                "superseded_reason": "已被同一推理机器上的新部署替换",
                "endpoint_url": None,
                "agent_status": {
                    **(
                        config.get("agent_status")
                        if isinstance(config.get("agent_status"), dict)
                        else {}
                    ),
                    "phase": "superseded",
                    "progress": 100,
                    "endpoint": None,
                    "last_event": "已被同一推理机器上的新部署替换",
                    "error": None,
                },
            }
            endpoint.status = "stopped"
            await self._unpublish_deployment_model(session, config)

    async def _unpublish_deployment_model(
        self,
        session: AsyncSession,
        config: dict[str, Any],
    ) -> None:
        model_id = config.get("experience_model_id")
        provider_id = config.get("experience_provider_id")
        if not isinstance(model_id, str) or not isinstance(provider_id, str):
            return
        try:
            model_uuid = UUID(model_id)
        except ValueError:
            return
        model = await session.get(Model, model_uuid)
        if model is None or str(model.provider_id) != provider_id:
            return
        model.provider_id = None
        if isinstance(model.capabilities_json, dict):
            model.capabilities_json = {
                key: value
                for key, value in model.capabilities_json.items()
                if key != "local_deployment_publish"
            }
