from collections.abc import AsyncIterator

from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from nta_backend.core.config import Settings, get_settings
from nta_backend.core.db import get_db_session


def get_app_settings() -> Settings:
    return get_settings()


async def get_session() -> AsyncIterator[AsyncSession]:
    async for session in get_db_session():
        yield session


SettingsDep = Depends(get_app_settings)
SessionDep = Depends(get_session)
