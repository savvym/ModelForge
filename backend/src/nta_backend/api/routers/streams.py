import asyncio
import json
from datetime import UTC, datetime
from uuid import UUID

from fastapi import APIRouter, HTTPException
from sse_starlette.sse import EventSourceResponse

router = APIRouter(prefix="/streams")
_EVAL_STREAM_DISABLED_DETAIL = "评测任务状态流和日志流已暂时下线。"


def _timestamp() -> str:
    return datetime.now(UTC).isoformat()


async def _status_event_stream(job_type: str, job_id: UUID):
    phases = ["queued", "preparing", "inferencing", "scoring"]
    for step, phase in enumerate(phases, start=1):
        yield {
            "event": "status",
            "data": json.dumps(
                {
                    "job_type": job_type,
                    "job_id": str(job_id),
                    "phase": phase,
                    "step": step,
                    "timestamp": _timestamp(),
                }
            ),
        }
        await asyncio.sleep(1)

    while True:
        yield {
            "event": "heartbeat",
            "data": json.dumps(
                {"job_type": job_type, "job_id": str(job_id), "timestamp": _timestamp()}
            ),
        }
        await asyncio.sleep(15)


async def _log_event_stream(job_type: str, job_id: UUID):
    lines = [
        f"INFO - Start stream for {job_type}:{job_id}",
        "INFO - Input validated",
        "INFO - Waiting for downstream task completion",
    ]
    for line in lines:
        yield {
            "event": "log",
            "data": json.dumps({"job_type": job_type, "job_id": str(job_id), "message": line}),
        }
        await asyncio.sleep(1)

    while True:
        yield {
            "event": "log-heartbeat",
            "data": json.dumps(
                {"job_type": job_type, "job_id": str(job_id), "timestamp": _timestamp()}
            ),
        }
        await asyncio.sleep(15)


@router.get("/eval-jobs/{job_id}")
async def stream_eval_job(job_id: str) -> EventSourceResponse:
    raise HTTPException(status_code=410, detail=_EVAL_STREAM_DISABLED_DETAIL)


@router.get("/batch-jobs/{job_id}")
async def stream_batch_job(job_id: UUID) -> EventSourceResponse:
    return EventSourceResponse(_status_event_stream("batch-job", job_id))


@router.get("/job-logs/{job_type}/{job_id}")
async def stream_job_logs(job_type: str, job_id: str) -> EventSourceResponse:
    if job_type == "eval-job":
        raise HTTPException(status_code=410, detail=_EVAL_STREAM_DISABLED_DETAIL)
    return EventSourceResponse(_log_event_stream(job_type, UUID(job_id)))
