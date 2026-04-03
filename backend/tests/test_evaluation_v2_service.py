import json
import threading
from uuid import uuid4

import pytest
from sqlalchemy import delete, select

from nta_backend.core.db import SessionLocal
from nta_backend.core.project_context import resolve_active_project_id
from nta_backend.evaluation_v2.execution import CanonicalExecutionResult
from nta_backend.models.evaluation_v2 import EvalSpec, EvalSuite, EvaluationRun, EvaluationRunItem
from nta_backend.models.modeling import Model, ModelProvider
from nta_backend.schemas.evaluation_v2 import (
    EvalSpecCreate,
    EvalSpecVersionCreate,
    EvalSuiteCreate,
    EvalSuiteItemCreate,
    EvalSuiteVersionCreate,
    EvaluationRunCreate,
    EvaluationTargetRef,
)
from nta_backend.services.evaluation_catalog_v2_service import EvaluationCatalogV2Service
from nta_backend.services.evaluation_run_v2_service import (
    EvaluationRunV2Service,
    activity_execute_evaluation_run_item,
    aggregate_run_summary,
)

pytestmark = pytest.mark.asyncio(loop_scope="module")


async def _create_model_and_provider() -> tuple[object, object]:
    async with SessionLocal() as session:
        project_id = await resolve_active_project_id(session)
        provider = ModelProvider(
            project_id=project_id,
            name=f"pytest-provider-{uuid4().hex[:8]}",
            provider_type="openai-compatible",
            adapter="litellm",
            api_format="responses",
            base_url="https://example.com/v1",
            api_key="secret-token",
            organization="org-demo",
            headers_json={"X-Test-Header": "1"},
            status="active",
        )
        session.add(provider)
        await session.flush()
        model = Model(
            project_id=project_id,
            provider_id=provider.id,
            name=f"pytest-model-{uuid4().hex[:8]}",
            model_code="gpt-5.4",
            api_format="responses",
            status="active",
        )
        session.add(model)
        await session.commit()
        return provider.id, model.id


async def _cleanup_run_provider_model(
    *,
    run_id,
    model_id,
    provider_id,
) -> None:
    async with SessionLocal() as session:
        if run_id is not None:
            run = await session.get(EvaluationRun, run_id)
            if run is not None:
                await session.delete(run)
        if model_id is not None:
            model = await session.get(Model, model_id)
            if model is not None:
                await session.delete(model)
        if provider_id is not None:
            provider = await session.get(ModelProvider, provider_id)
            if provider is not None:
                await session.delete(provider)
        await session.commit()


async def test_evaluation_catalog_lists_seeded_baseline_suite() -> None:
    service = EvaluationCatalogV2Service()

    catalog = await service.list_catalog()

    spec_names = {item.name for item in catalog.specs}
    assert {"ceval", "mmlu", "arc", "gsm8k", "bbh", "hellaswag"} <= spec_names

    suite_names = {item.name for item in catalog.suites}
    assert "baseline-general" in suite_names

    suite = next(item for item in catalog.suites if item.name == "baseline-general")
    assert suite.versions
    assert suite.versions[0].items
    assert {item.item_key for item in suite.versions[0].items} == {
        "ceval",
        "mmlu",
        "arc",
        "gsm8k",
        "bbh",
        "hellaswag",
    }


async def test_create_suite_run_compiles_provider_binding(monkeypatch: pytest.MonkeyPatch) -> None:
    service = EvaluationRunV2Service()

    async def _fake_start_workflow(payload, workflow_id=None):
        assert payload.run_id
        return workflow_id or f"evaluation-run-{payload.run_id}"

    monkeypatch.setattr(
        "nta_backend.core.temporal.start_evaluation_run_workflow",
        _fake_start_workflow,
    )

    provider_id = None
    model_id = None
    run_id = None

    try:
        provider_id, model_id = await _create_model_and_provider()

        summary = await service.create_run(
            EvaluationRunCreate(
                target=EvaluationTargetRef(kind="suite", name="baseline-general", version="v1"),
                model_id=model_id,
            )
        )
        run_id = summary.id
        assert summary.kind == "suite"
        assert summary.status == "queued"

        detail = await service.get_run(str(run_id))
        assert detail.kind == "suite"
        assert len(detail.items) == 6
        assert {item.group_name for item in detail.items} == {"学科", "数学", "推理"}

        model_binding = detail.execution_plan_json["model_binding"]
        assert model_binding["api_format"] == "responses"
        assert model_binding["organization"] == "org-demo"
        assert model_binding["headers"] == {"X-Test-Header": "1"}
    finally:
        await _cleanup_run_provider_model(run_id=run_id, model_id=model_id, provider_id=provider_id)


