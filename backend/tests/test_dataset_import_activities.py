import asyncio
import importlib.util
import sys
import types
from pathlib import Path

import pytest
from temporalio.exceptions import ApplicationError


def _load_target_module():
    async def _noop(*args, **kwargs):
        return None

    def _register_module(name: str, **attrs: object) -> None:
        module = types.ModuleType(name)
        for key, value in attrs.items():
            setattr(module, key, value)
        sys.modules[name] = module

    _register_module("nta_backend")
    _register_module("nta_backend.services")
    _register_module(
        "nta_backend.services.dataset_service",
        activity_finalize_dataset_import=_noop,
        activity_mark_dataset_import_failed=_noop,
        activity_process_dataset_import=_noop,
    )

    module_path = (
        Path(__file__).resolve().parents[1]
        / "src"
        / "nta_backend"
        / "activities"
        / "dataset_import.py"
    )
    spec = importlib.util.spec_from_file_location("test_dataset_import_activities_module", module_path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


TARGET_MODULE = _load_target_module()


@pytest.mark.parametrize("error", [ValueError("bad payload"), KeyError("missing dataset"), FileNotFoundError("missing object")])
def test_inspect_dataset_object_marks_terminal_errors_non_retryable(error: Exception) -> None:
    async def fake_process_dataset_import(**kwargs):
        raise error

    TARGET_MODULE.activity_process_dataset_import = fake_process_dataset_import

    with pytest.raises(ApplicationError) as exc_info:
        asyncio.run(
            TARGET_MODULE.inspect_dataset_object(
                {
                    "project_id": "project-id",
                    "dataset_id": "dataset-id",
                    "dataset_version_id": "version-id",
                }
            )
        )

    assert exc_info.value.non_retryable is True
