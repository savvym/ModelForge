from uuid import UUID

import httpx
from fastapi import APIRouter, HTTPException, status
from fastapi.responses import StreamingResponse

from nta_backend.schemas.model_registry import (
    RegistryModelChatRequest,
    RegistryModelChatResponse,
    RegistryModelCreate,
    RegistryModelSummary,
    RegistryModelTestRequest,
    RegistryModelTestResponse,
    RegistryModelUpdate,
)
from nta_backend.services.model_registry_service import ModelRegistryService

router = APIRouter(prefix="/models")
service = ModelRegistryService()


@router.get("", response_model=list[RegistryModelSummary])
async def list_models() -> list[RegistryModelSummary]:
    return await service.list_models()


@router.get("/{model_id}", response_model=RegistryModelSummary)
async def get_model(model_id: UUID) -> RegistryModelSummary:
    try:
        return await service.get_model(model_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="Model not found") from exc


@router.post("", response_model=RegistryModelSummary, status_code=status.HTTP_201_CREATED)
async def create_model(payload: RegistryModelCreate) -> RegistryModelSummary:
    try:
        return await service.create_model(payload)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="Model provider not found") from exc
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.patch("/{model_id}", response_model=RegistryModelSummary)
async def update_model(model_id: UUID, payload: RegistryModelUpdate) -> RegistryModelSummary:
    try:
        return await service.update_model(model_id, payload)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="Model not found") from exc
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.delete("/{model_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_model(model_id: UUID) -> None:
    try:
        await service.delete_model(model_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="Model not found") from exc


@router.post("/{model_id}/test", response_model=RegistryModelTestResponse)
async def test_model(
    model_id: UUID, payload: RegistryModelTestRequest
) -> RegistryModelTestResponse:
    try:
        return await service.test_model(model_id, payload)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="Model not found") from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except httpx.HTTPStatusError as exc:
        detail = exc.response.text.strip() or str(exc)
        raise HTTPException(
            status_code=502,
            detail=f"Provider request failed: {exc.response.status_code} {detail}",
        ) from exc
    except httpx.HTTPError as exc:
        raise HTTPException(status_code=502, detail=f"Provider request failed: {exc}") from exc


@router.post("/{model_id}/chat", response_model=RegistryModelChatResponse)
async def chat_model(
    model_id: UUID, payload: RegistryModelChatRequest
) -> RegistryModelChatResponse:
    try:
        return await service.chat_model(model_id, payload)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="Model not found") from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except httpx.HTTPStatusError as exc:
        detail = exc.response.text.strip() or str(exc)
        raise HTTPException(
            status_code=502,
            detail=f"Provider request failed: {exc.response.status_code} {detail}",
        ) from exc
    except httpx.HTTPError as exc:
        raise HTTPException(status_code=502, detail=f"Provider request failed: {exc}") from exc


@router.post("/{model_id}/chat/stream")
async def stream_chat_model(model_id: UUID, payload: RegistryModelChatRequest) -> StreamingResponse:
    try:
        stream = await service.stream_chat_model(model_id, payload)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="Model not found") from exc
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
