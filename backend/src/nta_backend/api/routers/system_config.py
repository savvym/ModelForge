from fastapi import APIRouter, HTTPException

from nta_backend.schemas.system_config import (
    SystemHuggingFaceSettings,
    SystemHuggingFaceSettingsUpdate,
    SystemTrainingCosProbeResponse,
    SystemTrainingCosSettings,
    SystemTrainingCosSettingsUpdate,
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


@router.get("/training-cos", response_model=SystemTrainingCosSettings)
async def get_training_cos_settings() -> SystemTrainingCosSettings:
    try:
        return await service.get_training_cos_settings()
    except PermissionError as exc:
        raise HTTPException(status_code=401, detail=str(exc)) from exc


@router.patch("/training-cos", response_model=SystemTrainingCosSettings)
async def update_training_cos_settings(
    payload: SystemTrainingCosSettingsUpdate,
) -> SystemTrainingCosSettings:
    try:
        return await service.update_training_cos_settings(payload)
    except PermissionError as exc:
        raise HTTPException(status_code=401, detail=str(exc)) from exc


@router.post("/training-cos/probe", response_model=SystemTrainingCosProbeResponse)
async def probe_training_cos_settings() -> SystemTrainingCosProbeResponse:
    try:
        return await service.probe_training_cos_settings()
    except PermissionError as exc:
        raise HTTPException(status_code=401, detail=str(exc)) from exc
