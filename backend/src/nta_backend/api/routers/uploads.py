from typing import Annotated, Literal

from fastapi import (
    APIRouter,
    File,
    Form,
    HTTPException,
    Query,
    Request,
    Response,
    UploadFile,
    status,
)
from fastapi.responses import StreamingResponse

from nta_backend.api.request_utils import build_browser_s3_endpoint
from nta_backend.core.config import get_settings
from nta_backend.core.object_store import (
    list_object_store_entries,
    normalize_object_prefix,
    search_object_store_entries,
)
from nta_backend.core.storage_layout import build_project_prefix, is_project_scoped_prefix
from nta_backend.schemas.dataset import PresignUploadRequest, PresignUploadResponse
from nta_backend.schemas.object_store import (
    ObjectStoreBrowserResponse,
    ObjectStoreDirectUploadInitRequest,
    ObjectStoreDirectUploadInitResponse,
    ObjectStoreFolderCreateRequest,
    ObjectStoreFolderResponse,
    ObjectStoreObjectPreviewResponse,
    ObjectStoreObjectTextUpdateRequest,
    ObjectStoreUploadResponse,
)
from nta_backend.services.dataset_service import DatasetService
from nta_backend.services.object_store_service import ObjectStoreService

router = APIRouter(prefix="/uploads")
service = DatasetService()
object_store_service = ObjectStoreService()


def _resolve_browser_prefix(request: Request, prefix: str | None) -> str:
    current_project_id = request.state.current_project_id
    normalized_prefix = normalize_object_prefix(prefix)
    if not normalized_prefix:
        return build_project_prefix(current_project_id)
    if not is_project_scoped_prefix(current_project_id, normalized_prefix):
        raise ValueError("对象目录超出当前项目范围")
    return normalized_prefix


@router.post("/presign", response_model=PresignUploadResponse)
async def presign_upload(request: Request, payload: PresignUploadRequest) -> PresignUploadResponse:
    return await service.presign_upload(
        payload,
        browser_endpoint_url=build_browser_s3_endpoint(request),
    )


@router.post("/files/direct/init", response_model=ObjectStoreDirectUploadInitResponse)
async def init_direct_upload(
    request: Request,
    payload: ObjectStoreDirectUploadInitRequest,
) -> ObjectStoreDirectUploadInitResponse:
    try:
        return object_store_service.initiate_direct_upload(
            project_id=request.state.current_project_id,
            payload=payload,
            browser_endpoint_url=build_browser_s3_endpoint(request),
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.get("/browser", response_model=ObjectStoreBrowserResponse)
async def browse_object_store(
    request: Request,
    bucket: str | None = Query(default=None),
    prefix: str | None = Query(default=None),
    q: str | None = Query(default=None),
) -> ObjectStoreBrowserResponse:
    target_bucket = bucket or get_settings().s3_bucket_dataset_raw
    try:
        scoped_prefix = _resolve_browser_prefix(request, prefix)
        if q and q.strip():
            return ObjectStoreBrowserResponse(
                **search_object_store_entries(target_bucket, q, scoped_prefix)
            )
        return ObjectStoreBrowserResponse(**list_object_store_entries(target_bucket, scoped_prefix))
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post(
    "/files",
    response_model=ObjectStoreUploadResponse,
    status_code=status.HTTP_201_CREATED,
)
async def upload_project_file(
    request: Request,
    file: Annotated[UploadFile, File(...)],
    prefix: Annotated[str | None, Form()] = None,
    bucket: Annotated[str | None, Form()] = None,
    relative_path: Annotated[str | None, Form()] = None,
) -> ObjectStoreUploadResponse:
    try:
        return await object_store_service.upload_project_file(
            project_id=request.state.current_project_id,
            upload_file=file,
            bucket=bucket,
            prefix=prefix,
            relative_path=relative_path,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post(
    "/folders",
    response_model=ObjectStoreFolderResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_project_folder(
    request: Request,
    payload: ObjectStoreFolderCreateRequest,
) -> ObjectStoreFolderResponse:
    try:
        return object_store_service.create_folder(
            project_id=request.state.current_project_id,
            bucket=payload.bucket,
            prefix=payload.prefix,
            name=payload.name,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.get("/object/download")
async def download_object(
    request: Request,
    bucket: str = Query(...),
    key: str = Query(...),
    disposition: Literal["attachment", "inline"] = Query(default="attachment"),
) -> StreamingResponse:
    try:
        file_name, body, content_type = object_store_service.download_object(
            project_id=request.state.current_project_id,
            bucket=bucket,
            object_key=key,
        )
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail="S3 对象不存在或尚未上传") from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    return StreamingResponse(
        iter([body]),
        media_type=content_type or "application/octet-stream",
        headers={"Content-Disposition": f'{disposition}; filename="{file_name}"'},
    )


@router.get("/object/preview", response_model=ObjectStoreObjectPreviewResponse)
async def preview_object(
    request: Request,
    bucket: str = Query(...),
    key: str = Query(...),
) -> ObjectStoreObjectPreviewResponse:
    try:
        return object_store_service.preview_object(
            project_id=request.state.current_project_id,
            bucket=bucket,
            object_key=key,
        )
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail="S3 对象不存在或尚未上传") from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.put("/object/text", response_model=ObjectStoreUploadResponse)
async def update_text_object(
    request: Request,
    payload: ObjectStoreObjectTextUpdateRequest,
) -> ObjectStoreUploadResponse:
    try:
        return object_store_service.update_text_object(
            project_id=request.state.current_project_id,
            payload=payload,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.delete("/object", status_code=status.HTTP_204_NO_CONTENT)
async def delete_object(
    request: Request,
    bucket: str = Query(...),
    key: str = Query(...),
) -> Response:
    try:
        object_store_service.delete_object(
            project_id=request.state.current_project_id,
            bucket=bucket,
            object_key=key,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.delete("/prefix", status_code=status.HTTP_204_NO_CONTENT)
async def delete_prefix(
    request: Request,
    bucket: str = Query(...),
    prefix: str = Query(...),
) -> Response:
    try:
        object_store_service.delete_prefix(
            project_id=request.state.current_project_id,
            bucket=bucket,
            prefix=prefix,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return Response(status_code=status.HTTP_204_NO_CONTENT)
