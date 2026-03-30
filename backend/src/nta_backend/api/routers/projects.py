from uuid import UUID

from fastapi import APIRouter, HTTPException, Response, status

from nta_backend.schemas.project import ProjectCreate, ProjectDetail, ProjectSummary
from nta_backend.services.project_service import ProjectService

router = APIRouter(prefix="/projects")
service = ProjectService()


@router.get("", response_model=list[ProjectSummary])
async def list_projects() -> list[ProjectSummary]:
    return await service.list_projects()


@router.get("/{project_id}", response_model=ProjectDetail)
async def get_project(project_id: UUID) -> ProjectDetail:
    try:
        return await service.get_project(project_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="Project not found") from exc


@router.post("", response_model=ProjectSummary, status_code=status.HTTP_201_CREATED)
async def create_project(payload: ProjectCreate) -> ProjectSummary:
    try:
        return await service.create_project(payload)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.delete("/{project_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_project(project_id: UUID) -> Response:
    try:
        await service.delete_project(project_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="Project not found") from exc
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    return Response(status_code=status.HTTP_204_NO_CONTENT)
