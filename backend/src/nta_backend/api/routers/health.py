from fastapi import APIRouter, HTTPException
from sqlalchemy import text

from nta_backend import __version__
from nta_backend.core.db import SessionLocal
from nta_backend.core.redis import get_redis
from nta_backend.schemas.health import HealthResponse, ReadinessResponse

router = APIRouter()


@router.get("/health", response_model=HealthResponse)
async def health_check() -> HealthResponse:
    return HealthResponse(status="ok", service="api", version=__version__)


@router.get("/ready", response_model=ReadinessResponse)
async def readiness_check() -> ReadinessResponse:
    database_status = "ok"
    redis_status = "ok"

    try:
        async with SessionLocal() as session:
            await session.execute(text("select 1"))
    except Exception as exc:  # pragma: no cover - infra-dependent
        database_status = "error"
        raise HTTPException(
            status_code=503,
            detail=ReadinessResponse(
                status="degraded", database=database_status, redis=redis_status
            ).model_dump(),
        ) from exc

    try:
        redis = await get_redis()
        await redis.ping()
    except Exception as exc:  # pragma: no cover - infra-dependent
        redis_status = "error"
        raise HTTPException(
            status_code=503,
            detail=ReadinessResponse(
                status="degraded", database=database_status, redis=redis_status
            ).model_dump(),
        ) from exc

    return ReadinessResponse(status="ok", database=database_status, redis=redis_status)
