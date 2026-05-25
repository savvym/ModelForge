from __future__ import annotations

import asyncio
import json
import logging
import re
import tempfile
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from urllib.parse import quote
from uuid import UUID

from botocore.exceptions import BotoCoreError, ClientError
from sqlalchemy import select

from nta_backend.core.db import SessionLocal
from nta_backend.core.project_context import resolve_active_project_id
from nta_backend.core.training_cos import (
    TrainingCosObjectEntry,
    download_training_cos_object_to_file,
    list_training_cos_objects,
)
from nta_backend.models.jobs import BatchJob, JobLog
from nta_backend.schemas.training_cos import (
    TrainingCosHuggingFaceFolderFile,
    TrainingCosHuggingFaceFolderFilesResponse,
    TrainingCosHuggingFaceRepoSearchResponse,
    TrainingCosHuggingFaceRepoSummary,
    TrainingCosHuggingFaceRepoType,
    TrainingCosHuggingFaceSyncCreateRequest,
    TrainingCosHuggingFaceSyncJob,
    TrainingCosHuggingFaceSyncJobListResponse,
    TrainingCosHuggingFaceSyncLog,
)
from nta_backend.services.system_config_service import (
    load_system_huggingface_config,
    load_training_cos_config,
)
from nta_backend.services.training_cos_browser_service import (
    _ensure_usable,
    _status_from_config,
    _wrap_boto_error,
)

logger = logging.getLogger(__name__)

JOB_TYPE = "training-cos-hf-sync"
JOB_NAME_PREFIX = "Training COS HF Sync"
MAX_JOB_NAME_LENGTH = 120
DEFAULT_SEARCH_LIMIT = 12
MAX_FILE_FILTER_RESULTS = 10000


