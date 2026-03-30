from __future__ import annotations

from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from nta_backend.core.db import SessionLocal
from nta_backend.core.project_context import resolve_active_project_id
from nta_backend.models.eval_collection import EvalCollection
from nta_backend.models.jobs import EvalJob
from nta_backend.schemas.eval_collection import (
    CollectionRunRequest,
    CollectionRunResponse,
    EvalCollectionCreate,
    EvalCollectionDetail,
    EvalCollectionSummary,
)
from nta_backend.schemas.eval_job import EvalJobCreate, EvalJobSummary
from nta_backend.services.benchmark_catalog_service import (
    get_benchmark_definition_record,
    resolve_benchmark_version_record,
)
from nta_backend.services.eval_service import EvalJobService


def _to_summary(record: EvalCollection, *, job_count: int = 0) -> EvalCollectionSummary:
    datasets = record.schema_json.get("datasets", [])
    return EvalCollectionSummary(
        id=record.id,
        name=record.name,
        description=record.description,
        dataset_count=len(datasets),
        job_count=job_count,
        created_at=record.created_at,
    )


def _to_detail(
    record: EvalCollection,
    *,
    jobs: list[EvalJob],
    to_job_summary: callable,
) -> EvalCollectionDetail:
    datasets = record.schema_json.get("datasets", [])
    return EvalCollectionDetail(
        id=record.id,
        name=record.name,
        description=record.description,
        dataset_count=len(datasets),
        job_count=len(jobs),
        created_at=record.created_at,
        schema_json=record.schema_json,
        jobs=[to_job_summary(j) for j in jobs],
    )


class EvalCollectionService:
    def __init__(self) -> None:
        self._eval_job_service = EvalJobService()

    async def create_collection(
        self, payload: EvalCollectionCreate,
    ) -> EvalCollectionSummary:
        async with SessionLocal() as session:
            project_id = await resolve_active_project_id(session)

            # Validate all benchmark+version entries
            for entry in payload.datasets:
                definition = await get_benchmark_definition_record(
                    session, entry.benchmark_name,
                )
                if definition is None:
                    raise ValueError(
                        f"Benchmark '{entry.benchmark_name}' 不存在。"
                    )
                _, version = await resolve_benchmark_version_record(
                    session,
                    benchmark_name=entry.benchmark_name,
                    version_id=entry.version_id,
                )
                if version is None:
                    raise ValueError(
                        f"Benchmark '{entry.benchmark_name}' 的版本 "
                        f"'{entry.version_id}' 不存在。"
                    )

            schema_json = {
                "name": payload.name.strip(),
                "datasets": [
                    {
                        "benchmark_name": e.benchmark_name,
                        "version_id": e.version_id,
                        "weight": e.weight,
                    }
                    for e in payload.datasets
                ],
            }

            record = EvalCollection(
                project_id=project_id,
                name=payload.name.strip(),
                description=payload.description,
                schema_json=schema_json,
            )
            session.add(record)
            await session.commit()
            await session.refresh(record)
            return _to_summary(record)

    async def list_collections(self) -> list[EvalCollectionSummary]:
        async with SessionLocal() as session:
            project_id = await resolve_active_project_id(session)
            rows = await session.execute(
                select(
                    EvalCollection,
                    func.count(EvalJob.id).label("job_count"),
                )
                .outerjoin(EvalJob, EvalJob.collection_id == EvalCollection.id)
                .where(EvalCollection.project_id == project_id)
                .group_by(EvalCollection.id)
                .order_by(EvalCollection.created_at.desc())
            )
            return [
                _to_summary(record, job_count=job_count)
                for record, job_count in rows.all()
            ]

    async def get_collection(self, collection_id: UUID) -> EvalCollectionDetail:
        async with SessionLocal() as session:
            row = await session.execute(
                select(EvalCollection)
                .options(selectinload(EvalCollection.jobs))
                .where(EvalCollection.id == collection_id)
            )
            record = row.scalar_one_or_none()
            if record is None:
                raise KeyError(str(collection_id))

            from nta_backend.services.eval_service import _to_summary as job_to_summary

            return _to_detail(
                record,
                jobs=record.jobs,
                to_job_summary=job_to_summary,
            )

    async def run_collection(
        self,
        collection_id: UUID,
        payload: CollectionRunRequest,
    ) -> CollectionRunResponse:
        async with SessionLocal() as session:
            row = await session.execute(
                select(EvalCollection).where(EvalCollection.id == collection_id)
            )
            record = row.scalar_one_or_none()
            if record is None:
                raise KeyError(str(collection_id))

        datasets = record.schema_json.get("datasets", [])
        if not datasets:
            raise ValueError("Collection 中没有评测数据集。")

        created_jobs: list[EvalJobSummary] = []
        for entry in datasets:
            benchmark_name = entry["benchmark_name"]
            version_id = entry["version_id"]

            job_payload = EvalJobCreate(
                name=f"{record.name} - {benchmark_name}",
                benchmark_name=benchmark_name,
                benchmark_version_id=version_id,
                model_id=payload.model_id,
                model_name=payload.model_name,
                model_source=payload.model_source,
                access_source=payload.access_source,
                judge_model_id=payload.judge_model_id,
                judge_model_name=payload.judge_model_name,
            )
            job_summary = await self._eval_job_service.create_eval_job(job_payload)
            created_jobs.append(job_summary)

            # Link job to collection
            async with SessionLocal() as session:
                job = await session.get(EvalJob, UUID(job_summary.id))
                if job is not None:
                    job.collection_id = collection_id
                    await session.commit()

        return CollectionRunResponse(
            collection_id=collection_id,
            jobs=created_jobs,
        )

    async def delete_collection(self, collection_id: UUID) -> None:
        async with SessionLocal() as session:
            row = await session.execute(
                select(EvalCollection).where(EvalCollection.id == collection_id)
            )
            record = row.scalar_one_or_none()
            if record is None:
                raise KeyError(str(collection_id))
            await session.delete(record)
            await session.commit()
