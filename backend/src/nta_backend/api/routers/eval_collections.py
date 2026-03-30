from uuid import UUID

from fastapi import APIRouter, HTTPException, status

from nta_backend.schemas.eval_collection import (
    CollectionRunRequest,
    CollectionRunResponse,
    EvalCollectionCreate,
    EvalCollectionDetail,
    EvalCollectionSummary,
)
from nta_backend.services.eval_collection_service import EvalCollectionService

router = APIRouter(prefix="/eval-collections")
service = EvalCollectionService()


@router.get("", response_model=list[EvalCollectionSummary])
async def list_collections() -> list[EvalCollectionSummary]:
    return await service.list_collections()


@router.post("", response_model=EvalCollectionSummary, status_code=status.HTTP_201_CREATED)
async def create_collection(payload: EvalCollectionCreate) -> EvalCollectionSummary:
    try:
        return await service.create_collection(payload)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc


@router.get("/{collection_id}", response_model=EvalCollectionDetail)
async def get_collection(collection_id: UUID) -> EvalCollectionDetail:
    try:
        return await service.get_collection(collection_id)
    except KeyError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Collection not found",
        ) from exc


@router.post(
    "/{collection_id}/run",
    response_model=CollectionRunResponse,
    status_code=status.HTTP_202_ACCEPTED,
)
async def run_collection(
    collection_id: UUID,
    payload: CollectionRunRequest,
) -> CollectionRunResponse:
    try:
        return await service.run_collection(collection_id, payload)
    except KeyError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Collection not found",
        ) from exc
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc


@router.delete("/{collection_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_collection(collection_id: UUID) -> None:
    try:
        await service.delete_collection(collection_id)
    except KeyError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Collection not found",
        ) from exc