class TrainingCosHuggingFaceSyncService:
    async def search_repos(
        self,
        *,
        repo_type: TrainingCosHuggingFaceRepoType,
        query: str,
        limit: int = DEFAULT_SEARCH_LIMIT,
    ) -> TrainingCosHuggingFaceRepoSearchResponse:
        endpoint_url, token = await _load_huggingface_credentials(require_token=False)
        api = _build_hf_api(endpoint_url, token)
        cleaned_query = query.strip()
        repos = await asyncio.to_thread(
            _search_huggingface_repos,
            api,
            repo_type,
            cleaned_query,
            max(1, min(limit, 50)),
            token,
            endpoint_url,
        )
        return TrainingCosHuggingFaceRepoSearchResponse(
            repo_type=repo_type,
            query=cleaned_query,
            repos=repos,
        )

    async def list_folder_files(
        self,
        *,
        prefix: str,
        limit: int = MAX_FILE_FILTER_RESULTS,
    ) -> TrainingCosHuggingFaceFolderFilesResponse:
        config = await _load_training_cos_config()
        status = _status_from_config(config)
        _ensure_usable(status)
        normalized = _normalize_folder_prefix(prefix)
        try:
            files, total_size, truncated = await asyncio.to_thread(
                _list_recursive_files,
                config,
                normalized,
                max(1, min(limit, MAX_FILE_FILTER_RESULTS)),
            )
        except (ClientError, BotoCoreError) as exc:
            logger.warning("Training COS recursive list failed at prefix=%s: %s", normalized, exc)
            raise _wrap_boto_error(exc) from exc

        return TrainingCosHuggingFaceFolderFilesResponse(
            prefix=normalized,
            files=[
                TrainingCosHuggingFaceFolderFile(
                    key=item.key,
                    relative_path=_safe_relative_path(normalized, item.key),
                    name=Path(item.key).name,
                    size=item.size,
                    last_modified=item.last_modified,
                    etag=item.etag,
                )
                for item in files
            ],
            total_size=total_size,
            truncated=truncated,
        )

    async def create_sync_job(
        self,
        payload: TrainingCosHuggingFaceSyncCreateRequest,
    ) -> TrainingCosHuggingFaceSyncJob:
        normalized_payload = _normalize_sync_payload(payload)
        async with SessionLocal() as session:
            project_id = await resolve_active_project_id(session)
            metadata = _initial_job_metadata(normalized_payload)
            job = BatchJob(
                project_id=project_id,
                name=_job_name(normalized_payload.prefix),
                description=json.dumps(metadata, ensure_ascii=False),
                input_object_key=normalized_payload.prefix,
                output_object_key=_huggingface_uri(
                    normalized_payload.repo_type,
                    normalized_payload.repo_id,
                ),
                progress_total=0,
                progress_done=0,
                status="pending",
            )
            session.add(job)
            await session.flush()
            _append_log(
                session,
                job,
                "info",
                "同步任务已创建，等待后端执行。",
                {"prefix": normalized_payload.prefix, "repo_id": normalized_payload.repo_id},
            )
            await session.commit()
            await session.refresh(job)
            return await self._serialize_job(job.id)

    async def run_job(self, job_id: UUID) -> None:
        try:
            async with SessionLocal() as session:
                job = await _get_job_or_raise(session, job_id)
                metadata = _job_metadata(job)
                payload = TrainingCosHuggingFaceSyncCreateRequest.model_validate(
                    metadata.get("request") or {}
                )
                if job.status == "running":
                    return
                job.status = "running"
                job.error_code = None
                job.error_message = None
                job.started_at = _now()
                job.finished_at = None
                job.progress_done = 0
                job.progress_total = 0
                metadata.update(
                    {
                        "downloaded_files": 0,
                        "downloaded_bytes": 0,
                        "skipped_files": 0,
                        "created_repo": False,
                        "repo_url": None,
                    }
                )
                _set_job_metadata(job, metadata)
                _append_log(session, job, "info", "同步任务开始执行。")
                await session.commit()

            await self._execute_job(job_id, payload)
        except Exception as exc:  # noqa: BLE001 - background jobs must be marked failed.
            logger.exception("Training COS Hugging Face sync job failed: %s", job_id)
            await self._mark_failed(job_id, exc)

    async def retry_job(self, job_id: UUID) -> TrainingCosHuggingFaceSyncJob:
        async with SessionLocal() as session:
            project_id = await resolve_active_project_id(session)
            job = await _get_project_job_or_raise(session, job_id, project_id)
            if job.status in {"pending", "running"}:
                raise ValueError("任务正在执行中，不能重复重试。")
            metadata = _job_metadata(job)
            job.status = "pending"
            job.error_code = None
            job.error_message = None
            job.started_at = None
            job.finished_at = None
            job.progress_done = 0
            job.progress_total = 0
            metadata.update(
                {
                    "downloaded_files": 0,
                    "downloaded_bytes": 0,
                    "created_repo": False,
                    "repo_url": None,
                }
            )
            _set_job_metadata(job, metadata)
            _append_log(session, job, "info", "用户触发失败重试，任务重新排队。")
            await session.commit()
        return await self._serialize_job(job_id)

    async def list_jobs(
        self,
        *,
        prefix: str | None = None,
        limit: int = 20,
    ) -> TrainingCosHuggingFaceSyncJobListResponse:
        normalized = _normalize_folder_prefix(prefix) if prefix else None
        async with SessionLocal() as session:
            project_id = await resolve_active_project_id(session)
            query = (
                select(BatchJob)
                .where(BatchJob.project_id == project_id)
                .where(BatchJob.name.like(f"{JOB_NAME_PREFIX}:%"))
                .order_by(BatchJob.updated_at.desc())
                .limit(max(1, min(limit, 50)))
            )
            if normalized:
                query = query.where(BatchJob.input_object_key == normalized)
            rows = await session.execute(query)
            jobs = rows.scalars().all()

        serialized = [await self._serialize_job(job.id, log_limit=80) for job in jobs]
        last_sync_at = next(
            (
                job.finished_at
                for job in serialized
                if job.status == "succeeded" and job.finished_at is not None
            ),
            None,
        )
        return TrainingCosHuggingFaceSyncJobListResponse(
            prefix=normalized,
            last_sync_at=last_sync_at,
            jobs=serialized,
        )

    async def get_job(self, job_id: UUID) -> TrainingCosHuggingFaceSyncJob:
        async with SessionLocal() as session:
            project_id = await resolve_active_project_id(session)
            await _get_project_job_or_raise(session, job_id, project_id)
        return await self._serialize_job(job_id)

    async def _execute_job(
        self,
        job_id: UUID,
        payload: TrainingCosHuggingFaceSyncCreateRequest,
    ) -> None:
        config = await _load_training_cos_config()
        status = _status_from_config(config)
        _ensure_usable(status)
        endpoint_url, token = await _load_huggingface_credentials(require_token=True)
        api = _build_hf_api(endpoint_url, token)

        try:
            all_files, _, _ = await asyncio.to_thread(
                _list_recursive_files,
                config,
                payload.prefix,
                None,
            )
        except (ClientError, BotoCoreError) as exc:
            raise _wrap_boto_error(exc) from exc

        excluded = {key.lstrip("/") for key in payload.exclude_keys}
        files = [item for item in all_files if item.key.lstrip("/") not in excluded]
        skipped_files = len(all_files) - len(files)
        if not files:
            raise ValueError("当前过滤条件下没有可同步的文件。")

        total_bytes = sum(item.size for item in files)
        progress_total = len(files) + 1
        await self._update_job(
            job_id,
            progress_done=0,
            progress_total=progress_total,
            metadata_updates={
                "total_files": len(files),
                "total_bytes": total_bytes,
                "skipped_files": skipped_files,
            },
            log=(
                "info",
                f"已扫描到 {len(files)} 个待同步文件，排除 {skipped_files} 个文件。",
                None,
            ),
        )

        exists = await asyncio.to_thread(
            api.repo_exists,
            repo_id=payload.repo_id,
            repo_type=_hf_repo_type_arg(payload.repo_type),
            token=token,
        )
        created_repo = False
        if not exists:
            if not payload.create_if_missing:
                raise ValueError("目标 Hugging Face Repo 不存在，且未启用自动创建。")
            await self._update_job(
                job_id,
                log=("info", f"目标 Repo 不存在，开始创建 {payload.repo_id}。", None),
            )
            await asyncio.to_thread(
                api.create_repo,
                repo_id=payload.repo_id,
                token=token,
                private=payload.private,
                repo_type=_hf_repo_type_arg(payload.repo_type),
                exist_ok=True,
                **({"space_sdk": "gradio"} if payload.repo_type == "space" else {}),
            )
            created_repo = True
            await self._update_job(
                job_id,
                metadata_updates={"created_repo": True},
                log=("info", "Hugging Face Repo 创建完成。", None),
            )
        else:
            await self._update_job(
                job_id,
                log=("info", f"已找到目标 Repo：{payload.repo_id}。", None),
            )

        with tempfile.TemporaryDirectory(prefix="nta-hf-sync-") as temp_root:
            temp_path = Path(temp_root)
            downloaded_bytes = 0
            for index, item in enumerate(files, start=1):
                relative_path = _safe_relative_path(payload.prefix, item.key)
                destination = temp_path / relative_path
                try:
                    await asyncio.to_thread(
                        download_training_cos_object_to_file,
                        config,
                        object_key=item.key,
                        destination_path=destination,
                    )
                except (ClientError, BotoCoreError) as exc:
                    raise _wrap_boto_error(exc) from exc
                downloaded_bytes += item.size
                log_entry = None
                if _should_log_file(index, len(files)):
                    log_entry = (
                        "info",
                        f"已拉取 {index}/{len(files)}：{relative_path}",
                        {"key": item.key, "size": item.size},
                    )
                await self._update_job(
                    job_id,
                    progress_done=index,
                    metadata_updates={
                        "downloaded_files": index,
                        "downloaded_bytes": downloaded_bytes,
                    },
                    log=log_entry,
                )

            if created_repo and payload.create_readme:
                readme_path = temp_path / "README.md"
                if not readme_path.exists():
                    readme_path.write_text(_build_readme(payload), encoding="utf-8")
                    await self._update_job(
                        job_id,
                        log=("info", "已生成基础 README / model card。", None),
                    )

            await self._update_job(
                job_id,
                log=("info", "开始上传到 Hugging Face Repo 根目录。", None),
            )
            await asyncio.to_thread(
                api.upload_folder,
                repo_id=payload.repo_id,
                repo_type=_hf_repo_type_arg(payload.repo_type),
                token=token,
                folder_path=temp_path,
                path_in_repo=None,
                commit_message=f"Sync {payload.prefix.rstrip('/')} from NTA training COS",
                commit_description=f"NTA Training COS prefix: {payload.prefix}\nJob ID: {job_id}",
            )

        repo_url = _repo_url(endpoint_url, payload.repo_type, payload.repo_id)
        async with SessionLocal() as session:
            job = await _get_job_or_raise(session, job_id)
            metadata = _job_metadata(job)
            metadata["repo_url"] = repo_url
            _set_job_metadata(job, metadata)
            job.status = "succeeded"
            job.progress_done = progress_total
            job.progress_total = progress_total
            job.finished_at = _now()
            job.error_code = None
            job.error_message = None
            _append_log(session, job, "info", "同步完成，临时文件已清理。", {"repo_url": repo_url})
            await session.commit()

    async def _mark_failed(self, job_id: UUID, exc: Exception) -> None:
        async with SessionLocal() as session:
            try:
                job = await _get_job_or_raise(session, job_id)
            except KeyError:
                return
            job.status = "failed"
            job.error_code = exc.__class__.__name__[:64]
            job.error_message = _short_error(str(exc))
            job.finished_at = _now()
            _append_log(session, job, "error", job.error_message or "同步失败。")
            await session.commit()

    async def _update_job(
        self,
        job_id: UUID,
        *,
        progress_done: int | None = None,
        progress_total: int | None = None,
        metadata_updates: dict[str, Any] | None = None,
        log: tuple[str, str, dict[str, Any] | None] | None = None,
    ) -> None:
        async with SessionLocal() as session:
            job = await _get_job_or_raise(session, job_id)
            if progress_done is not None:
                job.progress_done = progress_done
            if progress_total is not None:
                job.progress_total = progress_total
            if metadata_updates:
                metadata = _job_metadata(job)
                metadata.update(metadata_updates)
                _set_job_metadata(job, metadata)
            if log is not None:
                level, message, payload = log
                _append_log(session, job, level, message, payload)
            await session.commit()

    async def _serialize_job(
        self,
        job_id: UUID,
        *,
        log_limit: int = 200,
    ) -> TrainingCosHuggingFaceSyncJob:
        async with SessionLocal() as session:
            job = await _get_job_or_raise(session, job_id)
            log_rows = await session.execute(
                select(JobLog)
                .where(JobLog.job_type == JOB_TYPE)
                .where(JobLog.job_id == job.id)
                .order_by(JobLog.logged_at.desc())
                .limit(max(1, min(log_limit, 500)))
            )
            logs = list(reversed(log_rows.scalars().all()))
            metadata = _job_metadata(job)
            request = metadata.get("request") if isinstance(metadata.get("request"), dict) else {}
            total = job.progress_total or 0
            done = job.progress_done or 0
            if job.status == "succeeded":
                progress_percent = 100
            elif total:
                progress_percent = int((done / total) * 100)
            else:
                progress_percent = 0
            return TrainingCosHuggingFaceSyncJob(
                id=job.id,
                prefix=str(request.get("prefix") or job.input_object_key or ""),
                repo_id=str(request.get("repo_id") or "").strip(),
                repo_type=str(request.get("repo_type") or "model"),  # type: ignore[arg-type]
                status=job.status,  # type: ignore[arg-type]
                progress_total=job.progress_total,
                progress_done=job.progress_done,
                progress_percent=max(0, min(progress_percent, 100)),
                total_files=int(metadata.get("total_files") or 0),
                total_bytes=int(metadata.get("total_bytes") or 0),
                downloaded_files=int(metadata.get("downloaded_files") or 0),
                downloaded_bytes=int(metadata.get("downloaded_bytes") or 0),
                skipped_files=int(metadata.get("skipped_files") or 0),
                created_repo=bool(metadata.get("created_repo")),
                repo_url=_str_or_none(metadata.get("repo_url")),
                error_message=job.error_message,
                created_at=job.created_at,
                updated_at=job.updated_at,
                started_at=job.started_at,
                finished_at=job.finished_at,
                logs=[
                    TrainingCosHuggingFaceSyncLog(
                        level=item.level,
                        message=item.message,
                        logged_at=item.logged_at,
                        payload=item.payload_json,
                    )
                    for item in logs
                ],
            )


