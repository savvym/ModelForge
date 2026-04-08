from dataclasses import dataclass
from datetime import timedelta

from temporalio import workflow
from temporalio.common import RetryPolicy

with workflow.unsafe.imports_passed_through():
    from nta_backend.activities.evaluation_run import execute_evaluation_run_item


@dataclass
class EvaluationRunItemWorkflowInput:
    run_id: str
    item_id: str


@workflow.defn(name="evaluation_run_item_workflow")
class EvaluationRunItemWorkflow:
    @workflow.run
    async def run(self, payload: EvaluationRunItemWorkflowInput) -> dict:
        return await workflow.execute_activity(
            execute_evaluation_run_item,
            payload.__dict__,
            start_to_close_timeout=timedelta(hours=24),
            heartbeat_timeout=timedelta(seconds=30),
            retry_policy=RetryPolicy(maximum_attempts=1),
            cancellation_type=workflow.ActivityCancellationType.WAIT_CANCELLATION_COMPLETED,
        )
