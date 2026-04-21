from __future__ import annotations

from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from nta_backend.core.auth_context import get_current_user_id, resolve_current_user
from nta_backend.core.db import SessionLocal
from nta_backend.models.system import SystemSetting
from nta_backend.schemas.system_config import (
    SystemHuggingFaceSettings,
    SystemHuggingFaceSettingsUpdate,
)

HUGGINGFACE_SETTING_KEY = "huggingface"


def _normalize_optional_text(value: str | None) -> str | None:
    if value is None:
        return None
    text = value.strip()
    return text or None


def _read_string(value: dict[str, Any], key: str) -> str | None:
    raw_value = value.get(key)
    return raw_value.strip() if isinstance(raw_value, str) and raw_value.strip() else None


def _stored_huggingface_config(setting: SystemSetting | None) -> dict[str, str | None]:
    value = (
        setting.value_json if setting is not None and isinstance(setting.value_json, dict) else {}
    )
    return {
        "endpoint_url": _read_string(value, "endpoint_url"),
        "token": _read_string(value, "token"),
    }


async def load_system_huggingface_config(
    session: AsyncSession,
) -> dict[str, str | None]:
    row = await session.execute(
        select(SystemSetting).where(SystemSetting.key == HUGGINGFACE_SETTING_KEY)
    )
    setting = row.scalar_one_or_none()
    return _stored_huggingface_config(setting)


def _to_huggingface_settings(config: dict[str, str | None]) -> SystemHuggingFaceSettings:
    token = config.get("token")
    return SystemHuggingFaceSettings(
        endpoint_url=config.get("endpoint_url"),
        token=token,
        has_token=bool(token),
    )


class SystemConfigService:
    async def get_huggingface_settings(self) -> SystemHuggingFaceSettings:
        async with SessionLocal() as session:
            await resolve_current_user(session)
            await session.commit()
            config = await load_system_huggingface_config(session)
            return _to_huggingface_settings(config)

    async def update_huggingface_settings(
        self,
        payload: SystemHuggingFaceSettingsUpdate,
    ) -> SystemHuggingFaceSettings:
        async with SessionLocal() as session:
            await resolve_current_user(session)
            row = await session.execute(
                select(SystemSetting).where(SystemSetting.key == HUGGINGFACE_SETTING_KEY)
            )
            setting = row.scalar_one_or_none()
            if setting is None:
                setting = SystemSetting(
                    key=HUGGINGFACE_SETTING_KEY,
                    value_json={},
                    updated_by=get_current_user_id(),
                )
                session.add(setting)

            config = {
                key: value
                for key, value in _stored_huggingface_config(setting).items()
                if value is not None
            }
            endpoint_url = _normalize_optional_text(payload.endpoint_url)
            if endpoint_url:
                config["endpoint_url"] = endpoint_url.rstrip("/")
            else:
                config.pop("endpoint_url", None)

            token = _normalize_optional_text(payload.token)
            if token:
                config["token"] = token
            elif payload.clear_token:
                config.pop("token", None)

            setting.value_json = config
            setting.updated_by = get_current_user_id()
            await session.commit()
            await session.refresh(setting)
            return _to_huggingface_settings(_stored_huggingface_config(setting))
