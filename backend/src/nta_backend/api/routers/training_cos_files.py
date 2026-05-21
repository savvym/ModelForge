from __future__ import annotations

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, BackgroundTasks, HTTPException, Query, status
from fastapi.responses import StreamingResponse

from nta_backend.schemas.training_cos import (
    TrainingCosHuggingFaceFolderFilesResponse,
    TrainingCosHuggingFaceRepoSearchResponse,
    TrainingCosHuggingFaceRepoType,
    TrainingCosHuggingFaceSyncCreateRequest,
    TrainingCosHuggingFaceSyncJob,
    TrainingCosHuggingFaceSyncJobListResponse,
    TrainingCosListResponse,
    TrainingCosPreviewResponse,
    TrainingCosStatus,
)
from nta_backend.services.training_cos_browser_service import (
    TrainingCosBrowserService,
    TrainingCosUnavailable,
    TrainingCosUpstreamError,
)
from nta_backend.services.training_cos_huggingface_sync_service import (
    TrainingCosHuggingFaceSyncService,
)

router = APIRouter(prefix="/training-cos")
service = TrainingCosBrowserService()
hf_sync_service = TrainingCosHuggingFaceSyncService()


def _raise_unavailable(exc: TrainingCosUnavailable) -> HTTPException:
    return HTTPException(status_code=409 if exc.configured else 412, detail=str(exc))


def _raise_upstream(exc: TrainingCosUpstreamError) -> HTTPException:
    if exc.status_code == 404:
        return HTTPException(status_code=404, detail="对象不存在")
    if exc.status_code == 403:
        return HTTPException(status_code=403, detail="无权限访问该对象")
    return HTTPException(status_code=502, detail=f"训练环境 COS 错误：{exc}")


def _raw_download_path(key: str) -> str:
    return f"/api/v1/training-cos/object/raw?key={key}"


def _raise_bad_request(exc: ValueError) -> HTTPException:
    return HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))


@router.get("/status", response_model=TrainingCosStatus)
async def status_endpoint() -> TrainingCosStatus:
    return await service.get_status()


@router.get("/entries", response_model=TrainingCosListResponse)
async def list_entries(
    prefix: str = Query(default="", max_length=2048),
    next_token: str | None = Query(default=None, max_length=2048),
    page_size: int = Query(default=200, ge=1, le=1000),
) -> TrainingCosListResponse:
    try:
        return await service.list_entries(
            prefix=prefix, continuation_token=next_token, page_size=page_size
        )
    except TrainingCosUnavailable as exc:
        raise _raise_unavailable(exc) from exc
    except TrainingCosUpstreamError as exc:
        raise _raise_upstream(exc) from exc


@router.get("/object/preview", response_model=TrainingCosPreviewResponse)
async def preview_object(key: str = Query(..., min_length=1)) -> TrainingCosPreviewResponse:
    try:
        return await service.preview_object(key=key, download_url=_raw_download_path(key))
    except TrainingCosUnavailable as exc:
        raise _raise_unavailable(exc) from exc
    except TrainingCosUpstreamError as exc:
        raise _raise_upstream(exc) from exc


@router.get("/object/raw")
async def download_object(key: str = Query(..., min_length=1)) -> StreamingResponse:
    try:
        body = await service.download_object(key=key)
    except TrainingCosUnavailable as exc:
        raise _raise_unavailable(exc) from exc
    except TrainingCosUpstreamError as exc:
        raise _raise_upstream(exc) from exc

    name = body.object_key.split("/")[-1] or "download.bin"

    def _iter():
        yield body.body

    response = StreamingResponse(_iter(), media_type=body.content_type)
    # Encode filename per RFC 5987 to support non-ASCII names.
    from urllib.parse import quote

    response.headers["Content-Disposition"] = (
        f"attachment; filename*=UTF-8''{quote(name, safe='')}"
    )
    response.headers["Content-Length"] = str(body.size)
    return response


@router.get("/huggingface/repos", response_model=TrainingCosHuggingFaceRepoSearchResponse)
async def search_huggingface_repos(
    query: str = Query(default="", max_length=256),
    repo_type: Annotated[TrainingCosHuggingFaceRepoType, Query()] = "model",
    limit: int = Query(default=12, ge=1, le=50),
) -> TrainingCosHuggingFaceRepoSearchResponse:
    try:
        return await hf_sync_service.search_repos(
            repo_type=repo_type,
            query=query,
            limit=limit,
        )
    except ValueError as exc:
        raise _raise_bad_request(exc) from exc


@router.get(
    "/huggingface/folder-files",
    response_model=TrainingCosHuggingFaceFolderFilesResponse,
)
async def list_huggingface_folder_files(
    prefix: str = Query(..., min_length=1, max_length=2048),
    limit: int = Query(default=10000, ge=1, le=10000),
) -> TrainingCosHuggingFaceFolderFilesResponse:
    try:
        return await hf_sync_service.list_folder_files(prefix=prefix, limit=limit)
    except TrainingCosUnavailable as exc:
        raise _raise_unavailable(exc) from exc
    except TrainingCosUpstreamError as exc:
        raise _raise_upstream(exc) from exc
    except ValueError as exc:
        raise _raise_bad_request(exc) from exc


@router.post("/huggingface/sync-jobs", response_model=TrainingCosHuggingFaceSyncJob)
async def create_huggingface_sync_job(
    payload: TrainingCosHuggingFaceSyncCreateRequest,
    background_tasks: BackgroundTasks,
) -> TrainingCosHuggingFaceSyncJob:
    try:
        job = await hf_sync_service.create_sync_job(payload)
    except ValueError as exc:
        raise _raise_bad_request(exc) from exc
    background_tasks.add_task(hf_sync_service.run_job, job.id)
    return job


@router.get(
    "/huggingface/sync-jobs",
    response_model=TrainingCosHuggingFaceSyncJobListResponse,
)
async def list_huggingface_sync_jobs(
    prefix: str | None = Query(default=None, max_length=2048),
    limit: int = Query(default=20, ge=1, le=50),
) -> TrainingCosHuggingFaceSyncJobListResponse:
    try:
        return await hf_sync_service.list_jobs(prefix=prefix, limit=limit)
    except ValueError as exc:
        raise _raise_bad_request(exc) from exc


@router.get(
    "/huggingface/sync-jobs/{job_id}",
    response_model=TrainingCosHuggingFaceSyncJob,
)
async def get_huggingface_sync_job(job_id: UUID) -> TrainingCosHuggingFaceSyncJob:
    try:
        return await hf_sync_service.get_job(job_id)
    except KeyError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc


@router.post(
    "/huggingface/sync-jobs/{job_id}/retry",
    response_model=TrainingCosHuggingFaceSyncJob,
)
async def retry_huggingface_sync_job(
    job_id: UUID,
    background_tasks: BackgroundTasks,
) -> TrainingCosHuggingFaceSyncJob:
    try:
        job = await hf_sync_service.retry_job(job_id)
    except KeyError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except ValueError as exc:
        raise _raise_bad_request(exc) from exc
    background_tasks.add_task(hf_sync_service.run_job, job.id)
    return job