async def test_create_eval_spec_and_suite() -> None:
    catalog_service = EvaluationCatalogV2Service()
    created_spec_name = f"pytest_spec_{uuid4().hex[:8]}"
    created_suite_name = f"pytest_suite_{uuid4().hex[:8]}"
    created_spec_id = None
    created_suite_id = None

    try:
        spec = await catalog_service.create_spec(
            EvalSpecCreate(
                name=created_spec_name,
                display_name="Pytest Spec",
                description="spec for pytest",
                capability_group="综合",
                capability_category="推理",
                tags_json=["pytest", "evalscope"],
                initial_version=EvalSpecVersionCreate(
                    version="builtin-v1",
                    display_name="Builtin V1",
                    engine="evalscope",
                    execution_mode="builtin",
                    engine_benchmark_name="bbh",
                    sample_count=42,
                ),
            )
        )
        created_spec_id = spec.id
        assert spec.name == created_spec_name
        assert spec.versions[0].engine == "evalscope"

        suite = await catalog_service.create_suite(
            EvalSuiteCreate(
                name=created_suite_name,
                display_name="Pytest Suite",
                description="suite for pytest",
                capability_group="基线评测",
                initial_version=EvalSuiteVersionCreate(
                    version="v1",
                    display_name="Version 1",
                    items=[
                        EvalSuiteItemCreate(
                            item_key="pytest-item",
                            display_name="Pytest Item",
                            spec_version_id=spec.versions[0].id,
                            position=0,
                            weight=1.5,
                            group_name="推理",
                        )
                    ],
                ),
            )
        )
        created_suite_id = suite.id
        assert suite.name == created_suite_name
        assert suite.versions[0].items[0].spec_version_id == spec.versions[0].id
    finally:
        async with SessionLocal() as session:
            if created_suite_id is not None:
                await session.execute(
                    delete(EvalSuite).where(EvalSuite.id == created_suite_id)
                )
            if created_spec_id is not None:
                await session.execute(
                    delete(EvalSpec).where(EvalSpec.id == created_spec_id)
                )
            await session.commit()


