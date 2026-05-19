from __future__ import annotations

import base64
import logging
import mimetypes
from datetime import datetime
from typing import Any
from uuid import UUID

from sqlalchemy import delete, func, select

from nta_backend.core.auth_context import resolve_current_user
from nta_backend.core.config import get_settings
from nta_backend.core.db import SessionLocal
from nta_backend.core.gitea_client import (
    GiteaAuthor,
    GiteaClientError,
    GiteaError,
    GiteaUnreachable,
    UploadFile as GiteaUploadFile,
    get_gitea_client,
)
from nta_backend.core.project_context import resolve_active_project_id
from nta_backend.models.auth import Project, User
from nta_backend.models.lake_repo import LakeRepo
from nta_backend.schemas.lake_repo import (
    BatchUploadRequest,
    BatchUploadResponse,
    BranchSummary,
    CommitListResponse,
    CommitSummary,
    FileResponse,
    LakeRepoCreate,
    LakeRepoDetail,
    LakeRepoListResponse,
    LakeRepoSummary,
    LakeRepoUpdate,
    TreeEntry,
    TreeResponse,
    UploadFile,
)

logger = logging.getLogger(__name__)

_BINARY_PREFIXES = (b"\x00",)
_MAX_PROBE = 8192


def org_name_from_code(code: str) -> str:
    """Return the Gitea org name for a platform project code.

    Truncated to 40 chars to stay well below Gitea's 64-char limit.
    """
    settings = get_settings()
    return f"{settings.gitea_org_prefix}{code}"[:40]


def project_org_name(project: Project) -> str:
    return org_name_from_code(project.code)


def _to_summary(repo: LakeRepo) -> LakeRepoSummary:
    return LakeRepoSummary.model_validate(repo)


