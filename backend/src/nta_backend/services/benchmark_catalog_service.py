from __future__ import annotations

import json
from collections import defaultdict
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from tempfile import NamedTemporaryFile
from typing import Any
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from nta_backend.core.config import get_settings
from nta_backend.core.db import SessionLocal
from nta_backend.core.object_store import get_object_bytes, put_object_bytes
from nta_backend.core.project_context import DEFAULT_PROJECT_ID, resolve_active_project_id
from nta_backend.core.storage_layout import build_project_prefix
from nta_backend.eval_core.api.registry import get_benchmark
from nta_backend.eval_core.config import EvalTaskConfig
from nta_backend.models.benchmark_catalog import (
    BenchmarkDefinition as BenchmarkDefinitionRecord,
)
from nta_backend.models.benchmark_catalog import (
    BenchmarkVersion as BenchmarkVersionRecord,
)
from nta_backend.models.jobs import EvalJob
from nta_backend.schemas.benchmark_catalog import (
    BenchmarkDefinitionCreate,
    BenchmarkDefinitionDetail,
    BenchmarkDefinitionSummary,
    BenchmarkDefinitionUpdate,
    BenchmarkVersionCreate,
    BenchmarkVersionSummary,
    BenchmarkVersionUpdate,
)


@dataclass(frozen=True)
class _BenchmarkUsage:
    eval_job_count: int = 0
    latest_eval_at: datetime | None = None


@dataclass(frozen=True)
class _ResolvedVersionSource:
    dataset_path: str | None
    dataset_source_uri: str
    sample_count: int


@dataclass(frozen=True)
class _BenchmarkSampleFile:
    file_name: str
    content: bytes
    media_type: str


def _normalize_required_text(value: str | None, field_name: str) -> str:
    normalized = (value or "").strip()
    if not normalized:
        raise ValueError(f"{field_name} 不能为空。")
    return normalized


def _normalize_optional_text(value: str | None) -> str | None:
    normalized = (value or "").strip()
    return normalized or None


def _match_version(
    versions: list[BenchmarkVersionRecord],
    version_id: str,
) -> BenchmarkVersionRecord | None:
    normalized_id = version_id.strip()
    for version in versions:
        if version.version_id == normalized_id:
            return version
    return None


def _serialize_version(
    version: BenchmarkVersionRecord,
    *,
    usage: _BenchmarkUsage,
) -> BenchmarkVersionSummary:
    return BenchmarkVersionSummary(
        id=version.version_id,
        display_name=version.display_name,
        description=version.description or "",
        dataset_path=version.dataset_path,
        dataset_source_uri=version.dataset_source_uri,
        sample_count=version.sample_count,
        enabled=version.enabled,
        eval_job_count=usage.eval_job_count,
        latest_eval_at=usage.latest_eval_at,
    )


# ------------------------------------------------------------------
# Serialization: DB record → API response (no more merge helpers!)
# ------------------------------------------------------------------


def _metadata_source(record: BenchmarkDefinitionRecord) -> str:
    source = record.source_type or "builtin"
    if record.is_runnable and source == "builtin":
        return "builtin+runtime"
    if record.is_runnable:
        return "runtime"
    return source


def _serialize_definition(
    *,
    record: BenchmarkDefinitionRecord,
    benchmark_usage: _BenchmarkUsage,
    version_usage: dict[tuple[str, str], _BenchmarkUsage],
) -> BenchmarkDefinitionSummary:
    versions = record.versions or []
    serialized_versions = [
        _serialize_version(
            version,
            usage=version_usage.get((record.name, version.version_id), _BenchmarkUsage()),
        )
        for version in versions
    ]
    return BenchmarkDefinitionSummary(
        name=record.name,
        display_name=record.display_name,
        family_name=record.family_name,
        family_display_name=record.family_display_name or record.family_name,
        description=record.description or "",
        default_eval_method=record.default_eval_method,
        metadata_source=_metadata_source(record),
        runtime_available=bool(record.is_runnable),
        requires_judge_model=record.requires_judge_model,
        supports_custom_dataset=record.supports_custom_dataset,
        dataset_id=record.dataset_id,
        category=record.category,
        paper_url=record.paper_url,
        tags=list(record.tags) if record.tags else [],
        metric_names=list(record.metric_names) if record.metric_names else [],
        subset_list=list(record.subset_list) if record.subset_list else [],
        version_count=len(serialized_versions),
        enabled_version_count=sum(1 for v in serialized_versions if v.enabled),
        eval_job_count=benchmark_usage.eval_job_count,
        latest_eval_at=benchmark_usage.latest_eval_at,
        versions=serialized_versions,
    )


