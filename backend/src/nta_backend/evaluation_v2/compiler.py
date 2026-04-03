from __future__ import annotations

from dataclasses import dataclass
from typing import Any
from uuid import UUID

from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from nta_backend.models.evaluation_v2 import (
    EvalSpec,
    EvalSpecVersion,
    EvalSuite,
    EvalSuiteVersion,
    JudgePolicy,
    TemplateSpecVersion,
)
from nta_backend.models.modeling import Model, ModelProvider
from nta_backend.schemas.evaluation_v2 import (
    CompiledRunItemPlan,
    CompiledRunPlan,
    EvaluationRunCreate,
    ModelBindingSnapshot,
)


@dataclass(frozen=True)
class CompiledRunContext:
    plan: CompiledRunPlan
    source_spec_id: UUID | None = None
    source_spec_version_id: UUID | None = None
    source_suite_id: UUID | None = None
    source_suite_version_id: UUID | None = None
    judge_policy_id: UUID | None = None


async def compile_run_request(
    session: AsyncSession,
    *,
    project_id: UUID,
    payload: EvaluationRunCreate,
) -> CompiledRunContext:
    model_binding = await _resolve_model_binding(session, project_id=project_id, model_id=payload.model_id)
    judge_policy = await _resolve_judge_policy(
        session,
        project_id=project_id,
        judge_policy_id=payload.judge_policy_id,
    )

    if payload.target.kind == "spec":
        spec, spec_version = await _load_spec_version(
            session,
            project_id=project_id,
            spec_name=payload.target.name,
            version=payload.target.version,
        )
        item = await _build_item_plan(
            session,
            spec=spec,
            spec_version=spec_version,
            model_binding=model_binding,
            judge_policy=judge_policy,
            item_key=spec.name,
            display_name=spec.display_name,
            group_name=spec.capability_category,
        )
        plan = CompiledRunPlan(
            kind="spec",
            target_name=spec.name,
            target_version=spec_version.version,
            model_binding=model_binding,
            judge_policy_snapshot=_serialize_judge_policy(judge_policy),
            items=[item],
            overrides=payload.overrides,
        )
        return CompiledRunContext(
            plan=plan,
            source_spec_id=spec.id,
            source_spec_version_id=spec_version.id,
            judge_policy_id=judge_policy.id if judge_policy is not None else None,
        )

    suite, suite_version = await _load_suite_version(
        session,
        project_id=project_id,
        suite_name=payload.target.name,
        version=payload.target.version,
    )
    requested_keys = {item.strip() for item in payload.target.item_keys if item.strip()}
    item_plans: list[CompiledRunItemPlan] = []
    for suite_item in suite_version.items:
        if not suite_item.enabled:
            continue
        if requested_keys and suite_item.item_key not in requested_keys:
            continue
        spec_version = await session.get(EvalSpecVersion, suite_item.spec_version_id)
        if spec_version is None or not spec_version.enabled:
            raise ValueError(f"Suite item {suite_item.item_key} references an unavailable spec version.")
        spec = await session.get(EvalSpec, spec_version.spec_id)
        if spec is None:
            raise ValueError(f"Suite item {suite_item.item_key} references a missing spec.")
        item_plans.append(
            await _build_item_plan(
                session,
                spec=spec,
                spec_version=spec_version,
                model_binding=model_binding,
                judge_policy=judge_policy,
                item_key=suite_item.item_key,
                display_name=suite_item.display_name,
                group_name=suite_item.group_name,
                weight=suite_item.weight,
                overrides=suite_item.overrides_json,
            )
        )

    plan = CompiledRunPlan(
        kind="suite",
        target_name=suite.name,
        target_version=suite_version.version,
        model_binding=model_binding,
        judge_policy_snapshot=_serialize_judge_policy(judge_policy),
        items=item_plans,
        overrides=payload.overrides,
    )
    return CompiledRunContext(
        plan=plan,
        source_suite_id=suite.id,
        source_suite_version_id=suite_version.id,
        judge_policy_id=judge_policy.id if judge_policy is not None else None,
    )


async def _build_item_plan(
    session: AsyncSession,
    *,
    spec: EvalSpec,
    spec_version: EvalSpecVersion,
    model_binding: ModelBindingSnapshot,
    judge_policy: JudgePolicy | None,
    item_key: str,
    display_name: str,
    group_name: str | None = None,
    weight: float = 1.0,
    overrides: dict[str, Any] | None = None,
) -> CompiledRunItemPlan:
    template_snapshot = await _load_template_snapshot(
        session,
        template_version_id=spec_version.template_spec_version_id,
    )
    effective_engine_config = {
        **dict(spec_version.engine_config_json or {}),
        "engine_benchmark_name": spec_version.engine_benchmark_name,
        "dataset_source_uri": spec_version.dataset_source_uri,
        "scoring_config": dict(spec_version.scoring_config_json or {}),
        "overrides": dict(overrides or {}),
    }
    return CompiledRunItemPlan(
        item_key=item_key,
        display_name=display_name,
        group_name=group_name,
        weight=weight,
        engine=spec_version.engine,
        execution_mode=spec_version.execution_mode,
        spec_id=spec.id,
        spec_version_id=spec_version.id,
        spec_name=spec.name,
        spec_version=spec_version.version,
        expected_sample_count=spec_version.sample_count,
        engine_config=effective_engine_config,
        model_binding=model_binding,
        judge_policy_snapshot=_serialize_judge_policy(judge_policy),
        template_snapshot=template_snapshot,
    )


