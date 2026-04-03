from __future__ import annotations

from datetime import UTC, datetime
from mimetypes import guess_type
from pathlib import Path, PurePosixPath

import httpx
from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload
from sqlalchemy.orm.attributes import set_committed_value

from nta_backend.core.config import get_settings
from nta_backend.core.db import SessionLocal
from nta_backend.core.object_store import get_object_bytes, put_object_bytes
from nta_backend.core.project_context import resolve_active_project_id
from nta_backend.core.storage_layout import build_eval_spec_version_dataset_key
from nta_backend.models.evaluation_v2 import (
    EvalSpec,
    EvalSpecDatasetFile,
    EvalSpecVersion,
    EvalSuite,
    EvalSuiteItem,
    EvalSuiteVersion,
    EvaluationLeaderboard,
    EvaluationRun,
    EvaluationRunItem,
    JudgePolicy,
    TemplateSpec,
    TemplateSpecVersion,
)
from nta_backend.schemas.evaluation_v2 import (
    EvaluationCatalogResponse,
    EvalSpecCreate,
    EvalSpecDatasetFileCreate,
    EvalSpecSummary,
    EvalSpecUpdate,
    EvalSuiteCreate,
    EvalSuiteSummary,
    EvalSuiteUpdate,
    JudgePolicyCreate,
    JudgePolicySummary,
    TemplateSpecCreate,
    TemplateSpecSummary,
)


