from datetime import UTC, datetime, timedelta
from uuid import NAMESPACE_URL, UUID, uuid5


def fixed_uuid(name: str) -> UUID:
    return uuid5(NAMESPACE_URL, f"nta-platform:{name}")


NOW = datetime.now(UTC)
PROJECT_ID = fixed_uuid("project:default")
DATASET_ID = fixed_uuid("dataset:mmlu")
SECOND_DATASET_ID = fixed_uuid("dataset:knowledge-base-seed")
DATASET_VERSION_ID = fixed_uuid("dataset-version:mmlu:v1")
SECOND_DATASET_VERSION_ID = fixed_uuid("dataset-version:knowledge-base-seed:v3")
MODEL_ID = fixed_uuid("model:doubao-seed-2.0-pro")
EVAL_JOB_ID = fixed_uuid("eval-job:mmlu-baseline")
SECOND_EVAL_JOB_ID = fixed_uuid("eval-job:mmlu-second")


def recent(minutes_ago: int) -> datetime:
    return NOW - timedelta(minutes=minutes_ago)
