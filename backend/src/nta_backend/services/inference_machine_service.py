from __future__ import annotations

from dataclasses import dataclass
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
from nta_backend.models.modeling import InferenceMachine
from nta_backend.schemas.model_deployment import (
    InferenceMachineCreate,
    InferenceMachineHealth,
    InferenceMachineSummary,
)

DEFAULT_MACHINE_CONFIG = {
    "vllm_image": "vllm/vllm-openai:latest",
    "gpu_ids": [],
    "tensor_parallel_size": 8,
    "dtype": "bfloat16",
    "gpu_memory_utilization": 0.85,
    "max_model_len": None,
    "listen_port": 8000,
}


@dataclass(frozen=True)
class InferenceMachineRuntimeConfig:
    id: UUID | None
    name: str
    agent_base_url: str
    agent_token: str
    runtime_api_key: str
    runtime_public_host: str | None
    vllm_image: str
    gpu_ids: list[int]
    tensor_parallel_size: int
    dtype: str
    gpu_memory_utilization: float
    max_model_len: int | None
    listen_port: int


def _now() -> datetime:
    return datetime.now(UTC)


def _normalize_optional_text(value: str | None) -> str | None:
    if value is None:
        return None
    text = value.strip()
    return text or None


def _require_text(value: str | None, message: str) -> str:
    text = _normalize_optional_text(value)
    if text is None:
        raise ValueError(message)
    return text


def _normalize_base_url(value: str) -> str:
    return value.strip().rstrip("/")


def _validate_gpu_ids(value: list[int]) -> list[int]:
    gpu_ids = [int(item) for item in value]
    if any(item < 0 for item in gpu_ids):
        raise ValueError("GPU IDs 需要填写非负整数。")
    if len(gpu_ids) != len(set(gpu_ids)):
        raise ValueError("GPU IDs 不能重复。")
    return gpu_ids


def _sanitize_gpus(value: Any) -> list[dict[str, Any]]:
    if not isinstance(value, list):
        return []
    sanitized: list[dict[str, Any]] = []
    for item in value:
        if not isinstance(item, dict):
            continue
        sanitized.append(
            {
                key: item[key]
                for key in (
                    "index",
                    "name",
                    "memory_total_mb",
                    "memory_used_mb",
                    "utilization_gpu_percent",
                    "temperature_c",
                )
                if key in item
            }
        )
    return sanitized


def _config(machine: InferenceMachine) -> dict[str, Any]:
    config = machine.config_json if isinstance(machine.config_json, dict) else {}
    return {**DEFAULT_MACHINE_CONFIG, **config}


def _read_gpu_ids(config: dict[str, Any]) -> list[int]:
    value = config.get("gpu_ids")
    if not isinstance(value, list):
        return list(DEFAULT_MACHINE_CONFIG["gpu_ids"])
    return [int(item) for item in value if isinstance(item, int | str) and str(item).isdigit()]


def _read_int(config: dict[str, Any], key: str) -> int:
    value = config.get(key)
    if isinstance(value, int):
        return value
    if isinstance(value, str) and value.isdigit():
        return int(value)
    return int(DEFAULT_MACHINE_CONFIG[key])


def _read_float(config: dict[str, Any], key: str) -> float:
    value = config.get(key)
    if isinstance(value, int | float):
        return float(value)
    if isinstance(value, str):
        try:
            return float(value)
        except ValueError:
            pass
    return float(DEFAULT_MACHINE_CONFIG[key])


def _read_optional_int(config: dict[str, Any], key: str) -> int | None:
    value = config.get(key)
    if value is None:
        return None
    if isinstance(value, int):
        return value
    if isinstance(value, str) and value.isdigit():
        return int(value)
    return None


def _runtime_api_key(config: dict[str, Any]) -> str | None:
    value = config.get("runtime_api_key")
    return value.strip() if isinstance(value, str) and value.strip() else None


