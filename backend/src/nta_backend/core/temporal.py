from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass
from uuid import uuid4

from temporalio.api.enums.v1 import WorkflowExecutionStatus
from temporalio.client import Client
from temporalio.worker import Worker

from nta_backend.activities.batch_inference import (
    merge_batch_outputs,
    run_batch_inference_chunks,
    validate_batch_input,
)
from nta_backend.activities.dataset_import import (
    inspect_dataset_object,
    mark_dataset_import_failed,
    persist_dataset_import_result,
    validate_dataset_file,
)
from nta_backend.activities.eval_job import run_eval_job
from nta_backend.activities.usage_aggregation import aggregate_usage_daily, refresh_usage_cache
from nta_backend.core.config import get_settings
from nta_backend.workflows.batch_inference import BatchInferenceWorkflow
from nta_backend.workflows.dataset_import import DatasetImportWorkflow, DatasetImportWorkflowInput
from nta_backend.workflows.eval_job import EvalJobWorkflow, EvalJobWorkflowInput
from nta_backend.workflows.usage_aggregation import UsageAggregationWorkflow

_temporal_client: Client | None = None
logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class WorkflowExecutionState:
    status: str
    is_terminal: bool
    failure_message: str | None = None


_WORKFLOW_STATUS_MAP = {
    WorkflowExecutionStatus.WORKFLOW_EXECUTION_STATUS_RUNNING: "running",
    WorkflowExecutionStatus.WORKFLOW_EXECUTION_STATUS_COMPLETED: "completed",
    WorkflowExecutionStatus.WORKFLOW_EXECUTION_STATUS_FAILED: "failed",
    WorkflowExecutionStatus.WORKFLOW_EXECUTION_STATUS_CANCELED: "cancelled",
    WorkflowExecutionStatus.WORKFLOW_EXECUTION_STATUS_TERMINATED: "terminated",
    WorkflowExecutionStatus.WORKFLOW_EXECUTION_STATUS_CONTINUED_AS_NEW: "continued_as_new",
    WorkflowExecutionStatus.WORKFLOW_EXECUTION_STATUS_TIMED_OUT: "timed_out",
    WorkflowExecutionStatus.WORKFLOW_EXECUTION_STATUS_PAUSED: "paused",
}
_WORKFLOW_TERMINAL_STATUSES = frozenset(
    {"completed", "failed", "cancelled", "terminated", "continued_as_new", "timed_out"}
)


def _workflow_failure_root_message(exc: BaseException) -> str:
    current: BaseException = exc
    while True:
        cause = getattr(current, "cause", None)
        if cause is None or not isinstance(cause, BaseException):
            break
        current = cause
    message = str(current).strip()
    return message or current.__class__.__name__


async def get_temporal_client() -> Client:
    global _temporal_client
    if _temporal_client is None:
        settings = get_settings()
        logger.info(
            "Connecting to Temporal at %s (namespace=%s)",
            settings.temporal_host,
            settings.temporal_namespace,
        )
        _temporal_client = await Client.connect(
            settings.temporal_host,
            namespace=settings.temporal_namespace,
        )
        logger.info("Temporal client connected")
    return _temporal_client


async def start_eval_job_workflow(
    payload: EvalJobWorkflowInput,
    workflow_id: str | None = None,
) -> str:
    settings = get_settings()
    client = await get_temporal_client()
    workflow_id = workflow_id or f"eval-job-{uuid4()}"
    handle = await client.start_workflow(
        EvalJobWorkflow.run,
        payload,
        id=workflow_id,
        task_queue=settings.temporal_task_queue_eval,
    )
    return handle.id


async def start_dataset_import_workflow(
    payload: DatasetImportWorkflowInput, workflow_id: str | None = None
) -> str:
    settings = get_settings()
    client = await get_temporal_client()
    workflow_id = workflow_id or f"dataset-import-{uuid4()}"
    handle = await client.start_workflow(
        DatasetImportWorkflow.run,
        payload,
        id=workflow_id,
        task_queue=settings.temporal_task_queue_dataset,
    )
    return handle.id


async def get_workflow_execution_state(workflow_id: str) -> WorkflowExecutionState:
    client = await get_temporal_client()
    handle = client.get_workflow_handle(workflow_id)
    description = await handle.describe()
    raw_status = description.raw_description.workflow_execution_info.status
    status = _WORKFLOW_STATUS_MAP.get(raw_status, "unknown")
    failure_message: str | None = None
    if status in {"failed", "cancelled", "terminated", "timed_out"}:
        try:
            await handle.result(follow_runs=False)
        except Exception as exc:  # noqa: BLE001
            failure_message = _workflow_failure_root_message(exc)
    return WorkflowExecutionState(
        status=status,
        is_terminal=status in _WORKFLOW_TERMINAL_STATUSES,
        failure_message=failure_message,
    )


async def cancel_workflow_execution(workflow_id: str) -> None:
    client = await get_temporal_client()
    handle = client.get_workflow_handle(workflow_id)
    await handle.cancel()


async def run_workers() -> None:
    settings = get_settings()
    client = await get_temporal_client()
    logger.info(
        "Starting Temporal workers (dataset=%s, batch=%s, eval=%s)",
        settings.temporal_task_queue_dataset,
        settings.temporal_task_queue_batch,
        settings.temporal_task_queue_eval,
    )

    workers = [
        Worker(
            client,
            task_queue=settings.temporal_task_queue_dataset,
            workflows=[DatasetImportWorkflow],
            activities=[
                inspect_dataset_object,
                validate_dataset_file,
                persist_dataset_import_result,
                mark_dataset_import_failed,
            ],
        ),
        Worker(
            client,
            task_queue=settings.temporal_task_queue_batch,
            workflows=[BatchInferenceWorkflow],
            activities=[
                validate_batch_input,
                run_batch_inference_chunks,
                merge_batch_outputs,
            ],
        ),
        Worker(
            client,
            task_queue=settings.temporal_task_queue_eval,
            workflows=[EvalJobWorkflow, UsageAggregationWorkflow],
            activities=[
                run_eval_job,
                aggregate_usage_daily,
                refresh_usage_cache,
            ],
        ),
    ]

    await asyncio.gather(*(worker.run() for worker in workers))
