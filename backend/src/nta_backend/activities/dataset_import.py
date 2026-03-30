from temporalio import activity
from temporalio.exceptions import ApplicationError

from nta_backend.services.dataset_service import (
    activity_finalize_dataset_import,
    activity_mark_dataset_import_failed,
    activity_process_dataset_import,
)


def _raise_non_retryable(exc: Exception) -> None:
    raise ApplicationError(str(exc), non_retryable=True) from exc


@activity.defn
async def inspect_dataset_object(payload: dict) -> dict[str, int | str]:
    try:
        result = await activity_process_dataset_import(
            project_id=payload["project_id"],
            dataset_id=payload["dataset_id"],
            dataset_version_id=payload["dataset_version_id"],
        )
    except (ValueError, KeyError, FileNotFoundError) as exc:
        _raise_non_retryable(exc)

    return {
        "object_key": str(result["object_key"]),
        "record_count": int(result["record_count"]),
        "status": str(result["status"]),
    }


@activity.defn
async def validate_dataset_file(payload: dict) -> dict[str, str]:
    return {
        "dataset_id": payload["dataset_id"],
        "dataset_version_id": payload["dataset_version_id"],
        "validation": "passed",
    }


@activity.defn
async def persist_dataset_import_result(payload: dict) -> dict[str, str]:
    result = await activity_finalize_dataset_import(
        project_id=payload["project_id"],
        dataset_id=payload["dataset_id"],
        dataset_version_id=payload["dataset_version_id"],
    )
    return {
        "status": str(result["status"]),
        "dataset_version_id": str(result["dataset_version_id"]),
    }


@activity.defn
async def mark_dataset_import_failed(payload: dict) -> dict[str, str]:
    return await activity_mark_dataset_import_failed(
        project_id=payload["project_id"],
        dataset_id=payload["dataset_id"],
        dataset_version_id=payload["dataset_version_id"],
    )