async def _load_training_cos_config() -> dict[str, Any]:
    async with SessionLocal() as session:
        return await load_training_cos_config(session)


async def _load_huggingface_credentials(*, require_token: bool) -> tuple[str, str | None]:
    async with SessionLocal() as session:
        config = await load_system_huggingface_config(session)
    endpoint_url = (config.get("endpoint_url") or "https://huggingface.co").rstrip("/")
    token = _str_or_none(config.get("token"))
    if require_token and not token:
        raise ValueError("系统配置中未配置 HF Token，请先在系统配置保存 Token。")
    return endpoint_url, token


def _build_hf_api(endpoint_url: str, token: str | None):
    try:
        from huggingface_hub import HfApi
    except ImportError as exc:  # pragma: no cover - deployment dependency guard.
        raise ValueError("后端缺少 huggingface_hub 依赖，无法同步到 Hugging Face。") from exc
    return HfApi(endpoint=endpoint_url, token=token)


def _search_huggingface_repos(
    api: Any,
    repo_type: TrainingCosHuggingFaceRepoType,
    query: str,
    limit: int,
    token: str | None,
    endpoint_url: str,
) -> list[TrainingCosHuggingFaceRepoSummary]:
    kwargs = {
        "search": query or None,
        "limit": limit,
        "full": False,
        "token": token,
    }
    if repo_type == "dataset":
        items = api.list_datasets(**kwargs)
    elif repo_type == "space":
        items = api.list_spaces(**kwargs)
    else:
        items = api.list_models(**kwargs)

    repos: list[TrainingCosHuggingFaceRepoSummary] = []
    seen: set[str] = set()
    for item in items:
        repo_id = _str_or_none(
            getattr(item, "id", None)
            or getattr(item, "repo_id", None)
            or getattr(item, "modelId", None)
            or getattr(item, "datasetId", None)
        )
        if not repo_id or repo_id in seen:
            continue
        seen.add(repo_id)
        tags = getattr(item, "tags", None)
        last_modified = getattr(item, "last_modified", None) or getattr(item, "lastModified", None)
        repos.append(
            TrainingCosHuggingFaceRepoSummary(
                repo_id=repo_id,
                repo_type=repo_type,
                private=bool(getattr(item, "private", False)),
                author=_str_or_none(getattr(item, "author", None)),
                tags=[tag for tag in (tags or []) if isinstance(tag, str)][:12],
                last_modified=(
                    last_modified.isoformat()
                    if hasattr(last_modified, "isoformat")
                    else _str_or_none(last_modified)
                ),
                url=_repo_url(endpoint_url, repo_type, repo_id),
            )
        )
        if len(repos) >= limit:
            break
    return repos


