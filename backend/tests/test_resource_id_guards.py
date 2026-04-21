import asyncio
from uuid import UUID

import pytest
from nta_backend.services import dataset_service, eval_service


class _ForbiddenSession:
    def __init__(self) -> None:
        self.called = False

    async def get(self, *args, **kwargs):
        self.called = True
        raise AssertionError("session.get should not be used for legacy UUID ids")

    async def execute(self, *args, **kwargs):
        self.called = True
        raise AssertionError("session.execute should not be used for legacy UUID ids")


def test_dataset_service_rejects_legacy_uuid_identifier() -> None:
    session = _ForbiddenSession()

    with pytest.raises(KeyError):
        asyncio.run(
            dataset_service._resolve_dataset_or_raise(
                session,
                "11111111-1111-1111-1111-111111111111",
                UUID("22222222-2222-2222-2222-222222222222"),
            )
        )

    assert session.called is False


def test_eval_service_imports_without_runtime_dependencies() -> None:
    service = eval_service.EvalJobService()
    assert service is not None
