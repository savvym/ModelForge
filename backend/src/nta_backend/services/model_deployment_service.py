from __future__ import annotations

import json
import re
from collections.abc import AsyncIterator
from datetime import UTC, datetime
from time import perf_counter
from typing import Any
from uuid import UUID

import httpx
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

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
    ModelDeploymentPassiveHealth,
    ModelDeploymentSummary,
    ModelSource,
    ObjectStorageCredentials,
    ObjectStorageSource,
)
from nta_backend.schemas.model_registry import (
    RegistryModelChatRequest,
    RegistryModelDeploymentHints,
)
from nta_backend.services.inference_machine_service import (
    InferenceMachineRuntimeConfig,
    agent_headers,
    load_inference_machine_runtime,
    load_runtime_for_endpoint,
    runtime_headers,
)
from nta_backend.services.system_config_service import load_system_huggingface_config

DEPLOYMENT_ENDPOINT_TYPE = "infer-agent-vllm"
TASK_KINDS = {"deployment", "unload"}
RUNNING_TASK_PHASES = {
    "deploying",
    "downloading",
    "pending",
    "running",
    "smoke_testing",
    "starting",
    "stopping",
    "stopping_previous",
    "unloading",
    "warming",
}
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
VLLM_REASONING_PARSER_RULES: tuple[tuple[str, str], ...] = (
    ("qwen3", "qwen3"),
    ("deepseek-r1", "deepseek_r1"),
    ("deepseek_r1", "deepseek_r1"),
    ("qwq", "deepseek_r1"),
    ("glm-4.5", "glm45"),
    ("glm45", "glm45"),
)


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


def _read_deployment_hints(model: Model) -> RegistryModelDeploymentHints | None:
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


def _infer_vllm_reasoning_extra_args(
    model: Model,
    deployment_hints: RegistryModelDeploymentHints | None,
    *,
    huggingface_metadata: dict[str, str],
    object_storage_metadata: dict[str, str],
) -> dict[str, Any]:
    candidates: list[str] = [
        str(getattr(model, "name", "") or ""),
        str(getattr(model, "model_code", "") or ""),
        str(getattr(model, "base_model", "") or ""),
        huggingface_metadata.get("repo_id", ""),
        huggingface_metadata.get("source_uri", ""),
        object_storage_metadata.get("source_uri", ""),
    ]
    if deployment_hints is not None:
        candidates.append(deployment_hints.model_type or "")
        candidates.extend(deployment_hints.architectures)

    searchable = " ".join(candidate.lower() for candidate in candidates if candidate)
    for marker, parser in VLLM_REASONING_PARSER_RULES:
        if marker in searchable:
            return {
                "reasoning_parser": parser,
            }
    return {}


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


def _deployment_served_model_name(
    config: dict[str, Any],
    model_name: str | None = None,
) -> str | None:
    spec = config.get("spec") if isinstance(config.get("spec"), dict) else {}
    spec_model = spec.get("model") if isinstance(spec.get("model"), dict) else {}
    served_name = spec_model.get("served_name")
    if isinstance(served_name, str) and served_name.strip():
        return served_name.strip()
    return model_name.strip() if isinstance(model_name, str) and model_name.strip() else None


def _is_unloaded_config(config: dict[str, Any]) -> bool:
    return bool(config.get("unloaded_at"))


def _is_superseded_config(config: dict[str, Any], endpoint_id: UUID) -> bool:
    if config.get("superseded_by"):
        return True
    agent_status = (
        config.get("agent_status") if isinstance(config.get("agent_status"), dict) else {}
    )
    status_deployment_id = agent_status.get("deployment_id")
    return bool(status_deployment_id and str(status_deployment_id) != str(endpoint_id))


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


def _extract_chat_completion_text(payload: dict[str, Any]) -> str | None:
    choices = payload.get("choices")
    if not isinstance(choices, list) or not choices:
        return None
    first_choice = choices[0]
    if not isinstance(first_choice, dict):
        return None
    message = first_choice.get("message")
    if not isinstance(message, dict):
        return None
    content = message.get("content")
    return content.strip() if isinstance(content, str) and content.strip() else None