def _serialize_definition_detail(
    *,
    record: BenchmarkDefinitionRecord,
    benchmark_usage: _BenchmarkUsage,
    version_usage: dict[tuple[str, str], _BenchmarkUsage],
) -> BenchmarkDefinitionDetail:
    summary = _serialize_definition(
        record=record,
        benchmark_usage=benchmark_usage,
        version_usage=version_usage,
    )
    return BenchmarkDefinitionDetail(
        **summary.model_dump(),
        sample_schema_json=record.sample_schema_json or {},
        prompt_schema_json=record.prompt_schema_json or {},
        prompt_config_json=record.prompt_config_json or {},
        few_shot_num=record.few_shot_num,
        eval_split=record.eval_split,
        train_split=record.train_split,
        prompt_template=record.prompt_template,
        system_prompt=record.system_prompt,
        few_shot_prompt_template=record.few_shot_prompt_template,
        sample_example_json=record.sample_example_json,
        statistics_json=record.statistics_json,
        readme_json=record.readme_json,
    )


# ------------------------------------------------------------------
# Sample file generation
# ------------------------------------------------------------------


def _is_non_empty_dict(value: object) -> bool:
    return isinstance(value, dict) and bool(value)


def _example_from_schema(schema: dict[str, Any]) -> object:
    schema_type = schema.get("type")
    if schema_type == "object":
        properties = schema.get("properties") or {}
        required = schema.get("required") or []
        keys = required or list(properties)[:3]
        return {
            key: _example_from_schema(properties.get(key) or {})
            for key in keys
        }
    if schema_type == "array":
        items = schema.get("items")
        if isinstance(items, dict):
            return [_example_from_schema(items)]
        return []
    if schema_type == "string":
        enum = schema.get("enum")
        if isinstance(enum, list) and enum:
            return enum[0]
        return "example"
    if schema_type == "integer":
        return 0
    if schema_type == "number":
        return 0
    if schema_type == "boolean":
        return False
    return "example"


def _build_benchmark_sample_file(
    record: BenchmarkDefinitionRecord,
) -> _BenchmarkSampleFile:
    payload = None
    if _is_non_empty_dict(record.sample_example_json):
        data = record.sample_example_json.get("data")
        if _is_non_empty_dict(data):
            payload = data
        else:
            payload = record.sample_example_json
    if payload is None:
        payload = _example_from_schema(record.sample_schema_json or {})
        if not isinstance(payload, dict):
            payload = {"example": payload}
    content = (json.dumps(payload, ensure_ascii=False) + "\n").encode("utf-8")
    return _BenchmarkSampleFile(
        file_name=f"{record.name}-sample.jsonl",
        content=content,
        media_type="application/x-ndjson",
    )


# ------------------------------------------------------------------
# DB helpers
# ------------------------------------------------------------------


async def _load_benchmark_records(
    session: AsyncSession,
) -> list[BenchmarkDefinitionRecord]:
    rows = await session.execute(
        select(BenchmarkDefinitionRecord)
        .options(selectinload(BenchmarkDefinitionRecord.versions))
        .order_by(
            BenchmarkDefinitionRecord.display_name.asc(),
            BenchmarkDefinitionRecord.name.asc(),
        )
    )
    return rows.scalars().all()


async def _load_single_benchmark_record(
    session: AsyncSession,
    benchmark_name: str,
) -> BenchmarkDefinitionRecord | None:
    row = await session.execute(
        select(BenchmarkDefinitionRecord)
        .options(selectinload(BenchmarkDefinitionRecord.versions))
        .where(BenchmarkDefinitionRecord.name == benchmark_name.strip())
    )
    return row.scalar_one_or_none()


def _legacy_benchmark_object_key(
    project_id: UUID,
    benchmark_name: str,
    version_id: str,
    file_name: str,
) -> str:
    normalized_name = benchmark_name.strip().strip("/")
    normalized_version = version_id.strip().strip("/")
    safe_name = Path(file_name).name or "dataset.jsonl"
    return (
        f"{build_project_prefix(project_id)}benchmarks/{normalized_name}/versions/"
        f"{normalized_version}/{safe_name}"
    )


