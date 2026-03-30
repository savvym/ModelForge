import importlib.util
import sys
import types
from pathlib import Path

import pytest


def _load_target_module():
    async def _noop(*args, **kwargs):
        return None

    def _register_module(name: str, **attrs: object) -> None:
        module = types.ModuleType(name)
        for key, value in attrs.items():
            setattr(module, key, value)
        sys.modules[name] = module

    _register_module("nta_backend")
    _register_module("nta_backend.core")
    _register_module("nta_backend.core.db", SessionLocal=object())
    _register_module(
        "nta_backend.core.project_context",
        ensure_default_project=_noop,
        resolve_active_project_id=_noop,
    )
    _register_module("nta_backend.models")
    _register_module(
        "nta_backend.models.modeling",
        Model=type("Model", (), {}),
        ModelProvider=type("ModelProvider", (), {}),
    )
    _register_module("nta_backend.schemas")
    _register_module(
        "nta_backend.schemas.model_registry",
        ModelProviderCreate=type("ModelProviderCreate", (), {}),
        ModelProviderSummary=type("ModelProviderSummary", (), {}),
        ModelProviderSyncResult=type("ModelProviderSyncResult", (), {}),
        ModelProviderUpdate=type("ModelProviderUpdate", (), {}),
        RegistryModelChatRequest=type("RegistryModelChatRequest", (), {}),
        RegistryModelChatResponse=type("RegistryModelChatResponse", (), {}),
        RegistryModelCreate=type("RegistryModelCreate", (), {}),
        RegistryModelSummary=type("RegistryModelSummary", (), {}),
        RegistryModelTestRequest=type("RegistryModelTestRequest", (), {}),
        RegistryModelTestResponse=type("RegistryModelTestResponse", (), {}),
        RegistryModelUpdate=type("RegistryModelUpdate", (), {}),
    )

    module_path = (
        Path(__file__).resolve().parents[1]
        / "src"
        / "nta_backend"
        / "services"
        / "model_registry_service.py"
    )
    spec = importlib.util.spec_from_file_location("test_model_registry_service_module", module_path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


TARGET_MODULE = _load_target_module()


@pytest.mark.parametrize(
    ("raw_value", "expected"),
    [
        ("https://provider.example.com/v1/", "https://provider.example.com/v1"),
        ("https://provider.example.com/v1/models", "https://provider.example.com/v1"),
        (" https://provider.example.com/v1/models/ ", "https://provider.example.com/v1"),
        ("http://127.0.0.1:8000/v1", "http://127.0.0.1:8000/v1"),
        ("file:///etc/passwd", "file:///etc/passwd"),
    ],
)
def test_normalize_base_url(raw_value: str, expected: str) -> None:
    assert TARGET_MODULE._normalize_base_url(raw_value) == expected
