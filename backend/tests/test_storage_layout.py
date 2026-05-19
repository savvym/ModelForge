import importlib.util
import sys
from datetime import datetime
from pathlib import Path
from uuid import UUID

import pytest


def _load_target_module():
    backend_src = Path(__file__).resolve().parents[1] / "src"
    if str(backend_src) not in sys.path:
        sys.path.insert(0, str(backend_src))
    module_path = (
        Path(__file__).resolve().parents[1] / "src" / "nta_backend" / "core" / "storage_layout.py"
    )
    spec = importlib.util.spec_from_file_location("test_storage_layout_module", module_path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


TARGET_MODULE = _load_target_module()


PROJECT_ID = UUID("11111111-1111-1111-1111-111111111111")
DATASET_ID = UUID("22222222-2222-2222-2222-222222222222")
VERSION_ID = UUID("33333333-3333-3333-3333-333333333333")
CREATED_AT = datetime(2026, 3, 26, 12, 34, 56)


@pytest.fixture(autouse=True)
def _use_dev_storage_prefix(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("S3_ROOT_PREFIX", "nta-dev")
    TARGET_MODULE.get_settings.cache_clear()
    yield
    TARGET_MODULE.get_settings.cache_clear()


def test_build_project_files_key_uses_project_prefix() -> None:
    assert (
        TARGET_MODULE.build_project_files_key(
            PROJECT_ID,
            "book.pdf",
            prefix="imports/books",
            relative_path="chapter-1/book.pdf",
        )
        == "nta-dev/projects/11111111-1111-1111-1111-111111111111/files/"
        "imports/books/chapter-1/book.pdf"
    )


def test_build_dataset_source_key_uses_project_dataset_version_segments() -> None:
    assert (
        TARGET_MODULE.build_dataset_source_key(
            PROJECT_ID,
            DATASET_ID,
            CREATED_AT,
            VERSION_ID,
            CREATED_AT,
            "dataset.jsonl",
        )
        == "nta-dev/projects/11111111-1111-1111-1111-111111111111/datasets/"
        "ds-20260326123456-y8mjm/versions/"
        "dsv-20260326123456-xcxtf/source/dataset.jsonl"
    )


def test_build_dataset_artifact_key_uses_artifacts_directory() -> None:
    assert (
        TARGET_MODULE.build_dataset_artifact_key(
            PROJECT_ID,
            DATASET_ID,
            CREATED_AT,
            VERSION_ID,
            CREATED_AT,
            "schema-report.json",
        )
        == "nta-dev/projects/11111111-1111-1111-1111-111111111111/datasets/"
        "ds-20260326123456-y8mjm/versions/"
        "dsv-20260326123456-xcxtf/artifacts/schema-report.json"
    )


def test_project_scope_checks_only_match_project_prefix() -> None:
    own_prefix = TARGET_MODULE.build_project_prefix(PROJECT_ID)
    own_files_prefix = TARGET_MODULE.build_project_files_prefix(PROJECT_ID, "imports")

    assert TARGET_MODULE.is_project_scoped_prefix(PROJECT_ID, own_prefix)
    assert TARGET_MODULE.is_project_scoped_prefix(PROJECT_ID, own_files_prefix)
    assert TARGET_MODULE.is_project_scoped_key(PROJECT_ID, f"{own_files_prefix}book.pdf")
    assert not TARGET_MODULE.is_project_scoped_prefix(
        PROJECT_ID,
        "nta-dev/projects/aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa/files/",
    )
    assert not TARGET_MODULE.is_project_scoped_key(
        PROJECT_ID,
        "nta-dev/projects/aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa/files/book.pdf",
    )