def _normalize_sync_payload(
    payload: TrainingCosHuggingFaceSyncCreateRequest,
) -> TrainingCosHuggingFaceSyncCreateRequest:
    repo_id = _parse_huggingface_repo_id(payload.repo_id)
    return payload.model_copy(
        update={
            "prefix": _normalize_folder_prefix(payload.prefix),
            "repo_id": repo_id,
            "license": _str_or_none(payload.license),
            "base_model": _str_or_none(payload.base_model),
            "tags": _normalize_tags(payload.tags),
            "exclude_keys": sorted(
                {key.strip().lstrip("/") for key in payload.exclude_keys if key.strip()}
            ),
        }
    )


def _normalize_folder_prefix(prefix: str | None) -> str:
    cleaned = (prefix or "").strip().lstrip("/")
    if not cleaned:
        raise ValueError("请选择要同步的 COS 文件夹。")
    return cleaned if cleaned.endswith("/") else f"{cleaned}/"


def _parse_huggingface_repo_id(raw_repo_id: str) -> str:
    value = raw_repo_id.strip()
    if value.startswith("hf://"):
        value = value.removeprefix("hf://")
        parts = [part for part in value.strip("/").split("/") if part]
        if parts and parts[0] in {"model", "models", "dataset", "datasets", "space", "spaces"}:
            parts = parts[1:]
        value = "/".join(parts)
    elif "huggingface.co/" in value:
        value = value.split("huggingface.co/", maxsplit=1)[1]
        parts = [part for part in value.strip("/").split("/") if part]
        if parts and parts[0] in {"models", "datasets", "spaces"}:
            parts = parts[1:]
        if "tree" in parts:
            parts = parts[: parts.index("tree")]
        value = "/".join(parts)

    parts = [part for part in value.strip("/").split("/") if part]
    if len(parts) not in {1, 2}:
        raise ValueError("请输入有效的 Hugging Face Repo ID，例如 Qwen/Qwen2.5-7B。")
    repo_id = "/".join(parts)
    if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_.-]*(/[A-Za-z0-9][A-Za-z0-9_.-]*)?", repo_id):
        raise ValueError(
            "Hugging Face Repo ID 只能包含字母、数字、点、下划线、连字符和一个命名空间斜杠。"
        )
    return repo_id


