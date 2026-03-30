import importlib.util
from datetime import datetime
from pathlib import Path
from uuid import UUID


def _load_target_module():
    module_path = (
        Path(__file__).resolve().parents[1]
        / "src"
        / "nta_backend"
        / "core"
        / "storage_layout.py"
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
JOB_ID = UUID("44444444-4444-4444-4444-444444444444")
LAKE_BATCH_ID = UUID("55555555-5555-5555-5555-555555555555")
LAKE_ASSET_ID = UUID("66666666-6666-6666-6666-666666666666")
CREATED_AT = datetime(2026, 3, 26, 12, 34, 56)


def test_build_project_files_key_uses_project_prefix() -> None:
    assert (
        TARGET_MODULE.build_project_files_key(
            PROJECT_ID,
            "book.pdf",
            prefix="imports/books",
            relative_path="chapter-1/book.pdf",
        )
        == "projects/11111111-1111-1111-1111-111111111111/files/imports/books/chapter-1/book.pdf"
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
        == "projects/11111111-1111-1111-1111-111111111111/datasets/"
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
        == "projects/11111111-1111-1111-1111-111111111111/datasets/"
        "ds-20260326123456-y8mjm/versions/"
        "dsv-20260326123456-xcxtf/artifacts/schema-report.json"
    )


def test_build_lake_raw_key_preserves_original_relative_path() -> None:
    assert (
        TARGET_MODULE.build_lake_raw_key(PROJECT_ID, "batch-001", "asset-001", "docs/paper.pdf")
        == "projects/11111111-1111-1111-1111-111111111111/lake/raw/"
        "batch-001/original/docs/paper.pdf"
    )


def test_build_lake_resource_codes_use_expected_prefixes() -> None:
    assert (
        TARGET_MODULE.build_lake_batch_code(CREATED_AT, LAKE_BATCH_ID)
        == "lb-20260326123456-vlkd1"
    )
    assert (
        TARGET_MODULE.build_lake_asset_code(CREATED_AT, LAKE_ASSET_ID)
        == "la-20260326123456-upvmu"
    )


def test_build_eval_job_artifact_key_uses_ej_code() -> None:
    assert (
        TARGET_MODULE.build_eval_job_artifact_key(
            PROJECT_ID,
            JOB_ID,
            CREATED_AT,
            "inference_result",
            "results",
            "model-output.jsonl",
        )
        == "projects/11111111-1111-1111-1111-111111111111/eval-jobs/"
        "ej-20260326123456-wh938/inference_result/results/model-output.jsonl"
    )


def test_project_scope_checks_only_match_project_prefix() -> None:
    own_prefix = TARGET_MODULE.build_project_prefix(PROJECT_ID)
    own_files_prefix = TARGET_MODULE.build_project_files_prefix(PROJECT_ID, "imports")

    assert TARGET_MODULE.is_project_scoped_prefix(PROJECT_ID, own_prefix)
    assert TARGET_MODULE.is_project_scoped_prefix(PROJECT_ID, own_files_prefix)
    assert TARGET_MODULE.is_project_scoped_key(PROJECT_ID, f"{own_files_prefix}book.pdf")
    assert not TARGET_MODULE.is_project_scoped_prefix(
        PROJECT_ID,
        "projects/aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa/files/",
    )
    assert not TARGET_MODULE.is_project_scoped_key(
        PROJECT_ID,
        "projects/aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa/files/book.pdf",
    )
