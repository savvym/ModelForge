from dataclasses import dataclass
from datetime import timedelta

from temporalio import workflow

with workflow.unsafe.imports_passed_through():
    from nta_backend.activities.batch_inference import (
        merge_batch_outputs,
        run_batch_inference_chunks,
        validate_batch_input,
    )


@dataclass
class BatchInferenceWorkflowInput:
    project_id: str
    batch_job_id: str
    endpoint_id: str
    input_object_key: str
    output_object_key: str


@workflow.defn(name="batch_inference_workflow")
class BatchInferenceWorkflow:
    @workflow.run
    async def run(self, payload: BatchInferenceWorkflowInput) -> dict:
        await workflow.execute_activity(
            validate_batch_input,
            payload.__dict__,
            start_to_close_timeout=timedelta(minutes=1),
        )
        result = await workflow.execute_activity(
            run_batch_inference_chunks,
            payload.__dict__,
            start_to_close_timeout=timedelta(minutes=5),
        )
        await workflow.execute_activity(
            merge_batch_outputs,
            payload.__dict__,
            start_to_close_timeout=timedelta(minutes=2),
        )
        return result
