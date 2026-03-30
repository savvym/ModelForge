from __future__ import annotations

from contextvars import ContextVar, Token
from uuid import NAMESPACE_URL, UUID, uuid5

from sqlalchemy.ext.asyncio import AsyncSession

from nta_backend.models.auth import Project

CURRENT_PROJECT_HEADER = "X-Project-ID"
CURRENT_PROJECT_COOKIE = "nta_project_id"
DEFAULT_PROJECT_ID = uuid5(NAMESPACE_URL, "nta-platform:project:default")
DEFAULT_PROJECT_CODE = "default"
DEFAULT_PROJECT_NAME = "默认项目"
DEFAULT_PROJECT_DESCRIPTION = "系统默认项目。未显式切换项目时，资源默认归属到该项目。"

_current_project_id: ContextVar[UUID | None] = ContextVar(
    "current_project_id",
    default=None,
)


def parse_project_id(value: str | None) -> UUID | None:
    if not value:
        return None

    try:
        return UUID(value)
    except ValueError:
        return None


def set_current_project_id(project_id: UUID | None) -> Token[UUID | None]:
    return _current_project_id.set(project_id)


def reset_current_project_id(token: Token[UUID | None]) -> None:
    _current_project_id.reset(token)


def get_current_project_id() -> UUID:
    return _current_project_id.get() or DEFAULT_PROJECT_ID


async def ensure_default_project(session: AsyncSession) -> Project:
    project = await session.get(Project, DEFAULT_PROJECT_ID)
    if project is None:
        project = Project(
            id=DEFAULT_PROJECT_ID,
            code=DEFAULT_PROJECT_CODE,
            name=DEFAULT_PROJECT_NAME,
            description=DEFAULT_PROJECT_DESCRIPTION,
            status="active",
        )
        session.add(project)
        await session.flush()
        return project

    dirty = False
    if project.code != DEFAULT_PROJECT_CODE:
        project.code = DEFAULT_PROJECT_CODE
        dirty = True
    if project.name != DEFAULT_PROJECT_NAME:
        project.name = DEFAULT_PROJECT_NAME
        dirty = True
    if project.description != DEFAULT_PROJECT_DESCRIPTION:
        project.description = DEFAULT_PROJECT_DESCRIPTION
        dirty = True
    if project.status != "active":
        project.status = "active"
        dirty = True
    if dirty:
        await session.flush()
    return project


async def resolve_active_project_id(session: AsyncSession) -> UUID:
    requested_project_id = get_current_project_id()
    project = await session.get(Project, requested_project_id)
    if project is not None and project.status != "deleted":
        return project.id

    default_project = await ensure_default_project(session)
    return default_project.id