def _normalize_tags(values: list[str]) -> list[str]:
    seen: set[str] = set()
    tags: list[str] = []
    for value in values:
        tag = value.strip()
        if not tag or tag.lower() in seen:
            continue
        seen.add(tag.lower())
        tags.append(tag)
    return tags[:32]


def _list_recursive_files(
    config: dict[str, Any],
    prefix: str,
    max_files: int | None,
) -> tuple[list[TrainingCosObjectEntry], int, bool]:
    files: list[TrainingCosObjectEntry] = []
    total_size = 0
    continuation_token: str | None = None
    truncated = False
    while True:
        result = list_training_cos_objects(
            config,
            prefix=prefix,
            delimiter="",
            max_keys=1000,
            continuation_token=continuation_token,
        )
        for item in result.files:
            files.append(item)
            total_size += item.size
            if max_files is not None and len(files) >= max_files:
                truncated = result.truncated or bool(result.next_token)
                return files, total_size, truncated
        if not result.truncated or not result.next_token:
            break
        continuation_token = result.next_token
    return files, total_size, truncated


def _safe_relative_path(prefix: str, key: str) -> str:
    normalized_prefix = _normalize_folder_prefix(prefix)
    relative = (
        key[len(normalized_prefix) :]
        if key.startswith(normalized_prefix)
        else Path(key).name
    )
    relative = relative.replace("\\", "/").strip("/")
    parts = [part for part in relative.split("/") if part]
    if not parts or any(part in {".", ".."} for part in parts):
        raise ValueError(f"COS 对象路径不安全，无法同步：{key}")
    return "/".join(parts)


