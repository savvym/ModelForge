from typing import Annotated
from uuid import UUID

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
from nta_backend.schemas.dataset import (
    DatasetCreate,
    DatasetCreateResponse,
    DatasetDetail,
    DatasetDirectUploadCompleteRequest,
    DatasetDirectUploadFailedRequest,
    DatasetDirectUploadInitRequest,
    DatasetDirectUploadInitResponse,
    DatasetSummary,
    DatasetVersionCreate,
    DatasetVersionDirectUploadInitRequest,
    DatasetVersionPreview,
)
from nta_backend.services.dataset_service import DatasetService

router = APIRouter(prefix="/datasets")
service = DatasetService()


@router.get("", response_model=list[DatasetSummary])
async def list_datasets(
    scope: str | None = Query(default=None),
) -> list[DatasetSummary]:
    datasets = await service.list_datasets()
    if scope is None:
        return datasets
    return [dataset for dataset in datasets if dataset.scope == scope]


@router.get("/{dataset_id}", response_model=DatasetDetail)
async def get_dataset(dataset_id: str) -> DatasetDetail:
    try:
        return await service.get_dataset(str(dataset_id))
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="Dataset not found") from exc


@router.get("/{dataset_id}/versions/{version_id}/preview", response_model=DatasetVersionPreview)
async def get_dataset_version_preview(
    dataset_id: str,
    version_id: UUID,
    file_id: Annotated[UUID | None, Query()] = None,
) -> DatasetVersionPreview:
    try:
        return await service.get_dataset_version_preview(
            str(dataset_id),
            str(version_id),
            str(file_id) if file_id else None,
        )
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="Dataset version not found") from exc


@router.get("/{dataset_id}/versions/{version_id}/download")
async def download_dataset_version(
    dataset_id: str,
    version_id: UUID,
    file_id: Annotated[UUID | None, Query()] = None,
) -> StreamingResponse:
    try:
        payload = await service.get_dataset_version_download(
            str(dataset_id),
            str(version_id),
            str(file_id) if file_id else None,
        )
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="Dataset version not found") from exc

    return StreamingResponse(
        iter([payload.object_payload.body]),
        media_type=payload.object_payload.content_type or "application/octet-stream",
        headers={"Content-Disposition": f'attachment; filename="{payload.file_name}"'},
    )


@router.post("", response_model=DatasetCreateResponse, status_code=status.HTTP_201_CREATED)
async def create_dataset(payload: DatasetCreate) -> DatasetCreateResponse:
    try:
        return await service.create_dataset(payload)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post(
    "/direct-upload/init",
    response_model=DatasetDirectUploadInitResponse,
    status_code=status.HTTP_201_CREATED,
)
async def prepare_dataset_direct_upload(
    request: Request,
    payload: DatasetDirectUploadInitRequest,
) -> DatasetDirectUploadInitResponse:
    try:
        return await service.prepare_dataset_direct_upload(
            payload,
            browser_endpoint_url=build_browser_s3_endpoint(request),
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/upload", response_model=DatasetCreateResponse, status_code=status.HTTP_201_CREATED)
async def create_dataset_from_upload(
    name: Annotated[str, Form(...)],
    use_case: Annotated[str, Form(...)],
    modality: Annotated[str, Form(...)],
    recipe: Annotated[str, Form(...)],
    file: Annotated[UploadFile, File(...)],
    description: Annotated[str | None, Form()] = None,
) -> DatasetCreateResponse:
    try:
        return await service.create_dataset_from_upload(
            name=name,
            description=description,
            use_case=use_case,
            modality=modality,
            recipe=recipe,
            upload_file=file,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post(
    "/{dataset_id}/versions",
    response_model=DatasetCreateResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_dataset_version(
    dataset_id: str, payload: DatasetVersionCreate
) -> DatasetCreateResponse:
    try:
        return await service.create_dataset_version(str(dataset_id), payload)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="Dataset not found") from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post(
    "/{dataset_id}/versions/direct-upload/init",
    response_model=DatasetDirectUploadInitResponse,
    status_code=status.HTTP_201_CREATED,
)
async def prepare_dataset_version_direct_upload(
    request: Request,
    dataset_id: str,
    payload: DatasetVersionDirectUploadInitRequest,
) -> DatasetDirectUploadInitResponse:
    try:
        return await service.prepare_dataset_version_direct_upload(
            str(dataset_id),
            payload,
            browser_endpoint_url=build_browser_s3_endpoint(request),
        )
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="Dataset not found") from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post(
    "/{dataset_id}/versions/upload",
    response_model=DatasetCreateResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_dataset_version_from_upload(
    dataset_id: str,
    file: Annotated[UploadFile, File(...)],
    description: Annotated[str | None, Form()] = None,
) -> DatasetCreateResponse:
    try:
        return await service.create_dataset_version_from_upload(
            str(dataset_id), description, file
        )
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="Dataset not found") from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post(
    "/{dataset_id}/versions/{version_id}/direct-upload/complete",
    response_model=DatasetCreateResponse,
)
async def complete_dataset_direct_upload(
    dataset_id: str,
    version_id: UUID,
    payload: DatasetDirectUploadCompleteRequest,
) -> DatasetCreateResponse:
    try:
        return await service.complete_dataset_direct_upload(
            str(dataset_id),
            str(version_id),
            payload,
        )
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="Dataset version not found") from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post(
    "/{dataset_id}/versions/{version_id}/direct-upload/fail",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def fail_dataset_direct_upload(
    dataset_id: str,
    version_id: UUID,
    payload: DatasetDirectUploadFailedRequest,
) -> Response:
    try:
        await service.fail_dataset_direct_upload(
            str(dataset_id),
            str(version_id),
            payload,
        )
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="Dataset version not found") from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.delete("/{dataset_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_dataset(dataset_id: str) -> Response:
    try:
        await service.delete_dataset(str(dataset_id))
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="Dataset not found") from exc
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.delete(
    "/{dataset_id}/versions/{version_id}", status_code=status.HTTP_204_NO_CONTENT
)
async def delete_dataset_version(dataset_id: str, version_id: UUID) -> Response:
    try:
        await service.delete_dataset_version(str(dataset_id), str(version_id))
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="Dataset version not found") from exc
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    return Response(status_code=status.HTTP_204_NO_CONTENT)