def _extract_reasoning_delta(delta_data: dict[str, Any]) -> str | None:
    for key in ("reasoning", "reasoning_content", "reasoning_text"):
        value = delta_data.get(key)
        if isinstance(value, str) and value:
            return value
    return None


def _is_http_status(exc: httpx.HTTPError, status_code: int) -> bool:
    return isinstance(exc, httpx.HTTPStatusError) and exc.response.status_code == status_code


def _unload_task_config(config: dict[str, Any]) -> dict[str, Any]:
    task = config.get("unload_task")
    return task if isinstance(task, dict) else {}


def _unload_task_summary_fields(config: dict[str, Any]) -> dict[str, Any]:
    task = _unload_task_config(config)
    return {
        "unload_task_status": str(task.get("status")) if task.get("status") else None,
        "unload_task_started_at": task.get("started_at"),
        "unload_task_finished_at": task.get("finished_at"),
        "unload_task_message": str(task.get("message")) if task.get("message") else None,
        "unload_task_warning": str(task.get("warning")) if task.get("warning") else None,
    }


def _deleted_task_kinds(config: dict[str, Any]) -> list[str]:
    task_kinds = config.get("deleted_task_kinds")
    if not isinstance(task_kinds, list):
        return []
    seen: set[str] = set()
    deleted: list[str] = []
    for task_kind in task_kinds:
        if not isinstance(task_kind, str) or task_kind not in TASK_KINDS:
            continue
        if task_kind in seen:
            continue
        seen.add(task_kind)
        deleted.append(task_kind)
    return deleted


def _clear_deleted_task_kind(config: dict[str, Any], task_kind: str) -> dict[str, Any]:
    next_config = {**config}
    deleted = [kind for kind in _deleted_task_kinds(config) if kind != task_kind]
    if deleted:
        next_config["deleted_task_kinds"] = deleted
    else:
        next_config.pop("deleted_task_kinds", None)
    return next_config


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


def _serialize_deployment(
    endpoint: Endpoint,
    model_name: str | None = None,
) -> ModelDeploymentSummary:
    config = _deployment_config(endpoint)
    agent_status = (
        config.get("agent_status") if isinstance(config.get("agent_status"), dict) else {}
    )
    status_deployment_id = agent_status.get("deployment_id")
    is_superseded = _is_superseded_config(config, endpoint.id)
    is_unloaded = _is_unloaded_config(config)
    phase = str(agent_status.get("phase") or "") if agent_status.get("phase") else None
    endpoint_url = agent_status.get("endpoint") or config.get("endpoint_url")
    progress = int(agent_status.get("progress") or 0)
    last_event = agent_status.get("last_event")
    is_current = bool(status_deployment_id and str(status_deployment_id) == str(endpoint.id))
    passive_health = (
        config.get("passive_health") if isinstance(config.get("passive_health"), dict) else {}
    )
    if is_unloaded:
        phase = "unloaded"
        endpoint_url = None
        progress = 100
        last_event = config.get("unloaded_reason") or "部署已卸载"
        is_current = False
    elif is_superseded:
        phase = "superseded"
        endpoint_url = None
        progress = 100
        last_event = config.get("superseded_reason") or "已被同一推理机器上的新部署替换"
        is_current = False
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
        served_model_name=_deployment_served_model_name(config, model_name),
        is_current=is_current,
        generation=int(config.get("generation") or agent_status.get("generation") or 0),
        phase=phase,
        progress=progress,
        last_event=last_event,
        error_message=(
            agent_status.get("error", {}).get("message")
            if not is_superseded and isinstance(agent_status.get("error"), dict)
            else None
        ),
        last_passive_health_status=(
            str(passive_health.get("status")) if passive_health.get("status") else None
        ),
        last_passive_health_checked_at=passive_health.get("checked_at"),
        last_passive_health_latency_ms=(
            int(passive_health["latency_ms"])
            if isinstance(passive_health.get("latency_ms"), int | float)
            else None
        ),
        last_passive_health_error=(
            str(passive_health.get("error")) if passive_health.get("error") else None
        ),
        **_unload_task_summary_fields(config),
        deleted_task_kinds=_deleted_task_kinds(config),
        created_at=endpoint.created_at,
        updated_at=endpoint.updated_at,
    )


