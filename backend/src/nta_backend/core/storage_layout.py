from __future__ import annotations

from datetime import datetime
from pathlib import PurePosixPath
from uuid import UUID
from zoneinfo import ZoneInfo

PROJECTS_ROOT = "projects"
SYSTEM_ROOT = "system"
SYSTEM_SHARED_PREFIX = f"{SYSTEM_ROOT}/shared/"
RESOURCE_CODE_TZ = ZoneInfo("Asia/Shanghai")


def _normalize_relative_prefix(prefix: str | None) -> str:
    if not prefix:
        return ""

    normalized = prefix.strip().replace("\\", "/").lstrip("/")
    if not normalized:
        return ""

    parts = [part for part in PurePosixPath(normalized.rstrip("/")).parts if part not in ("", ".")]
    if any(part == ".." for part in parts):
        raise ValueError("对象目录不合法")
    if not parts:
        return ""
    return "/".join(parts) + "/"


def normalize_relative_object_path(path: str | None, fallback_name: str = "upload.bin") -> str:
    normalized = (path or "").strip().replace("\\", "/").lstrip("/")
    if not normalized:
        return fallback_name

    parts = [part for part in PurePosixPath(normalized).parts if part not in ("", ".")]
    if any(part == ".." for part in parts):
        raise ValueError("对象路径不合法")
    if not parts:
        return fallback_name
    return "/".join(parts)


def _base36(value: int) -> str:
    alphabet = "0123456789abcdefghijklmnopqrstuvwxyz"
    if value == 0:
        return "0"

    digits: list[str] = []
    current = value
    while current:
        current, remainder = divmod(current, 36)
        digits.append(alphabet[remainder])
    return "".join(reversed(digits))


def build_resource_code(prefix: str, created_at: datetime, resource_id: UUID) -> str:
    normalized_created_at = (
        created_at.astimezone(RESOURCE_CODE_TZ)
        if created_at.tzinfo is not None
        else created_at
    )
    timestamp = normalized_created_at.strftime("%Y%m%d%H%M%S")
    token = _base36(resource_id.int)[-5:].rjust(5, "0")
    return f"{prefix}-{timestamp}-{token}"


def build_dataset_code(created_at: datetime, dataset_id: UUID) -> str:
    return build_resource_code("ds", created_at, dataset_id)


def build_dataset_version_code(created_at: datetime, version_id: UUID) -> str:
    return build_resource_code("dsv", created_at, version_id)


def build_eval_job_code(created_at: datetime, job_id: UUID) -> str:
    return build_resource_code("ej", created_at, job_id)


def build_lake_batch_code(created_at: datetime, batch_id: UUID) -> str:
    return build_resource_code("lb", created_at, batch_id)


def build_lake_asset_code(created_at: datetime, asset_id: UUID) -> str:
    return build_resource_code("la", created_at, asset_id)


def build_project_prefix(project_id: UUID) -> str:
    return f"{PROJECTS_ROOT}/{project_id}/"


def build_project_domain_prefix(project_id: UUID, domain: str) -> str:
    normalized_domain = domain.strip().strip("/")
    if not normalized_domain:
        raise ValueError("对象域不能为空")
    return f"{build_project_prefix(project_id)}{normalized_domain}/"


def build_project_files_prefix(project_id: UUID, prefix: str | None = None) -> str:
    base = build_project_domain_prefix(project_id, "files")
    relative_prefix = _normalize_relative_prefix(prefix)
    return f"{base}{relative_prefix}"


def build_project_files_key(
    project_id: UUID,
    file_name: str,
    prefix: str | None = None,
    relative_path: str | None = None,
) -> str:
    object_path = normalize_relative_object_path(
        relative_path or file_name,
        fallback_name=file_name,
    )
    return f"{build_project_files_prefix(project_id, prefix)}{object_path}"


def build_dataset_prefix(project_id: UUID, dataset_id: UUID, dataset_created_at: datetime) -> str:
    dataset_code = build_dataset_code(dataset_created_at, dataset_id)
    return f"{build_project_domain_prefix(project_id, 'datasets')}{dataset_code}/"


def build_dataset_version_prefix(
    project_id: UUID,
    dataset_id: UUID,
    dataset_created_at: datetime,
    version_id: UUID,
    version_created_at: datetime,
) -> str:
    version_code = build_dataset_version_code(version_created_at, version_id)
    return (
        f"{build_dataset_prefix(project_id, dataset_id, dataset_created_at)}"
        f"versions/{version_code}/"
    )


