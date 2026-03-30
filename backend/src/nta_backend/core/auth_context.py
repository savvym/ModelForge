from __future__ import annotations

import base64
import hashlib
import hmac
import json
import time
from contextvars import ContextVar, Token
from uuid import NAMESPACE_URL, UUID, uuid5

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from nta_backend.core.config import get_settings
from nta_backend.core.project_context import ensure_default_project
from nta_backend.models.auth import Project, ProjectMember, User

CURRENT_USER_COOKIE = "nta_session"
CURRENT_USER_HEADER = "X-User-ID"

DEFAULT_USER_ID = uuid5(NAMESPACE_URL, "nta-platform:user:default")
DEFAULT_USER_EMAIL = "admin@local.nta"
DEFAULT_USER_NAME = "NTA Admin"

_current_user_id: ContextVar[UUID | None] = ContextVar("current_user_id", default=None)


def _urlsafe_encode(value: bytes) -> str:
    return base64.urlsafe_b64encode(value).decode("utf-8").rstrip("=")


def _urlsafe_decode(value: str) -> bytes:
    padding = "=" * (-len(value) % 4)
    return base64.urlsafe_b64decode(f"{value}{padding}".encode())


def set_current_user_id(user_id: UUID | None) -> Token[UUID | None]:
    return _current_user_id.set(user_id)


def reset_current_user_id(token: Token[UUID | None]) -> None:
    _current_user_id.reset(token)


def get_current_user_id() -> UUID | None:
    return _current_user_id.get()


def build_session_token(user_id: UUID) -> str:
    settings = get_settings()
    payload = {
        "sub": str(user_id),
        "exp": int(time.time()) + settings.auth_session_max_age_seconds,
    }
    encoded_payload = _urlsafe_encode(
        json.dumps(payload, separators=(",", ":"), sort_keys=True).encode("utf-8")
    )
    signature = hmac.new(
        settings.secret_key.get_secret_value().encode("utf-8"),
        encoded_payload.encode("utf-8"),
        hashlib.sha256,
    ).digest()
    return f"{encoded_payload}.{_urlsafe_encode(signature)}"


def parse_session_user_id(token: str | None) -> UUID | None:
    if not token:
        return None

    try:
        encoded_payload, encoded_signature = token.split(".", 1)
        expected_signature = hmac.new(
            get_settings().secret_key.get_secret_value().encode("utf-8"),
            encoded_payload.encode("utf-8"),
            hashlib.sha256,
        ).digest()
        if not hmac.compare_digest(_urlsafe_decode(encoded_signature), expected_signature):
            return None

        payload = json.loads(_urlsafe_decode(encoded_payload).decode("utf-8"))
        if int(payload.get("exp", 0)) <= int(time.time()):
            return None

        return UUID(str(payload["sub"]))
    except (KeyError, ValueError, TypeError, json.JSONDecodeError):
        return None


async def ensure_default_user(session: AsyncSession) -> User:
    await ensure_default_project(session)

    user = await session.get(User, DEFAULT_USER_ID)
    if user is None:
        user = User(
            id=DEFAULT_USER_ID,
            email=DEFAULT_USER_EMAIL,
            name=DEFAULT_USER_NAME,
            status="active",
        )
        session.add(user)
        await session.flush()
    elif user.status != "active":
        user.status = "active"
        await session.flush()

    project_rows = await session.execute(
        select(Project.id).where(Project.status != "deleted").order_by(Project.created_at.asc())
    )
    project_ids = [project_id for project_id in project_rows.scalars().all()]
    if project_ids:
        member_rows = await session.execute(
            select(ProjectMember.project_id).where(
                ProjectMember.user_id == user.id,
                ProjectMember.project_id.in_(project_ids),
            )
        )
        existing_project_ids = set(member_rows.scalars().all())
        for project_id in project_ids:
            if project_id in existing_project_ids:
                continue
            session.add(
                ProjectMember(
                    project_id=project_id,
                    user_id=user.id,
                    role="owner",
                )
            )
        await session.flush()

    return user


async def resolve_current_user(session: AsyncSession) -> User:
    requested_user_id = get_current_user_id()
    if requested_user_id is not None:
        user = await session.get(User, requested_user_id)
        if user is not None and user.status == "active":
            return user

    settings = get_settings()
    if not settings.auth_auto_login_enabled:
        raise PermissionError("Authentication required")

    user = await ensure_default_user(session)
    await session.flush()
    return user
