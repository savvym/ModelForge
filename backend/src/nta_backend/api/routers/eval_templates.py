from fastapi import APIRouter, HTTPException, status

from nta_backend.schemas.eval_template import (
    EvalTemplateCreate,
    EvalTemplateSummary,
    EvalTemplateUpdate,
)
from nta_backend.services.eval_template_service import EvalTemplateService

router = APIRouter(prefix="/eval-templates")
service = EvalTemplateService()


@router.get("", response_model=list[EvalTemplateSummary])
async def list_templates() -> list[EvalTemplateSummary]:
    return await service.list_templates()


@router.post(
    "",
    response_model=EvalTemplateSummary,
    status_code=status.HTTP_201_CREATED,
)
async def create_template(payload: EvalTemplateCreate) -> EvalTemplateSummary:
    try:
        return await service.create_template(payload)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.get("/{name}", response_model=EvalTemplateSummary)
async def get_template(name: str, version: int | None = None) -> EvalTemplateSummary:
    try:
        return await service.get_template(name, version)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="Template not found") from exc


@router.get("/{name}/versions", response_model=list[EvalTemplateSummary])
async def get_template_versions(name: str) -> list[EvalTemplateSummary]:
    try:
        return await service.get_template_versions(name)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="Template not found") from exc


@router.put("/{name}", response_model=EvalTemplateSummary)
async def update_template(
    name: str, payload: EvalTemplateUpdate
) -> EvalTemplateSummary:
    try:
        return await service.update_template(name, payload)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="Template not found") from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
