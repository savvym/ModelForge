from fastapi import APIRouter, HTTPException, Response, status

from nta_backend.schemas.eval_job import EvalJobCreate, EvalJobDetail, EvalJobSummary
from nta_backend.services.eval_service import EvalJobService

router = APIRouter(prefix="/eval-jobs")
service = EvalJobService()

_DETAIL_DISABLED_DETAIL = "评测详情、导出和任务操作已暂时下线。"


@router.get("", response_model=list[EvalJobSummary])
async def list_eval_jobs() -> list[EvalJobSummary]:
    return await service.list_eval_jobs()


@router.get("/{job_id}", response_model=EvalJobDetail)
async def get_eval_job(job_id: str) -> EvalJobDetail:
    try:
        return await service.get_eval_job(job_id)
    except KeyError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Eval job not found",
        ) from exc


@router.get("/{job_id}/export.xlsx")
async def export_eval_job_results(job_id: str) -> None:
    raise HTTPException(status_code=status.HTTP_410_GONE, detail=_DETAIL_DISABLED_DETAIL)


@router.post("", response_model=EvalJobSummary, status_code=status.HTTP_202_ACCEPTED)
async def create_eval_job(payload: EvalJobCreate) -> EvalJobSummary:
    try:
        return await service.create_eval_job(payload)
    except (FileNotFoundError, ValueError) as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc


@router.post("/{job_id}/stop", response_model=EvalJobSummary)
async def stop_eval_job(job_id: str) -> EvalJobSummary:
    try:
        return await service.stop_eval_job(job_id)
    except KeyError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Eval job not found",
        ) from exc
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc


@router.delete("/{job_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_eval_job(job_id: str) -> Response:
    try:
        await service.delete_eval_job(job_id)
    except KeyError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Eval job not found",
        ) from exc
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc
    return Response(status_code=status.HTTP_204_NO_CONTENT)
