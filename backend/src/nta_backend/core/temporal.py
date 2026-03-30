from __future__ import annotations

import asyncio
import logging
from uuid import uuid4

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
from nta_backend.activities.usage_aggregation import aggregate_usage_daily, refresh_usage_cache
from nta_backend.core.config import get_settings
from nta_backend.workflows.batch_inference import BatchInferenceWorkflow
from nta_backend.workflows.dataset_import import DatasetImportWorkflow, DatasetImportWorkflowInput
from nta_backend.workflows.usage_aggregation import UsageAggregationWorkflow

_temporal_client: Client | None = None
logger = logging.getLogger(__name__)


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


async def start_eval_job_workflow(payload: object, workflow_id: str | None = None) -> str:
    raise RuntimeError("Eval workflow is disabled")


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


async def run_workers() -> None:
    settings = get_settings()
    client = await get_temporal_client()
    logger.info(
        "Starting Temporal workers (dataset=%s, batch=%s, usage=%s)",
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
            workflows=[UsageAggregationWorkflow],
            activities=[
                aggregate_usage_daily,
                refresh_usage_cache,
            ],
        ),
    ]

    await asyncio.gather(*(worker.run() for worker in workers))
