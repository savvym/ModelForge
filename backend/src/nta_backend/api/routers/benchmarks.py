from fastapi import APIRouter, HTTPException, Response, status

from nta_backend.schemas.benchmark_catalog import (
    BenchmarkDefinitionCreate,
    BenchmarkDefinitionDetail,
    BenchmarkDefinitionSummary,
    BenchmarkDefinitionUpdate,
    BenchmarkVersionCreate,
    BenchmarkVersionSummary,
    BenchmarkVersionUpdate,
)
from nta_backend.services.benchmark_catalog_service import BenchmarkCatalogService

router = APIRouter(prefix="/benchmarks")
service = BenchmarkCatalogService()


@router.get("", response_model=list[BenchmarkDefinitionSummary])
async def list_benchmarks() -> list[BenchmarkDefinitionSummary]:
    return await service.list_benchmarks()


@router.post(
    "",
    response_model=BenchmarkDefinitionSummary,
    status_code=status.HTTP_201_CREATED,
)
async def create_benchmark(
    payload: BenchmarkDefinitionCreate,
) -> BenchmarkDefinitionSummary:
    try:
        return await service.create_benchmark_definition(payload)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.get("/{benchmark_name}", response_model=BenchmarkDefinitionDetail)
async def get_benchmark(benchmark_name: str) -> BenchmarkDefinitionDetail:
    try:
        return await service.get_benchmark(benchmark_name)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="Benchmark not found") from exc


@router.patch("/{benchmark_name}", response_model=BenchmarkDefinitionSummary)
async def update_benchmark(
    benchmark_name: str,
    payload: BenchmarkDefinitionUpdate,
) -> BenchmarkDefinitionSummary:
    try:
        return await service.update_benchmark_definition(benchmark_name, payload)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="Benchmark not found") from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.get("/{benchmark_name}/sample-file")
async def download_benchmark_sample_file(benchmark_name: str) -> Response:
    try:
        sample_file = await service.get_benchmark_sample_file(benchmark_name)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="Benchmark not found") from exc
    return Response(
        content=sample_file.content,
        media_type=sample_file.media_type,
        headers={
            "Content-Disposition": f'attachment; filename="{sample_file.file_name}"',
        },
    )


@router.post(
    "/{benchmark_name}/versions",
    response_model=BenchmarkVersionSummary,
    status_code=status.HTTP_201_CREATED,
)
async def create_benchmark_version(
    benchmark_name: str,
    payload: BenchmarkVersionCreate,
) -> BenchmarkVersionSummary:
    try:
        return await service.create_benchmark_version(benchmark_name, payload)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="Benchmark not found") from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.patch(
    "/{benchmark_name}/versions/{version_id}",
    response_model=BenchmarkVersionSummary,
)
async def update_benchmark_version(
    benchmark_name: str,
    version_id: str,
    payload: BenchmarkVersionUpdate,
) -> BenchmarkVersionSummary:
    try:
        return await service.update_benchmark_version(benchmark_name, version_id, payload)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="Benchmark version not found") from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
