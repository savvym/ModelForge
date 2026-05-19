from __future__ import annotations

from fastapi import APIRouter, HTTPException, Query, status
from fastapi.responses import StreamingResponse

from nta_backend.schemas.training_cos import (
    TrainingCosListResponse,
    TrainingCosPreviewResponse,
    TrainingCosStatus,
)
from nta_backend.services.training_cos_browser_service import (
    TrainingCosBrowserService,
    TrainingCosUnavailable,
    TrainingCosUpstreamError,
)

router = APIRouter(prefix="/training-cos")
service = TrainingCosBrowserService()


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
