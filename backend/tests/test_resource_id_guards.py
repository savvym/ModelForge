import asyncio
import importlib.util
import sys
from pathlib import Path
from uuid import UUID

import pytest


def _load_target_module(module_name: str, relative_path: str):
    module_path = Path(__file__).resolve().parents[1] / "src" / "nta_backend" / relative_path
    spec = importlib.util.spec_from_file_location(module_name, module_path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    spec.loader.exec_module(module)
    return module


for module_name, module in list(sys.modules.items()):
    if not module_name.startswith("nta_backend"):
        continue
    if getattr(module, "__file__", None) or hasattr(module, "__path__"):
        continue
    del sys.modules[module_name]

dataset_service = _load_target_module(
    "test_resource_dataset_service",
    "services/dataset_service.py",
)
eval_service = _load_target_module(
    "test_resource_eval_service",
    "services/eval_service.py",
)


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