async def _resolve_model_binding(
    session: AsyncSession,
    *,
    project_id: UUID,
    model_id: UUID,
) -> ModelBindingSnapshot:
    row = await session.execute(
        select(Model).where(
            Model.id == model_id,
            or_(Model.project_id == project_id, Model.project_id.is_(None)),
        )
    )
    model = row.scalar_one_or_none()
    if model is None:
        raise ValueError("指定模型不存在。")
    if model.provider_id is None:
        raise ValueError(f"模型 {model.name} 未绑定 Provider。")
    provider = await session.get(ModelProvider, model.provider_id)
    if provider is None:
        raise ValueError(f"模型 {model.name} 绑定的 Provider 不存在。")
    if not provider.base_url.strip():
        raise ValueError(f"Provider {provider.name} 缺少 base_url。")
    return ModelBindingSnapshot(
        model_id=model.id,
        model_name=(model.model_code or model.name).strip(),
        display_name=model.name,
        api_url=provider.base_url.strip(),
        api_format=(model.api_format or provider.api_format or "chat-completions").strip(),
        api_key=provider.api_key,
        organization=provider.organization,
        headers={str(key): str(value) for key, value in (provider.headers_json or {}).items()},
        model_params={},
    )


async def _resolve_judge_policy(
    session: AsyncSession,
    *,
    project_id: UUID,
    judge_policy_id: UUID | None,
) -> JudgePolicy | None:
    if judge_policy_id is None:
        return None
    row = await session.execute(
        select(JudgePolicy).where(
            JudgePolicy.id == judge_policy_id,
            or_(JudgePolicy.project_id == project_id, JudgePolicy.project_id.is_(None)),
        )
    )
    policy = row.scalar_one_or_none()
    if policy is None:
        raise ValueError("指定 Judge Policy 不存在。")
    return policy


async def _load_spec_version(
    session: AsyncSession,
    *,
    project_id: UUID,
    spec_name: str,
    version: str,
) -> tuple[EvalSpec, EvalSpecVersion]:
    row = await session.execute(
        select(EvalSpec)
        .options(selectinload(EvalSpec.versions))
        .where(
            EvalSpec.name == spec_name.strip(),
            or_(EvalSpec.project_id == project_id, EvalSpec.project_id.is_(None)),
        )
    )
    spec = row.scalar_one_or_none()
    if spec is None:
        raise ValueError("指定评测类型不存在。")
    spec_version = next((item for item in spec.versions if item.version == version.strip()), None)
    if spec_version is None or not spec_version.enabled:
        raise ValueError("指定评测版本不可用。")
    return spec, spec_version


async def _load_suite_version(
    session: AsyncSession,
    *,
    project_id: UUID,
    suite_name: str,
    version: str,
) -> tuple[EvalSuite, EvalSuiteVersion]:
    row = await session.execute(
        select(EvalSuite)
        .options(selectinload(EvalSuite.versions).selectinload(EvalSuiteVersion.items))
        .where(
            EvalSuite.name == suite_name.strip(),
            or_(EvalSuite.project_id == project_id, EvalSuite.project_id.is_(None)),
        )
    )
    suite = row.scalar_one_or_none()
    if suite is None:
        raise ValueError("指定评测套件不存在。")
    suite_version = next((item for item in suite.versions if item.version == version.strip()), None)
    if suite_version is None or not suite_version.enabled:
        raise ValueError("指定评测套件版本不可用。")
    return suite, suite_version


def _serialize_judge_policy(policy: JudgePolicy | None) -> dict[str, Any] | None:
    if policy is None:
        return None
    return {
        "id": str(policy.id),
        "name": policy.name,
        "display_name": policy.display_name,
        "strategy": policy.strategy,
        "template_spec_version_id": (
            str(policy.template_spec_version_id) if policy.template_spec_version_id else None
        ),
        "model_selector": dict(policy.model_selector_json or {}),
        "execution_params": dict(policy.execution_params_json or {}),
        "parser_config": dict(policy.parser_config_json or {}),
        "retry_policy": dict(policy.retry_policy_json or {}),
    }


async def _load_template_snapshot(
    session: AsyncSession,
    *,
    template_version_id: UUID | None,
) -> dict[str, Any] | None:
    if template_version_id is None:
        return None
    template = await session.get(TemplateSpecVersion, template_version_id)
    if template is None:
        return None
    return {
        "id": str(template.id),
        "version": template.version,
        "prompt": template.prompt,
        "vars": list(template.vars_json or []),
        "output_schema": dict(template.output_schema_json or {}),
        "parser_config": dict(template.parser_config_json or {}),
    }
