from __future__ import annotations

from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from nta_backend.core.db import SessionLocal
from nta_backend.core.project_context import resolve_active_project_id
from nta_backend.models.evaluation_v2 import (
    EvalSpec,
    EvalSpecVersion,
    EvalSuite,
    EvalSuiteItem,
    EvalSuiteVersion,
    JudgePolicy,
    TemplateSpec,
    TemplateSpecVersion,
)
from nta_backend.schemas.evaluation_v2 import (
    EvaluationCatalogResponse,
    EvalSpecCreate,
    EvalSpecSummary,
    EvalSuiteCreate,
    EvalSuiteSummary,
    JudgePolicyCreate,
    JudgePolicySummary,
    TemplateSpecCreate,
    TemplateSpecSummary,
)


def _serialize_spec(record: EvalSpec) -> EvalSpecSummary:
    return EvalSpecSummary.model_validate(record)


def _serialize_suite(record: EvalSuite) -> EvalSuiteSummary:
    return EvalSuiteSummary.model_validate(record)


def _serialize_template(record: TemplateSpec) -> TemplateSpecSummary:
    return TemplateSpecSummary.model_validate(record)


def _serialize_judge_policy(record: JudgePolicy) -> JudgePolicySummary:
    return JudgePolicySummary.model_validate(record)


