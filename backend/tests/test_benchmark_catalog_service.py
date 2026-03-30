import json
from uuid import uuid4

import pytest
from sqlalchemy import delete

from nta_backend.core.config import get_settings
from nta_backend.core.db import SessionLocal, dispose_engine
from nta_backend.core.object_store import delete_object, put_object_bytes
from nta_backend.models.benchmark_catalog import (
    BenchmarkDefinition as BenchmarkDefinitionRecord,
    BenchmarkVersion as BenchmarkVersionRecord,
)
from nta_backend.models.eval_template import EvalTemplate
from nta_backend.schemas.benchmark_catalog import (
    BenchmarkDefinitionCreate,
    BenchmarkDefinitionUpdate,
    BenchmarkVersionCreate,
    BenchmarkVersionUpdate,
)
from nta_backend.services.benchmark_catalog_service import BenchmarkCatalogService


@pytest.fixture(autouse=True)
async def _dispose_db_engine_between_tests():
    yield
    await dispose_engine()


async def test_benchmark_catalog_service_lists_only_custom_benchmarks() -> None:
    service = BenchmarkCatalogService()
    benchmark_name = f"custom_benchmark_{uuid4().hex[:8]}"
    template_name = f"template_for_catalog_{uuid4().hex[:8]}"
    bucket = get_settings().s3_bucket_dataset_raw
    object_key = f"projects/{uuid4()}/files/benchmarks/{benchmark_name}/dataset.jsonl"
    template_id: str | None = None
    template_uuid = None
    version_id: str | None = None

    try:
        async with SessionLocal() as session:
            template = EvalTemplate(
                name=template_name,
                version=1,
                prompt="Question: {{input}}\nReference: {{target}}\nAnswer: {{output}}",
                vars=["input", "target", "output"],
                template_type="llm_categorical",
                preset_id="rubric-check",
                output_type="categorical",
                output_config={
                    "label_groups": [
                        {"key": "pass", "label": "Pass", "labels": ["Pass"], "score_policy": "pass"},
                        {"key": "fail", "label": "Fail", "labels": ["Fail"], "score_policy": "fail"},
                    ]
                },
                model="GPT-5.4",
            )
            session.add(template)
            await session.commit()
            await session.refresh(template)
            template_id = str(template.id)
            template_uuid = template.id

        await service.create_benchmark_definition(
            BenchmarkDefinitionCreate(
                name=benchmark_name,
                display_name="Custom Benchmark",
                description="custom benchmark for catalog tests",
                category="llm",
                field_mapping={
                    "input_field": "question",
                    "target_field": "answer",
                    "id_field": "uid",
                },
                eval_template_id=template_id,
            )
        )

        put_object_bytes(
            bucket,
            object_key,
            (
                json.dumps(
                    {
                        "question": "2 + 2 = ?",
                        "answer": "4",
                        "uid": "sample-1",
                    },
                    ensure_ascii=False,
                )
                + "\n"
            ).encode("utf-8"),
            content_type="application/x-ndjson",
        )
        version = await service.create_benchmark_version(
            benchmark_name,
            BenchmarkVersionCreate(
                display_name="Custom Version",
                description="custom version for tests",
                dataset_source_uri=f"s3://{bucket}/{object_key}",
                enabled=True,
            ),
        )
        version_id = version.id
        assert version.id.startswith("ver-")
        assert version.sample_count == 1

        catalog = await service.list_benchmarks()
        catalog_names = {item.name for item in catalog}
        assert benchmark_name in catalog_names
        assert "cl_bench" not in catalog_names
        assert "mmlu" not in catalog_names
        assert all(item.source_type == "custom" for item in catalog)

        summary = next(item for item in catalog if item.name == benchmark_name)
        assert summary.version_count == 1
        assert summary.enabled_version_count == 1
        assert summary.eval_template_id == template_id
        assert summary.metric_names == ["judge_template"]

        detail = await service.get_benchmark(benchmark_name)
        assert detail.sample_schema_json["required"] == ["question"]
        assert detail.sample_example_json == {
            "question": "What is the capital of France?",
            "answer": "Paris",
            "uid": "sample-1",
        }

        sample_file = await service.get_benchmark_sample_file(benchmark_name)
        assert sample_file.file_name == f"{benchmark_name}-sample.jsonl"
        sample_line = json.loads(sample_file.content.decode("utf-8").splitlines()[0])
        assert sample_line == detail.sample_example_json

        updated_version = await service.update_benchmark_version(
            benchmark_name,
            version_id,
            BenchmarkVersionUpdate(enabled=False),
        )
        assert updated_version.enabled is False
        assert updated_version.sample_count == 1
    finally:
        async with SessionLocal() as session:
            if version_id is not None:
                await session.execute(
                    delete(BenchmarkVersionRecord).where(
                        BenchmarkVersionRecord.version_id == version_id
                    )
                )
            await session.execute(
                delete(BenchmarkDefinitionRecord).where(
                    BenchmarkDefinitionRecord.name == benchmark_name
                )
            )
            if template_uuid is not None:
                await session.execute(
                    delete(EvalTemplate).where(EvalTemplate.id == template_uuid)
                )
            await session.commit()
        delete_object(bucket, object_key)


