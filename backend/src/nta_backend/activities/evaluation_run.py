from __future__ import annotations

import asyncio
import threading

from temporalio import activity

from nta_backend.services.evaluation_run_v2_service import (
    _is_run_cancel_requested,
    activity_execute_evaluation_run_item,
    aggregate_run_summary,
    list_evaluation_run_item_ids,
)


@activity.defn(name="execute_evaluation_run_item")
async def execute_evaluation_run_item(payload: dict[str, str]) -> dict[str, str]:
    cancel_event = threading.Event()

    async def _watch_for_cancel() -> None:
        while True:
            if activity.is_cancelled():
                cancel_event.set()
                return
            if await _is_run_cancel_requested(run_id=payload["run_id"]):
                cancel_event.set()
                return
            activity.heartbeat({"run_id": str(payload["run_id"]), "item_id": str(payload["item_id"])})
            await asyncio.sleep(2)

    watcher = asyncio.create_task(_watch_for_cancel())
    try:
        return await activity_execute_evaluation_run_item(
            run_id=str(payload["run_id"]),
            item_id=str(payload["item_id"]),
            cancel_event=cancel_event,
        )
    finally:
        watcher.cancel()


@activity.defn(name="aggregate_evaluation_run")
async def aggregate_evaluation_run(payload: dict[str, str]) -> dict[str, str]:
    await aggregate_run_summary(run_id=str(payload["run_id"]))
    return {"run_id": str(payload["run_id"]), "status": "aggregated"}


@activity.defn(name="list_evaluation_run_items")
async def list_evaluation_run_items(payload: dict[str, str]) -> dict[str, object]:
    item_ids = await list_evaluation_run_item_ids(run_id=str(payload["run_id"]))
    return {"run_id": str(payload["run_id"]), "item_ids": item_ids}
