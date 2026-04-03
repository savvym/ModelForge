import asyncio
from dataclasses import dataclass
from datetime import timedelta

from temporalio import workflow
from temporalio.common import RetryPolicy

with workflow.unsafe.imports_passed_through():
    from nta_backend.activities.evaluation_run import aggregate_evaluation_run
    from nta_backend.activities.evaluation_run import list_evaluation_run_items
    from nta_backend.workflows.evaluation_run_item import (
        EvaluationRunItemWorkflow,
        EvaluationRunItemWorkflowInput,
    )


@dataclass
class EvaluationRunWorkflowInput:
    run_id: str


@workflow.defn(name="evaluation_run_workflow")
class EvaluationRunWorkflow:
    @workflow.run
    async def run(self, payload: EvaluationRunWorkflowInput) -> dict:
        item_ids = await workflow.execute_activity(
            list_evaluation_run_items,
            {"run_id": payload.run_id},
            start_to_close_timeout=timedelta(minutes=5),
            retry_policy=RetryPolicy(maximum_attempts=1),
        )
        child_handles = []
        for item_id in item_ids:
            child_handles.append(
                await workflow.start_child_workflow(
                    EvaluationRunItemWorkflow.run,
                    EvaluationRunItemWorkflowInput(run_id=payload.run_id, item_id=item_id),
                    id=f"evaluation-run-item-{item_id}",
                    cancellation_type=workflow.ChildWorkflowCancellationType.WAIT_CANCELLATION_COMPLETED,
                )
            )
        results = await asyncio.gather(*child_handles, return_exceptions=True)
        for item_id, result in zip(item_ids, results, strict=False):
            if isinstance(result, Exception):
                workflow.logger.error(
                    "Evaluation run item workflow failed",
                    extra={"item_id": item_id, "error": str(result)},
                )
        await workflow.execute_activity(
            aggregate_evaluation_run,
            {"run_id": payload.run_id},
            start_to_close_timeout=timedelta(minutes=10),
            retry_policy=RetryPolicy(maximum_attempts=1),
        )
        return {"run_id": payload.run_id, "status": "completed"}
