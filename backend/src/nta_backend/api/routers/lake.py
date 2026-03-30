from fastapi import APIRouter, HTTPException, Request, status

from nta_backend.api.request_utils import build_browser_s3_endpoint
from nta_backend.schemas.lake import (
    LakeAssetDirectUploadCompleteRequest,
    LakeAssetDirectUploadFailedRequest,
    LakeAssetDirectUploadInitRequest,
    LakeAssetDirectUploadInitResponse,
    LakeAssetSummary,
    LakeBatchCreate,
    LakeBatchSummary,
    LakeUploadAbortRequest,
)
from nta_backend.services.lake_service import LakeService

router = APIRouter(prefix="/lake")
service = LakeService()


@router.get("/batches", response_model=list[LakeBatchSummary])
async def list_lake_batches() -> list[LakeBatchSummary]:
    return await service.list_batches()


@router.get("/assets", response_model=list[LakeAssetSummary])
async def list_lake_assets(stage: str | None = None) -> list[LakeAssetSummary]:
    return await service.list_assets(stage=stage)


@router.post("/batches", response_model=LakeBatchSummary, status_code=status.HTTP_201_CREATED)
async def create_lake_batch(payload: LakeBatchCreate) -> LakeBatchSummary:
    try:
        return await service.create_batch(payload)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post(
    "/assets/direct-upload/init",
    response_model=LakeAssetDirectUploadInitResponse,
    status_code=status.HTTP_201_CREATED,
)
async def prepare_lake_asset_direct_upload(
    request: Request,
    payload: LakeAssetDirectUploadInitRequest,
) -> LakeAssetDirectUploadInitResponse:
    try:
        return await service.prepare_asset_direct_upload(
            payload,
            browser_endpoint_url=build_browser_s3_endpoint(request),
        )
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="Lake batch not found") from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/assets/{asset_id}/direct-upload/complete", response_model=LakeAssetSummary)
async def complete_lake_asset_direct_upload(
    asset_id: str,
    payload: LakeAssetDirectUploadCompleteRequest,
) -> LakeAssetSummary:
    try:
        return await service.complete_asset_direct_upload(asset_id, payload)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="Lake asset not found") from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/assets/{asset_id}/direct-upload/fail", status_code=status.HTTP_204_NO_CONTENT)
async def fail_lake_asset_direct_upload(
    asset_id: str,
    payload: LakeAssetDirectUploadFailedRequest,
) -> None:
    try:
        await service.fail_asset_direct_upload(asset_id, payload)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="Lake asset not found") from exc


@router.post("/uploads/abort", status_code=status.HTTP_204_NO_CONTENT)
async def abort_lake_uploads(payload: LakeUploadAbortRequest) -> None:
    try:
        await service.abort_uploads(payload)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="Lake upload not found") from exc


@router.delete("/assets/{asset_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_lake_asset(asset_id: str) -> None:
    try:
        await service.delete_asset(asset_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="Lake asset not found") from exc
