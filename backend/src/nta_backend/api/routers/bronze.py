from fastapi import APIRouter, HTTPException, status

from nta_backend.core.config import get_settings
from nta_backend.schemas.bronze import (
    BronzeArtifactSignedUrl,
    BronzeArtifactSummary,
    BronzeAssetDetail,
    BronzeAssetPatch,
    BronzeAssetSummary,
    BronzeImportCreate,
    BronzeImportCreateResponse,
    BronzeJobSummary,
    BronzeSnapshotSummary,
)
from nta_backend.services.bronze_service import BronzeService, build_artifact_download_url

router = APIRouter(prefix="/bronze")
service = BronzeService()


@router.post(
    "/imports",
    response_model=BronzeImportCreateResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_bronze_import(payload: BronzeImportCreate) -> BronzeImportCreateResponse:
    try:
        return await service.create_import(payload)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.get("/assets", response_model=list[BronzeAssetSummary])
async def list_bronze_assets() -> list[BronzeAssetSummary]:
    return await service.list_assets()


@router.get("/assets/{asset_id}", response_model=BronzeAssetDetail)
async def get_bronze_asset(asset_id: str) -> BronzeAssetDetail:
    try:
        return await service.get_asset(asset_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="Bronze asset not found") from exc


@router.patch("/assets/{asset_id}", response_model=BronzeAssetDetail)
async def update_bronze_asset(asset_id: str, payload: BronzeAssetPatch) -> BronzeAssetDetail:
    try:
        return await service.update_asset(asset_id, payload)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="Bronze asset not found") from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/assets/{asset_id}/refresh", response_model=BronzeJobSummary)
async def refresh_bronze_asset(asset_id: str) -> BronzeJobSummary:
    try:
        return await service.refresh_asset(asset_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="Bronze asset not found") from exc


@router.post("/assets/{asset_id}/archive", response_model=BronzeAssetDetail)
async def archive_bronze_asset(asset_id: str) -> BronzeAssetDetail:
    try:
        return await service.archive_asset(asset_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="Bronze asset not found") from exc


@router.delete("/assets/{asset_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_bronze_asset(asset_id: str) -> None:
    try:
        await service.soft_delete_asset(asset_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="Bronze asset not found") from exc


@router.get("/assets/{asset_id}/snapshots", response_model=list[BronzeSnapshotSummary])
async def list_bronze_asset_snapshots(asset_id: str) -> list[BronzeSnapshotSummary]:
    try:
        return await service.list_snapshots(asset_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="Bronze asset not found") from exc


@router.get("/snapshots/{snapshot_id}", response_model=BronzeSnapshotSummary)
async def get_bronze_snapshot(snapshot_id: str) -> BronzeSnapshotSummary:
    try:
        return await service.get_snapshot(snapshot_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="Bronze snapshot not found") from exc


@router.get("/snapshots/{snapshot_id}/artifacts", response_model=list[BronzeArtifactSummary])
async def list_bronze_snapshot_artifacts(snapshot_id: str) -> list[BronzeArtifactSummary]:
    try:
        return await service.list_snapshot_artifacts(snapshot_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="Bronze snapshot not found") from exc


@router.get("/artifacts/{artifact_id}/signed-url", response_model=BronzeArtifactSignedUrl)
async def get_bronze_artifact_signed_url(artifact_id: str) -> BronzeArtifactSignedUrl:
    try:
        artifact = await service.get_artifact(artifact_id)
        return BronzeArtifactSignedUrl(
            artifact_id=artifact.id,
            url=build_artifact_download_url(get_settings().api_base_path, artifact),
        )
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="Bronze artifact not found") from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.get("/jobs", response_model=list[BronzeJobSummary])
async def list_bronze_jobs() -> list[BronzeJobSummary]:
    return await service.list_jobs()


@router.get("/jobs/{job_id}", response_model=BronzeJobSummary)
async def get_bronze_job(job_id: str) -> BronzeJobSummary:
    try:
        return await service.get_job(job_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="Bronze job not found") from exc


@router.post("/jobs/{job_id}/cancel", response_model=BronzeJobSummary)
async def cancel_bronze_job(job_id: str) -> BronzeJobSummary:
    try:
        return await service.cancel_job(job_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="Bronze job not found") from exc