def build_dataset_source_key(
    project_id: UUID,
    dataset_id: UUID,
    dataset_created_at: datetime,
    version_id: UUID,
    version_created_at: datetime,
    file_name: str,
) -> str:
    safe_name = PurePosixPath(file_name).name or "dataset.jsonl"
    version_prefix = build_dataset_version_prefix(
        project_id,
        dataset_id,
        dataset_created_at,
        version_id,
        version_created_at,
    )
    return (
        f"{version_prefix}source/{safe_name}"
    )


def build_dataset_artifact_key(
    project_id: UUID,
    dataset_id: UUID,
    dataset_created_at: datetime,
    version_id: UUID,
    version_created_at: datetime,
    artifact_name: str,
) -> str:
    safe_name = PurePosixPath(artifact_name).name or "artifact.bin"
    version_prefix = build_dataset_version_prefix(
        project_id,
        dataset_id,
        dataset_created_at,
        version_id,
        version_created_at,
    )
    return (
        f"{version_prefix}artifacts/{safe_name}"
    )


def build_eval_job_prefix(project_id: UUID, job_id: UUID, job_created_at: datetime) -> str:
    job_code = build_eval_job_code(job_created_at, job_id)
    return f"{build_project_domain_prefix(project_id, 'eval-jobs')}{job_code}/"


def build_eval_job_artifact_key(
    project_id: UUID,
    job_id: UUID,
    job_created_at: datetime,
    *parts: str,
) -> str:
    normalized_parts = [part.strip("/") for part in parts if part and part.strip("/")]
    if not normalized_parts:
        return build_eval_job_prefix(project_id, job_id, job_created_at).rstrip("/")
    path = PurePosixPath(*normalized_parts)
    return f"{build_eval_job_prefix(project_id, job_id, job_created_at)}{path.as_posix()}"


def build_eval_spec_version_dataset_key(
    project_id: UUID,
    spec_name: str,
    spec_version: str,
    file_name: str,
) -> str:
    safe_spec_name = normalize_relative_object_path(spec_name, fallback_name="spec")
    safe_version = normalize_relative_object_path(spec_version, fallback_name="version")
    safe_name = PurePosixPath(file_name).name or "dataset.bin"
    return (
        f"{build_project_domain_prefix(project_id, 'evaluation-catalog')}"
        f"specs/{safe_spec_name}/versions/{safe_version}/datasets/{safe_name}"
    )


def build_lake_prefix(project_id: UUID, stage: str) -> str:
    normalized_stage = stage.strip().strip("/")
    if not normalized_stage:
        raise ValueError("数据湖层级不能为空")
    return f"{build_project_domain_prefix(project_id, 'lake')}{normalized_stage}/"


def build_lake_raw_key(project_id: UUID, batch_id: str, asset_id: str, relative_path: str) -> str:
    normalized_relative_path = normalize_relative_object_path(
        relative_path,
        fallback_name="asset.bin",
    )
    return (
        f"{build_lake_prefix(project_id, 'raw')}"
        f"{batch_id}/original/{normalized_relative_path}"
    )


def build_lake_processed_key(
    project_id: UUID,
    asset_id: str,
    artifact_type: str,
    file_name: str,
) -> str:
    safe_name = PurePosixPath(file_name).name or "artifact.bin"
    normalized_artifact_type = artifact_type.strip().strip("/")
    if not normalized_artifact_type:
        raise ValueError("处理产物类型不能为空")
    return (
        f"{build_lake_prefix(project_id, 'processed')}"
        f"{asset_id}/{normalized_artifact_type}/{safe_name}"
    )


def build_lake_curated_key(project_id: UUID, collection_id: str, file_name: str) -> str:
    safe_name = PurePosixPath(file_name).name or "artifact.bin"
    return f"{build_lake_prefix(project_id, 'curated')}{collection_id}/{safe_name}"


def build_scoped_object_key(prefix: str, file_name: str, relative_path: str | None = None) -> str:
    normalized_prefix = prefix.strip().replace("\\", "/").lstrip("/")
    if not normalized_prefix:
        raise ValueError("对象目录不能为空")
    if not normalized_prefix.endswith("/"):
        normalized_prefix = f"{normalized_prefix}/"

    object_path = normalize_relative_object_path(
        relative_path or file_name,
        fallback_name=file_name,
    )
    return f"{normalized_prefix}{object_path}"


def is_project_scoped_key(project_id: UUID, object_key: str) -> bool:
    normalized_key = object_key.strip().replace("\\", "/").lstrip("/")
    return normalized_key.startswith(build_project_prefix(project_id))


def is_project_scoped_prefix(project_id: UUID, prefix: str) -> bool:
    normalized_prefix = prefix.strip().replace("\\", "/").lstrip("/")
    if normalized_prefix and not normalized_prefix.endswith("/"):
        normalized_prefix = f"{normalized_prefix}/"
    return normalized_prefix.startswith(build_project_prefix(project_id))