async def _sync_legacy_local_versions(
    session: AsyncSession,
    benchmark_name: str,
    versions: list[BenchmarkVersionRecord],
) -> None:
    bucket = get_settings().s3_bucket_dataset_raw
    changed = False
    for version in versions:
        if version.dataset_source_uri and version.dataset_source_uri.startswith("s3://"):
            source_bucket, source_object_key = _parse_s3_uri(version.dataset_source_uri)
            is_internal_legacy_source = source_object_key.startswith("system/shared/benchmarks/")
            desired_object_key = _legacy_benchmark_object_key(
                DEFAULT_PROJECT_ID,
                benchmark_name,
                version.version_id,
                Path(source_object_key).name,
            )
            desired_uri = f"s3://{bucket}/{desired_object_key}"
            if is_internal_legacy_source and version.dataset_source_uri != desired_uri:
                payload = get_object_bytes(source_bucket, source_object_key)
                put_object_bytes(
                    bucket,
                    desired_object_key,
                    payload.body,
                    content_type=payload.content_type,
                )
                version.dataset_source_uri = desired_uri
                changed = True
            continue

        if not version.dataset_path:
            continue
        local_path = Path(version.dataset_path)
        if not local_path.exists():
            continue
        desired_object_key = _legacy_benchmark_object_key(
            DEFAULT_PROJECT_ID,
            benchmark_name,
            version.version_id,
            local_path.name,
        )
        desired_uri = f"s3://{bucket}/{desired_object_key}"
        put_object_bytes(
            bucket,
            desired_object_key,
            local_path.read_bytes(),
            content_type="application/x-ndjson",
        )
        version.dataset_source_uri = desired_uri
        version.dataset_path = None
        changed = True
    if changed:
        await session.commit()


async def get_benchmark_definition_record(
    session: AsyncSession,
    benchmark_name: str | None,
) -> BenchmarkDefinitionRecord | None:
    if not benchmark_name or not benchmark_name.strip():
        return None
    return await _load_single_benchmark_record(session, benchmark_name)


async def _get_or_create_benchmark_definition_record(
    session: AsyncSession,
    benchmark_name: str,
) -> BenchmarkDefinitionRecord:
    record = await get_benchmark_definition_record(session, benchmark_name)
    if record is not None:
        return record

    # Fallback: create from runtime registry if benchmark is runnable but not in DB
    from nta_backend.eval_core.api.registry import get_benchmark_meta

    runtime_meta = get_benchmark_meta(benchmark_name.strip())
    if runtime_meta is None:
        raise KeyError(benchmark_name)

    record = BenchmarkDefinitionRecord(
        name=runtime_meta.name,
        display_name=runtime_meta.display_name or runtime_meta.name,
        description=runtime_meta.description or None,
        default_eval_method=runtime_meta.default_eval_method,
        sample_schema_json=runtime_meta.sample_schema_json,
        prompt_schema_json=runtime_meta.prompt_schema_json,
        prompt_config_json=runtime_meta.prompt_config_json,
        requires_judge_model=runtime_meta.requires_judge_model,
        supports_custom_dataset=runtime_meta.supports_custom_dataset,
        source_type="runtime",
        is_runnable=True,
    )
    session.add(record)
    await session.flush()
    return record


async def resolve_benchmark_version_record(
    session: AsyncSession,
    *,
    benchmark_name: str | None,
    version_id: str | None,
) -> tuple[BenchmarkDefinitionRecord | None, BenchmarkVersionRecord | None]:
    if not version_id or not version_id.strip():
        return None, None

    normalized_version_id = version_id.strip()
    if benchmark_name and benchmark_name.strip():
        definition = await get_benchmark_definition_record(session, benchmark_name)
        if definition is None:
            return None, None
        return definition, _match_version(definition.versions, normalized_version_id)

    definitions = await _load_benchmark_records(session)
    for definition in definitions:
        version = _match_version(definition.versions, normalized_version_id)
        if version is not None:
            return definition, version
    return None, None


async def _version_exists(
    session: AsyncSession,
    *,
    benchmark_id: UUID,
    version_id: str,
) -> bool:
    row = await session.execute(
        select(BenchmarkVersionRecord.id).where(
            BenchmarkVersionRecord.benchmark_id == benchmark_id,
            BenchmarkVersionRecord.version_id == version_id,
        )
    )
    return row.scalar_one_or_none() is not None