async def test_spec_run_item_execution_persists_canonical_summary(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    service = EvaluationRunV2Service()

    async def _fake_start_workflow(payload, workflow_id=None):
        return workflow_id or f"evaluation-run-{payload.run_id}"

    class _FakeAdapter:
        def execute(self, *, item_plan, context):
            context.output_dir.mkdir(parents=True, exist_ok=True)
            if context.progress_callback is not None:
                context.progress_callback(1, 1)
            canonical_report = {
                "engine": "fake",
                "engine_mode": "builtin",
                "spec": {"name": item_plan.spec_name, "version": item_plan.spec_version},
                "metrics": [
                    {
                        "metric_name": "score",
                        "metric_value": 0.75,
                        "metric_scope": "overall",
                    }
                ],
                "samples": [
                    {
                        "sample_id": "sample-1",
                        "score": 1.0,
                        "passed": True,
                    }
                ],
            }
            (context.output_dir / "canonical-report.json").write_text(
                json.dumps(canonical_report, ensure_ascii=False),
                encoding="utf-8",
            )
            return CanonicalExecutionResult(report_payload=canonical_report)

    monkeypatch.setattr(
        "nta_backend.core.temporal.start_evaluation_run_workflow",
        _fake_start_workflow,
    )
    monkeypatch.setattr(
        "nta_backend.services.evaluation_run_v2_service.get_engine_adapter",
        lambda **_: _FakeAdapter(),
    )

    provider_id = None
    model_id = None
    run_id = None
    try:
        provider_id, model_id = await _create_model_and_provider()
        summary = await service.create_run(
            EvaluationRunCreate(
                target=EvaluationTargetRef(kind="spec", name="gsm8k", version="builtin-v1"),
                model_id=model_id,
            )
        )
        run_id = summary.id

        async with SessionLocal() as session:
            run = await session.get(EvaluationRun, run_id)
            item = (
                await session.execute(
                    select(EvaluationRunItem).where(EvaluationRunItem.run_id == run_id)
                )
            ).scalar_one()
            assert run is not None

        result = await activity_execute_evaluation_run_item(
            run_id=str(run_id),
            item_id=str(item.id),
            cancel_event=threading.Event(),
        )
        assert result["status"] == "completed"

        await aggregate_run_summary(run_id=str(run_id))
        detail = await service.get_run(str(run_id))
        assert detail.status == "completed"
        assert detail.summary_report_uri is not None
        assert len(detail.items) == 1
        assert detail.items[0].status == "completed"
        assert detail.items[0].report_uri is not None
        assert detail.metrics
        assert detail.metrics[0].metric_value == pytest.approx(0.75)
    finally:
        await _cleanup_run_provider_model(run_id=run_id, model_id=model_id, provider_id=provider_id)


async def test_cancelled_run_short_circuits_item_execution(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    service = EvaluationRunV2Service()

    async def _fake_start_workflow(payload, workflow_id=None):
        return workflow_id or f"evaluation-run-{payload.run_id}"

    adapter_called = False

    class _FakeAdapter:
        def execute(self, *, item_plan, context):
            nonlocal adapter_called
            adapter_called = True
            raise AssertionError("Cancelled run should not invoke engine adapter.")

    monkeypatch.setattr(
        "nta_backend.core.temporal.start_evaluation_run_workflow",
        _fake_start_workflow,
    )
    monkeypatch.setattr(
        "nta_backend.services.evaluation_run_v2_service.get_engine_adapter",
        lambda **_: _FakeAdapter(),
    )

    provider_id = None
    model_id = None
    run_id = None
    try:
        provider_id, model_id = await _create_model_and_provider()
        summary = await service.create_run(
            EvaluationRunCreate(
                target=EvaluationTargetRef(kind="spec", name="arc", version="builtin-v1"),
                model_id=model_id,
            )
        )
        run_id = summary.id
        await service.cancel_run(str(run_id))

        async with SessionLocal() as session:
            item = (
                await session.execute(
                    select(EvaluationRunItem).where(EvaluationRunItem.run_id == run_id)
                )
            ).scalar_one()

        result = await activity_execute_evaluation_run_item(
            run_id=str(run_id),
            item_id=str(item.id),
            cancel_event=threading.Event(),
        )
        assert result["status"] == "cancelled"
        assert adapter_called is False

        await aggregate_run_summary(run_id=str(run_id))
        detail = await service.get_run(str(run_id))
        assert detail.status == "cancelled"
        assert detail.items[0].status == "cancelled"
    finally:
        await _cleanup_run_provider_model(run_id=run_id, model_id=model_id, provider_id=provider_id)


async def test_cancel_run_finalizes_when_temporal_workflow_is_missing(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    service = EvaluationRunV2Service()

    async def _fake_start_workflow(payload, workflow_id=None):
        return workflow_id or f"evaluation-run-{payload.run_id}"

    async def _fake_cancel_workflow_execution(workflow_id: str) -> None:
        raise RuntimeError(f"workflow not found for ID: {workflow_id}")

    monkeypatch.setattr(
        "nta_backend.core.temporal.start_evaluation_run_workflow",
        _fake_start_workflow,
    )
    monkeypatch.setattr(
        "nta_backend.core.temporal.cancel_workflow_execution",
        _fake_cancel_workflow_execution,
    )

    provider_id = None
    model_id = None
    run_id = None
    try:
        provider_id, model_id = await _create_model_and_provider()
        summary = await service.create_run(
            EvaluationRunCreate(
                target=EvaluationTargetRef(kind="spec", name="arc", version="builtin-v1"),
                model_id=model_id,
            )
        )
        run_id = summary.id

        response = await service.cancel_run(str(run_id))
        assert response.status == "cancelled"

        detail = await service.get_run(str(run_id))
        assert detail.status == "cancelled"
        assert len(detail.items) == 1
        assert detail.items[0].status == "cancelled"
    finally:
        await _cleanup_run_provider_model(run_id=run_id, model_id=model_id, provider_id=provider_id)
