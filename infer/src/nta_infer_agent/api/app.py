from __future__ import annotations

import json
import logging

from fastapi import Depends, FastAPI, Header, HTTPException, Query, Request
from fastapi.responses import JSONResponse, PlainTextResponse, StreamingResponse

from nta_infer_agent import __version__
from nta_infer_agent.config import get_settings
from nta_infer_agent.process import run_command
from nta_infer_agent.reconciler import DeploymentReconciler
from nta_infer_agent.schemas import DeploymentSpec, HealthResponse
from nta_infer_agent.state import EventBus, StateStore

logger = logging.getLogger(__name__)
AUTH_ERROR_DETAIL = "Invalid infer-agent token"

event_bus = EventBus()
settings = get_settings()
state = StateStore(settings.state_path, event_bus)
reconciler = DeploymentReconciler(settings, state)


async def require_token(authorization: str | None = Header(default=None)) -> None:
    if authorization != _expected_authorization_header():
        raise HTTPException(status_code=401, detail=AUTH_ERROR_DETAIL)


def _expected_authorization_header() -> str:
    return f"Bearer {settings.agent_token.get_secret_value()}"


def create_app() -> FastAPI:
    app = FastAPI(title="NTA Infer Agent", version=__version__)

    @app.middleware("http")
    async def require_token_for_all_urls(request: Request, call_next):
        if request.headers.get("authorization") != _expected_authorization_header():
            return JSONResponse(status_code=401, content={"detail": AUTH_ERROR_DETAIL})
        return await call_next(request)

    @app.on_event("startup")
    async def startup() -> None:
        logging.basicConfig(level=settings.log_level.upper())
        settings.model_cache_root.mkdir(parents=True, exist_ok=True)
        settings.runtime_root.mkdir(parents=True, exist_ok=True)
        await state.init()
        reconciler.start()
        logger.info("infer-agent started for node %s", settings.node_name)

    @app.get("/v1/health", response_model=HealthResponse)
    async def health(_: None = Depends(require_token)) -> HealthResponse:
        return HealthResponse(
            status="ok",
            node_name=settings.node_name,
            current=await state.get_status(),
            gpus=await _read_gpus(),
        )

    @app.get("/v1/deployments/current")
    async def get_current(_: None = Depends(require_token)):
        return await state.get_status()

    @app.put("/v1/deployments/current")
    async def put_current(spec: DeploymentSpec, _: None = Depends(require_token)):
        try:
            status = await state.set_desired(spec)
        except ValueError as exc:
            if str(exc) == "stale_generation":
                raise HTTPException(status_code=409, detail="stale_generation") from exc
            raise
        await state.add_event(
            event_type="desired.accepted",
            message=f"接收部署期望态 generation={spec.generation}",
            deployment_id=spec.deployment_id,
            generation=spec.generation,
            progress=0,
        )
        reconciler.kick()
        return status

    @app.delete("/v1/deployments/current")
    async def stop_current(_: None = Depends(require_token)):
        desired = await state.get_desired()
        if desired is None:
            await reconciler.docker.stop_current()
            return await state.get_status()
        stopped = desired.model_copy(
            update={"desired_phase": "stopped", "generation": desired.generation + 1}
        )
        status = await state.set_desired(stopped)
        await state.add_event(
            event_type="desired.stop_requested",
            message="接收停止期望态",
            deployment_id=stopped.deployment_id,
            generation=stopped.generation,
            progress=0,
        )
        reconciler.kick()
        return status

    @app.get("/v1/events/recent")
    async def recent_events(
        deployment_id: str | None = None,
        limit: int = Query(default=200, ge=1, le=1000),
        _: None = Depends(require_token),
    ):
        return await state.list_events(deployment_id=deployment_id, limit=limit)

    @app.get("/v1/events")
    async def stream_events(_: None = Depends(require_token)):
        async def stream():
            async for event in event_bus.subscribe():
                payload = event.model_dump(mode="json")
                data = json.dumps(payload, ensure_ascii=False)
                yield f"id: {event.id or 0}\nevent: {event.event_type}\ndata: {data}\n\n"

        return StreamingResponse(stream(), media_type="text/event-stream")

    @app.get("/v1/deployments/current/logs", response_class=PlainTextResponse)
    async def logs(tail: int = Query(default=200, ge=1, le=2000), _: None = Depends(require_token)):
        return await reconciler.docker.logs(tail=tail)

    return app


async def _read_gpus() -> list[dict]:
    output = await run_command(
        [
            "nvidia-smi",
            "--query-gpu=index,name,memory.total,memory.used,utilization.gpu,temperature.gpu",
            "--format=csv,noheader,nounits",
        ],
        check=False,
    )
    gpus = []
    for line in output.splitlines():
        parts = [part.strip() for part in line.split(",")]
        if len(parts) != 6:
            continue
        gpus.append(
            {
                "index": int(parts[0]),
                "name": parts[1],
                "memory_total_mb": int(parts[2]),
                "memory_used_mb": int(parts[3]),
                "utilization_gpu_percent": int(parts[4]),
                "temperature_c": int(parts[5]),
            }
        )
    return gpus


app = create_app()