def _initial_job_metadata(payload: TrainingCosHuggingFaceSyncCreateRequest) -> dict[str, Any]:
    return {
        "request": payload.model_dump(mode="json"),
        "total_files": 0,
        "total_bytes": 0,
        "downloaded_files": 0,
        "downloaded_bytes": 0,
        "skipped_files": 0,
        "created_repo": False,
        "repo_url": None,
    }


def _job_metadata(job: BatchJob) -> dict[str, Any]:
    if not job.description:
        return {}
    try:
        payload = json.loads(job.description)
    except ValueError:
        return {}
    return payload if isinstance(payload, dict) else {}


def _set_job_metadata(job: BatchJob, metadata: dict[str, Any]) -> None:
    job.description = json.dumps(metadata, ensure_ascii=False)


async def _get_job_or_raise(session, job_id: UUID) -> BatchJob:
    job = await session.get(BatchJob, job_id)
    if job is None or not job.name.startswith(f"{JOB_NAME_PREFIX}:"):
        raise KeyError("同步任务不存在。")
    return job


async def _get_project_job_or_raise(session, job_id: UUID, project_id: UUID) -> BatchJob:
    job = await _get_job_or_raise(session, job_id)
    if job.project_id != project_id:
        raise KeyError("同步任务不存在。")
    return job


