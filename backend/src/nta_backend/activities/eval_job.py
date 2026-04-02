import asyncio
import contextlib
import threading

from temporalio import activity

from nta_backend.services.eval_service import (
    activity_is_eval_job_cancel_requested,
    activity_run_eval_job,
)

_HEARTBEAT_INTERVAL_SECONDS = 5.0


@activity.defn
async def run_eval_job(payload: dict) -> dict[str, str]:
    job_id = str(payload["job_id"])
    payload_data = dict(payload["payload"])
    cancel_event = threading.Event()
    latest_progress = {"progress_done": 0, "progress_total": 0}

    def _record_progress(progress_done: int, progress_total: int) -> None:
        latest_progress["progress_done"] = progress_done
        latest_progress["progress_total"] = progress_total
        activity.heartbeat(dict(latest_progress))

    async def _watch_for_cancellation() -> None:
        while not cancel_event.is_set():
            if activity.is_cancelled():
                cancel_event.set()
                return
            if await activity_is_eval_job_cancel_requested(job_id=job_id):
                cancel_event.set()
                return
            activity.heartbeat(dict(latest_progress))
            await asyncio.sleep(_HEARTBEAT_INTERVAL_SECONDS)

    watcher = asyncio.create_task(_watch_for_cancellation())
    try:
        return await activity_run_eval_job(
            job_id=job_id,
            payload_data=payload_data,
            cancel_event=cancel_event,
            progress_listener=_record_progress,
        )
    finally:
        cancel_event.set()
        watcher.cancel()
        with contextlib.suppress(asyncio.CancelledError):
            await watcher
