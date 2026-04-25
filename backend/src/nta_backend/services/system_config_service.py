from __future__ import annotations

from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from nta_backend.core.auth_context import get_current_user_id, resolve_current_user
from nta_backend.core.db import SessionLocal
from nta_backend.core.training_cos import build_training_cos_endpoint_url, probe_training_cos
from nta_backend.models.system import SystemSetting
from nta_backend.schemas.system_config import (
    SystemHuggingFaceSettings,
    SystemHuggingFaceSettingsUpdate,
    SystemTrainingCosProbeResponse,
    SystemTrainingCosSettings,
    SystemTrainingCosSettingsUpdate,
)

HUGGINGFACE_SETTING_KEY = "huggingface"
TRAINING_COS_SETTING_KEY = "training_cos"
DEFAULT_TRAINING_COS_TARGET_PREFIX = "training/datasets"


def _normalize_optional_text(value: str | None) -> str | None:
    if value is None:
        return None
    text = value.strip()
    return text or None


def _read_string(value: dict[str, Any], key: str) -> str | None:
    raw_value = value.get(key)
    return raw_value.strip() if isinstance(raw_value, str) and raw_value.strip() else None


def _mask_secret(value: str | None) -> str | None:
    if not value:
        return None
    if len(value) <= 8:
        return "*" * len(value)
    return f"{value[:4]}{'*' * 8}{value[-4:]}"


def _stored_setting_value(setting: SystemSetting | None) -> dict[str, Any]:
    if setting is not None and isinstance(setting.value_json, dict):
        return setting.value_json
    return {}


def _stored_huggingface_config(setting: SystemSetting | None) -> dict[str, str | None]:
    value = _stored_setting_value(setting)
    return {
        "endpoint_url": _read_string(value, "endpoint_url"),
        "token": _read_string(value, "token"),
    }


def _stored_training_cos_config(setting: SystemSetting | None) -> dict[str, Any]:
    value = _stored_setting_value(setting)
    return {
        "enabled": bool(value.get("enabled")),
        "protocol": _read_string(value, "protocol") or "http",
        "endpoint": _read_string(value, "endpoint"),
        "region": _read_string(value, "region"),
        "bucket": _read_string(value, "bucket"),
        "bucket_alias": _read_string(value, "bucket_alias"),
        "target_prefix": _read_string(value, "target_prefix") or DEFAULT_TRAINING_COS_TARGET_PREFIX,
        "addressing_style": _read_string(value, "addressing_style") or "virtual",
        "secret_id": _read_string(value, "secret_id"),
        "secret_key": _read_string(value, "secret_key"),
        "session_token": _read_string(value, "session_token"),
    }


async def load_system_huggingface_config(
    session: AsyncSession,
) -> dict[str, str | None]:
    row = await session.execute(
        select(SystemSetting).where(SystemSetting.key == HUGGINGFACE_SETTING_KEY)
    )
    setting = row.scalar_one_or_none()
    return _stored_huggingface_config(setting)


async def load_training_cos_config(session: AsyncSession) -> dict[str, Any]:
    row = await session.execute(
        select(SystemSetting).where(SystemSetting.key == TRAINING_COS_SETTING_KEY)
    )
    setting = row.scalar_one_or_none()
    return _stored_training_cos_config(setting)


def _to_huggingface_settings(config: dict[str, str | None]) -> SystemHuggingFaceSettings:
    token = config.get("token")
    return SystemHuggingFaceSettings(
        endpoint_url=config.get("endpoint_url"),
        token=token,
        has_token=bool(token),
    )


def _to_training_cos_settings(config: dict[str, Any]) -> SystemTrainingCosSettings:
    endpoint_url = None
    if config.get("endpoint"):
        try:
            endpoint_url = build_training_cos_endpoint_url(config)
        except ValueError:
            endpoint_url = None
    secret_id = config.get("secret_id")
    secret_key = config.get("secret_key")
    session_token = config.get("session_token")
    return SystemTrainingCosSettings(
        enabled=bool(config.get("enabled")),
        protocol=str(config.get("protocol") or "http"),
        endpoint=config.get("endpoint"),
        endpoint_url=endpoint_url,
        region=config.get("region"),
        bucket=config.get("bucket"),
        bucket_alias=config.get("bucket_alias"),
        target_prefix=config.get("target_prefix") or DEFAULT_TRAINING_COS_TARGET_PREFIX,
        addressing_style=str(config.get("addressing_style") or "virtual"),
        has_secret_id=bool(secret_id),
        has_secret_key=bool(secret_key),
        has_session_token=bool(session_token),
        secret_id_masked=_mask_secret(secret_id),
        secret_key_masked=_mask_secret(secret_key),
        session_token_masked=_mask_secret(session_token),
    )


async def _get_or_create_setting(session: AsyncSession, key: str) -> SystemSetting:
    row = await session.execute(select(SystemSetting).where(SystemSetting.key == key))
    setting = row.scalar_one_or_none()
    if setting is None:
        setting = SystemSetting(key=key, value_json={}, updated_by=get_current_user_id())
        session.add(setting)
    return setting


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
            setting = await _get_or_create_setting(session, HUGGINGFACE_SETTING_KEY)

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

    async def get_training_cos_settings(self) -> SystemTrainingCosSettings:
        async with SessionLocal() as session:
            await resolve_current_user(session)
            await session.commit()
            config = await load_training_cos_config(session)
            return _to_training_cos_settings(config)

    async def update_training_cos_settings(
        self,
        payload: SystemTrainingCosSettingsUpdate,
    ) -> SystemTrainingCosSettings:
        async with SessionLocal() as session:
            await resolve_current_user(session)
            setting = await _get_or_create_setting(session, TRAINING_COS_SETTING_KEY)
            config = {
                key: value
                for key, value in _stored_training_cos_config(setting).items()
                if value is not None
            }

            config["enabled"] = bool(payload.enabled)
            for key in (
                "protocol",
                "endpoint",
                "region",
                "bucket",
                "bucket_alias",
                "target_prefix",
                "addressing_style",
            ):
                value = _normalize_optional_text(getattr(payload, key))
                if value:
                    config[key] = value.strip("/")
                elif key in {"endpoint", "bucket"}:
                    config.pop(key, None)
                elif key == "target_prefix":
                    config[key] = DEFAULT_TRAINING_COS_TARGET_PREFIX
                elif key == "protocol":
                    config[key] = "http"
                elif key == "addressing_style":
                    config[key] = "virtual"
                else:
                    config.pop(key, None)

            for key, clear_key in (
                ("secret_id", "clear_secret_id"),
                ("secret_key", "clear_secret_key"),
                ("session_token", "clear_session_token"),
            ):
                value = _normalize_optional_text(getattr(payload, key))
                if value:
                    config[key] = value
                elif getattr(payload, clear_key):
                    config.pop(key, None)

            setting.value_json = config
            setting.updated_by = get_current_user_id()
            await session.commit()
            await session.refresh(setting)
            return _to_training_cos_settings(_stored_training_cos_config(setting))

    async def probe_training_cos_settings(self) -> SystemTrainingCosProbeResponse:
        async with SessionLocal() as session:
            await resolve_current_user(session)
            config = await load_training_cos_config(session)
        try:
            result = probe_training_cos(config)
        except Exception as exc:
            return SystemTrainingCosProbeResponse(ok=False, message=str(exc))
        return SystemTrainingCosProbeResponse(
            ok=True,
            message="训练环境 COS 连接正常。",
            bucket=str(result.get("bucket") or ""),
            prefix=str(result.get("prefix") or ""),
            object_count=int(result.get("object_count") or 0),
        )
