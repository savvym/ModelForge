from temporalio import activity


@activity.defn
async def aggregate_usage_daily(payload: dict) -> dict[str, str | int]:
    return {"status": "aggregated", "project_id": payload["project_id"], "rows": 1}


@activity.defn
async def refresh_usage_cache(payload: dict) -> dict[str, str]:
    return {"status": "refreshed", "project_id": payload["project_id"]}