async def _load_benchmark_usage(
    session: AsyncSession,
    project_id: UUID,
) -> tuple[dict[str, _BenchmarkUsage], dict[tuple[str, str], _BenchmarkUsage]]:
    rows = await session.execute(
        select(
            EvalJob.benchmark_name,
            EvalJob.benchmark_version_id,
            func.count(EvalJob.id),
            func.max(EvalJob.created_at),
        )
        .where(
            EvalJob.project_id == project_id,
            EvalJob.benchmark_name.is_not(None),
            EvalJob.benchmark_version_id.is_not(None),
        )
        .group_by(EvalJob.benchmark_name, EvalJob.benchmark_version_id)
    )

    benchmark_usage: dict[str, _BenchmarkUsage] = {}
    version_usage: dict[tuple[str, str], _BenchmarkUsage] = {}
    aggregate_counts: dict[str, int] = defaultdict(int)
    aggregate_latest: dict[str, datetime | None] = {}

    for benchmark_name, version_id, count, latest_eval_at in rows.all():
        if benchmark_name is None or version_id is None:
            continue
        usage = _BenchmarkUsage(
            eval_job_count=int(count or 0),
            latest_eval_at=latest_eval_at,
        )
        version_usage[(benchmark_name, version_id)] = usage
        aggregate_counts[benchmark_name] += usage.eval_job_count
        current_latest = aggregate_latest.get(benchmark_name)
        if current_latest is None or (
            usage.latest_eval_at is not None and usage.latest_eval_at > current_latest
        ):
            aggregate_latest[benchmark_name] = usage.latest_eval_at

    for benchmark_name, count in aggregate_counts.items():
        benchmark_usage[benchmark_name] = _BenchmarkUsage(
            eval_job_count=count,
            latest_eval_at=aggregate_latest.get(benchmark_name),
        )

    return benchmark_usage, version_usage


def _parse_s3_uri(value: str) -> tuple[str, str]:
    normalized = value.removeprefix("s3://")
    if "/" not in normalized:
        raise ValueError("S3 URI 缺少 object key。")
    bucket, object_key = normalized.split("/", 1)
    if not bucket or not object_key:
        raise ValueError("S3 URI 不合法。")
    return bucket, object_key


def _materialize_dataset_source(
    *,
    dataset_source_uri: str | None,
    dataset_path: str | None,
) -> tuple[Path, str | None, str, bool]:
    if dataset_source_uri:
        if dataset_source_uri.startswith("s3://"):
            bucket, object_key = _parse_s3_uri(dataset_source_uri)
            payload = get_object_bytes(bucket, object_key)
            suffix = Path(object_key).suffix or ".jsonl"
            with NamedTemporaryFile(
                mode="wb",
                suffix=suffix,
                prefix="benchmark-version-",
                delete=False,
            ) as handle:
                handle.write(payload.body)
                return Path(handle.name), None, dataset_source_uri, True
        raise ValueError("Benchmark Version 数据源目前仅支持 s3:// 对象存储 URI。")

    if dataset_path:
        local_path = Path(dataset_path)
        if local_path.exists():
            return local_path, dataset_path, dataset_path, False
        raise FileNotFoundError(str(local_path))

    raise ValueError("请提供 Benchmark Version 数据源 URI。")


def _inspect_dataset_source(
    *,
    benchmark_name: str,
    dataset_source_uri: str | None,
    dataset_path: str | None,
) -> _ResolvedVersionSource:
    local_path, normalized_path, normalized_uri, should_cleanup = _materialize_dataset_source(
        dataset_source_uri=dataset_source_uri,
        dataset_path=dataset_path,
    )
    try:
        benchmark = get_benchmark(
            benchmark_name,
            task_config=EvalTaskConfig(
                benchmark=benchmark_name,
                model="openai_compatible",
                dataset_path=str(local_path),
            ),
        )
        dataset = benchmark.load_dataset()
        sample_count = sum(len(samples) for samples in dataset.values())
        if sample_count <= 0:
            raise ValueError("Benchmark Version 数据集为空。")
        return _ResolvedVersionSource(
            dataset_path=normalized_path,
            dataset_source_uri=normalized_uri,
            sample_count=sample_count,
        )
    except ValueError as exc:
        raise ValueError(f"Benchmark Version 数据格式校验失败: {exc}") from exc
    finally:
        if should_cleanup:
            local_path.unlink(missing_ok=True)


