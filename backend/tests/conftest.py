import pytest

from nta_backend.core.db import dispose_engine


@pytest.fixture(autouse=True)
async def _dispose_db_engine_after_each_test():
    yield
    await dispose_engine()