def _serialize_deployment_task(
    endpoint: Endpoint,
    model_name: str | None = None,
) -> ModelDeploymentSummary:
    config = _deployment_config(endpoint)
    agent_status = (
        config.get("agent_status") if isinstance(config.get("agent_status"), dict) else {}
    )
    passive_health = (
        config.get("passive_health") if isinstance(config.get("passive_health"), dict) else {}
    )
    raw_phase = str(agent_status.get("phase") or endpoint.status or "")
    has_been_ready = bool(config.get("has_been_ready")) or raw_phase == "ready"
    error_message = (
        agent_status.get("error", {}).get("message")
        if isinstance(agent_status.get("error"), dict)
        else None
    )
    if raw_phase == "superseded":
        task_phase = "superseded"
        task_status = "stopped"
        progress = 100
        last_event = agent_status.get("last_event") or "已被同一推理机器上的新部署替换"
        error_message = None
    elif raw_phase in {"stopped", "unloaded"}:
        task_phase = raw_phase
        task_status = "stopped"
        progress = 100
        last_event = agent_status.get("last_event") or (
            "部署已卸载" if raw_phase == "unloaded" else "部署已停止"
        )
        error_message = None
    elif endpoint.status == "failed" or raw_phase == "error":
        task_phase = "failed"
        task_status = "failed"
        progress = 100
        last_event = agent_status.get("last_event") or "部署失败"
    elif has_been_ready:
        task_phase = "succeeded"
        task_status = "succeeded"
        progress = 100
        last_event = (
            agent_status.get("last_event")
            if raw_phase not in {"unloaded", "unloading"}
            else None
        ) or "成功部署"
        error_message = None
    else:
        task_phase = (
            raw_phase
            if raw_phase in {"deploying", "downloading", "pending", "warming"}
            else "deploying"
        )
        task_status = "deploying"
        progress = int(agent_status.get("progress") or 0)
        last_event = agent_status.get("last_event")

    return ModelDeploymentSummary(
        id=endpoint.id,
        name=endpoint.name,
        model_id=endpoint.model_id,
        model_name=model_name,
        status=task_status,
        endpoint_url=config.get("endpoint_url"),
        machine_id=config.get("machine_id"),
        machine_name=config.get("machine_name"),
        experience_model_id=config.get("experience_model_id"),
        experience_provider_id=config.get("experience_provider_id"),
        agent_base_url=config.get("agent_base_url"),
        served_model_name=_deployment_served_model_name(config, model_name),
        is_current=False,
        generation=int(config.get("generation") or agent_status.get("generation") or 0),
        phase=task_phase,
        progress=progress,
        last_event=last_event,
        error_message=str(error_message) if error_message else None,
        last_passive_health_status=(
            str(passive_health.get("status")) if passive_health.get("status") else None
        ),
        last_passive_health_checked_at=passive_health.get("checked_at"),
        last_passive_health_latency_ms=(
            int(passive_health["latency_ms"])
            if isinstance(passive_health.get("latency_ms"), int | float)
            else None
        ),
        last_passive_health_error=(
            str(passive_health.get("error")) if passive_health.get("error") else None
        ),
        **_unload_task_summary_fields(config),
        deleted_task_kinds=_deleted_task_kinds(config),
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
                _serialize_deployment_task(endpoint, model_name)
                for endpoint, model_name in rows.all()
            ]
            return deployments

    async def list_my_deployments(self) -> list[ModelDeploymentSummary]:
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
            deployments: list[ModelDeploymentSummary] = []
            for endpoint, model_name in rows.all():
                config = _deployment_config(endpoint)
                if _is_unloaded_config(config) or _is_superseded_config(config, endpoint.id):
                    continue
                agent_status = (
                    config.get("agent_status")
                    if isinstance(config.get("agent_status"), dict)
                    else {}
                )
                phase = str(agent_status.get("phase") or "")
                has_been_ready = bool(config.get("has_been_ready"))
                if endpoint.status == "active" or phase in {"ready", "stopped"} or has_been_ready:
                    deployments.append(_serialize_deployment(endpoint, model_name))
            return deployments

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

        try:
            agent_status = await self._put_agent_spec(spec, machine)
        except httpx.HTTPError as exc:
            await self._mark_deployment_failed(endpoint.id, f"infer-agent request failed: {exc}")
            raise
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

    async def delete_task(
        self,
        deployment_id: UUID,
        task_kind: str,
    ) -> ModelDeploymentSummary:
        if task_kind not in TASK_KINDS:
            raise ValueError("不支持的任务类型。")

        async with SessionLocal() as session:
            project_id = await resolve_active_project_id(session)
            rows = await session.execute(
                select(Endpoint, Model.name)
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

            endpoint, model_name = row
            config = _deployment_config(endpoint)
            if task_kind == "deployment":
                task_summary = _serialize_deployment_task(endpoint, model_name)
                task_phase = task_summary.phase or task_summary.status
                if task_phase in RUNNING_TASK_PHASES:
                    raise ValueError("进行中的任务不能删除。")
            else:
                unload_task = _unload_task_config(config)
                task_status = str(unload_task.get("status") or "")
                if not task_status:
                    raise ValueError("卸载任务不存在。")
                if task_status in RUNNING_TASK_PHASES:
                    raise ValueError("进行中的任务不能删除。")

            deleted = _deleted_task_kinds(config)
            if task_kind not in deleted:
                deleted.append(task_kind)
            endpoint.config_json = {**config, "deleted_task_kinds": deleted}
            await session.commit()
            await session.refresh(endpoint)
            return _serialize_deployment_task(endpoint, model_name)

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

    async def stop_deployment(self, deployment_id: UUID) -> ModelDeploymentSummary:
        async with SessionLocal() as session:
            project_id = await resolve_active_project_id(session)
            endpoint = await session.get(Endpoint, deployment_id)
            if (
                endpoint is None
                or endpoint.project_id != project_id
                or endpoint.endpoint_type != DEPLOYMENT_ENDPOINT_TYPE
            ):
                raise KeyError(str(deployment_id))
            config = _deployment_config(endpoint)
            if _is_unloaded_config(config):
                raise ValueError("该部署已卸载。")
            machine = await load_runtime_for_endpoint(session, project_id, config)

        agent_status = await self._get_agent_status(machine)
        if agent_status.deployment_id != str(deployment_id):
            raise ValueError("该部署不是当前运行中的部署。")
        if agent_status.phase in {"idle", "stopped"}:
            raise ValueError("该部署当前没有运行中的 vLLM 容器。")

        stopped_status = await self._delete_agent_current(machine)
        await self._save_agent_status(deployment_id, stopped_status)
        return await self.get_deployment(deployment_id)

    async def start_deployment(self, deployment_id: UUID) -> ModelDeploymentSummary:
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
                raise ValueError("部署任务没有关联模型，无法启动。")
            config = _deployment_config(endpoint)
            if _is_unloaded_config(config):
                raise ValueError("该部署已卸载，无法启动。")
            machine = await load_runtime_for_endpoint(session, project_id, config)
            hf_config = await load_system_huggingface_config(session)

            stored_spec = config.get("spec") if isinstance(config.get("spec"), dict) else {}
            stored_model = (
                stored_spec.get("model") if isinstance(stored_spec.get("model"), dict) else {}
            )
            stored_engine = (
                stored_spec.get("engine") if isinstance(stored_spec.get("engine"), dict) else {}
            )
            spec = self._build_spec(
                model,
                DeployModelRequest(
                    name=endpoint.name,
                    machine_id=machine.id,
                    served_model_name=(
                        str(stored_model.get("served_name"))
                        if stored_model.get("served_name")
                        else model.model_code or model.name
                    ),
                    gpu_ids=(
                        [
                            int(gpu_id)
                            for gpu_id in stored_engine.get("gpu_ids", [])
                            if isinstance(gpu_id, int | float)
                        ]
                        if isinstance(stored_engine.get("gpu_ids"), list)
                        else None
                    ),
                    tensor_parallel_size=(
                        int(stored_engine["tensor_parallel_size"])
                        if isinstance(stored_engine.get("tensor_parallel_size"), int | float)
                        else None
                    ),
                    max_model_len=(
                        int(stored_engine["max_model_len"])
                        if isinstance(stored_engine.get("max_model_len"), int | float)
                        else None
                    ),
                    dtype=(
                        str(stored_engine["dtype"])
                        if isinstance(stored_engine.get("dtype"), str)
                        else None
                    ),
                ),
                inference_machine=machine,
                system_huggingface_config=hf_config,
            )
            current_agent_status = await self._get_agent_status(machine)
            stored_generation = int(config.get("generation") or stored_spec.get("generation") or 0)
            spec.deployment_id = str(endpoint.id)
            spec.desired_phase = "running"
            spec.generation = max(1, stored_generation + 1, current_agent_status.generation + 1)

            next_config = {
                key: value
                for key, value in config.items()
                if key
                not in {
                    "superseded_at",
                    "superseded_by",
                    "superseded_reason",
                    "unloaded_at",
                    "unloaded_reason",
                }
            }
            next_config = _clear_deleted_task_kind(next_config, "deployment")
            endpoint.config_json = {
                **next_config,
                "endpoint_url": None,
                "generation": spec.generation,
                "spec": _redact_spec(spec),
            }
            endpoint.status = "deploying"
            await session.commit()

        try:
            agent_status = await self._put_agent_spec(spec, machine)
        except httpx.HTTPError as exc:
            await self._mark_deployment_failed(deployment_id, f"infer-agent request failed: {exc}")
            raise
        await self._save_agent_status(deployment_id, agent_status)
        return await self.get_deployment(deployment_id)

    async def unload_deployment(self, deployment_id: UUID) -> ModelDeploymentSummary:
        async with SessionLocal() as session:
            project_id = await resolve_active_project_id(session)
            endpoint = await session.get(Endpoint, deployment_id)
            if (
                endpoint is None
                or endpoint.project_id != project_id
                or endpoint.endpoint_type != DEPLOYMENT_ENDPOINT_TYPE
            ):
                raise KeyError(str(deployment_id))
            config = _clear_deleted_task_kind(_deployment_config(endpoint), "unload")
            if _is_unloaded_config(config):
                return _serialize_deployment(endpoint)
            unload_started_at = _now().isoformat()
            endpoint.config_json = {
                **config,
                "agent_status": {
                    **(
                        config.get("agent_status")
                        if isinstance(config.get("agent_status"), dict)
                        else {}
                    ),
                    "phase": "unloading",
                    "progress": 20,
                    "endpoint": None,
                    "last_event": "卸载任务已提交",
                    "error": None,
                },
                "endpoint_url": None,
                "unload_task": {
                    "status": "running",
                    "started_at": unload_started_at,
                    "message": "卸载任务已提交",
                },
            }
            endpoint.status = "unloading"
            await session.commit()

            try:
                machine = await load_runtime_for_endpoint(session, project_id, config)
            except (KeyError, ValueError) as exc:
                machine = None
                load_runtime_error = str(exc)
            else:
                load_runtime_error = None

        agent_status: AgentDeploymentStatus | None = None
        current_agent_status: AgentDeploymentStatus | None = None
        cleanup_warning: str | None = None
        unload_reason = "卸载任务完成"
        if machine is None:
            cleanup_warning = load_runtime_error or "推理机器不存在，已跳过远端清理。"
            unload_reason = "推理机器不可用，已完成本地节点卸载"
        else:
            try:
                current_agent_status = await self._get_agent_status(machine)
            except httpx.HTTPError as exc:
                if _is_http_status(exc, 404):
                    unload_reason = "远端部署不存在，已完成本地节点卸载"
                else:
                    cleanup_warning = f"infer-agent 不可达，远端清理未确认：{exc}"
                    unload_reason = "本地节点已卸载，远端清理未确认"

            if (
                current_agent_status is not None
                and current_agent_status.deployment_id == str(deployment_id)
            ):
                try:
                    agent_status = await self._delete_agent_current(machine)
                    unload_reason = "卸载任务完成，远端 vLLM 已清理"
                except httpx.HTTPError as exc:
                    if _is_http_status(exc, 404):
                        unload_reason = "远端部署不存在，已完成本地节点卸载"
                    else:
                        cleanup_warning = f"infer-agent 清理失败，远端清理未确认：{exc}"
                        unload_reason = "本地节点已卸载，远端清理未确认"
            elif current_agent_status is not None and current_agent_status.deployment_id:
                cleanup_warning = "同一推理机器当前运行的是其他部署，未删除远端容器。"
                unload_reason = "本地节点已卸载，远端当前部署不匹配"

        async with SessionLocal() as session:
            project_id = await resolve_active_project_id(session)
            endpoint = await session.get(Endpoint, deployment_id)
            if endpoint is None or endpoint.project_id != project_id:
                raise KeyError(str(deployment_id))
            config = _deployment_config(endpoint)
            status_payload = (
                agent_status.model_dump(mode="json")
                if agent_status is not None
                else (
                    config.get("agent_status")
                    if isinstance(config.get("agent_status"), dict)
                    else {}
                )
            )
            endpoint.config_json = {
                **config,
                "agent_status": {
                    **status_payload,
                    "phase": "unloaded",
                    "progress": 100,
                    "endpoint": None,
                    "last_event": unload_reason,
                    "error": (
                        {"code": "remote_cleanup_warning", "message": cleanup_warning}
                        if cleanup_warning
                        else None
                    ),
                },
                "endpoint_url": None,
                "unloaded_at": _now().isoformat(),
                "unloaded_reason": unload_reason,
                "unload_task": {
                    **(
                        config.get("unload_task")
                        if isinstance(config.get("unload_task"), dict)
                        else {}
                    ),
                    "status": "completed_with_warnings" if cleanup_warning else "succeeded",
                    "finished_at": _now().isoformat(),
                    "message": unload_reason,
                    "warning": cleanup_warning,
                },
            }
            endpoint.status = "unloaded"
            await self._unpublish_deployment_model(session, config)
            await session.commit()
            await session.refresh(endpoint)
            return _serialize_deployment(endpoint)

    async def stream_chat_deployment(
        self,
        deployment_id: UUID,
        payload: RegistryModelChatRequest,
    ) -> AsyncIterator[str]:
        async with SessionLocal() as session:
            project_id = await resolve_active_project_id(session)
            rows = await session.execute(
                select(Endpoint, Model.name)
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
            endpoint, model_name = row
            config = _deployment_config(endpoint)
            if _is_unloaded_config(config) or _is_superseded_config(config, endpoint.id):
                raise ValueError("该部署当前不可用。")
            served_model_name = _deployment_served_model_name(config, model_name)
            if not served_model_name:
                raise ValueError("部署缺少 Model ID，无法发起对话。")
            machine = await load_runtime_for_endpoint(session, project_id, config)

        agent_status = await self._get_agent_status(machine)
        await self._save_agent_status(deployment_id, agent_status)
        if agent_status.deployment_id != str(deployment_id):
            raise ValueError("该部署已被同一推理机器上的其他部署替换。")
        if agent_status.phase != "ready" or not agent_status.endpoint:
            raise ValueError("部署尚未 ready，暂不能发起体验。")

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
        if not any(message["role"] == "system" for message in messages):
            messages = [
                {
                    "role": "system",
                    "content": (
                        "你是一个简洁、可靠的助手。请直接回答用户问题，"
                        "避免重复相同句子或无意义续写。"
                    ),
                },
                *messages,
            ]

        endpoint_url = agent_status.endpoint.rstrip("/")
        provider_name = machine.name

        async def generator() -> AsyncIterator[str]:
            start_time = perf_counter()
            usage_input_tokens: int | None = None
            usage_output_tokens: int | None = None
            usage_total_tokens: int | None = None
            request_id: str | None = None
            yielded_reasoning = False

            yield _sse_payload(
                {
                    "type": "start",
                    "model_name": served_model_name,
                    "model_code": served_model_name,
                    "provider_name": provider_name,
                    "api_format": "chat-completions",
                    "reasoning_depth": payload.reasoning_depth,
                }
            )

            request_body: dict[str, Any] = {
                "model": served_model_name,
                "messages": messages,
                "stream": True,
                "stream_options": {"include_usage": True},
                "temperature": 0.6,
                "top_p": 0.9,
                "repetition_penalty": 1.08,
                "max_tokens": 2048,
            }
            if payload.parameters:
                protected_keys = {"model", "messages", "stream", "stream_options"}
                request_body.update(
                    {
                        key: value
                        for key, value in payload.parameters.items()
                        if key not in protected_keys
                    }
                )

            try:
                async with httpx.AsyncClient(timeout=None) as client:
                    async with client.stream(
                        "POST",
                        f"{endpoint_url}/chat/completions",
                        headers={
                            "Accept": "text/event-stream",
                            "Content-Type": "application/json",
                            **runtime_headers(machine),
                        },
                        json=request_body,
                    ) as response:
                        request_id = response.headers.get("x-request-id") or response.headers.get(
                            "request-id"
                        )
                        if response.status_code >= 400:
                            detail = (await response.aread()).decode("utf-8", errors="replace")
                            yield _sse_payload(
                                {
                                    "type": "error",
                                    "message": detail
                                    or f"vLLM request failed: {response.status_code}",
                                }
                            )
                            return

                        async for _event_name, raw_data in _iter_sse_events(response):
                            if raw_data == "[DONE]":
                                break
                            payload_data = json.loads(raw_data)
                            choices = payload_data.get("choices")
                            if isinstance(choices, list) and choices:
                                choice = choices[0] if isinstance(choices[0], dict) else {}
                                delta_data = choice.get("delta") if isinstance(choice, dict) else {}
                                if isinstance(delta_data, dict):
                                    content = delta_data.get("content")
                                    if isinstance(content, str) and content:
                                        yield _sse_payload(
                                            {
                                                "type": "text_delta",
                                                "delta": content,
                                            }
                                        )
                                    reasoning_delta = _extract_reasoning_delta(delta_data)
                                    if reasoning_delta:
                                        yielded_reasoning = True
                                        yield _sse_payload(
                                            {
                                                "type": "reasoning_delta",
                                                "delta": reasoning_delta,
                                            }
                                        )

                            input_tokens, output_tokens, total_tokens = _extract_usage_tokens(
                                payload_data
                            )
                            usage_input_tokens = input_tokens or usage_input_tokens
                            usage_output_tokens = output_tokens or usage_output_tokens
                            usage_total_tokens = total_tokens or usage_total_tokens

                yield _sse_payload(
                    {
                        "type": "done",
                        "latency_ms": int((perf_counter() - start_time) * 1000),
                        "request_id": request_id,
                        "input_tokens": usage_input_tokens,
                        "output_tokens": usage_output_tokens,
                        "total_tokens": usage_total_tokens,
                        "reasoning_available": yielded_reasoning,
                        "streaming_mode": "deployment",
                    }
                )
            except Exception as exc:
                yield _sse_payload({"type": "error", "message": str(exc)})

        return generator()

    async def check_passive_health(
        self,
        deployment_id: UUID,
    ) -> ModelDeploymentPassiveHealth:
        async with SessionLocal() as session:
            project_id = await resolve_active_project_id(session)
            rows = await session.execute(
                select(Endpoint, Model.name)
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
            endpoint, model_name = row
            config = _deployment_config(endpoint)
            if _is_unloaded_config(config) or _is_superseded_config(config, endpoint.id):
                result = ModelDeploymentPassiveHealth(
                    deployment_id=deployment_id,
                    status="error",
                    checked_at=_now(),
                    error="该部署当前不是可用节点。",
                )
                await self._save_passive_health_result(deployment_id, result)
                return result
            served_model_name = _deployment_served_model_name(config, model_name)
            if not served_model_name:
                raise ValueError("部署缺少 Model ID，无法执行被动健康检查。")
            machine = await load_runtime_for_endpoint(session, project_id, config)

        checked_at = _now()
        prompt = "hi"
        try:
            agent_status = await self._get_agent_status(machine)
            await self._save_agent_status(deployment_id, agent_status)
            if agent_status.deployment_id != str(deployment_id):
                raise ValueError("该部署已被同一推理机器上的其他部署替换。")
            if agent_status.phase != "ready" or not agent_status.endpoint:
                raise ValueError("部署尚未 ready，暂不能执行被动健康检查。")

            started_at = perf_counter()
            async with httpx.AsyncClient(timeout=20.0) as client:
                response = await client.post(
                    f"{agent_status.endpoint.rstrip('/')}/chat/completions",
                    headers={
                        "Content-Type": "application/json",
                        **runtime_headers(machine),
                    },
                    json={
                        "model": served_model_name,
                        "messages": [{"role": "user", "content": prompt}],
                        "stream": False,
                        "temperature": 0,
                        "max_tokens": 8,
                    },
                )
                response.raise_for_status()
                payload = response.json()

            result = ModelDeploymentPassiveHealth(
                deployment_id=deployment_id,
                status="ok",
                prompt=prompt,
                output_text=_extract_chat_completion_text(payload),
                latency_ms=int((perf_counter() - started_at) * 1000),
                checked_at=checked_at,
            )
        except (httpx.HTTPError, ValueError) as exc:
            result = ModelDeploymentPassiveHealth(
                deployment_id=deployment_id,
                status="error",
                prompt=prompt,
                checked_at=checked_at,
                error=str(exc),
            )

        await self._save_passive_health_result(deployment_id, result)
        return result

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

        return await self._delete_agent_current(machine)

    async def _delete_agent_current(
        self,
        machine: InferenceMachineRuntimeConfig,
    ) -> AgentDeploymentStatus:
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
        deployment_hints = _read_deployment_hints(model)
        tp_options = (
            deployment_hints.tensor_parallel_size_options if deployment_hints is not None else []
        )
        if tp_options and tensor_parallel_size not in tp_options:
            option_text = "、".join(str(option) for option in tp_options)
            raise ValueError(
                f"Tensor Parallel Size {tensor_parallel_size} 与模型 config.json 不匹配，"
                f"可选值：{option_text}。"
            )
        vllm_extra_args = _infer_vllm_reasoning_extra_args(
            model,
            deployment_hints,
            huggingface_metadata=huggingface_metadata,
            object_storage_metadata=object_storage_metadata,
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
                api_key=inference_machine.runtime_api_key,
                extra_args=vllm_extra_args,
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
            if _is_unloaded_config(config):
                return
            if (
                agent_status.deployment_id
                and agent_status.deployment_id != str(endpoint.id)
                and agent_status.phase == "ready"
            ):
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
                "has_been_ready": bool(config.get("has_been_ready"))
                or agent_status.phase == "ready",
                "updated_from_agent_at": _now().isoformat(),
            }
            if agent_status.phase == "ready":
                endpoint.status = "active"
            elif agent_status.phase == "error":
                endpoint.status = "failed"
            elif agent_status.phase == "stopped":
                endpoint.status = "stopped"
            elif agent_status.phase == "stopping":
                endpoint.status = "stopping"
            else:
                endpoint.status = "deploying"
            if agent_status.deployment_id == str(endpoint.id) and agent_status.phase == "ready":
                await self._mark_sibling_deployments_superseded(session, endpoint)
            await session.commit()

    async def _save_passive_health_result(
        self,
        deployment_id: UUID,
        result: ModelDeploymentPassiveHealth,
    ) -> None:
        async with SessionLocal() as session:
            endpoint = await session.get(Endpoint, deployment_id)
            if endpoint is None:
                return
            endpoint.config_json = {
                **_deployment_config(endpoint),
                "passive_health": result.model_dump(mode="json"),
            }
            await session.commit()

    async def _mark_deployment_failed(self, deployment_id: UUID, message: str) -> None:
        async with SessionLocal() as session:
            endpoint = await session.get(Endpoint, deployment_id)
            if endpoint is None:
                return
            config = _deployment_config(endpoint)
            endpoint.config_json = {
                **config,
                "agent_status": {
                    **(
                        config.get("agent_status")
                        if isinstance(config.get("agent_status"), dict)
                        else {}
                    ),
                    "deployment_id": str(endpoint.id),
                    "phase": "error",
                    "progress": 100,
                    "endpoint": None,
                    "last_event": "deployment failed",
                    "error": {
                        "code": "agent_request_failed",
                        "message": message,
                    },
                },
                "endpoint_url": None,
                "updated_from_agent_at": _now().isoformat(),
            }
            endpoint.status = "failed"
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