def _serialize_machine(machine: InferenceMachine) -> InferenceMachineSummary:
    config = _config(machine)
    return InferenceMachineSummary(
        id=machine.id,
        name=machine.name,
        agent_base_url=machine.agent_base_url,
        runtime_public_host=machine.runtime_public_host,
        description=machine.description,
        status=machine.status,
        has_agent_token=bool(machine.agent_token),
        has_runtime_api_key=bool(_runtime_api_key(config)),
        vllm_image=str(config.get("vllm_image") or DEFAULT_MACHINE_CONFIG["vllm_image"]),
        gpu_ids=_read_gpu_ids(config),
        tensor_parallel_size=_read_int(config, "tensor_parallel_size"),
        dtype=str(config.get("dtype") or DEFAULT_MACHINE_CONFIG["dtype"]),
        gpu_memory_utilization=_read_float(config, "gpu_memory_utilization"),
        max_model_len=_read_optional_int(config, "max_model_len"),
        listen_port=_read_int(config, "listen_port"),
        last_health_status=_normalize_optional_text(config.get("last_health_status")),
        last_health_checked_at=config.get("last_health_checked_at"),
        last_health_error=_normalize_optional_text(config.get("last_health_error")),
        last_node_name=_normalize_optional_text(config.get("last_node_name")),
        last_gpu_count=_read_optional_int(config, "last_gpu_count"),
        last_gpus=_sanitize_gpus(config.get("last_gpus")),
        created_at=machine.created_at,
        updated_at=machine.updated_at,
    )


def machine_runtime_config(machine: InferenceMachine) -> InferenceMachineRuntimeConfig:
    config = _config(machine)
    return InferenceMachineRuntimeConfig(
        id=machine.id,
        name=machine.name,
        agent_base_url=machine.agent_base_url.rstrip("/"),
        agent_token=_require_text(machine.agent_token, "推理机器缺少 Agent Token。"),
        runtime_api_key=_require_text(
            _runtime_api_key(config),
            "推理机器缺少 Runtime API Key。",
        ),
        runtime_public_host=machine.runtime_public_host,
        vllm_image=str(config.get("vllm_image") or DEFAULT_MACHINE_CONFIG["vllm_image"]),
        gpu_ids=_read_gpu_ids(config),
        tensor_parallel_size=_read_int(config, "tensor_parallel_size"),
        dtype=str(config.get("dtype") or DEFAULT_MACHINE_CONFIG["dtype"]),
        gpu_memory_utilization=_read_float(config, "gpu_memory_utilization"),
        max_model_len=_read_optional_int(config, "max_model_len"),
        listen_port=_read_int(config, "listen_port"),
    )


def legacy_env_machine_runtime_config() -> InferenceMachineRuntimeConfig | None:
    settings = get_settings()
    if not settings.infer_agent_base_url:
        return None
    if settings.infer_agent_token is None:
        raise ValueError("INFER_AGENT_TOKEN is required when INFER_AGENT_BASE_URL is configured.")
    if settings.infer_runtime_api_key is None:
        raise ValueError(
            "INFER_RUNTIME_API_KEY is required when INFER_AGENT_BASE_URL is configured."
        )
    gpu_ids = [
        int(item.strip())
        for item in settings.infer_default_gpu_ids.split(",")
        if item.strip()
    ]
    return InferenceMachineRuntimeConfig(
        id=None,
        name="环境变量机器",
        agent_base_url=settings.infer_agent_base_url.rstrip("/"),
        agent_token=settings.infer_agent_token.get_secret_value().strip(),
        runtime_api_key=settings.infer_runtime_api_key.get_secret_value().strip(),
        runtime_public_host=settings.infer_runtime_public_host,
        vllm_image=settings.infer_vllm_image,
        gpu_ids=gpu_ids,
        tensor_parallel_size=settings.infer_default_tensor_parallel_size,
        dtype=settings.infer_default_dtype,
        gpu_memory_utilization=settings.infer_default_gpu_memory_utilization,
        max_model_len=settings.infer_default_max_model_len,
        listen_port=settings.infer_default_listen_port,
    )


