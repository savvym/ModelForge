from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from nta_backend.api.deps import get_session
from nta_backend.schemas.auth import CurrentUserResponse
from nta_backend.services.auth_service import AuthService

router = APIRouter(prefix="/auth")
service = AuthService()


@router.get("/me", response_model=CurrentUserResponse)
async def get_current_user(
    session: Annotated[AsyncSession, Depends(get_session)],
) -> CurrentUserResponse:
    try:
        return await service.get_current_user(session)
    except PermissionError as exc:
        raise HTTPException(status_code=401, detail=str(exc)) from exc
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="Current project not found") from exc
