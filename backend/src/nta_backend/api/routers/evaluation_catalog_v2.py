from fastapi import APIRouter, HTTPException, status
from uuid import UUID

from nta_backend.schemas.evaluation_v2 import (
    EvaluationCatalogResponse,
    EvalSpecCreate,
    EvalSpecSummary,
    EvalSpecUpdate,
    EvalSuiteCreate,
    EvalSuiteSummary,
    EvalSuiteUpdate,
    JudgePolicyCreate,
    JudgePolicySummary,
    TemplateSpecCreate,
    TemplateSpecSummary,
)
from nta_backend.services.evaluation_catalog_v2_service import (
    CatalogConflictError,
    EvaluationCatalogV2Service,
)

router = APIRouter(prefix="/api/v2/evaluation-catalog")
service = EvaluationCatalogV2Service()


@router.get("", response_model=EvaluationCatalogResponse)
async def list_evaluation_catalog() -> EvaluationCatalogResponse:
    return await service.list_catalog()


@router.get("/specs/{name}", response_model=EvalSpecSummary)
async def get_eval_spec(name: str) -> EvalSpecSummary:
    try:
        return await service.get_spec(name)
    except KeyError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Eval spec not found") from exc


@router.post("/specs", response_model=EvalSpecSummary, status_code=status.HTTP_201_CREATED)
async def create_eval_spec(payload: EvalSpecCreate) -> EvalSpecSummary:
    try:
        return await service.create_spec(payload)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc


@router.patch("/specs/{name}", response_model=EvalSpecSummary)
async def update_eval_spec(name: str, payload: EvalSpecUpdate) -> EvalSpecSummary:
    try:
        return await service.update_spec(name, payload)
    except KeyError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Eval spec not found") from exc
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc


@router.delete("/specs/{name}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_eval_spec(name: str) -> None:
    try:
        await service.delete_spec(name)
    except KeyError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Eval spec not found") from exc
    except CatalogConflictError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc


@router.post("/specs/{name}/versions/{version_id}/sync-datasets", response_model=EvalSpecSummary)
async def sync_eval_spec_version_datasets(name: str, version_id: UUID) -> EvalSpecSummary:
    try:
        return await service.sync_spec_version_datasets(name, version_id)
    except KeyError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Eval spec not found") from exc
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc


@router.get("/suites/{name}", response_model=EvalSuiteSummary)
async def get_eval_suite(name: str) -> EvalSuiteSummary:
    try:
        return await service.get_suite(name)
    except KeyError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Eval suite not found") from exc


@router.post("/suites", response_model=EvalSuiteSummary, status_code=status.HTTP_201_CREATED)
async def create_eval_suite(payload: EvalSuiteCreate) -> EvalSuiteSummary:
    try:
        return await service.create_suite(payload)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc


@router.patch("/suites/{name}", response_model=EvalSuiteSummary)
async def update_eval_suite(name: str, payload: EvalSuiteUpdate) -> EvalSuiteSummary:
    try:
        return await service.update_suite(name, payload)
    except KeyError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Eval suite not found") from exc
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc


@router.delete("/suites/{name}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_eval_suite(name: str) -> None:
    try:
        await service.delete_suite(name)
    except KeyError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Eval suite not found") from exc
    except CatalogConflictError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc


@router.get("/templates", response_model=list[TemplateSpecSummary])
async def list_template_specs() -> list[TemplateSpecSummary]:
    return await service.list_templates()


@router.post("/templates", response_model=TemplateSpecSummary, status_code=status.HTTP_201_CREATED)
async def create_template_spec(payload: TemplateSpecCreate) -> TemplateSpecSummary:
    try:
        return await service.create_template(payload)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc


@router.get("/judge-policies", response_model=list[JudgePolicySummary])
async def list_judge_policies() -> list[JudgePolicySummary]:
    return await service.list_judge_policies()


@router.post(
    "/judge-policies",
    response_model=JudgePolicySummary,
    status_code=status.HTTP_201_CREATED,
)
async def create_judge_policy(payload: JudgePolicyCreate) -> JudgePolicySummary:
    try:
        return await service.create_judge_policy(payload)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
