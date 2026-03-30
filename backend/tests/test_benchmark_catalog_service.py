import json
from pathlib import Path
from uuid import uuid4

import pytest
from sqlalchemy import delete

from nta_backend.core.config import get_settings
from nta_backend.core.db import SessionLocal
from nta_backend.core.object_store import delete_object, put_object_bytes
from nta_backend.eval_catalog.contracts import (
    CL_BENCH_PROMPT_CONFIG,
    CL_BENCH_PROMPT_SCHEMA,
    CL_BENCH_SAMPLE_SCHEMA,
    GENERAL_MCQ_PROMPT_CONFIG,
    GENERAL_MCQ_PROMPT_SCHEMA,
    MMLU_SOURCE_SCHEMA,
)
from nta_backend.models.benchmark_catalog import (
    BenchmarkVersion as BenchmarkVersionRecord,
)
from nta_backend.schemas.benchmark_catalog import (
    BenchmarkVersionCreate,
    BenchmarkVersionUpdate,
)
from nta_backend.services.benchmark_catalog_service import BenchmarkCatalogService


async def test_benchmark_catalog_service_lists_code_defined_benchmark_versions() -> None:
    service = BenchmarkCatalogService()

    catalog = await service.list_benchmarks()
    catalog_names = {item.name for item in catalog}
    assert "cl_bench" in catalog_names
    assert "mmlu" in catalog_names
    assert "cmmlu" in catalog_names
    assert "ceval" in catalog_names
    assert "arc" in catalog_names
    assert "nta_bench_network" in catalog_names

    mmlu_summary = next(item for item in catalog if item.name == "mmlu")
    assert mmlu_summary.runtime_available is True
    assert mmlu_summary.metadata_source == "builtin+runtime"
    assert mmlu_summary.version_count >= 1
    assert "acc" in mmlu_summary.metric_names

    summary = await service.get_benchmark("cl_bench")
    sample_file = await service.get_benchmark_sample_file("cl_bench")

    assert summary.name == "cl_bench"
    assert summary.display_name == "CL-bench"
    assert summary.runtime_available is True
    assert summary.metadata_source == "builtin+runtime"
    assert summary.version_count >= 2
    assert summary.enabled_version_count >= 2
    assert summary.sample_schema_json == CL_BENCH_SAMPLE_SCHEMA
    assert summary.prompt_schema_json == CL_BENCH_PROMPT_SCHEMA
    assert summary.prompt_config_json == CL_BENCH_PROMPT_CONFIG
    assert summary.sample_example_json is not None
    assert summary.statistics_json is not None
    assert sample_file.file_name == "cl_bench-sample.jsonl"
    assert sample_file.media_type == "application/x-ndjson"
    assert sample_file.content.strip()
    sample_line = json.loads(sample_file.content.decode("utf-8").splitlines()[0])
    assert "input" in sample_line or "messages" in sample_line

    mmlu_detail = await service.get_benchmark("mmlu")
    assert mmlu_detail.name == "mmlu"
    assert mmlu_detail.runtime_available is True
    assert mmlu_detail.sample_schema_json == MMLU_SOURCE_SCHEMA
    assert mmlu_detail.prompt_schema_json == GENERAL_MCQ_PROMPT_SCHEMA
    assert mmlu_detail.prompt_config_json == GENERAL_MCQ_PROMPT_CONFIG
    assert mmlu_detail.prompt_template is not None

    network_detail = await service.get_benchmark("nta_bench_network")
    assert network_detail.name == "nta_bench_network"
    assert network_detail.family_name == "grounded_rubric_qa"
    assert network_detail.family_display_name == "Grounded Rubric QA"
    assert network_detail.runtime_available is True
    assert network_detail.sample_example_json is not None

    smoke_version = next(
        version for version in summary.versions if version.id == "cl_bench_smoke_1"
    )
    assert smoke_version.dataset_source_uri is not None
    assert smoke_version.dataset_source_uri.startswith("s3://")
    assert smoke_version.dataset_source_uri.endswith("/cl_bench_smoke_1/CL-bench-1.jsonl")
    assert smoke_version.sample_count == 1
    version_id = f"tmp_cl_bench_{uuid4().hex[:8]}"
    mmlu_version_id = f"tmp_mmlu_{uuid4().hex[:8]}"
    dataset_path = (
        Path(__file__).resolve().parents[1] / ".datasets" / "cl_bench" / "CL-bench-1.jsonl"
    )
    bucket = get_settings().s3_bucket_dataset_raw
    mmlu_object_key = f"projects/{uuid4()}/files/benchmarks/mmlu/{mmlu_version_id}.jsonl"
    cl_bench_object_key = f"projects/{uuid4()}/files/benchmarks/cl_bench/{version_id}.jsonl"
    invalid_version_id = f"invalid_cl_bench_{uuid4().hex[:8]}"
    invalid_object_key = f"projects/{uuid4()}/files/benchmarks/cl_bench/{invalid_version_id}.jsonl"

    try:
        put_object_bytes(
            bucket,
            mmlu_object_key,
            (
                json.dumps(
                    {
                        "question": "2 + 2 = ?",
                        "subject": "abstract_algebra",
                        "choices": ["1", "4", "3", "5"],
                        "answer": 1,
                    },
                    ensure_ascii=False,
                )
                + "\n"
            ).encode("utf-8"),
            content_type="application/x-ndjson",
        )
        mmlu_version = await service.create_benchmark_version(
            "mmlu",
            BenchmarkVersionCreate(
                id=mmlu_version_id,
                display_name="MMLU Smoke V1",
                description="mmlu version for tests",
                dataset_source_uri=f"s3://{bucket}/{mmlu_object_key}",
                enabled=True,
            ),
        )
        assert mmlu_version.id == mmlu_version_id
        assert mmlu_version.sample_count == 1

        put_object_bytes(
            bucket,
            cl_bench_object_key,
            dataset_path.read_bytes(),
            content_type="application/x-ndjson",
        )
        version = await service.create_benchmark_version(
            "cl_bench",
            BenchmarkVersionCreate(
                id=version_id,
                display_name="Smoke V1",
                description="version for tests",
                dataset_source_uri=f"s3://{bucket}/{cl_bench_object_key}",
                enabled=True,
            ),
        )
        assert version.id == version_id
        assert version.sample_count == 1

        updated_version = await service.update_benchmark_version(
            "cl_bench",
            version_id,
            BenchmarkVersionUpdate(
                enabled=False,
            ),
        )
        assert updated_version.enabled is False
        assert updated_version.sample_count == 1

        put_object_bytes(
            bucket,
            invalid_object_key,
            b'{"messages": []}\n',
            content_type="application/x-ndjson",
        )
        with pytest.raises(ValueError):
            await service.create_benchmark_version(
                "cl_bench",
                BenchmarkVersionCreate(
                    id=invalid_version_id,
                    display_name="Invalid V1",
                    dataset_source_uri=f"s3://{bucket}/{invalid_object_key}",
                    enabled=True,
                ),
            )
        with pytest.raises(ValueError):
            await service.create_benchmark_version(
                "mmlu",
                BenchmarkVersionCreate(
                    id=f"invalid_local_{uuid4().hex[:8]}",
                    display_name="Invalid Local Source",
                    dataset_source_uri="file:///tmp/not-allowed.jsonl",
                    enabled=True,
                ),
            )
    finally:
        async with SessionLocal() as session:
            await session.execute(
                delete(BenchmarkVersionRecord).where(
                    BenchmarkVersionRecord.version_id.in_(
                        [version_id, mmlu_version_id, invalid_version_id]
                    )
                )
            )
            await session.commit()
        for object_key in (mmlu_object_key, cl_bench_object_key, invalid_object_key):
            delete_object(bucket, object_key)
