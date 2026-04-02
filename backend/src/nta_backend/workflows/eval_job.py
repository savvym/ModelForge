from dataclasses import dataclass
from datetime import timedelta
from typing import Any

from temporalio import workflow
from temporalio.common import RetryPolicy

with workflow.unsafe.imports_passed_through():
    from nta_backend.activities.eval_job import run_eval_job


@dataclass
class EvalJobWorkflowInput:
    job_id: str
    payload: dict[str, Any]


@workflow.defn(name="eval_job_workflow")
class EvalJobWorkflow:
    @workflow.run
    async def run(self, payload: EvalJobWorkflowInput) -> dict:
        return await workflow.execute_activity(
            run_eval_job,
            payload.__dict__,
            start_to_close_timeout=timedelta(hours=24),
            heartbeat_timeout=timedelta(seconds=30),
            retry_policy=RetryPolicy(maximum_attempts=1),
            cancellation_type=workflow.ActivityCancellationType.WAIT_CANCELLATION_COMPLETED,
        )
