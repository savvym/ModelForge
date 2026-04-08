from uuid import UUID

from fastapi import APIRouter, HTTPException, Response, status

from nta_backend.schemas.evaluation_v2 import (
    EvaluationLeaderboardAddRuns,
    EvaluationLeaderboardCreate,
    EvaluationLeaderboardDetail,
    EvaluationLeaderboardRunCandidate,
    EvaluationLeaderboardSummary,
)
from nta_backend.services.evaluation_leaderboard_v2_service import EvaluationLeaderboardV2Service

router = APIRouter(prefix="/api/v2/evaluation-leaderboards")
service = EvaluationLeaderboardV2Service()


@router.get("", response_model=list[EvaluationLeaderboardSummary])
async def list_evaluation_leaderboards() -> list[EvaluationLeaderboardSummary]:
    return await service.list_leaderboards()


@router.get("/available-runs", response_model=list[EvaluationLeaderboardRunCandidate])
async def list_available_evaluation_leaderboard_runs(
    kind: str,
    name: str,
    version: str,
    exclude_leaderboard_id: UUID | None = None,
) -> list[EvaluationLeaderboardRunCandidate]:
    try:
        return await service.list_available_runs(
            kind=kind,
            name=name,
            version=version,
            exclude_leaderboard_id=exclude_leaderboard_id,
        )
    except KeyError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Evaluation target or leaderboard not found") from exc


@router.post("", response_model=EvaluationLeaderboardSummary, status_code=status.HTTP_201_CREATED)
async def create_evaluation_leaderboard(
    payload: EvaluationLeaderboardCreate,
) -> EvaluationLeaderboardSummary:
    try:
        return await service.create_leaderboard(payload)
    except KeyError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Evaluation target not found") from exc
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc


@router.get("/{leaderboard_id}", response_model=EvaluationLeaderboardDetail)
async def get_evaluation_leaderboard(leaderboard_id: UUID) -> EvaluationLeaderboardDetail:
    try:
        return await service.get_leaderboard(leaderboard_id)
    except KeyError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Evaluation leaderboard not found") from exc


@router.post("/{leaderboard_id}/runs", response_model=EvaluationLeaderboardDetail)
async def add_evaluation_leaderboard_runs(
    leaderboard_id: UUID,
    payload: EvaluationLeaderboardAddRuns,
) -> EvaluationLeaderboardDetail:
    try:
        return await service.add_runs(leaderboard_id, payload)
    except KeyError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Evaluation leaderboard not found") from exc
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc


@router.delete("/{leaderboard_id}/runs/{run_id}", status_code=status.HTTP_204_NO_CONTENT)
async def remove_evaluation_leaderboard_run(
    leaderboard_id: UUID,
    run_id: UUID,
) -> Response:
    try:
        await service.remove_run(leaderboard_id, run_id)
    except KeyError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Evaluation leaderboard or run not found") from exc
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.delete("/{leaderboard_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_evaluation_leaderboard(leaderboard_id: UUID) -> Response:
    try:
        await service.delete_leaderboard(leaderboard_id)
    except KeyError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Evaluation leaderboard not found") from exc
    return Response(status_code=status.HTTP_204_NO_CONTENT)
