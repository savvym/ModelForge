import logging
from contextlib import asynccontextmanager

from fastapi import APIRouter, FastAPI

from nta_backend import __version__
from nta_backend.api.middleware import install_middleware
from nta_backend.api.routers import (
    auth,
    benchmarks,
    datasets,
    eval_templates,
    evaluation_catalog_v2,
    evaluation_leaderboards_v2,
    evaluation_runs_v2,
    health,
    lake_repos,
    training_cos_files,
    model_deployments,
    model_providers,
    models,
    probes,
    projects,
    streams,
    system_config,
    uploads,
    ws,
)
from nta_backend.core.config import get_settings
from nta_backend.core.db import dispose_engine
from nta_backend.core.gitea_client import shutdown_gitea_client

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(_: FastAPI):
    settings = get_settings()
    logger.info(
        "API process started (env=%s, base_path=%s)",
        settings.app_env,
        settings.api_base_path,
    )
    yield
    logger.info("API shutdown started")
    await shutdown_gitea_client()
    await dispose_engine()
    logger.info("API shutdown completed")


def create_app() -> FastAPI:
    settings = get_settings()
    app = FastAPI(
        title="NTA Platform API",
        version=__version__,
        lifespan=lifespan,
    )
    install_middleware(app)

    api_router = APIRouter(prefix=settings.api_base_path)
    api_router.include_router(health.router, tags=["health"])
    api_router.include_router(auth.router, tags=["auth"])
    api_router.include_router(benchmarks.router, tags=["benchmarks"])
    api_router.include_router(projects.router, tags=["projects"])
    api_router.include_router(model_providers.router, tags=["model-providers"])
    api_router.include_router(models.router, tags=["models"])
    api_router.include_router(model_deployments.router, tags=["model-deployments"])
    api_router.include_router(system_config.router, tags=["system-config"])
    api_router.include_router(datasets.router, tags=["datasets"])
    api_router.include_router(lake_repos.router, tags=["data-lake"])
    api_router.include_router(training_cos_files.router, tags=["training-cos"])
    api_router.include_router(eval_templates.router, tags=["eval-templates"])
    api_router.include_router(uploads.router, tags=["uploads"])
    api_router.include_router(streams.router, tags=["streams"])

    app.include_router(api_router)
    app.include_router(evaluation_catalog_v2.router)
    app.include_router(evaluation_leaderboards_v2.router)
    app.include_router(evaluation_runs_v2.router)
    app.include_router(probes.router)
    app.include_router(ws.router)
    logger.info("API application initialized with %s routers", len(api_router.routes))
    return app
