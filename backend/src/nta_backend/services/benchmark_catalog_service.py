from __future__ import annotations

import json
import re
from collections import defaultdict
from dataclasses import dataclass
from datetime import datetime
from mimetypes import guess_type
from pathlib import Path, PurePosixPath
from tempfile import NamedTemporaryFile
from typing import Any
from uuid import UUID, uuid4

from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from nta_backend.core.config import get_settings
from nta_backend.core.db import SessionLocal
from nta_backend.core.object_store import delete_object_prefix, get_object_bytes, put_object_bytes
from nta_backend.core.project_context import DEFAULT_PROJECT_ID, resolve_active_project_id
from nta_backend.core.storage_layout import build_project_prefix
from nta_backend.evaluation.runtime.api.registry import get_benchmark
from nta_backend.evaluation.runtime.config import EvalTaskConfig
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
from nta_backend.schemas.object_store import ObjectStoreObjectPreviewResponse


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


@dataclass(frozen=True)
class _EvalTemplateRef:
    id: UUID
    name: str
    version: int
    template_type: str
    preset_id: str | None


_BENCHMARK_SUPPORTED_TEMPLATE_TYPES = {"llm_categorical", "llm_numeric"}
_CUSTOM_BENCHMARK_TEMPLATE_VAR_RE = re.compile(r"{(\w+)}")
_BENCHMARK_PREVIEW_LIMIT_BYTES = 100 * 1024
_TEXT_PREVIEW_EXTENSIONS = {
    "css",
    "csv",
    "html",
    "htm",
    "js",
    "json",
    "jsonl",
    "jsx",
    "log",
    "md",
    "py",
    "sh",
    "sql",
    "ts",
    "tsx",
    "txt",
    "xml",
    "yaml",
    "yml",
}
_TEXT_PREVIEW_CONTENT_TYPES = {
    "application/javascript",
    "application/json",
    "application/sql",
    "application/x-ndjson",
    "application/xml",
    "application/x-yaml",
    "text/csv",
}


@dataclass(frozen=True)
class _VersionFilePayload:
    file_name: str
    body: bytes
    content_type: str | None
    object_bucket: str | None = None
    object_key: str | None = None


def _normalize_required_text(value: str | None, field_name: str) -> str:
    normalized = (value or "").strip()
    if not normalized:
        raise ValueError(f"{field_name} 不能为空。")
    return normalized


def _normalize_optional_text(value: str | None) -> str | None:
    normalized = (value or "").strip()
    return normalized or None


async def _generate_benchmark_name(session: AsyncSession) -> str:
    for _ in range(16):
        candidate = f"bench-{uuid4().hex[:8]}"
        if await _load_single_benchmark_record(session, candidate) is None:
            return candidate
    raise ValueError("系统生成 Benchmark ID 失败，请重试。")


async def _generate_benchmark_version_id(
    session: AsyncSession,
    *,
    benchmark_id: UUID,
) -> str:
    for _ in range(16):
        candidate = f"ver-{uuid4().hex[:8]}"
        if not await _version_exists(session, benchmark_id=benchmark_id, version_id=candidate):
            return candidate
    raise ValueError("系统生成 Version ID 失败，请重试。")


def _build_custom_benchmark_contract(
    field_mapping: dict[str, Any] | None,
) -> tuple[dict[str, Any], dict[str, Any]]:
    mapping = field_mapping or {}
    properties: dict[str, Any] = {}
    example: dict[str, Any] = {}
    required: list[str] = []

    input_template = mapping.get("input_template")
    if isinstance(input_template, str) and input_template.strip():
        for field_name in _CUSTOM_BENCHMARK_TEMPLATE_VAR_RE.findall(input_template):
            properties.setdefault(field_name, {"type": "string"})
            example.setdefault(field_name, f"{field_name} example")
            if field_name not in required:
                required.append(field_name)
    else:
        input_field = str(mapping.get("input_field") or "input").strip() or "input"
        properties[input_field] = {
            "oneOf": [
                {"type": "string"},
                {
                    "type": "array",
                    "items": {"type": "object"},
                },
            ]
        }
        example[input_field] = "What is the capital of France?"
        required.append(input_field)

    target_field = str(mapping.get("target_field") or "target").strip() or "target"
    id_field = str(mapping.get("id_field") or "id").strip() or "id"
    properties.setdefault(
        target_field,
        {
            "oneOf": [
                {"type": "string"},
                {"type": "array", "items": {"type": "string"}},
            ]
        },
    )
    properties.setdefault(id_field, {"type": "string"})
    example.setdefault(target_field, "Paris")
    example.setdefault(id_field, "sample-1")

    return (
        {
            "type": "object",
            "properties": properties,
            "required": required,
        },
        example,
    )


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