class EvaluationCatalogV2Service:
    async def list_catalog(self) -> EvaluationCatalogResponse:
        async with SessionLocal() as session:
            project_id = await resolve_active_project_id(session)
            specs = await _load_specs(session, project_id=project_id)
            suites = await _load_suites(session, project_id=project_id)
            templates = await _load_templates(session, project_id=project_id)
            judge_policies = await _load_judge_policies(session, project_id=project_id)
            return EvaluationCatalogResponse(
                specs=[_serialize_spec(spec) for spec in specs],
                suites=[_serialize_suite(suite) for suite in suites],
                templates=[_serialize_template(template) for template in templates],
                judge_policies=[_serialize_judge_policy(policy) for policy in judge_policies],
            )

    async def get_spec(self, name: str) -> EvalSpecSummary:
        async with SessionLocal() as session:
            project_id = await resolve_active_project_id(session)
            rows = await _load_specs(session, project_id=project_id, name=name)
            if not rows:
                raise KeyError(name)
            return _serialize_spec(rows[0])

    async def get_suite(self, name: str) -> EvalSuiteSummary:
        async with SessionLocal() as session:
            project_id = await resolve_active_project_id(session)
            rows = await _load_suites(session, project_id=project_id, name=name)
            if not rows:
                raise KeyError(name)
            return _serialize_suite(rows[0])

    async def list_templates(self) -> list[TemplateSpecSummary]:
        async with SessionLocal() as session:
            project_id = await resolve_active_project_id(session)
            return [
                _serialize_template(record)
                for record in await _load_templates(session, project_id=project_id)
            ]

    async def list_judge_policies(self) -> list[JudgePolicySummary]:
        async with SessionLocal() as session:
            project_id = await resolve_active_project_id(session)
            return [
                _serialize_judge_policy(record)
                for record in await _load_judge_policies(session, project_id=project_id)
            ]

    async def create_template(self, payload: TemplateSpecCreate) -> TemplateSpecSummary:
        from nta_backend.models.evaluation_v2 import TemplateSpec, TemplateSpecVersion

        async with SessionLocal() as session:
            project_id = await resolve_active_project_id(session)
            record = TemplateSpec(
                project_id=project_id,
                name=payload.name.strip(),
                display_name=payload.display_name.strip(),
                description=payload.description,
                template_type=payload.template_type.strip(),
                status="active",
            )
            session.add(record)
            await session.flush()
            session.add(
                TemplateSpecVersion(
                    template_spec_id=record.id,
                    version=1,
                    prompt=payload.prompt,
                    vars_json=list(payload.vars_json),
                    output_schema_json=dict(payload.output_schema_json),
                    parser_config_json=dict(payload.parser_config_json),
                    is_active=True,
                )
            )
            await session.commit()
            rows = await _load_templates(session, project_id=project_id)
            created = next((item for item in rows if item.id == record.id), None)
            if created is None:
                raise ValueError("创建模板后无法重新加载记录。")
            return _serialize_template(created)

    async def create_spec(self, payload: EvalSpecCreate) -> EvalSpecSummary:
        async with SessionLocal() as session:
            project_id = await resolve_active_project_id(session)
            spec_name = payload.name.strip()
            display_name = payload.display_name.strip()
            version_name = payload.initial_version.version.strip()
            version_display_name = payload.initial_version.display_name.strip()
            if not spec_name or not display_name or not version_name or not version_display_name:
                raise ValueError("评测类型名称、显示名称、版本号和版本显示名称不能为空。")
            existing = await session.execute(
                select(EvalSpec.id).where(
                    or_(EvalSpec.project_id == project_id, EvalSpec.project_id.is_(None)),
                    EvalSpec.name == spec_name,
                )
            )
            if existing.scalar_one_or_none() is not None:
                raise ValueError("同名评测类型已存在。")
            if payload.initial_version.template_spec_version_id is not None:
                await _ensure_template_version_available(
                    session,
                    project_id=project_id,
                    template_spec_version_id=payload.initial_version.template_spec_version_id,
                )
            if payload.initial_version.default_judge_policy_id is not None:
                await _ensure_judge_policy_available(
                    session,
                    project_id=project_id,
                    judge_policy_id=payload.initial_version.default_judge_policy_id,
                )

            spec = EvalSpec(
                project_id=project_id,
                name=spec_name,
                display_name=display_name,
                description=payload.description,
                capability_group=payload.capability_group,
                capability_category=payload.capability_category,
                tags_json=list(payload.tags_json),
                input_schema_json=dict(payload.input_schema_json),
                output_schema_json=dict(payload.output_schema_json),
                status="active",
            )
            session.add(spec)
            await session.flush()
            version = EvalSpecVersion(
                spec_id=spec.id,
                version=version_name,
                display_name=version_display_name,
                description=payload.initial_version.description,
                engine=payload.initial_version.engine.strip(),
                execution_mode=payload.initial_version.execution_mode.strip(),
                engine_benchmark_name=payload.initial_version.engine_benchmark_name,
                engine_config_json=dict(payload.initial_version.engine_config_json),
                scoring_config_json=dict(payload.initial_version.scoring_config_json),
                dataset_source_uri=payload.initial_version.dataset_source_uri,
                template_spec_version_id=payload.initial_version.template_spec_version_id,
                default_judge_policy_id=payload.initial_version.default_judge_policy_id,
                sample_count=payload.initial_version.sample_count,
                enabled=payload.initial_version.enabled,
                is_recommended=payload.initial_version.is_recommended,
            )
            session.add(version)
            await session.commit()

            rows = await _load_specs(session, project_id=project_id, name=spec.name)
            created = next((item for item in rows if item.id == spec.id), None)
            if created is None:
                raise ValueError("创建评测类型后无法重新加载记录。")
            return _serialize_spec(created)

    async def create_judge_policy(self, payload: JudgePolicyCreate) -> JudgePolicySummary:
        async with SessionLocal() as session:
            project_id = await resolve_active_project_id(session)
            record = JudgePolicy(
                project_id=project_id,
                name=payload.name.strip(),
                display_name=payload.display_name.strip(),
                description=payload.description,
                strategy=payload.strategy.strip(),
                template_spec_version_id=payload.template_spec_version_id,
                model_selector_json=dict(payload.model_selector_json),
                execution_params_json=dict(payload.execution_params_json),
                parser_config_json=dict(payload.parser_config_json),
                retry_policy_json=dict(payload.retry_policy_json),
                status="active",
            )
            session.add(record)
            await session.commit()
            await session.refresh(record)
            return _serialize_judge_policy(record)

    async def create_suite(self, payload: EvalSuiteCreate) -> EvalSuiteSummary:
        async with SessionLocal() as session:
            project_id = await resolve_active_project_id(session)
            suite_name = payload.name.strip()
            display_name = payload.display_name.strip()
            version_name = payload.initial_version.version.strip()
            version_display_name = payload.initial_version.display_name.strip()
            if not suite_name or not display_name or not version_name or not version_display_name:
                raise ValueError("评测套件名称、显示名称、版本号和版本显示名称不能为空。")
            existing = await session.execute(
                select(EvalSuite.id).where(
                    or_(EvalSuite.project_id == project_id, EvalSuite.project_id.is_(None)),
                    EvalSuite.name == suite_name,
                )
            )
            if existing.scalar_one_or_none() is not None:
                raise ValueError("同名评测套件已存在。")

            suite = EvalSuite(
                project_id=project_id,
                name=suite_name,
                display_name=display_name,
                description=payload.description,
                capability_group=payload.capability_group,
                status="active",
            )
            session.add(suite)
            await session.flush()
            suite_version = EvalSuiteVersion(
                suite_id=suite.id,
                version=version_name,
                display_name=version_display_name,
                description=payload.initial_version.description,
                enabled=payload.initial_version.enabled,
            )
            session.add(suite_version)
            await session.flush()

            seen_item_keys: set[str] = set()
            for index, item in enumerate(payload.initial_version.items):
                item_key = item.item_key.strip()
                item_display_name = item.display_name.strip()
                if not item_key or not item_display_name:
                    raise ValueError("评测套件中的 item_key 和 display_name 不能为空。")
                if item_key in seen_item_keys:
                    raise ValueError(f"Suite item key 重复：{item_key}")
                seen_item_keys.add(item_key)
                if item.weight <= 0:
                    raise ValueError("评测套件中的权重必须大于 0。")
                await _ensure_spec_version_available(
                    session,
                    project_id=project_id,
                    spec_version_id=item.spec_version_id,
                )
                session.add(
                    EvalSuiteItem(
                        suite_version_id=suite_version.id,
                        item_key=item_key,
                        display_name=item_display_name,
                        spec_version_id=item.spec_version_id,
                        position=item.position if item.position >= 0 else index,
                        weight=item.weight,
                        group_name=item.group_name,
                        overrides_json=dict(item.overrides_json),
                        enabled=item.enabled,
                    )
                )
            await session.commit()

            rows = await _load_suites(session, project_id=project_id, name=suite.name)
            created = next((item for item in rows if item.id == suite.id), None)
            if created is None:
                raise ValueError("创建评测套件后无法重新加载记录。")
            return _serialize_suite(created)