def _append_log(
    session,
    job: BatchJob,
    level: str,
    message: str,
    payload: dict[str, Any] | None = None,
) -> None:
    session.add(
        JobLog(
            project_id=job.project_id,
            job_type=JOB_TYPE,
            job_id=job.id,
            level=level,
            message=message,
            payload_json=payload,
        )
    )


def _build_readme(payload: TrainingCosHuggingFaceSyncCreateRequest) -> str:
    yaml_lines = ["---"]
    if payload.license:
        yaml_lines.append(f"license: {payload.license}")
    base_model = _normalize_readme_base_model(payload.base_model)
    if base_model:
        yaml_lines.append("base_model:")
        yaml_lines.append(f"- {base_model}")
    if payload.tags:
        yaml_lines.append("tags:")
        yaml_lines.extend(f"- {tag}" for tag in payload.tags)
    yaml_lines.append("---")
    title = payload.repo_id.split("/")[-1]
    synced_at = datetime.now(UTC).isoformat()
    return "\n".join(
        [
            *yaml_lines,
            "",
            f"# {title}",
            "",
            "This repository was initialized from NTA Platform training COS.",
            "",
            f"- Source prefix: `{payload.prefix}`",
            f"- Synced at: `{synced_at}`",
            "",
        ]
    )


def _normalize_readme_base_model(value: str | None) -> str | None:
    if not value:
        return None
    try:
        return _parse_huggingface_repo_id(value)
    except ValueError:
        return None


def _repo_url(
    endpoint_url: str,
    repo_type: TrainingCosHuggingFaceRepoType,
    repo_id: str,
) -> str:
    encoded = "/".join(quote(part, safe="") for part in repo_id.split("/"))
    base = endpoint_url.rstrip("/")
    if repo_type == "dataset":
        return f"{base}/datasets/{encoded}"
    if repo_type == "space":
        return f"{base}/spaces/{encoded}"
    return f"{base}/{encoded}"


def _huggingface_uri(repo_type: TrainingCosHuggingFaceRepoType, repo_id: str) -> str:
    return f"hf://{repo_type}/{repo_id}"


def _job_name(prefix: str) -> str:
    display_prefix = prefix.rstrip("/") or prefix
    name_prefix = f"{JOB_NAME_PREFIX}: "
    remaining = MAX_JOB_NAME_LENGTH - len(name_prefix)
    if len(display_prefix) <= remaining:
        return f"{name_prefix}{display_prefix}"
    if remaining <= 1:
        return name_prefix[:MAX_JOB_NAME_LENGTH]
    suffix = "..."
    if remaining <= len(suffix):
        return f"{name_prefix}{display_prefix[:remaining]}"
    return f"{name_prefix}{display_prefix[: remaining - len(suffix)]}{suffix}"


def _hf_repo_type_arg(repo_type: TrainingCosHuggingFaceRepoType) -> str | None:
    return None if repo_type == "model" else repo_type


def _should_log_file(index: int, total: int) -> bool:
    return total <= 80 or index <= 3 or index == total or index % 20 == 0


def _short_error(message: str) -> str:
    cleaned = message.strip() or "同步失败。"
    return cleaned[:497] + "..." if len(cleaned) > 500 else cleaned


def _str_or_none(value: Any) -> str | None:
    if not isinstance(value, str):
        return None
    stripped = value.strip()
    return stripped or None


def _now() -> datetime:
    return datetime.now(UTC)
