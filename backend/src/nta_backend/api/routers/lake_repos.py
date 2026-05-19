from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, HTTPException, Query, Response, status
from fastapi.responses import StreamingResponse

from nta_backend.core.gitea_client import GiteaClientError, GiteaServerError, GiteaUnreachable
from nta_backend.schemas.lake_repo import (
    BatchUploadRequest,
    BatchUploadResponse,
    BranchSummary,
    CommitListResponse,
    FileResponse as LakeFileResponse,
    LakeRepoCreate,
    LakeRepoDetail,
    LakeRepoListResponse,
    LakeRepoSummary,
    LakeRepoUpdate,
    TreeResponse,
)
from nta_backend.services.lake_repo_service import LakeRepoService

router = APIRouter(prefix="/data-lake")
service = LakeRepoService()


def _gitea_to_http(exc: Exception) -> HTTPException:
    if isinstance(exc, GiteaUnreachable):
        return HTTPException(status_code=503, detail="Gitea 暂时不可达，请稍后重试")
    if isinstance(exc, GiteaServerError):
        return HTTPException(status_code=502, detail=f"Gitea 错误：{exc.message}")
    if isinstance(exc, GiteaClientError):
        if exc.status_code == 404:
            return HTTPException(status_code=404, detail="资源不存在")
        return HTTPException(status_code=400, detail=exc.message)
    return HTTPException(status_code=500, detail=str(exc))


@router.get("/repos", response_model=LakeRepoListResponse)
async def list_repos(
    query: str | None = Query(default=None, max_length=128),
    page: int = Query(default=1, ge=1, le=10_000),
    page_size: int = Query(default=50, ge=1, le=200),
) -> LakeRepoListResponse:
    return await service.list_repos(query=query, page=page, page_size=page_size)


@router.post(
    "/repos",
    response_model=LakeRepoSummary,
    status_code=status.HTTP_201_CREATED,
)
async def create_repo(payload: LakeRepoCreate) -> LakeRepoSummary:
    try:
        return await service.create_repo(payload)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="项目不存在") from exc
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except (GiteaClientError, GiteaServerError, GiteaUnreachable) as exc:
        raise _gitea_to_http(exc) from exc


@router.get("/repos/{repo_id}", response_model=LakeRepoDetail)
async def get_repo(repo_id: UUID) -> LakeRepoDetail:
    try:
        return await service.get_repo(repo_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="仓库不存在") from exc


@router.patch("/repos/{repo_id}", response_model=LakeRepoSummary)
async def update_repo(repo_id: UUID, payload: LakeRepoUpdate) -> LakeRepoSummary:
    try:
        return await service.update_repo(repo_id, payload)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="仓库不存在") from exc


@router.delete("/repos/{repo_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_repo(repo_id: UUID) -> Response:
    try:
        await service.delete_repo(repo_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="仓库不存在") from exc
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get("/repos/{repo_id}/branches", response_model=list[BranchSummary])
async def list_branches(repo_id: UUID) -> list[BranchSummary]:
    try:
        return await service.list_branches(repo_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="仓库不存在") from exc


@router.get("/repos/{repo_id}/tree/{ref}", response_model=TreeResponse)
async def get_tree(
    repo_id: UUID,
    ref: str,
    path: str = Query(default=""),
) -> TreeResponse:
    try:
        return await service.get_tree(repo_id, ref, path)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="仓库不存在") from exc
    except (GiteaClientError, GiteaServerError, GiteaUnreachable) as exc:
        raise _gitea_to_http(exc) from exc


@router.get("/repos/{repo_id}/file/{ref}", response_model=LakeFileResponse)
async def get_file(
    repo_id: UUID,
    ref: str,
    path: str = Query(..., min_length=1),
) -> LakeFileResponse:
    try:
        return await service.get_file(repo_id, ref, path)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="仓库不存在") from exc
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail="文件不存在") from exc
    except (GiteaClientError, GiteaServerError, GiteaUnreachable) as exc:
        raise _gitea_to_http(exc) from exc


@router.get("/repos/{repo_id}/raw/{ref}/{path:path}")
async def get_raw(repo_id: UUID, ref: str, path: str) -> StreamingResponse:
    try:
        body, content_type = await service.get_file_raw(repo_id, ref, path)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="仓库不存在") from exc
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail="文件不存在") from exc
    except (GiteaClientError, GiteaServerError, GiteaUnreachable) as exc:
        raise _gitea_to_http(exc) from exc

    def _iter() -> bytes:
        yield body

    return StreamingResponse(_iter(), media_type=content_type)


@router.post("/repos/{repo_id}/commits", response_model=BatchUploadResponse)
async def upload_files(repo_id: UUID, payload: BatchUploadRequest) -> BatchUploadResponse:
    try:
        return await service.upload_files(repo_id, payload)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="仓库不存在") from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except (GiteaClientError, GiteaServerError, GiteaUnreachable) as exc:
        raise _gitea_to_http(exc) from exc


@router.get("/repos/{repo_id}/commits/{ref}", response_model=CommitListResponse)
async def list_commits(
    repo_id: UUID,
    ref: str,
    path: str | None = Query(default=None),
    page: int = Query(default=1, ge=1, le=10_000),
    page_size: int = Query(default=30, ge=1, le=100),
) -> CommitListResponse:
    try:
        return await service.list_commits(
            repo_id, ref, path=path, page=page, page_size=page_size
        )
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="仓库不存在") from exc
    except (GiteaClientError, GiteaServerError, GiteaUnreachable) as exc:
        raise _gitea_to_http(exc) from exc