def _apply_version_update(
    record: BenchmarkVersionRecord,
    payload: BenchmarkVersionUpdate,
) -> None:
    if "display_name" in payload.model_fields_set:
        record.display_name = _normalize_required_text(payload.display_name, "display_name")
    if "description" in payload.model_fields_set:
        record.description = _normalize_optional_text(payload.description)
    if "dataset_source_uri" in payload.model_fields_set:
        record.dataset_source_uri = _normalize_optional_text(payload.dataset_source_uri)
    if "enabled" in payload.model_fields_set and payload.enabled is not None:
        record.enabled = bool(payload.enabled)


def _metric_names_for_method(eval_method: str | None) -> list[str]:
    mapping = {"accuracy": ["acc"], "acc": ["acc"], "judge-model": ["cl_bench_acc"]}
    return mapping.get(eval_method or "accuracy", [eval_method or "accuracy"])


class BenchmarkCatalogService:
    async def list_benchmarks(self) -> list[BenchmarkDefinitionSummary]:
        async with SessionLocal() as session:
            records = await _load_benchmark_records(session)
            project_id = await resolve_active_project_id(session)
            benchmark_usage, version_usage = await _load_benchmark_usage(session, project_id)
            for record in records:
                await _sync_legacy_local_versions(session, record.name, record.versions)
            return [
                _serialize_definition(
                    record=record,
                    benchmark_usage=benchmark_usage.get(record.name, _BenchmarkUsage()),
                    version_usage=version_usage,
                )
                for record in records
            ]

    async def get_benchmark(self, benchmark_name: str) -> BenchmarkDefinitionDetail:
        async with SessionLocal() as session:
            record = await _load_single_benchmark_record(session, benchmark_name)
            if record is None:
                raise KeyError(benchmark_name)
            await _sync_legacy_local_versions(session, benchmark_name, record.versions)
            project_id = await resolve_active_project_id(session)
            benchmark_usage, version_usage = await _load_benchmark_usage(session, project_id)
            return _serialize_definition_detail(
                record=record,
                benchmark_usage=benchmark_usage.get(record.name, _BenchmarkUsage()),
                version_usage=version_usage,
            )

    async def get_benchmark_sample_file(self, benchmark_name: str) -> _BenchmarkSampleFile:
        async with SessionLocal() as session:
            record = await _load_single_benchmark_record(session, benchmark_name)
            if record is None:
                raise KeyError(benchmark_name)
            return _build_benchmark_sample_file(record)

    async def create_benchmark_definition(
        self, payload: BenchmarkDefinitionCreate,
    ) -> BenchmarkDefinitionSummary:
        async with SessionLocal() as session:
            project_id = await resolve_active_project_id(session)

            existing = await _load_single_benchmark_record(session, payload.name)
            if existing is not None:
                raise ValueError(f"Benchmark '{payload.name}' 已存在。")

            record = BenchmarkDefinitionRecord(
                name=_normalize_required_text(payload.name, "name"),
                display_name=_normalize_required_text(payload.display_name, "display_name"),
                description=_normalize_optional_text(payload.description),
                category=_normalize_optional_text(payload.category),
                tags=payload.tags or [],
                default_eval_method=payload.default_eval_method or "accuracy",
                field_mapping_json=payload.field_mapping,
                prompt_template=_normalize_optional_text(payload.prompt_template),
                system_prompt=_normalize_optional_text(payload.system_prompt),
                requires_judge_model=payload.requires_judge_model,
                supports_custom_dataset=True,
                sample_schema_json={"type": "object"},
                prompt_schema_json={"type": "object"},
                prompt_config_json={},
                metric_names=_metric_names_for_method(payload.default_eval_method),
                aggregator_names=["mean"],
                source_type="custom",
                is_runnable=True,
                adapter_class=None,
            )
            session.add(record)
            try:
                await session.commit()
            except IntegrityError as exc:
                await session.rollback()
                raise ValueError("Benchmark 创建失败。") from exc
            await session.refresh(record)
            return _serialize_definition(
                record=record,
                benchmark_usage=_BenchmarkUsage(),
                version_usage={},
            )

    async def update_benchmark_definition(
        self,
        benchmark_name: str,
        payload: BenchmarkDefinitionUpdate,
    ) -> BenchmarkDefinitionSummary:
        async with SessionLocal() as session:
            record = await _load_single_benchmark_record(session, benchmark_name)
            if record is None:
                raise KeyError(benchmark_name)
            if record.source_type != "custom":
                raise ValueError("仅支持编辑自定义 Benchmark。")

            if payload.display_name is not None:
                record.display_name = _normalize_required_text(payload.display_name, "display_name")
            if payload.description is not None:
                record.description = _normalize_optional_text(payload.description)
            if payload.category is not None:
                record.category = _normalize_optional_text(payload.category)
            if payload.tags is not None:
                record.tags = payload.tags
            if payload.default_eval_method is not None:
                record.default_eval_method = payload.default_eval_method
                record.metric_names = _metric_names_for_method(payload.default_eval_method)
            if payload.field_mapping is not None:
                record.field_mapping_json = payload.field_mapping
            if payload.prompt_template is not None:
                record.prompt_template = _normalize_optional_text(payload.prompt_template)
            if payload.system_prompt is not None:
                record.system_prompt = _normalize_optional_text(payload.system_prompt)
            if payload.requires_judge_model is not None:
                record.requires_judge_model = payload.requires_judge_model

            try:
                await session.commit()
            except IntegrityError as exc:
                await session.rollback()
                raise ValueError("Benchmark 更新失败。") from exc
            await session.refresh(record)
            project_id = await resolve_active_project_id(session)
            benchmark_usage, version_usage = await _load_benchmark_usage(session, project_id)
            return _serialize_definition(
                record=record,
                benchmark_usage=benchmark_usage.get(record.name, _BenchmarkUsage()),
                version_usage=version_usage,
            )

    async def create_benchmark_version(
        self,
        benchmark_name: str,
        payload: BenchmarkVersionCreate,
    ) -> BenchmarkVersionSummary:
        async with SessionLocal() as session:
            definition = await get_benchmark_definition_record(session, benchmark_name)
            if definition is None or not definition.is_runnable:
                raise KeyError(benchmark_name)
            if await _version_exists(
                session,
                benchmark_id=definition.id,
                version_id=payload.id,
            ):
                raise ValueError("Benchmark Version ID 已存在。")
            resolved_source = _inspect_dataset_source(
                benchmark_name=definition.name,
                dataset_source_uri=_normalize_optional_text(payload.dataset_source_uri),
                dataset_path=None,
            )

            version = BenchmarkVersionRecord(
                benchmark_id=definition.id,
                version_id=_normalize_required_text(payload.id, "id"),
                display_name=_normalize_required_text(payload.display_name, "display_name"),
                description=_normalize_optional_text(payload.description),
                dataset_path=resolved_source.dataset_path,
                dataset_source_uri=resolved_source.dataset_source_uri,
                sample_count=resolved_source.sample_count,
                enabled=payload.enabled,
            )
            session.add(version)
            try:
                await session.commit()
            except IntegrityError as exc:
                await session.rollback()
                raise ValueError("Benchmark Version 创建失败。") from exc
            await session.refresh(version)
            return _serialize_version(version, usage=_BenchmarkUsage())

    async def update_benchmark_version(
        self,
        benchmark_name: str,
        version_id: str,
        payload: BenchmarkVersionUpdate,
    ) -> BenchmarkVersionSummary:
        async with SessionLocal() as session:
            definition, version = await resolve_benchmark_version_record(
                session,
                benchmark_name=benchmark_name,
                version_id=version_id,
            )
            if definition is None or version is None:
                raise KeyError(version_id)

            _apply_version_update(version, payload)
            should_reinspect_source = (
                "dataset_source_uri" in payload.model_fields_set
            )
            if should_reinspect_source:
                resolved_source = _inspect_dataset_source(
                    benchmark_name=definition.name,
                    dataset_source_uri=version.dataset_source_uri,
                    dataset_path=version.dataset_path,
                )
                version.dataset_path = resolved_source.dataset_path
                version.dataset_source_uri = resolved_source.dataset_source_uri
                version.sample_count = resolved_source.sample_count
            try:
                await session.commit()
            except IntegrityError as exc:
                await session.rollback()
                raise ValueError("Benchmark Version 更新失败。") from exc
            project_id = await resolve_active_project_id(session)
            _, version_usage = await _load_benchmark_usage(session, project_id)
            await session.refresh(version)
            return _serialize_version(
                version,
                usage=version_usage.get(
                    (definition.name, version.version_id), _BenchmarkUsage()
                ),
            )
