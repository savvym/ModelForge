from __future__ import annotations

import re
from uuid import UUID

from sqlalchemy import delete, func, select

from nta_backend.core.auth_context import resolve_current_user
from nta_backend.core.db import SessionLocal
from nta_backend.core.project_context import (
    DEFAULT_PROJECT_CODE,
    DEFAULT_PROJECT_ID,
    ensure_default_project,
)
from nta_backend.models.auth import Project, ProjectMember
from nta_backend.models.dataset import Dataset
from nta_backend.models.evaluation_v2 import EvaluationRun
from nta_backend.models.lake import LakeAsset
from nta_backend.models.modeling import Endpoint, Model, ModelProvider
from nta_backend.schemas.project import ProjectCreate, ProjectDetail, ProjectSummary

_PROJECT_CODE_RE = re.compile(r"^[a-z0-9][a-z0-9-]{1,63}$")


def _normalize_project_code(value: str) -> str:
    normalized = value.strip().lower().replace("_", "-")
    normalized = re.sub(r"[^a-z0-9-]", "-", normalized)
    normalized = re.sub(r"-{2,}", "-", normalized).strip("-")
    if not _PROJECT_CODE_RE.fullmatch(normalized):
        raise ValueError("项目名称仅支持小写字母、数字和连字符，且长度需在 2-64 之间。")
    return normalized


def _normalize_optional_text(value: str | None) -> str | None:
    if value is None:
        return None
    text = value.strip()
    return text or None


class _ProjectCounts(dict[str, dict[UUID, int]]):
    dataset: dict[UUID, int]
    evaluation_run: dict[UUID, int]
    lake_asset: dict[UUID, int]
    provider: dict[UUID, int]
    model: dict[UUID, int]
    endpoint: dict[UUID, int]
    member: dict[UUID, int]


async def _count_by_project(session, stmt) -> dict[UUID, int]:
    rows = await session.execute(stmt)
    return {project_id: count for project_id, count in rows.all()}


async def _load_project_counts(session) -> _ProjectCounts:
    return _ProjectCounts(
        dataset=await _count_by_project(
            session,
            select(Dataset.project_id, func.count(Dataset.id))
            .where(Dataset.status != "deleted")
            .group_by(Dataset.project_id),
        ),
        evaluation_run=await _count_by_project(
            session,
            select(EvaluationRun.project_id, func.count(EvaluationRun.id)).group_by(EvaluationRun.project_id),
        ),
        lake_asset=await _count_by_project(
            session,
            select(LakeAsset.project_id, func.count(LakeAsset.id))
            .where(LakeAsset.status != "deleted")
            .group_by(LakeAsset.project_id),
        ),
        provider=await _count_by_project(
            session,
            select(ModelProvider.project_id, func.count(ModelProvider.id))
            .where(ModelProvider.status != "deleted")
            .group_by(ModelProvider.project_id),
        ),
        model=await _count_by_project(
            session,
            select(Model.project_id, func.count(Model.id))
            .where(
                Model.project_id.is_not(None),
                Model.status != "deleted",
            )
            .group_by(Model.project_id),
        ),
        endpoint=await _count_by_project(
            session,
            select(Endpoint.project_id, func.count(Endpoint.id))
            .where(Endpoint.status != "deleted")
            .group_by(Endpoint.project_id),
        ),
        member=await _count_by_project(
            session,
            select(ProjectMember.project_id, func.count(ProjectMember.id)).group_by(
                ProjectMember.project_id
            ),
        ),
    )


def _resource_count(project: Project, counts: _ProjectCounts) -> int:
    return (
        counts["dataset"].get(project.id, 0)
        + counts["evaluation_run"].get(project.id, 0)
        + counts["lake_asset"].get(project.id, 0)
        + counts["provider"].get(project.id, 0)
        + counts["model"].get(project.id, 0)
        + counts["endpoint"].get(project.id, 0)
    )


def _member_count(project: Project, counts: _ProjectCounts) -> int:
    count = counts["member"].get(project.id, 0)
    if project.id == DEFAULT_PROJECT_ID:
        return max(count, 1)
    return count


