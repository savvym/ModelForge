from uuid import UUID

from fastapi import APIRouter, HTTPException, Response, status

from nta_backend.schemas.benchmark_leaderboard import (
    BenchmarkLeaderboardAddJobs,
    BenchmarkLeaderboardCreate,
    BenchmarkLeaderboardDetail,
    BenchmarkLeaderboardJobCandidate,
    BenchmarkLeaderboardSummary,
)
from nta_backend.services.benchmark_leaderboard_service import BenchmarkLeaderboardService

router = APIRouter(prefix="/benchmark-leaderboards")
service = BenchmarkLeaderboardService()


@router.get("", response_model=list[BenchmarkLeaderboardSummary])
async def list_benchmark_leaderboards() -> list[BenchmarkLeaderboardSummary]:
    return await service.list_leaderboards()


@router.get("/available-jobs", response_model=list[BenchmarkLeaderboardJobCandidate])
async def list_available_benchmark_leaderboard_jobs(
    benchmark_name: str,
    benchmark_version_id: str,
    exclude_leaderboard_id: UUID | None = None,
) -> list[BenchmarkLeaderboardJobCandidate]:
    try:
        return await service.list_available_jobs(
            benchmark_name=benchmark_name,
            benchmark_version_id=benchmark_version_id,
            exclude_leaderboard_id=exclude_leaderboard_id,
        )
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="Benchmark, Version or leaderboard not found") from exc


@router.post(
    "",
    response_model=BenchmarkLeaderboardSummary,
    status_code=status.HTTP_201_CREATED,
)
async def create_benchmark_leaderboard(
    payload: BenchmarkLeaderboardCreate,
) -> BenchmarkLeaderboardSummary:
    try:
        return await service.create_leaderboard(payload)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.get("/{leaderboard_id}", response_model=BenchmarkLeaderboardDetail)
async def get_benchmark_leaderboard(
    leaderboard_id: UUID,
) -> BenchmarkLeaderboardDetail:
    try:
        return await service.get_leaderboard(leaderboard_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="Leaderboard not found") from exc


@router.post("/{leaderboard_id}/jobs", response_model=BenchmarkLeaderboardDetail)
async def add_benchmark_leaderboard_jobs(
    leaderboard_id: UUID,
    payload: BenchmarkLeaderboardAddJobs,
) -> BenchmarkLeaderboardDetail:
    try:
        return await service.add_jobs(leaderboard_id, payload)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="Leaderboard not found") from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.delete(
    "/{leaderboard_id}/jobs/{eval_job_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def remove_benchmark_leaderboard_job(
    leaderboard_id: UUID,
    eval_job_id: str,
) -> Response:
    try:
        await service.remove_job(leaderboard_id, eval_job_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="Leaderboard job not found") from exc
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.delete("/{leaderboard_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_benchmark_leaderboard(
    leaderboard_id: UUID,
) -> Response:
    try:
        await service.delete_leaderboard(leaderboard_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="Leaderboard not found") from exc
    return Response(status_code=status.HTTP_204_NO_CONTENT)