async def test_benchmark_definition_can_bind_eval_template() -> None:
    service = BenchmarkCatalogService()
    template_name = f"template_link_{uuid4().hex[:8]}"
    template_id: str | None = None
    template_uuid = None
    benchmark_name: str | None = None

    try:
        async with SessionLocal() as session:
            template = EvalTemplate(
                name=template_name,
                version=1,
                prompt="Question: {{input}}\nAnswer: {{output}}",
                vars=["input", "output"],
                template_type="llm_categorical",
                preset_id="rubric-check",
                output_type="categorical",
                output_config={
                    "label_groups": [
                        {"key": "pass", "label": "Pass", "labels": ["Pass"], "score_policy": "pass"},
                        {"key": "fail", "label": "Fail", "labels": ["Fail"], "score_policy": "fail"},
                    ]
                },
                model="GPT-5.4",
            )
            session.add(template)
            await session.commit()
            await session.refresh(template)
            template_id = str(template.id)
            template_uuid = template.id

        created = await service.create_benchmark_definition(
            BenchmarkDefinitionCreate(
                display_name="Template Benchmark",
                description="benchmark bound to eval template",
                category="llm",
                default_eval_method="accuracy",
                requires_judge_model=False,
                eval_template_id=template_id,
            )
        )

        benchmark_name = created.name
        assert created.name.startswith("bench-")
        assert created.eval_template_id == template_id
        assert created.eval_template_name == template_name
        assert created.eval_template_version == 1
        assert created.eval_template_type == "llm_categorical"
        assert created.eval_template_preset_id == "rubric-check"
        assert created.default_eval_method == "judge-template"
        assert created.requires_judge_model is True
        assert created.metric_names == ["judge_template"]

        detail = await service.get_benchmark(benchmark_name)
        assert detail.eval_template_name == template_name

        updated = await service.update_benchmark_definition(
            benchmark_name,
            BenchmarkDefinitionUpdate(
                description="updated benchmark bound to eval template",
                eval_template_id=template_id,
            ),
        )
        assert updated.eval_template_id == template_id
        assert updated.eval_template_name == template_name
        assert updated.default_eval_method == "judge-template"
        assert updated.requires_judge_model is True
        assert updated.metric_names == ["judge_template"]
        assert updated.description == "updated benchmark bound to eval template"
    finally:
        async with SessionLocal() as session:
            if benchmark_name is not None:
                await session.execute(
                    delete(BenchmarkDefinitionRecord).where(
                        BenchmarkDefinitionRecord.name == benchmark_name
                    )
                )
            if template_id is not None:
                await session.execute(
                    delete(EvalTemplate).where(EvalTemplate.id == template_uuid)
                )
            await session.commit()


async def test_benchmark_definition_requires_eval_template() -> None:
    service = BenchmarkCatalogService()

    with pytest.raises(ValueError, match="必须选择一个评测模板"):
        await service.create_benchmark_definition(
            BenchmarkDefinitionCreate(
                name=f"template_required_{uuid4().hex[:8]}",
                display_name="Template Required Benchmark",
                description="should fail without eval template",
                category="llm",
            )
        )


async def test_benchmark_version_preview_and_download() -> None:
    service = BenchmarkCatalogService()
    benchmark_name = f"preview_benchmark_{uuid4().hex[:8]}"
    template_name = f"preview_template_{uuid4().hex[:8]}"
    bucket = get_settings().s3_bucket_dataset_raw
    object_key = f"manual-evals/{benchmark_name}.jsonl"
    template_uuid = None
    version_id: str | None = None

    try:
        async with SessionLocal() as session:
            template = EvalTemplate(
                name=template_name,
                version=1,
                prompt="Question: {{input}}\nReference: {{target}}\nAnswer: {{output}}",
                vars=["input", "target", "output"],
                template_type="llm_categorical",
                preset_id="rubric-check",
                output_type="categorical",
                output_config={
                    "label_groups": [
                        {"key": "pass", "label": "Pass", "labels": ["Pass"], "score_policy": "pass"},
                        {"key": "fail", "label": "Fail", "labels": ["Fail"], "score_policy": "fail"},
                    ]
                },
                model="GPT-5.4",
            )
            session.add(template)
            await session.commit()
            await session.refresh(template)
            template_uuid = template.id

        created = await service.create_benchmark_definition(
            BenchmarkDefinitionCreate(
                name=benchmark_name,
                display_name="Preview Benchmark",
                description="benchmark for preview tests",
                category="llm",
                field_mapping={
                    "input_field": "input",
                    "target_field": "target",
                    "id_field": "id",
                },
                eval_template_id=str(template_uuid),
            )
        )

        put_object_bytes(
            bucket,
            object_key,
            (
                json.dumps(
                    {
                        "id": "sample-1",
                        "input": "hello",
                        "target": "world",
                    },
                    ensure_ascii=False,
                )
                + "\n"
            ).encode("utf-8"),
            content_type="application/x-ndjson",
        )

        version = await service.create_benchmark_version(
            created.name,
            BenchmarkVersionCreate(
                display_name="Preview Version",
                dataset_source_uri=f"s3://{bucket}/{object_key}",
            ),
        )
        version_id = version.id

        preview = await service.preview_benchmark_version_file(created.name, version.id)
        assert preview.preview_kind == "text"
        assert preview.file_name == f"{benchmark_name}.jsonl"
        assert preview.content is not None
        assert '"input": "hello"' in preview.content

        file_name, body, content_type = await service.download_benchmark_version_file(
            created.name,
            version.id,
        )
        assert file_name == f"{benchmark_name}.jsonl"
        assert body.decode("utf-8").strip().startswith('{"id": "sample-1"')
        assert content_type == "application/x-ndjson"
    finally:
        async with SessionLocal() as session:
            if version_id is not None:
                await session.execute(
                    delete(BenchmarkVersionRecord).where(
                        BenchmarkVersionRecord.version_id == version_id
                    )
                )
            await session.execute(
                delete(BenchmarkDefinitionRecord).where(
                    BenchmarkDefinitionRecord.name == benchmark_name
                )
            )
            if template_uuid is not None:
                await session.execute(
                    delete(EvalTemplate).where(EvalTemplate.id == template_uuid)
                )
            await session.commit()
        delete_object(bucket, object_key)
