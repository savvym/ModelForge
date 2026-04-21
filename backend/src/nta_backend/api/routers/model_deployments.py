from uuid import UUID

import httpx
from fastapi import APIRouter, HTTPException, Query, status

from nta_backend.schemas.model_deployment import (
    AgentDeploymentStatus,
    DeployModelRequest,
    ModelDeploymentEvent,
    ModelDeploymentSummary,
)
from nta_backend.services.model_deployment_service import ModelDeploymentService

router = APIRouter(prefix="/model-deployments")
service = ModelDeploymentService()


@router.get("", response_model=list[ModelDeploymentSummary])
async def list_deployments() -> list[ModelDeploymentSummary]:
    return await service.list_deployments()


@router.post(
    "/from-model/{model_id}",
    response_model=ModelDeploymentSummary,
    status_code=status.HTTP_201_CREATED,
)
async def deploy_model(model_id: UUID, payload: DeployModelRequest) -> ModelDeploymentSummary:
    try:
        return await service.deploy_model(model_id, payload)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="Model not found") from exc
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


@router.get("/{deployment_id}/events", response_model=list[ModelDeploymentEvent])
async def list_events(
    deployment_id: UUID,
    limit: int = Query(default=200, ge=1, le=1000),
) -> list[ModelDeploymentEvent]:
    try:
        return await service.list_events(deployment_id, limit=limit)
    except httpx.HTTPError as exc:
        raise HTTPException(status_code=502, detail=f"infer-agent request failed: {exc}") from exc


@router.delete("/current", response_model=AgentDeploymentStatus)
async def stop_current() -> AgentDeploymentStatus:
    try:
        return await service.stop_current()
    except httpx.HTTPError as exc:
        raise HTTPException(status_code=502, detail=f"infer-agent request failed: {exc}") from exc
