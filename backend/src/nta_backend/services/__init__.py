from importlib import import_module
from typing import Any

__all__ = ["DatasetService", "EvalJobService", "ObjectStoreService", "ProjectService"]


def __getattr__(name: str) -> Any:
    if name == "DatasetService":
        return import_module("nta_backend.services.dataset_service").DatasetService
    if name == "EvalJobService":
        return import_module("nta_backend.services.eval_service").EvalJobService
    if name == "ObjectStoreService":
        return import_module("nta_backend.services.object_store_service").ObjectStoreService
    if name == "ProjectService":
        return import_module("nta_backend.services.project_service").ProjectService
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
