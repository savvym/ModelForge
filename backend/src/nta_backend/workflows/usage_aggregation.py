from dataclasses import dataclass
from datetime import timedelta

from temporalio import workflow

with workflow.unsafe.imports_passed_through():
    from nta_backend.activities.usage_aggregation import aggregate_usage_daily, refresh_usage_cache


@dataclass
class UsageAggregationWorkflowInput:
    project_id: str
    date: str


@workflow.defn(name="usage_aggregation_workflow")
class UsageAggregationWorkflow:
    @workflow.run
    async def run(self, payload: UsageAggregationWorkflowInput) -> dict:
        result = await workflow.execute_activity(
            aggregate_usage_daily,
            payload.__dict__,
            start_to_close_timeout=timedelta(minutes=2),
        )
        await workflow.execute_activity(
            refresh_usage_cache,
            payload.__dict__,
            start_to_close_timeout=timedelta(minutes=1),
        )
        return result
