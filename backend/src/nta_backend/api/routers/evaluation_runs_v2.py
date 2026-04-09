from fastapi import APIRouter, HTTPException, Response, status

from nta_backend.schemas.evaluation_v2 import (
    BenchmarkEvaluationRunCreate,
    EvaluationRunCancelResponse,
    EvaluationRunCreate,
    EvaluationRunDetail,
    EvaluationRunSummary,
)
from nta_backend.services.evaluation_run_v2_service import EvaluationRunV2Service

router = APIRouter(prefix="/api/v2/evaluation-runs")
service = EvaluationRunV2Service()


@router.get("", response_model=list[EvaluationRunSummary])
async def list_evaluation_runs() -> list[EvaluationRunSummary]:
    return await service.list_runs()


@router.get("/{run_id}", response_model=EvaluationRunDetail)
async def get_evaluation_run(run_id: str) -> EvaluationRunDetail:
    try:
        return await service.get_run(run_id)
    except KeyError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Evaluation run not found") from exc


@router.post("", response_model=EvaluationRunSummary, status_code=status.HTTP_202_ACCEPTED)
async def create_evaluation_run(payload: EvaluationRunCreate) -> EvaluationRunSummary:
    try:
        return await service.create_run(payload)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc


@router.post(
    "/benchmark",
    response_model=EvaluationRunSummary,
    status_code=status.HTTP_202_ACCEPTED,
)
async def create_benchmark_evaluation_run(
    payload: BenchmarkEvaluationRunCreate,
) -> EvaluationRunSummary:
    try:
        return await service.create_benchmark_run(payload)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc


@router.post("/{run_id}/cancel", response_model=EvaluationRunCancelResponse)
async def cancel_evaluation_run(run_id: str) -> EvaluationRunCancelResponse:
    try:
        return await service.cancel_run(run_id)
    except KeyError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Evaluation run not found") from exc
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc


@router.delete("/{run_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_evaluation_run(run_id: str) -> Response:
    try:
        await service.delete_run(run_id)
    except KeyError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Evaluation run not found") from exc
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc
    return Response(status_code=status.HTTP_204_NO_CONTENT)