async def load_inference_machine_runtime(
    session: AsyncSession,
    project_id: UUID,
    machine_id: UUID | None,
) -> InferenceMachineRuntimeConfig:
    if machine_id is not None:
        machine = await session.get(InferenceMachine, machine_id)
        if machine is None or machine.project_id != project_id or machine.status == "deleted":
            raise KeyError(str(machine_id))
        return machine_runtime_config(machine)

    rows = await session.execute(
        select(InferenceMachine)
        .where(
            InferenceMachine.project_id == project_id,
            InferenceMachine.status == "active",
        )
        .order_by(InferenceMachine.created_at.asc())
    )
    machines = list(rows.scalars().all())
    if len(machines) == 1:
        return machine_runtime_config(machines[0])
    if machines:
        raise ValueError("请先选择推理机器后再部署。")

    legacy_machine = legacy_env_machine_runtime_config()
    if legacy_machine is not None:
        return legacy_machine

    raise ValueError("请先在在线推理的机器管理中添加已部署 infer-agent 的机器。")


async def load_runtime_for_endpoint(
    session: AsyncSession,
    project_id: UUID,
    endpoint_config: dict[str, Any],
) -> InferenceMachineRuntimeConfig:
    raw_machine_id = endpoint_config.get("machine_id")
    if isinstance(raw_machine_id, str) and raw_machine_id:
        return await load_inference_machine_runtime(session, project_id, UUID(raw_machine_id))

    legacy_machine = legacy_env_machine_runtime_config()
    if legacy_machine is not None:
        return legacy_machine

    agent_base_url = endpoint_config.get("agent_base_url")
    if isinstance(agent_base_url, str) and agent_base_url.strip():
        endpoint_agent_token = endpoint_config.get("agent_token")
        if not isinstance(endpoint_agent_token, str):
            endpoint_agent_token = None
        return InferenceMachineRuntimeConfig(
            id=None,
            name=str(endpoint_config.get("machine_name") or "历史部署机器"),
            agent_base_url=agent_base_url.rstrip("/"),
            agent_token=_require_text(
                endpoint_agent_token,
                "历史部署记录缺少 Agent Token。",
            ),
            runtime_api_key=_require_text(
                endpoint_config.get("runtime_api_key")
                if isinstance(endpoint_config.get("runtime_api_key"), str)
                else None,
                "历史部署记录缺少 Runtime API Key。",
            ),
            runtime_public_host=None,
            vllm_image=str(
                endpoint_config.get("vllm_image") or DEFAULT_MACHINE_CONFIG["vllm_image"]
            ),
            gpu_ids=list(DEFAULT_MACHINE_CONFIG["gpu_ids"]),
            tensor_parallel_size=int(DEFAULT_MACHINE_CONFIG["tensor_parallel_size"]),
            dtype=str(DEFAULT_MACHINE_CONFIG["dtype"]),
            gpu_memory_utilization=float(DEFAULT_MACHINE_CONFIG["gpu_memory_utilization"]),
            max_model_len=None,
            listen_port=int(DEFAULT_MACHINE_CONFIG["listen_port"]),
        )

    raise ValueError("部署记录缺少推理机器信息。")


def agent_headers(machine: InferenceMachineRuntimeConfig) -> dict[str, str]:
    return {"Authorization": f"Bearer {machine.agent_token}"}


def runtime_headers(machine: InferenceMachineRuntimeConfig) -> dict[str, str]:
    return {"Authorization": f"Bearer {machine.runtime_api_key}"}


