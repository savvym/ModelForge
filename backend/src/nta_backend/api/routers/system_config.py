from fastapi import APIRouter, HTTPException

from nta_backend.schemas.system_config import (
    SystemHuggingFaceSettings,
    SystemHuggingFaceSettingsUpdate,
)
from nta_backend.services.system_config_service import SystemConfigService

router = APIRouter(prefix="/system/config")
service = SystemConfigService()


@router.get("/huggingface", response_model=SystemHuggingFaceSettings)
async def get_huggingface_settings() -> SystemHuggingFaceSettings:
    try:
        return await service.get_huggingface_settings()
    except PermissionError as exc:
        raise HTTPException(status_code=401, detail=str(exc)) from exc


@router.patch("/huggingface", response_model=SystemHuggingFaceSettings)
async def update_huggingface_settings(
    payload: SystemHuggingFaceSettingsUpdate,
) -> SystemHuggingFaceSettings:
    try:
        return await service.update_huggingface_settings(payload)
    except PermissionError as exc:
        raise HTTPException(status_code=401, detail=str(exc)) from exc