async def _load_specs(
    session: AsyncSession,
    *,
    project_id,
    name: str | None = None,
) -> list[EvalSpec]:
    query = (
        select(EvalSpec)
        .options(selectinload(EvalSpec.versions))
        .where(or_(EvalSpec.project_id == project_id, EvalSpec.project_id.is_(None)))
        .order_by(EvalSpec.display_name.asc(), EvalSpec.name.asc())
    )
    if name:
        query = query.where(EvalSpec.name == name.strip())
    return (await session.execute(query)).scalars().all()


async def _load_suites(
    session: AsyncSession,
    *,
    project_id,
    name: str | None = None,
) -> list[EvalSuite]:
    from nta_backend.models.evaluation_v2 import EvalSuiteVersion

    query = (
        select(EvalSuite)
        .options(selectinload(EvalSuite.versions).selectinload(EvalSuiteVersion.items))
        .where(or_(EvalSuite.project_id == project_id, EvalSuite.project_id.is_(None)))
        .order_by(EvalSuite.display_name.asc(), EvalSuite.name.asc())
    )
    if name:
        query = query.where(EvalSuite.name == name.strip())
    return (await session.execute(query)).scalars().all()


async def _load_templates(
    session: AsyncSession,
    *,
    project_id,
) -> list[TemplateSpec]:
    query = (
        select(TemplateSpec)
        .options(selectinload(TemplateSpec.versions))
        .where(or_(TemplateSpec.project_id == project_id, TemplateSpec.project_id.is_(None)))
        .order_by(TemplateSpec.display_name.asc(), TemplateSpec.name.asc())
    )
    return (await session.execute(query)).scalars().all()


async def _load_judge_policies(
    session: AsyncSession,
    *,
    project_id,
) -> list[JudgePolicy]:
    query = (
        select(JudgePolicy)
        .where(or_(JudgePolicy.project_id == project_id, JudgePolicy.project_id.is_(None)))
        .order_by(JudgePolicy.display_name.asc(), JudgePolicy.name.asc())
    )
    return (await session.execute(query)).scalars().all()


async def _ensure_template_version_available(
    session: AsyncSession,
    *,
    project_id,
    template_spec_version_id,
) -> None:
    row = await session.execute(
        select(TemplateSpecVersion.id)
        .join(TemplateSpecVersion.template_spec)
        .where(
            TemplateSpecVersion.id == template_spec_version_id,
            or_(TemplateSpec.project_id == project_id, TemplateSpec.project_id.is_(None)),
        )
    )
    if row.scalar_one_or_none() is None:
        raise ValueError("指定模板版本不存在或不可用。")


async def _ensure_judge_policy_available(
    session: AsyncSession,
    *,
    project_id,
    judge_policy_id,
) -> None:
    row = await session.execute(
        select(JudgePolicy.id).where(
            JudgePolicy.id == judge_policy_id,
            or_(JudgePolicy.project_id == project_id, JudgePolicy.project_id.is_(None)),
        )
    )
    if row.scalar_one_or_none() is None:
        raise ValueError("指定 Judge Policy 不存在或不可用。")


async def _ensure_spec_version_available(
    session: AsyncSession,
    *,
    project_id,
    spec_version_id,
) -> None:
    row = await session.execute(
        select(EvalSpecVersion.id)
        .join(EvalSpecVersion.spec)
        .where(
            EvalSpecVersion.id == spec_version_id,
            EvalSpecVersion.enabled.is_(True),
            or_(EvalSpec.project_id == project_id, EvalSpec.project_id.is_(None)),
        )
    )
    if row.scalar_one_or_none() is None:
        raise ValueError("指定评测版本不存在或不可用。")