class InferenceMachineService:
    async def list_machines(self) -> list[InferenceMachineSummary]:
        async with SessionLocal() as session:
            project_id = await resolve_active_project_id(session)
            rows = await session.execute(
                select(InferenceMachine)
                .where(
                    InferenceMachine.project_id == project_id,
                    InferenceMachine.status != "deleted",
                )
                .order_by(InferenceMachine.created_at.desc())
            )
            return [_serialize_machine(machine) for machine in rows.scalars().all()]

    async def create_machine(
        self,
        payload: InferenceMachineCreate,
    ) -> InferenceMachineSummary:
        async with SessionLocal() as session:
            project_id = await resolve_active_project_id(session)
            name = payload.name.strip()
            agent_base_url = _normalize_base_url(payload.agent_base_url)
            vllm_image = payload.vllm_image.strip()
            dtype = payload.dtype.strip()
            gpu_ids = _validate_gpu_ids(payload.gpu_ids)
            if not name:
                raise ValueError("请填写推理机器名称。")
            if not agent_base_url:
                raise ValueError("请填写 Agent URL。")
            agent_token = _require_text(payload.agent_token, "请填写 Agent Token。")
            runtime_api_key = _require_text(payload.runtime_api_key, "请填写 Runtime API Key。")
            if not vllm_image:
                raise ValueError("请填写 vLLM Image。")
            if not dtype:
                raise ValueError("请填写 dtype。")
            machine = InferenceMachine(
                project_id=project_id,
                name=name,
                agent_base_url=agent_base_url,
                agent_token=agent_token,
                runtime_public_host=_normalize_optional_text(payload.runtime_public_host),
                description=_normalize_optional_text(payload.description),
                status="active",
                created_by=get_current_user_id(),
                config_json={
                    "vllm_image": vllm_image,
                    "gpu_ids": gpu_ids,
                    "tensor_parallel_size": payload.tensor_parallel_size,
                    "dtype": dtype,
                    "gpu_memory_utilization": payload.gpu_memory_utilization,
                    "max_model_len": payload.max_model_len,
                    "listen_port": payload.listen_port,
                    "runtime_api_key": runtime_api_key,
                },
            )
            session.add(machine)
            try:
                await session.commit()
            except IntegrityError as exc:
                await session.rollback()
                raise ValueError("推理机器名称已存在，请更换后重试。") from exc
            await session.refresh(machine)
            return _serialize_machine(machine)

    async def delete_machine(self, machine_id: UUID) -> None:
        async with SessionLocal() as session:
            project_id = await resolve_active_project_id(session)
            machine = await session.get(InferenceMachine, machine_id)
            if machine is None or machine.project_id != project_id:
                raise KeyError(str(machine_id))
            machine.status = "deleted"
            await session.commit()

    async def check_machine_health(self, machine_id: UUID) -> InferenceMachineHealth:
        async with SessionLocal() as session:
            project_id = await resolve_active_project_id(session)
            machine = await session.get(InferenceMachine, machine_id)
            if machine is None or machine.project_id != project_id or machine.status == "deleted":
                raise KeyError(str(machine_id))
            runtime = machine_runtime_config(machine)

            checked_at = _now()
            try:
                async with httpx.AsyncClient(timeout=8.0) as client:
                    response = await client.get(
                        f"{runtime.agent_base_url}/v1/health",
                        headers=agent_headers(runtime),
                    )
                    response.raise_for_status()
                    payload = response.json()
                status = (
                    str(payload.get("status") or "unknown")
                    if isinstance(payload, dict)
                    else "unknown"
                )
                node_name = (
                    payload.get("node_name")
                    if isinstance(payload, dict) and isinstance(payload.get("node_name"), str)
                    else None
                )
                current = payload.get("current") if isinstance(payload, dict) else None
                gpus = payload.get("gpus") if isinstance(payload, dict) else []
                if not isinstance(current, dict):
                    current = None
                if not isinstance(gpus, list):
                    gpus = []
                error = None
            except (httpx.HTTPError, ValueError) as exc:
                status = "unreachable"
                node_name = None
                current = None
                gpus = []
                error = str(exc)

            config = _config(machine)
            config.update(
                {
                    "last_health_status": status,
                    "last_health_checked_at": checked_at.isoformat(),
                    "last_health_error": error,
                    "last_node_name": node_name,
                    "last_gpu_count": len(gpus),
                    "last_gpus": _sanitize_gpus(gpus),
                }
            )
            machine.config_json = config
            await session.commit()

        return InferenceMachineHealth(
            machine_id=machine_id,
            status=status,
            node_name=node_name,
            current=current,
            gpus=[item for item in gpus if isinstance(item, dict)],
            checked_at=checked_at,
            error=error,
        )
