from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from nta_backend.core.auth_context import resolve_current_user
from nta_backend.core.project_context import resolve_active_project_id
from nta_backend.models.auth import Project, ProjectMember
from nta_backend.schemas.auth import CurrentUserResponse


class AuthService:
    async def get_current_user(self, session: AsyncSession) -> CurrentUserResponse:
        user = await resolve_current_user(session)
        project_id = await resolve_active_project_id(session)
        project = await session.get(Project, project_id)
        if project is None:
            raise KeyError(str(project_id))

        membership_row = await session.execute(
            select(ProjectMember.role).where(
                ProjectMember.project_id == project.id,
                ProjectMember.user_id == user.id,
            )
        )
        role = membership_row.scalar_one_or_none() or "owner"

        return CurrentUserResponse(
            id=user.id,
            email=user.email,
            name=user.name,
            status=user.status,
            current_project_id=project.id,
            current_project_code=project.code,
            current_project_name=project.name,
            current_project_role=role,
        )