def _serialize_definition(
    *,
    record: BenchmarkDefinitionRecord,
    benchmark_usage: _BenchmarkUsage,
    version_usage: dict[tuple[str, str], _BenchmarkUsage],
    eval_template: _EvalTemplateRef | None = None,
) -> BenchmarkDefinitionSummary:
    versions = record.__dict__.get("versions") or []
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
        requires_judge_model=record.requires_judge_model,
        supports_custom_dataset=record.supports_custom_dataset,
        dataset_id=record.dataset_id,
        category=record.category,
        source_type=record.source_type,
        paper_url=record.paper_url,
        tags=list(record.tags) if record.tags else [],
        metric_names=list(record.metric_names) if record.metric_names else [],
        subset_list=list(record.subset_list) if record.subset_list else [],
        eval_template_id=str(eval_template.id) if eval_template else None,
        eval_template_name=eval_template.name if eval_template else None,
        eval_template_version=eval_template.version if eval_template else None,
        eval_template_type=eval_template.template_type if eval_template else None,
        eval_template_preset_id=eval_template.preset_id if eval_template else None,
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
    eval_template: _EvalTemplateRef | None = None,
) -> BenchmarkDefinitionDetail:
    summary = _serialize_definition(
        record=record,
        benchmark_usage=benchmark_usage,
        version_usage=version_usage,
        eval_template=eval_template,
    )
    return BenchmarkDefinitionDetail(
        **summary.model_dump(),
        sample_schema_json=record.sample_schema_json or {},
        prompt_schema_json=record.prompt_schema_json or {},
        prompt_config_json=record.prompt_config_json or {},
        field_mapping_json=record.field_mapping_json,
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


async def _load_eval_template_refs(
    session: AsyncSession,
    template_ids: list[UUID],
) -> dict[UUID, _EvalTemplateRef]:
    if not template_ids:
        return {}

    from nta_backend.models.eval_template import EvalTemplate

    rows = await session.execute(
        select(EvalTemplate).where(EvalTemplate.id.in_(template_ids))
    )
    refs: dict[UUID, _EvalTemplateRef] = {}
    for template in rows.scalars().all():
        refs[template.id] = _EvalTemplateRef(
            id=template.id,
            name=template.name,
            version=template.version,
            template_type=template.template_type,
            preset_id=template.preset_id,
        )
    return refs


async def _resolve_eval_template_for_binding(
    session: AsyncSession,
    eval_template_id: str | None,
) -> _EvalTemplateRef | None:
    normalized = _normalize_optional_text(eval_template_id)
    if not normalized:
        return None

    try:
        template_uuid = UUID(normalized)
    except ValueError as exc:
        raise ValueError("评测模板 ID 无效。") from exc

    refs = await _load_eval_template_refs(session, [template_uuid])
    template = refs.get(template_uuid)
    if template is None:
        raise ValueError("所选评测模板不存在。")
    if template.template_type not in _BENCHMARK_SUPPORTED_TEMPLATE_TYPES:
        raise ValueError("Benchmark 当前仅支持绑定 LLM 自动评测模板。")
    return template


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
    from nta_backend.evaluation.runtime.api.registry import get_benchmark_meta

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


def _guess_preview_content_type(
    location: str,
    stored_content_type: str | None = None,
) -> str | None:
    lower_name = PurePosixPath(location).name.lower()
    if lower_name.endswith(".jsonl"):
        return "application/x-ndjson"
    if lower_name.endswith(".md"):
        return "text/markdown"
    if stored_content_type and stored_content_type != "application/octet-stream":
        return stored_content_type
    guessed, _ = guess_type(PurePosixPath(location).name)
    return guessed or stored_content_type


def _resolve_preview_kind(location: str, content_type: str | None) -> str:
    lower_name = PurePosixPath(location).name.lower()
    extension = lower_name.rsplit(".", 1)[-1] if "." in lower_name else ""
    normalized_content_type = (content_type or "").lower()

    if normalized_content_type == "application/pdf" or extension == "pdf":
        return "pdf"
    if normalized_content_type.startswith("image/"):
        return "image"
    if (
        normalized_content_type.startswith("text/")
        or normalized_content_type in _TEXT_PREVIEW_CONTENT_TYPES
        or extension in _TEXT_PREVIEW_EXTENSIONS
    ):
        return "text"
    return "unsupported"


def _load_version_file_payload(version: BenchmarkVersionRecord) -> _VersionFilePayload:
    dataset_source_uri = version.dataset_source_uri
    if dataset_source_uri:
        if dataset_source_uri.startswith("s3://"):
            bucket, object_key = _parse_s3_uri(dataset_source_uri)
            payload = get_object_bytes(bucket, object_key)
            return _VersionFilePayload(
                file_name=PurePosixPath(object_key).name or version.version_id,
                body=payload.body,
                content_type=_guess_preview_content_type(object_key, payload.content_type),
                object_bucket=bucket,
                object_key=object_key,
            )

        if dataset_source_uri.startswith("file://"):
            local_path = Path(dataset_source_uri.removeprefix("file://"))
            if local_path.exists():
                return _VersionFilePayload(
                    file_name=local_path.name or version.version_id,
                    body=local_path.read_bytes(),
                    content_type=_guess_preview_content_type(
                        str(local_path),
                        guess_type(local_path.name)[0],
                    ),
                )
            raise FileNotFoundError(str(local_path))

        if dataset_source_uri.startswith("/"):
            local_path = Path(dataset_source_uri)
            if local_path.exists():
                return _VersionFilePayload(
                    file_name=local_path.name or version.version_id,
                    body=local_path.read_bytes(),
                    content_type=_guess_preview_content_type(
                        str(local_path),
                        guess_type(local_path.name)[0],
                    ),
                )
            raise FileNotFoundError(str(local_path))

    if version.dataset_path:
        local_path = Path(version.dataset_path)
        if local_path.exists():
            return _VersionFilePayload(
                file_name=local_path.name or version.version_id,
                body=local_path.read_bytes(),
                content_type=_guess_preview_content_type(
                    str(local_path),
                    guess_type(local_path.name)[0],
                ),
            )
        raise FileNotFoundError(str(local_path))

    raise ValueError("当前 Version 还没有可读取的数据文件。")


async def _list_benchmark_eval_job_references(
    session: AsyncSession,
    *,
    project_id: UUID,
    benchmark_name: str,
    version_id: str,
) -> list[EvalJob]:
    rows = await session.execute(
        select(EvalJob)
        .where(
            EvalJob.project_id == project_id,
            EvalJob.benchmark_name == benchmark_name,
            EvalJob.benchmark_version_id == version_id,
        )
        .order_by(EvalJob.created_at.asc(), EvalJob.id.asc())
    )
    return list(rows.scalars().all())


def _build_benchmark_eval_reference_error(jobs: list[EvalJob]) -> str:
    preview = "、".join(job.name for job in jobs[:3])
    if len(jobs) > 3:
        preview = f"{preview} 等 {len(jobs)} 个任务"
    return f"该 Version 已被评测任务引用：{preview}。请先处理相关评测任务后再删除。"


def _resolve_managed_version_prefix(
    *,
    benchmark_name: str,
    version_id: str,
    dataset_source_uri: str | None,
) -> tuple[str, str] | None:
    normalized_uri = _normalize_optional_text(dataset_source_uri)
    if not normalized_uri or not normalized_uri.startswith("s3://"):
        return None

    bucket, object_key = _parse_s3_uri(normalized_uri)
    pattern = re.compile(
        rf"^(projects/[^/]+/benchmarks/{re.escape(benchmark_name)}/versions/{re.escape(version_id)}/)"
    )
    matched = pattern.match(object_key)
    if not matched:
        return None
    return bucket, matched.group(1)


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
    benchmark_definition: BenchmarkDefinitionRecord | None = None,
) -> _ResolvedVersionSource:
    local_path, normalized_path, normalized_uri, should_cleanup = _materialize_dataset_source(
        dataset_source_uri=dataset_source_uri,
        dataset_path=dataset_path,
    )
    try:
        if benchmark_definition is not None and benchmark_definition.source_type == "custom":
            benchmark = get_benchmark(
                "_generic",
                task_config=EvalTaskConfig(
                    benchmark="_generic",
                    model="openai_compatible",
                    dataset_path=str(local_path),
                ),
                dataset_path=str(local_path),
                field_mapping=benchmark_definition.field_mapping_json or {},
                eval_method=benchmark_definition.default_eval_method or "judge-template",
            )
        else:
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
    mapping = {
        "accuracy": ["acc"],
        "acc": ["acc"],
        "judge-rubric": ["judge_rubric"],
        "judge-quality": ["judge_quality"],
        "judge-template": ["judge_template"],
        "judge-model": ["judge_rubric"],  # backward compat
    }
    return mapping.get(eval_method or "accuracy", [eval_method or "accuracy"])