def _parse_dt(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None


def _commit_from_gitea(entry: dict[str, Any]) -> CommitSummary:
    commit = entry.get("commit", {}) or {}
    author = commit.get("author") or entry.get("author") or {}
    committer = commit.get("committer") or {}
    committed_at = _parse_dt(committer.get("date") or author.get("date")) or datetime.min
    parents = [p.get("sha", "") for p in entry.get("parents", []) if isinstance(p, dict)]
    return CommitSummary(
        sha=entry.get("sha", ""),
        message=commit.get("message", "").strip(),
        author_name=author.get("name", ""),
        author_email=author.get("email", ""),
        committed_at=committed_at,
        parents=parents,
    )


def _guess_mime(name: str) -> str | None:
    mime, _ = mimetypes.guess_type(name)
    return mime


def _is_lfs(entry: dict[str, Any]) -> bool:
    if not isinstance(entry, dict):
        return False
    if entry.get("lfs_oid") or entry.get("lfs_size"):
        return True
    download_url = entry.get("download_url") or ""
    return "/media/" in download_url and "lfs" in download_url.lower()


def _decode_inline(content_b64: str | None, mime: str | None) -> tuple[str | None, str | None, bool]:
    if not content_b64:
        return None, None, False
    try:
        raw = base64.b64decode(content_b64)
    except (ValueError, TypeError):
        return None, None, False
    probe = raw[:_MAX_PROBE]
    is_binary = any(probe.startswith(prefix) for prefix in _BINARY_PREFIXES) or b"\x00" in probe
    if not is_binary and (mime is None or mime.startswith("text/") or mime in ("application/json", "application/xml", "application/javascript")):
        try:
            return raw.decode("utf-8"), "utf8", False
        except UnicodeDecodeError:
            pass
    return content_b64, "base64", is_binary


class LakeRepoService:
    async def list_repos(
        self,
        *,
        query: str | None = None,
        page: int = 1,
        page_size: int = 50,
    ) -> LakeRepoListResponse:
        async with SessionLocal() as session:
            project_id = await resolve_active_project_id(session)
            await session.commit()
            stmt = (
                select(LakeRepo)
                .where(LakeRepo.project_id == project_id, LakeRepo.status != "deleted")
                .order_by(LakeRepo.updated_at.desc())
            )
            count_stmt = (
                select(func.count(LakeRepo.id))
                .where(LakeRepo.project_id == project_id, LakeRepo.status != "deleted")
            )
            if query:
                pattern = f"%{query.strip().lower()}%"
                stmt = stmt.where(
                    func.lower(LakeRepo.name).like(pattern)
                    | func.lower(LakeRepo.display_name).like(pattern)
                )
                count_stmt = count_stmt.where(
                    func.lower(LakeRepo.name).like(pattern)
                    | func.lower(LakeRepo.display_name).like(pattern)
                )
            stmt = stmt.offset(max(0, (page - 1) * page_size)).limit(page_size)
            rows = (await session.execute(stmt)).scalars().all()
            total = (await session.execute(count_stmt)).scalar_one()
            return LakeRepoListResponse(
                items=[_to_summary(row) for row in rows],
                total=total,
                page=page,
                page_size=page_size,
            )

    async def _load_repo(
        self,
        session,
        project_id: UUID,
        repo_id: UUID,
    ) -> LakeRepo:
        result = await session.execute(
            select(LakeRepo).where(
                LakeRepo.id == repo_id,
                LakeRepo.project_id == project_id,
                LakeRepo.status != "deleted",
            )
        )
        row = result.scalar_one_or_none()
        if row is None:
            raise KeyError(str(repo_id))
        return row

    async def create_repo(self, payload: LakeRepoCreate) -> LakeRepoSummary:
        async with SessionLocal() as session:
            user = await resolve_current_user(session)
            project_id = await resolve_active_project_id(session)
            project = await session.get(Project, project_id)
            if project is None:
                raise KeyError(str(project_id))
            await session.commit()

            existing = await session.execute(
                select(LakeRepo.id).where(
                    LakeRepo.project_id == project_id,
                    LakeRepo.name == payload.name,
                    LakeRepo.status != "deleted",
                )
            )
            if existing.scalar_one_or_none() is not None:
                raise ValueError("仓库名称已存在，请更换后重试。")

            org = project_org_name(project)
            repo = LakeRepo(
                project_id=project_id,
                name=payload.name,
                display_name=(payload.display_name or payload.name).strip(),
                description=(payload.description or "").strip() or None,
                gitea_org=org,
                gitea_repo=payload.name,
                default_branch=get_settings().gitea_default_branch,
                visibility=payload.visibility,
                status="provisioning",
                created_by=user.id,
            )
            session.add(repo)
            await session.commit()
            await session.refresh(repo)

            client = get_gitea_client()
            try:
                if await client.get_org(org) is None:
                    await client.create_org(org)
                await client.create_repo(
                    org,
                    payload.name,
                    description=repo.description,
                    default_branch=repo.default_branch,
                    private=(payload.visibility == "private"),
                    auto_init=True,
                )
            except GiteaError as exc:
                logger.warning("Gitea create_repo failed for %s/%s: %s", org, payload.name, exc)
                repo.status = "failed"
                await session.commit()
                raise

            repo.status = "active"
            await session.commit()
            await session.refresh(repo)
            return _to_summary(repo)

    async def get_repo(self, repo_id: UUID) -> LakeRepoDetail:
        async with SessionLocal() as session:
            project_id = await resolve_active_project_id(session)
            await session.commit()
            repo = await self._load_repo(session, project_id, repo_id)
            summary = _to_summary(repo)

        detail = LakeRepoDetail(**summary.model_dump())
        try:
            client = get_gitea_client()
            data = await client.get_repo(repo.gitea_org, repo.gitea_repo)
        except GiteaUnreachable as exc:
            logger.warning("Gitea unreachable while loading repo %s: %s", repo_id, exc)
            return detail
        if data is None:
            detail.empty = True
            return detail

        detail.web_url = data.get("html_url")
        detail.clone_url = data.get("clone_url") or data.get("ssh_url")
        detail.size_kib = data.get("size")
        detail.empty = bool(data.get("empty"))

        if not detail.empty:
            try:
                commits, _ = await client.list_commits(
                    repo.gitea_org, repo.gitea_repo, ref=repo.default_branch, page=1, limit=1
                )
                if commits:
                    detail.last_commit = _commit_from_gitea(commits[0])
            except GiteaError as exc:
                logger.debug("Could not load last commit for %s: %s", repo_id, exc)
        return detail

    async def update_repo(self, repo_id: UUID, payload: LakeRepoUpdate) -> LakeRepoSummary:
        async with SessionLocal() as session:
            project_id = await resolve_active_project_id(session)
            await session.commit()
            repo = await self._load_repo(session, project_id, repo_id)
            if payload.display_name is not None:
                repo.display_name = payload.display_name.strip() or repo.display_name
            if payload.description is not None:
                stripped = payload.description.strip()
                repo.description = stripped or None
            if payload.default_branch is not None:
                repo.default_branch = payload.default_branch.strip() or repo.default_branch
            await session.commit()
            await session.refresh(repo)
            return _to_summary(repo)

    async def delete_repo(self, repo_id: UUID) -> None:
        async with SessionLocal() as session:
            project_id = await resolve_active_project_id(session)
            await session.commit()
            repo = await self._load_repo(session, project_id, repo_id)
            org, repo_name = repo.gitea_org, repo.gitea_repo
            await session.execute(delete(LakeRepo).where(LakeRepo.id == repo.id))
            await session.commit()

        client = get_gitea_client()
        try:
            await client.delete_repo(org, repo_name)
        except GiteaError as exc:
            logger.warning("Gitea delete_repo failed for %s/%s: %s", org, repo_name, exc)

    async def list_branches(self, repo_id: UUID) -> list[BranchSummary]:
        async with SessionLocal() as session:
            project_id = await resolve_active_project_id(session)
            await session.commit()
            repo = await self._load_repo(session, project_id, repo_id)

        client = get_gitea_client()
        try:
            data = await client.list_branches(repo.gitea_org, repo.gitea_repo)
        except GiteaError as exc:
            logger.warning("Gitea list_branches failed for %s: %s", repo_id, exc)
            return []
        return [
            BranchSummary(
                name=entry.get("name", ""),
                commit_sha=(entry.get("commit") or {}).get("id", ""),
                is_default=(entry.get("name") == repo.default_branch),
            )
            for entry in data
        ]

    async def get_tree(self, repo_id: UUID, ref: str, path: str = "") -> TreeResponse:
        async with SessionLocal() as session:
            project_id = await resolve_active_project_id(session)
            await session.commit()
            repo = await self._load_repo(session, project_id, repo_id)

        client = get_gitea_client()
        data = await client.get_contents(repo.gitea_org, repo.gitea_repo, ref=ref, path=path)
        if data is None:
            return TreeResponse(ref=ref, path=path, entries=[])
        if isinstance(data, dict):
            data = [data]
        entries = [
            TreeEntry(
                type=entry.get("type", "file"),
                path=entry.get("path", ""),
                name=entry.get("name", ""),
                sha=entry.get("sha", ""),
                size=entry.get("size"),
                is_lfs=_is_lfs(entry),
            )
            for entry in data
            if isinstance(entry, dict)
        ]
        return TreeResponse(ref=ref, path=path, entries=entries)

    async def get_file(self, repo_id: UUID, ref: str, path: str) -> FileResponse:
        settings = get_settings()
        async with SessionLocal() as session:
            project_id = await resolve_active_project_id(session)
            await session.commit()
            repo = await self._load_repo(session, project_id, repo_id)

        client = get_gitea_client()
        entry = await client.get_contents(repo.gitea_org, repo.gitea_repo, ref=ref, path=path)
        if not isinstance(entry, dict):
            raise FileNotFoundError(path)

        mime = _guess_mime(entry.get("name", path))
        is_lfs = _is_lfs(entry)
        size = entry.get("size") or 0
        download_url = f"/api/v1/data-lake/repos/{repo_id}/raw/{ref}/{path.lstrip('/')}"

        content_b64 = entry.get("content") if entry.get("encoding") == "base64" else None
        if is_lfs or size > settings.gitea_lake_inline_max_bytes or content_b64 is None:
            return FileResponse(
                path=entry.get("path", path),
                ref=ref,
                name=entry.get("name", ""),
                sha=entry.get("sha", ""),
                size=size,
                mime_type=mime,
                is_binary=is_lfs or (mime is not None and not mime.startswith("text/") and mime != "application/json"),
                is_lfs=is_lfs,
                download_url=download_url,
            )

        content, encoding, is_binary = _decode_inline(content_b64, mime)
        return FileResponse(
            path=entry.get("path", path),
            ref=ref,
            name=entry.get("name", ""),
            sha=entry.get("sha", ""),
            size=size,
            mime_type=mime,
            is_binary=is_binary,
            is_lfs=False,
            encoding=encoding,
            content=content,
            download_url=download_url,
        )

    async def get_file_raw(self, repo_id: UUID, ref: str, path: str) -> tuple[bytes, str]:
        async with SessionLocal() as session:
            project_id = await resolve_active_project_id(session)
            await session.commit()
            repo = await self._load_repo(session, project_id, repo_id)
        client = get_gitea_client()
        return await client.get_file_raw(repo.gitea_org, repo.gitea_repo, ref=ref, path=path)

    async def upload_files(
        self,
        repo_id: UUID,
        payload: BatchUploadRequest,
    ) -> BatchUploadResponse:
        async with SessionLocal() as session:
            project_id = await resolve_active_project_id(session)
            user = await resolve_current_user(session)
            await session.commit()
            repo = await self._load_repo(session, project_id, repo_id)

        author = GiteaAuthor(name=user.name, email=user.email)
        client = get_gitea_client()
        result = await client.batch_commit(
            repo.gitea_org,
            repo.gitea_repo,
            branch=payload.branch,
            message=payload.message,
            files=[GiteaUploadFile(path=f.path, content_b64=f.content_b64) for f in payload.files],
            author=author,
        )
        commit = result.get("commit") or result
        sha = commit.get("sha") or commit.get("html_url", "").rsplit("/", 1)[-1]
        committed_at = _parse_dt(((commit.get("committer") or {}).get("date")) or commit.get("date"))
        return BatchUploadResponse(commit_sha=sha or "", committed_at=committed_at)

    async def list_commits(
        self,
        repo_id: UUID,
        ref: str,
        *,
        path: str | None = None,
        page: int = 1,
        page_size: int = 30,
    ) -> CommitListResponse:
        async with SessionLocal() as session:
            project_id = await resolve_active_project_id(session)
            await session.commit()
            repo = await self._load_repo(session, project_id, repo_id)

        client = get_gitea_client()
        try:
            data, total = await client.list_commits(
                repo.gitea_org, repo.gitea_repo, ref=ref, path=path, page=page, limit=page_size
            )
        except GiteaClientError as exc:
            if exc.status_code == 404:
                return CommitListResponse(commits=[], page=page, page_size=page_size, total=0)
            raise
        return CommitListResponse(
            commits=[_commit_from_gitea(entry) for entry in data],
            page=page,
            page_size=page_size,
            total=total,
        )

    async def reconcile_org_for_project(self, project: Project) -> None:
        """Best-effort: ensure the Gitea org for ``project`` exists."""
        client = get_gitea_client()
        org = project_org_name(project)
        try:
            existing = await client.get_org(org)
            if existing is None:
                await client.create_org(org, description=project.name)
        except GiteaError as exc:
            logger.warning("reconcile_org_for_project failed for %s: %s", org, exc)

    async def reconcile_delete_org(self, project: Project) -> None:
        client = get_gitea_client()
        try:
            await client.delete_org(project_org_name(project))
        except GiteaError as exc:
            logger.warning("reconcile_delete_org failed: %s", exc)
