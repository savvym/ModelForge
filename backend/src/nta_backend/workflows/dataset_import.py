from dataclasses import dataclass
from datetime import timedelta

from temporalio import workflow

with workflow.unsafe.imports_passed_through():
    from nta_backend.activities.dataset_import import (
        inspect_dataset_object,
        mark_dataset_import_failed,
        persist_dataset_import_result,
        validate_dataset_file,
    )


@dataclass
class DatasetImportWorkflowInput:
    project_id: str
    dataset_id: str
    dataset_version_id: str
    object_key: str


@workflow.defn(name="dataset_import_workflow")
class DatasetImportWorkflow:
    @workflow.run
    async def run(self, payload: DatasetImportWorkflowInput) -> dict:
        activity_payload = {
            "project_id": payload.project_id,
            "dataset_id": payload.dataset_id,
            "dataset_version_id": payload.dataset_version_id,
            "object_key": payload.object_key,
        }

        try:
            metadata = await workflow.execute_activity(
                inspect_dataset_object,
                activity_payload,
                start_to_close_timeout=timedelta(minutes=2),
            )
            await workflow.execute_activity(
                validate_dataset_file,
                activity_payload,
                start_to_close_timeout=timedelta(minutes=2),
            )
            persisted = await workflow.execute_activity(
                persist_dataset_import_result,
                activity_payload,
                start_to_close_timeout=timedelta(minutes=2),
            )
            return {"metadata": metadata, **persisted}
        except Exception:
            await workflow.execute_activity(
                mark_dataset_import_failed,
                activity_payload,
                start_to_close_timeout=timedelta(minutes=1),
            )
            return {
                "status": "failed",
                "dataset_id": payload.dataset_id,
                "dataset_version_id": payload.dataset_version_id,
            }