class CatalogConflictError(Exception):
    pass


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
            await session.flush()
            _replace_spec_version_dataset_files(
                version=version,
                dataset_files=_materialize_dataset_files(
                    payload.initial_version.dataset_files,
                    engine_benchmark_name=payload.initial_version.engine_benchmark_name,
                ),
                preserve_existing=False,
            )
            _refresh_spec_version_dataset_source_uri(version)
            await session.commit()

            rows = await _load_specs(session, project_id=project_id, name=spec.name)
            created = next((item for item in rows if item.id == spec.id), None)
            if created is None:
                raise ValueError("创建评测类型后无法重新加载记录。")
            return _serialize_spec(created)

    async def update_spec(self, name: str, payload: EvalSpecUpdate) -> EvalSpecSummary:
        async with SessionLocal() as session:
            project_id = await resolve_active_project_id(session)
            spec = await _get_spec_record(session, project_id=project_id, name=name)
            if spec is None:
                raise KeyError(name)

            version = next(
                (item for item in spec.versions if item.id == payload.version.version_id),
                None,
            )
            if version is None:
                raise ValueError("指定的评测版本不存在。")
            if payload.version.template_spec_version_id is not None:
                await _ensure_template_version_available(
                    session,
                    project_id=project_id,
                    template_spec_version_id=payload.version.template_spec_version_id,
                )
            if payload.version.default_judge_policy_id is not None:
                await _ensure_judge_policy_available(
                    session,
                    project_id=project_id,
                    judge_policy_id=payload.version.default_judge_policy_id,
                )

            version_name = payload.version.version.strip()
            version_display_name = payload.version.display_name.strip()
            if not payload.display_name.strip() or not version_name or not version_display_name:
                raise ValueError("评测类型显示名称、版本号和版本显示名称不能为空。")
            duplicate_version = await session.execute(
                select(EvalSpecVersion.id).where(
                    EvalSpecVersion.spec_id == spec.id,
                    EvalSpecVersion.version == version_name,
                    EvalSpecVersion.id != version.id,
                )
            )
            if duplicate_version.scalar_one_or_none() is not None:
                raise ValueError("同一评测类型下已存在相同版本号。")

            spec.display_name = payload.display_name.strip()
            spec.description = payload.description
            spec.capability_group = payload.capability_group
            spec.capability_category = payload.capability_category
            spec.tags_json = list(payload.tags_json)
            spec.input_schema_json = dict(payload.input_schema_json)
            spec.output_schema_json = dict(payload.output_schema_json)

            version.version = version_name
            version.display_name = version_display_name
            version.description = payload.version.description
            version.engine = payload.version.engine.strip()
            version.execution_mode = payload.version.execution_mode.strip()
            version.engine_benchmark_name = payload.version.engine_benchmark_name
            version.engine_config_json = dict(payload.version.engine_config_json)
            version.scoring_config_json = dict(payload.version.scoring_config_json)
            version.dataset_source_uri = payload.version.dataset_source_uri
            version.template_spec_version_id = payload.version.template_spec_version_id
            version.default_judge_policy_id = payload.version.default_judge_policy_id
            version.sample_count = payload.version.sample_count
            version.enabled = payload.version.enabled
            version.is_recommended = payload.version.is_recommended
            _replace_spec_version_dataset_files(
                version=version,
                dataset_files=_materialize_dataset_files(
                    payload.version.dataset_files,
                    engine_benchmark_name=payload.version.engine_benchmark_name,
                ),
            )
            _refresh_spec_version_dataset_source_uri(version)

            if version.is_recommended:
                for item in spec.versions:
                    if item.id != version.id:
                        item.is_recommended = False

            await session.commit()

            rows = await _load_specs(session, project_id=project_id, name=spec.name)
            updated = next((item for item in rows if item.id == spec.id), None)
            if updated is None:
                raise ValueError("更新评测类型后无法重新加载记录。")
            return _serialize_spec(updated)

    async def sync_spec_version_datasets(self, name: str, version_id) -> EvalSpecSummary:
        async with SessionLocal() as session:
            project_id = await resolve_active_project_id(session)
            spec = await _get_spec_record(session, project_id=project_id, name=name)
            if spec is None:
                raise KeyError(name)
            version = next((item for item in spec.versions if item.id == version_id), None)
            if version is None:
                raise ValueError("指定的评测版本不存在。")
            await _sync_spec_version_dataset_files(
                session,
                project_id=project_id,
                spec=spec,
                version=version,
            )
            await session.commit()
            rows = await _load_specs(session, project_id=project_id, name=spec.name)
            updated = next((item for item in rows if item.id == spec.id), None)
            if updated is None:
                raise ValueError("同步评测版本数据集后无法重新加载记录。")
            return _serialize_spec(updated)

    async def delete_spec(self, name: str) -> None:
        async with SessionLocal() as session:
            project_id = await resolve_active_project_id(session)
            spec = await _get_spec_record(session, project_id=project_id, name=name)
            if spec is None:
                raise KeyError(name)

            version_ids = [version.id for version in spec.versions]
            if version_ids:
                suite_item_ref = await session.execute(
                    select(EvalSuiteItem.id)
                    .where(EvalSuiteItem.spec_version_id.in_(version_ids))
                    .limit(1)
                )
                if suite_item_ref.scalar_one_or_none() is not None:
                    raise CatalogConflictError("当前评测类型仍被评测套件引用，无法删除。")

            run_ref = await session.execute(
                select(EvaluationRun.id)
                .where(
                    or_(
                        EvaluationRun.source_spec_id == spec.id,
                        EvaluationRun.source_spec_version_id.in_(version_ids),
                    )
                )
                .limit(1)
            )
            if run_ref.scalar_one_or_none() is not None:
                raise CatalogConflictError("当前评测类型已有评测任务记录，无法删除。")

            run_item_ref = await session.execute(
                select(EvaluationRunItem.id)
                .where(
                    or_(
                        EvaluationRunItem.spec_id == spec.id,
                        EvaluationRunItem.spec_version_id.in_(version_ids),
                    )
                )
                .limit(1)
            )
            if run_item_ref.scalar_one_or_none() is not None:
                raise CatalogConflictError("当前评测类型已有评测任务明细记录，无法删除。")

            leaderboard_ref = await session.execute(
                select(EvaluationLeaderboard.id)
                .where(
                    or_(
                        EvaluationLeaderboard.source_spec_id == spec.id,
                        EvaluationLeaderboard.source_spec_version_id.in_(version_ids),
                    )
                )
                .limit(1)
            )
            if leaderboard_ref.scalar_one_or_none() is not None:
                raise CatalogConflictError("当前评测类型仍被排行榜引用，无法删除。")

            await session.delete(spec)
            await session.commit()

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

    async def update_suite(self, name: str, payload: EvalSuiteUpdate) -> EvalSuiteSummary:
        async with SessionLocal() as session:
            project_id = await resolve_active_project_id(session)
            suite = await _get_suite_record(session, project_id=project_id, name=name)
            if suite is None:
                raise KeyError(name)

            version = next(
                (item for item in suite.versions if item.id == payload.version.version_id),
                None,
            )
            if version is None:
                raise ValueError("指定的套件版本不存在。")

            version_name = payload.version.version.strip()
            version_display_name = payload.version.display_name.strip()
            if not payload.display_name.strip() or not version_name or not version_display_name:
                raise ValueError("评测套件显示名称、版本号和版本显示名称不能为空。")
            duplicate_version = await session.execute(
                select(EvalSuiteVersion.id).where(
                    EvalSuiteVersion.suite_id == suite.id,
                    EvalSuiteVersion.version == version_name,
                    EvalSuiteVersion.id != version.id,
                )
            )
            if duplicate_version.scalar_one_or_none() is not None:
                raise ValueError("同一评测套件下已存在相同版本号。")

            suite.display_name = payload.display_name.strip()
            suite.description = payload.description
            suite.capability_group = payload.capability_group

            version.version = version_name
            version.display_name = version_display_name
            version.description = payload.version.description
            version.enabled = payload.version.enabled

            version.items.clear()
            await session.flush()

            seen_item_keys: set[str] = set()
            for index, item in enumerate(payload.version.items):
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
                version.items.append(
                    EvalSuiteItem(
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
            updated = next((item for item in rows if item.id == suite.id), None)
            if updated is None:
                raise ValueError("更新评测套件后无法重新加载记录。")
            return _serialize_suite(updated)

    async def delete_suite(self, name: str) -> None:
        async with SessionLocal() as session:
            project_id = await resolve_active_project_id(session)
            suite = await _get_suite_record(session, project_id=project_id, name=name)
            if suite is None:
                raise KeyError(name)

            version_ids = [version.id for version in suite.versions]
            run_ref = await session.execute(
                select(EvaluationRun.id)
                .where(
                    or_(
                        EvaluationRun.source_suite_id == suite.id,
                        EvaluationRun.source_suite_version_id.in_(version_ids),
                    )
                )
                .limit(1)
            )
            if run_ref.scalar_one_or_none() is not None:
                raise CatalogConflictError("当前评测套件已有评测任务记录，无法删除。")

            leaderboard_ref = await session.execute(
                select(EvaluationLeaderboard.id)
                .where(
                    or_(
                        EvaluationLeaderboard.source_suite_id == suite.id,
                        EvaluationLeaderboard.source_suite_version_id.in_(version_ids),
                    )
                )
                .limit(1)
            )
            if leaderboard_ref.scalar_one_or_none() is not None:
                raise CatalogConflictError("当前评测套件仍被排行榜引用，无法删除。")

            await session.delete(suite)
            await session.commit()


def _materialize_dataset_files(
    dataset_files: list[EvalSpecDatasetFileCreate],
    *,
    engine_benchmark_name: str | None,
) -> list[EvalSpecDatasetFileCreate]:
    normalized: list[EvalSpecDatasetFileCreate] = []
    seen_keys: set[str] = set()
    source_items = dataset_files
    if not source_items:
        benchmark_name = (engine_benchmark_name or "").strip()
        if benchmark_name:
            source_items = [
                EvalSpecDatasetFileCreate(
                    file_key="builtin-dataset",
                    display_name="内置数据集",
                    role="dataset",
                    position=0,
                    file_name=f"{benchmark_name}.builtin",
                    format="evalscope-builtin",
                    source_uri=f"evalscope://builtin/{benchmark_name}",
                    is_required=True,
                )
            ]
    for index, item in enumerate(source_items):
        file_key = item.file_key.strip()
        display_name = item.display_name.strip()
        if not file_key or not display_name:
            raise ValueError("数据集文件的 file_key 和 display_name 不能为空。")
        if file_key in seen_keys:
            raise ValueError(f"数据集文件 file_key 重复：{file_key}")
        seen_keys.add(file_key)
        source_uri = (item.source_uri or "").strip() or None
        file_name = (item.file_name or "").strip() or None
        if file_name is None and source_uri:
            file_name = PurePosixPath(source_uri.replace("\\", "/")).name or None
        normalized.append(
            EvalSpecDatasetFileCreate(
                file_key=file_key,
                display_name=display_name,
                role=(item.role or "dataset").strip() or "dataset",
                position=item.position if item.position >= 0 else index,
                file_name=file_name,
                format=(item.format or "").strip() or None,
                source_uri=source_uri,
                is_required=item.is_required,
            )
        )
    return normalized


def _replace_spec_version_dataset_files(
    *,
    version: EvalSpecVersion,
    dataset_files: list[EvalSpecDatasetFileCreate],
    preserve_existing: bool = True,
) -> None:
    if "dataset_files" not in version.__dict__:
        set_committed_value(version, "dataset_files", [])
    existing_items = list(version.dataset_files) if preserve_existing else []
    existing_by_key = {item.file_key: item for item in existing_items}
    desired_keys = {item.file_key for item in dataset_files}
    if preserve_existing:
        for existing in list(version.dataset_files):
            if existing.file_key not in desired_keys:
                version.dataset_files.remove(existing)
    for index, item in enumerate(dataset_files):
        preserved = existing_by_key.get(item.file_key)
        should_preserve_payload = (
            preserved is not None
            and (preserved.source_uri or None) == item.source_uri
            and (preserved.file_name or None) == item.file_name
        )
        status = _infer_dataset_file_status(item.source_uri)
        if should_preserve_payload and preserved is not None and preserved.status in {"available", "external"}:
            status = preserved.status
        if preserved is None:
            preserved = EvalSpecDatasetFile(file_key=item.file_key)
            version.dataset_files.append(preserved)
        preserved.display_name = item.display_name
        preserved.role = item.role
        preserved.position = item.position if item.position >= 0 else index
        preserved.file_name = item.file_name
        preserved.format = item.format
        preserved.source_uri = item.source_uri
        preserved.object_key = preserved.object_key if should_preserve_payload else None
        preserved.content_type = preserved.content_type if should_preserve_payload else None
        preserved.size_bytes = preserved.size_bytes if should_preserve_payload else None
        preserved.is_required = item.is_required
        preserved.status = status
        preserved.error_message = None
        preserved.last_synced_at = preserved.last_synced_at if should_preserve_payload else None


def _infer_dataset_file_status(source_uri: str | None) -> str:
    normalized = (source_uri or "").strip()
    if normalized.startswith("evalscope://"):
        return "external"
    if normalized:
        return "missing"
    return "missing"


def _refresh_spec_version_dataset_source_uri(version: EvalSpecVersion) -> None:
    preferred = next(
        (
            item
            for item in version.dataset_files
            if item.is_required and item.status in {"external", "available"}
        ),
        None,
    ) or next((item for item in version.dataset_files if item.status in {"external", "available"}), None)
    if preferred is None:
        version.dataset_source_uri = None
        return
    if preferred.status == "available" and preferred.object_key:
        bucket = get_settings().s3_bucket_dataset_raw
        version.dataset_source_uri = f"s3://{bucket}/{preferred.object_key}"
        return
    version.dataset_source_uri = preferred.source_uri


async def _sync_spec_version_dataset_files(
    session: AsyncSession,
    *,
    project_id,
    spec: EvalSpec,
    version: EvalSpecVersion,
) -> None:
    bucket = get_settings().s3_bucket_dataset_raw
    for dataset_file in version.dataset_files:
        if dataset_file.status == "external":
            dataset_file.error_message = None
            continue
        source_uri = (dataset_file.source_uri or "").strip()
        if not source_uri:
            dataset_file.status = "missing"
            dataset_file.error_message = "缺少 source_uri，无法拉取。"
            continue
        dataset_file.status = "syncing"
        dataset_file.error_message = None
        await session.flush()
        try:
            body, content_type, file_name = _read_dataset_file_source(source_uri)
            resolved_content_type = content_type or guess_type(file_name or dataset_file.file_name or "")[0]
            object_key = build_eval_spec_version_dataset_key(
                project_id,
                spec.name,
                version.version,
                file_name or dataset_file.file_name or f"{dataset_file.file_key}.bin",
            )
            put_object_bytes(
                bucket,
                object_key,
                body,
                content_type=resolved_content_type,
            )
            dataset_file.file_name = file_name or dataset_file.file_name
            dataset_file.object_key = object_key
            dataset_file.content_type = resolved_content_type
            dataset_file.size_bytes = len(body)
            dataset_file.status = "available"
            dataset_file.error_message = None
            dataset_file.last_synced_at = datetime.now(UTC)
        except Exception as exc:  # noqa: BLE001
            dataset_file.status = "failed"
            dataset_file.error_message = str(exc)
    _refresh_spec_version_dataset_source_uri(version)


def _read_dataset_file_source(source_uri: str) -> tuple[bytes, str | None, str | None]:
    normalized = source_uri.strip()
    if normalized.startswith("s3://"):
        bucket, object_key = _parse_s3_uri(normalized)
        payload = get_object_bytes(bucket, object_key)
        return payload.body, payload.content_type, PurePosixPath(object_key).name
    if normalized.startswith("file://"):
        local_path = Path(normalized.removeprefix("file://"))
        if not local_path.exists():
            raise FileNotFoundError(str(local_path))
        return local_path.read_bytes(), guess_type(local_path.name)[0], local_path.name
    if normalized.startswith("/"):
        local_path = Path(normalized)
        if not local_path.exists():
            raise FileNotFoundError(str(local_path))
        return local_path.read_bytes(), guess_type(local_path.name)[0], local_path.name
    if normalized.startswith("http://") or normalized.startswith("https://"):
        response = httpx.get(normalized, timeout=60.0, follow_redirects=True)
        response.raise_for_status()
        file_name = PurePosixPath(response.url.path).name or None
        return response.content, response.headers.get("content-type"), file_name
    raise ValueError("数据集文件 source_uri 目前仅支持 s3://、file://、绝对路径和 http(s)://。")


def _parse_s3_uri(value: str) -> tuple[str, str]:
    stripped = value.removeprefix("s3://")
    bucket, _, object_key = stripped.partition("/")
    if not bucket or not object_key:
        raise ValueError("s3:// URI 不合法。")
    return bucket, object_key


async def _load_specs(
    session: AsyncSession,
    *,
    project_id,
    name: str | None = None,
) -> list[EvalSpec]:
    query = (
        select(EvalSpec)
        .options(selectinload(EvalSpec.versions).selectinload(EvalSpecVersion.dataset_files))
        .where(or_(EvalSpec.project_id == project_id, EvalSpec.project_id.is_(None)))
        .order_by(EvalSpec.display_name.asc(), EvalSpec.name.asc())
    )
    if name:
        query = query.where(EvalSpec.name == name.strip())
    return (await session.execute(query)).scalars().all()


async def _get_spec_record(
    session: AsyncSession,
    *,
    project_id,
    name: str,
) -> EvalSpec | None:
    rows = await _load_specs(session, project_id=project_id, name=name)
    return rows[0] if rows else None


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


async def _get_suite_record(
    session: AsyncSession,
    *,
    project_id,
    name: str,
) -> EvalSuite | None:
    rows = await _load_suites(session, project_id=project_id, name=name)
    return rows[0] if rows else None


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
