from uuid import UUID

import httpx
from fastapi import APIRouter, HTTPException, status

from nta_backend.schemas.model_registry import (
    ModelProviderCreate,
    ModelProviderSummary,
    ModelProviderSyncResult,
    ModelProviderUpdate,
)
from nta_backend.services.model_registry_service import ModelRegistryService

router = APIRouter(prefix="/model-providers")
service = ModelRegistryService()


@router.get("", response_model=list[ModelProviderSummary])
async def list_model_providers() -> list[ModelProviderSummary]:
    return await service.list_providers()


@router.get("/{provider_id}", response_model=ModelProviderSummary)
async def get_model_provider(provider_id: UUID) -> ModelProviderSummary:
    try:
        return await service.get_provider(provider_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="Model provider not found") from exc


@router.post("", response_model=ModelProviderSummary, status_code=status.HTTP_201_CREATED)
async def create_model_provider(payload: ModelProviderCreate) -> ModelProviderSummary:
    try:
        return await service.create_provider(payload)
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.patch("/{provider_id}", response_model=ModelProviderSummary)
async def update_model_provider(
    provider_id: UUID, payload: ModelProviderUpdate
) -> ModelProviderSummary:
    try:
        return await service.update_provider(provider_id, payload)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="Model provider not found") from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.delete("/{provider_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_model_provider(provider_id: UUID) -> None:
    try:
        await service.delete_provider(provider_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="Model provider not found") from exc


@router.post("/{provider_id}/sync-models", response_model=ModelProviderSyncResult)
async def sync_model_provider(provider_id: UUID) -> ModelProviderSyncResult:
    try:
        return await service.sync_provider_models(provider_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="Model provider not found") from exc
    except httpx.HTTPError as exc:
        raise HTTPException(
            status_code=502,
            detail=f"Failed to sync models from provider: {exc}",
        ) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
