from typing import Annotated
from uuid import UUID

import httpx
from fastapi import APIRouter, HTTPException, Query, status
from fastapi.responses import StreamingResponse

from nta_backend.schemas.model_deployment import (
    AgentDeploymentStatus,
    DeployModelRequest,
    InferenceMachineCreate,
    InferenceMachineHealth,
    InferenceMachineSummary,
    ModelDeploymentEvent,
    ModelDeploymentPassiveHealth,
    ModelDeploymentSummary,
)
from nta_backend.schemas.model_registry import RegistryModelChatRequest
from nta_backend.services.inference_machine_service import InferenceMachineService
from nta_backend.services.model_deployment_service import ModelDeploymentService

router = APIRouter(prefix="/model-deployments")
service = ModelDeploymentService()
machine_service = InferenceMachineService()


@router.get("", response_model=list[ModelDeploymentSummary])
async def list_deployments() -> list[ModelDeploymentSummary]:
    return await service.list_deployments()


@router.get("/my", response_model=list[ModelDeploymentSummary])
async def list_my_deployments() -> list[ModelDeploymentSummary]:
    return await service.list_my_deployments()


@router.get("/machines", response_model=list[InferenceMachineSummary])
async def list_inference_machines() -> list[InferenceMachineSummary]:
    return await machine_service.list_machines()


@router.post(
    "/machines",
    response_model=InferenceMachineSummary,
    status_code=status.HTTP_201_CREATED,
)
async def create_inference_machine(
    payload: InferenceMachineCreate,
) -> InferenceMachineSummary:
    try:
        return await machine_service.create_machine(payload)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/machines/{machine_id}/health", response_model=InferenceMachineHealth)
async def check_inference_machine_health(machine_id: UUID) -> InferenceMachineHealth:
    try:
        return await machine_service.check_machine_health(machine_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="Inference machine not found") from exc


@router.delete("/machines/{machine_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_inference_machine(machine_id: UUID) -> None:
    try:
        await machine_service.delete_machine(machine_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="Inference machine not found") from exc


@router.post(
    "/from-model/{model_id}",
    response_model=ModelDeploymentSummary,
    status_code=status.HTTP_201_CREATED,
)
async def deploy_model(model_id: UUID, payload: DeployModelRequest) -> ModelDeploymentSummary:
    try:
        return await service.deploy_model(model_id, payload)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="Model or inference machine not found") from exc
    except httpx.HTTPError as exc:
        raise HTTPException(status_code=502, detail=f"infer-agent request failed: {exc}") from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.get("/{deployment_id}", response_model=ModelDeploymentSummary)
async def get_deployment(deployment_id: UUID) -> ModelDeploymentSummary:
    try:
        return await service.get_deployment(deployment_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="Deployment not found") from exc


@router.post("/{deployment_id}/refresh", response_model=ModelDeploymentSummary)
async def refresh_deployment(deployment_id: UUID) -> ModelDeploymentSummary:
    try:
        return await service.refresh_deployment(deployment_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="Deployment not found") from exc
    except httpx.HTTPError as exc:
        raise HTTPException(status_code=502, detail=f"infer-agent request failed: {exc}") from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/{deployment_id}/stop", response_model=ModelDeploymentSummary)
async def stop_deployment(deployment_id: UUID) -> ModelDeploymentSummary:
    try:
        return await service.stop_deployment(deployment_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="Deployment not found") from exc
    except httpx.HTTPError as exc:
        raise HTTPException(status_code=502, detail=f"infer-agent request failed: {exc}") from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/{deployment_id}/start", response_model=ModelDeploymentSummary)
async def start_deployment(deployment_id: UUID) -> ModelDeploymentSummary:
    try:
        return await service.start_deployment(deployment_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="Deployment not found") from exc
    except httpx.HTTPError as exc:
        raise HTTPException(status_code=502, detail=f"infer-agent request failed: {exc}") from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/{deployment_id}/unload", response_model=ModelDeploymentSummary)
async def unload_deployment(deployment_id: UUID) -> ModelDeploymentSummary:
    try:
        return await service.unload_deployment(deployment_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="Deployment not found") from exc
    except httpx.HTTPError as exc:
        raise HTTPException(status_code=502, detail=f"infer-agent request failed: {exc}") from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/{deployment_id}/passive-health", response_model=ModelDeploymentPassiveHealth)
async def check_deployment_passive_health(
    deployment_id: UUID,
) -> ModelDeploymentPassiveHealth:
    try:
        return await service.check_passive_health(deployment_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="Deployment not found") from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.delete("/{deployment_id}/tasks/{task_kind}", response_model=ModelDeploymentSummary)
async def delete_deployment_task(
    deployment_id: UUID,
    task_kind: str,
) -> ModelDeploymentSummary:
    try:
        return await service.delete_task(deployment_id, task_kind)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="Deployment not found") from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/{deployment_id}/chat/stream")
async def stream_deployment_chat(
    deployment_id: UUID,
    payload: RegistryModelChatRequest,
) -> StreamingResponse:
    try:
        stream = await service.stream_chat_deployment(deployment_id, payload)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="Deployment not found") from exc
    except httpx.HTTPError as exc:
        raise HTTPException(status_code=502, detail=f"infer-agent request failed: {exc}") from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    return StreamingResponse(
        stream,
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


@router.get("/{deployment_id}/events", response_model=list[ModelDeploymentEvent])
async def list_events(
    deployment_id: UUID,
    limit: int = Query(default=200, ge=1, le=1000),
) -> list[ModelDeploymentEvent]:
    try:
        return await service.list_events(deployment_id, limit=limit)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="Deployment not found") from exc
    except httpx.HTTPError as exc:
        raise HTTPException(status_code=502, detail=f"infer-agent request failed: {exc}") from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.delete("/current", response_model=AgentDeploymentStatus)
async def stop_current(machine_id: Annotated[UUID | None, Query()] = None) -> AgentDeploymentStatus:
    try:
        return await service.stop_current(machine_id=machine_id)
    except httpx.HTTPError as exc:
        raise HTTPException(status_code=502, detail=f"infer-agent request failed: {exc}") from exc
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="Inference machine not found") from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