class BenchmarkCatalogService:
    async def list_benchmarks(self) -> list[BenchmarkDefinitionSummary]:
        async with SessionLocal() as session:
            records = [
                record
                for record in await _load_benchmark_records(session)
                if record.source_type == "custom"
            ]
            template_ids = [
                template_id
                for template_id in {record.eval_template_id for record in records}
                if template_id is not None
            ]
            eval_templates = await _load_eval_template_refs(session, template_ids)
            project_id = await resolve_active_project_id(session)
            benchmark_usage, version_usage = await _load_benchmark_usage(session, project_id)
            for record in records:
                await _sync_legacy_local_versions(session, record.name, record.versions)
            return [
                _serialize_definition(
                    record=record,
                    benchmark_usage=benchmark_usage.get(record.name, _BenchmarkUsage()),
                    version_usage=version_usage,
                    eval_template=eval_templates.get(record.eval_template_id) if record.eval_template_id else None,
                )
                for record in records
            ]

    async def get_benchmark(self, benchmark_name: str) -> BenchmarkDefinitionDetail:
        async with SessionLocal() as session:
            record = await _load_single_benchmark_record(session, benchmark_name)
            if record is None:
                raise KeyError(benchmark_name)
            await _sync_legacy_local_versions(session, benchmark_name, record.versions)
            eval_template = await _resolve_eval_template_for_binding(
                session,
                str(record.eval_template_id) if record.eval_template_id else None,
            )
            project_id = await resolve_active_project_id(session)
            benchmark_usage, version_usage = await _load_benchmark_usage(session, project_id)
            return _serialize_definition_detail(
                record=record,
                benchmark_usage=benchmark_usage.get(record.name, _BenchmarkUsage()),
                version_usage=version_usage,
                eval_template=eval_template,
            )

    async def get_benchmark_sample_file(self, benchmark_name: str) -> _BenchmarkSampleFile:
        async with SessionLocal() as session:
            record = await _load_single_benchmark_record(session, benchmark_name)
            if record is None:
                raise KeyError(benchmark_name)
            return _build_benchmark_sample_file(record)

    async def preview_benchmark_version_file(
        self,
        benchmark_name: str,
        version_id: str,
    ) -> ObjectStoreObjectPreviewResponse:
        async with SessionLocal() as session:
            _, version = await resolve_benchmark_version_record(
                session,
                benchmark_name=benchmark_name,
                version_id=version_id,
            )
            if version is None:
                raise KeyError(version_id)

            payload = _load_version_file_payload(version)
            preview_kind = _resolve_preview_kind(payload.file_name, payload.content_type)

            if preview_kind != "text":
                return ObjectStoreObjectPreviewResponse(
                    bucket=payload.object_bucket or "",
                    object_key=payload.object_key or payload.file_name,
                    file_name=payload.file_name,
                    preview_kind=preview_kind,
                    content_type=payload.content_type,
                )

            preview_bytes = payload.body[:_BENCHMARK_PREVIEW_LIMIT_BYTES]
            return ObjectStoreObjectPreviewResponse(
                bucket=payload.object_bucket or "",
                object_key=payload.object_key or payload.file_name,
                file_name=payload.file_name,
                preview_kind="text",
                content_type=payload.content_type,
                content=preview_bytes.decode("utf-8", errors="replace"),
                truncated=len(payload.body) > _BENCHMARK_PREVIEW_LIMIT_BYTES,
                content_bytes=len(payload.body),
            )

    async def download_benchmark_version_file(
        self,
        benchmark_name: str,
        version_id: str,
    ) -> tuple[str, bytes, str | None]:
        async with SessionLocal() as session:
            _, version = await resolve_benchmark_version_record(
                session,
                benchmark_name=benchmark_name,
                version_id=version_id,
            )
            if version is None:
                raise KeyError(version_id)

            payload = _load_version_file_payload(version)
            return payload.file_name, payload.body, payload.content_type

    async def create_benchmark_definition(
        self, payload: BenchmarkDefinitionCreate,
    ) -> BenchmarkDefinitionSummary:
        if _normalize_optional_text(payload.eval_template_id) is None:
            raise ValueError("创建自定义 Benchmark 时必须选择一个评测模板。")

        async with SessionLocal() as session:
            project_id = await resolve_active_project_id(session)
            generated_name = _normalize_optional_text(payload.name)
            benchmark_name = generated_name or await _generate_benchmark_name(session)

            existing = await _load_single_benchmark_record(session, benchmark_name)
            if existing is not None:
                raise ValueError(f"Benchmark '{benchmark_name}' 已存在。")

            eval_template = await _resolve_eval_template_for_binding(
                session,
                payload.eval_template_id,
            )
            default_eval_method = "judge-template"
            requires_judge_model = True
            sample_schema_json, sample_example_json = _build_custom_benchmark_contract(
                payload.field_mapping,
            )

            record = BenchmarkDefinitionRecord(
                name=benchmark_name,
                display_name=_normalize_required_text(payload.display_name, "display_name"),
                description=_normalize_optional_text(payload.description),
                category=_normalize_optional_text(payload.category),
                tags=payload.tags or [],
                default_eval_method=default_eval_method,
                field_mapping_json=payload.field_mapping,
                prompt_template=_normalize_optional_text(payload.prompt_template),
                system_prompt=_normalize_optional_text(payload.system_prompt),
                requires_judge_model=requires_judge_model,
                supports_custom_dataset=True,
                sample_schema_json=sample_schema_json,
                prompt_schema_json={"type": "object"},
                prompt_config_json={},
                metric_names=_metric_names_for_method(default_eval_method),
                eval_template_id=eval_template.id if eval_template else None,
                aggregator_names=["mean"],
                source_type="custom",
                adapter_class=None,
                sample_example_json=sample_example_json,
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
                eval_template=eval_template,
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

            eval_template = await _resolve_eval_template_for_binding(
                session,
                payload.eval_template_id if "eval_template_id" in payload.model_fields_set else (
                    str(record.eval_template_id) if record.eval_template_id else None
                ),
            )
            if eval_template is None:
                raise ValueError("自定义 Benchmark 必须绑定一个评测模板。")

            if payload.display_name is not None:
                record.display_name = _normalize_required_text(payload.display_name, "display_name")
            if payload.description is not None:
                record.description = _normalize_optional_text(payload.description)
            if payload.category is not None:
                record.category = _normalize_optional_text(payload.category)
            if payload.tags is not None:
                record.tags = payload.tags
            if payload.field_mapping is not None:
                record.field_mapping_json = payload.field_mapping
                sample_schema_json, sample_example_json = _build_custom_benchmark_contract(
                    payload.field_mapping,
                )
                record.sample_schema_json = sample_schema_json
                record.sample_example_json = sample_example_json
            if payload.prompt_template is not None:
                record.prompt_template = _normalize_optional_text(payload.prompt_template)
            if payload.system_prompt is not None:
                record.system_prompt = _normalize_optional_text(payload.system_prompt)
            record.eval_template_id = eval_template.id
            record.default_eval_method = "judge-template"
            record.metric_names = _metric_names_for_method("judge-template")
            record.requires_judge_model = True

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
                eval_template=eval_template,
            )

    async def create_benchmark_version(
        self,
        benchmark_name: str,
        payload: BenchmarkVersionCreate,
    ) -> BenchmarkVersionSummary:
        async with SessionLocal() as session:
            definition = await get_benchmark_definition_record(session, benchmark_name)
            if definition is None:
                raise KeyError(benchmark_name)
            version_id = _normalize_optional_text(payload.id) or await _generate_benchmark_version_id(
                session,
                benchmark_id=definition.id,
            )
            if await _version_exists(
                session,
                benchmark_id=definition.id,
                version_id=version_id,
            ):
                raise ValueError("Benchmark Version ID 已存在。")
            resolved_source = _inspect_dataset_source(
                benchmark_name=definition.name,
                dataset_source_uri=_normalize_optional_text(payload.dataset_source_uri),
                dataset_path=None,
                benchmark_definition=definition,
            )

            version = BenchmarkVersionRecord(
                benchmark_id=definition.id,
                version_id=version_id,
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
                    benchmark_definition=definition,
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

    async def delete_benchmark_version(
        self,
        benchmark_name: str,
        version_id: str,
    ) -> None:
        managed_prefix: tuple[str, str] | None = None

        async with SessionLocal() as session:
            project_id = await resolve_active_project_id(session)
            definition, version = await resolve_benchmark_version_record(
                session,
                benchmark_name=benchmark_name,
                version_id=version_id,
            )
            if definition is None or version is None:
                raise KeyError(version_id)

            references = await _list_benchmark_eval_job_references(
                session,
                project_id=project_id,
                benchmark_name=definition.name,
                version_id=version.version_id,
            )
            if references:
                raise ValueError(_build_benchmark_eval_reference_error(references))

            managed_prefix = _resolve_managed_version_prefix(
                benchmark_name=definition.name,
                version_id=version.version_id,
                dataset_source_uri=version.dataset_source_uri,
            )

            await session.delete(version)
            await session.commit()

        if managed_prefix is not None:
            bucket, prefix = managed_prefix
            delete_object_prefix(bucket, prefix)