def _to_project_summary(project: Project, counts: _ProjectCounts) -> ProjectSummary:
    return ProjectSummary(
        id=project.id,
        code=project.code,
        name=project.name,
        description=project.description,
        status=project.status,
        is_default=project.id == DEFAULT_PROJECT_ID,
        resource_count=_resource_count(project, counts),
        member_count=_member_count(project, counts),
        dataset_count=counts["dataset"].get(project.id, 0),
        evaluation_run_count=counts["evaluation_run"].get(project.id, 0),
        created_at=project.created_at,
        updated_at=project.updated_at,
    )


def _to_project_detail(project: Project, counts: _ProjectCounts) -> ProjectDetail:
    return ProjectDetail(
        **_to_project_summary(project, counts).model_dump(),
        endpoint_count=counts["endpoint"].get(project.id, 0),
        model_provider_count=counts["provider"].get(project.id, 0),
        model_count=counts["model"].get(project.id, 0),
    )


class ProjectService:
    async def list_projects(self) -> list[ProjectSummary]:
        async with SessionLocal() as session:
            await ensure_default_project(session)
            current_user = await resolve_current_user(session)
            await session.commit()

            rows = await session.execute(
                select(Project)
                .join(ProjectMember, ProjectMember.project_id == Project.id)
                .where(Project.status != "deleted")
                .where(ProjectMember.user_id == current_user.id)
                .order_by(Project.created_at.asc(), Project.code.asc())
            )
            projects = rows.scalars().all()
            counts = await _load_project_counts(session)
            return [_to_project_summary(project, counts) for project in projects]

    async def get_project(self, project_id: UUID) -> ProjectDetail:
        async with SessionLocal() as session:
            await ensure_default_project(session)
            current_user = await resolve_current_user(session)
            await session.commit()

            project = await session.get(Project, project_id)
            if project is None or project.status == "deleted":
                raise KeyError(str(project_id))
            membership = await session.execute(
                select(ProjectMember.id).where(
                    ProjectMember.project_id == project.id,
                    ProjectMember.user_id == current_user.id,
                )
            )
            if membership.scalar_one_or_none() is None:
                raise KeyError(str(project_id))
            counts = await _load_project_counts(session)
            return _to_project_detail(project, counts)

    async def create_project(self, payload: ProjectCreate) -> ProjectSummary:
        async with SessionLocal() as session:
            await ensure_default_project(session)
            current_user = await resolve_current_user(session)
            code = _normalize_project_code(payload.code)
            if code == DEFAULT_PROJECT_CODE:
                raise ValueError("default 为系统保留项目名称，请使用其他名称。")
            display_name = payload.name.strip()
            if not display_name:
                raise ValueError("显示名称不能为空。")

            exists = await session.execute(select(Project.id).where(Project.code == code))
            if exists.scalar_one_or_none() is not None:
                raise ValueError("项目名称已存在，请更换后重试。")

            project = Project(
                code=code,
                name=display_name,
                description=_normalize_optional_text(payload.description),
                status="active",
            )
            session.add(project)
            await session.flush()
            session.add(
                ProjectMember(
                    project_id=project.id,
                    user_id=current_user.id,
                    role="owner",
                )
            )
            await session.commit()
            await session.refresh(project)
            counts = await _load_project_counts(session)
            return _to_project_summary(project, counts)

    async def delete_project(self, project_id: UUID) -> None:
        async with SessionLocal() as session:
            await ensure_default_project(session)
            current_user = await resolve_current_user(session)
            project = await session.get(Project, project_id)
            if project is None or project.status == "deleted":
                raise KeyError(str(project_id))
            if project.id == DEFAULT_PROJECT_ID or project.code == DEFAULT_PROJECT_CODE:
                raise ValueError("default 项目为系统默认项目，不能删除。")

            membership_row = await session.execute(
                select(ProjectMember.role).where(
                    ProjectMember.project_id == project.id,
                    ProjectMember.user_id == current_user.id,
                )
            )
            role = membership_row.scalar_one_or_none()
            if role is None:
                raise KeyError(str(project_id))
            if role != "owner":
                raise ValueError("仅项目所有者可以删除项目。")

            counts = await _load_project_counts(session)
            resource_count = _resource_count(project, counts)
            if resource_count > 0:
                raise ValueError("项目下仍有资源，请先清理资源后再删除。")

            await session.execute(
                delete(ProjectMember).where(ProjectMember.project_id == project.id)
            )
            await session.delete(project)
            await session.commit()
