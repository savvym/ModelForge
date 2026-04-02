from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from nta_backend.core.db import SessionLocal
from nta_backend.evaluation.runtime.template_utils import collect_template_vars
from nta_backend.models.eval_template import EvalTemplate
from nta_backend.schemas.eval_template import (
    EvalTemplateCreate,
    EvalTemplateSummary,
    EvalTemplateUpdate,
)


# ---------------------------------------------------------------------------
# Serialization
# ---------------------------------------------------------------------------


def _to_summary(record: EvalTemplate) -> EvalTemplateSummary:
    return EvalTemplateSummary(
        id=record.id,
        name=record.name,
        version=record.version,
        prompt=record.prompt,
        vars=list(record.vars) if record.vars else [],
        template_type=_normalize_template_type(record.template_type, record.output_type),
        preset_id=record.preset_id,
        output_type=record.output_type,
        output_config=dict(record.output_config) if record.output_config else {},
        model=record.model,
        provider=record.provider,
        model_params=dict(record.model_params) if record.model_params else None,
        description=record.description,
        created_at=record.created_at,
    )


# ---------------------------------------------------------------------------
# Service
# ---------------------------------------------------------------------------


class EvalTemplateService:
    async def list_templates(self) -> list[EvalTemplateSummary]:
        """Return the latest version of each template name."""
        async with SessionLocal() as session:
            # Subquery: max version per name
            from sqlalchemy import func

            max_version = (
                select(
                    EvalTemplate.name,
                    func.max(EvalTemplate.version).label("max_version"),
                )
                .group_by(EvalTemplate.name)
                .subquery()
            )
            stmt = (
                select(EvalTemplate)
                .join(
                    max_version,
                    (EvalTemplate.name == max_version.c.name)
                    & (EvalTemplate.version == max_version.c.max_version),
                )
                .order_by(EvalTemplate.name)
            )
            result = await session.execute(stmt)
            return [_to_summary(row) for row in result.scalars().all()]

    async def get_template(
        self, name: str, version: int | None = None
    ) -> EvalTemplateSummary:
        """Get a template by name. Returns latest version if version is None."""
        async with SessionLocal() as session:
            record = await _load_template(session, name, version)
            if record is None:
                raise KeyError(name)
            return _to_summary(record)

    async def get_template_versions(self, name: str) -> list[EvalTemplateSummary]:
        """Get all versions of a template."""
        async with SessionLocal() as session:
            stmt = (
                select(EvalTemplate)
                .where(EvalTemplate.name == name)
                .order_by(EvalTemplate.version.desc())
            )
            result = await session.execute(stmt)
            records = result.scalars().all()
            if not records:
                raise KeyError(name)
            return [_to_summary(r) for r in records]

    async def create_template(
        self, payload: EvalTemplateCreate
    ) -> EvalTemplateSummary:
        """Create a new template (version 1)."""
        template_type = _normalize_template_type(payload.template_type, payload.output_type)
        _validate_template_config(
            template_type=template_type,
            output_type=payload.output_type,
            prompt=payload.prompt,
            output_config=payload.output_config,
        )
        async with SessionLocal() as session:
            # Check if name already exists
            existing = await _load_template(session, payload.name)
            if existing is not None:
                raise ValueError(f"Template '{payload.name}' already exists. Use update to create a new version.")

            record = EvalTemplate(
                name=payload.name.strip(),
                version=1,
                prompt=payload.prompt,
                vars=collect_template_vars(payload.prompt, payload.output_config),
                template_type=template_type,
                preset_id=payload.preset_id,
                output_type=payload.output_type,
                output_config=payload.output_config,
                model=payload.model,
                provider=payload.provider,
                model_params=payload.model_params,
                description=payload.description,
            )
            session.add(record)
            await session.commit()
            await session.refresh(record)
            return _to_summary(record)

    async def update_template(
        self, name: str, payload: EvalTemplateUpdate
    ) -> EvalTemplateSummary:
        """Create a new version of an existing template."""
        async with SessionLocal() as session:
            latest = await _load_template(session, name)
            if latest is None:
                raise KeyError(name)

            # Inherit unchanged fields from latest version
            new_prompt = payload.prompt if payload.prompt is not None else latest.prompt
            new_output_type = payload.output_type if payload.output_type is not None else latest.output_type
            new_template_type = (
                _normalize_template_type(payload.template_type, new_output_type)
                if payload.template_type is not None
                else latest.template_type
            )
            new_preset_id = payload.preset_id if payload.preset_id is not None else latest.preset_id
            new_output_config = payload.output_config if payload.output_config is not None else latest.output_config
            new_model = payload.model if payload.model is not None else latest.model
            new_provider = payload.provider if payload.provider is not None else latest.provider
            new_model_params = payload.model_params if payload.model_params is not None else latest.model_params
            new_description = payload.description if payload.description is not None else latest.description

            _validate_template_config(
                template_type=new_template_type,
                output_type=new_output_type,
                prompt=new_prompt,
                output_config=new_output_config,
            )

            record = EvalTemplate(
                project_id=latest.project_id,
                name=name,
                version=latest.version + 1,
                prompt=new_prompt,
                vars=collect_template_vars(new_prompt, new_output_config),
                template_type=new_template_type,
                preset_id=new_preset_id,
                output_type=new_output_type,
                output_config=new_output_config,
                model=new_model,
                provider=new_provider,
                model_params=new_model_params,
                description=new_description,
            )
            session.add(record)
            await session.commit()
            await session.refresh(record)
            return _to_summary(record)


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


async def _load_template(
    session: AsyncSession, name: str, version: int | None = None
) -> EvalTemplate | None:
    stmt = select(EvalTemplate).where(EvalTemplate.name == name)
    if version is not None:
        stmt = stmt.where(EvalTemplate.version == version)
    else:
        stmt = stmt.order_by(EvalTemplate.version.desc())
    stmt = stmt.limit(1)
    result = await session.execute(stmt)
    return result.scalar_one_or_none()


_VALID_OUTPUT_TYPES = {"numeric", "boolean", "categorical"}
_VALID_TEMPLATE_TYPES = {
    "llm_categorical",
    "llm_numeric",
    "rule_string_match",
    "rule_text_similarity",
    "manual_categorical",
}


def _normalize_template_type(template_type: str | None, output_type: str) -> str:
    if template_type:
        return template_type
    if output_type == "numeric":
        return "llm_numeric"
    if output_type in {"boolean", "categorical"}:
        return "llm_categorical"
    return "llm_numeric"


def _validate_output_type(output_type: str) -> None:
    if output_type not in _VALID_OUTPUT_TYPES:
        raise ValueError(
            f"Invalid output_type '{output_type}'. Must be one of: {', '.join(sorted(_VALID_OUTPUT_TYPES))}"
        )


def _extract_categories(output_config: dict) -> list[str]:
    categories = output_config.get("categories", [])
    if isinstance(categories, list):
        normalized = [str(category) for category in categories if str(category).strip()]
        if normalized:
            return normalized

    label_groups = output_config.get("label_groups", [])
    if not isinstance(label_groups, list):
        return []

    values: list[str] = []
    for group in label_groups:
        if not isinstance(group, dict):
            continue
        labels = group.get("labels", [])
        if not isinstance(labels, list):
            continue
        for label in labels:
            label_text = str(label).strip()
            if label_text:
                values.append(label_text)
    return list(dict.fromkeys(values))


def _read_numeric_range(output_config: dict) -> tuple[float | None, float | None, float | None]:
    numeric_range = output_config.get("numeric_range", {})
    if not isinstance(numeric_range, dict):
        numeric_range = {}

    score_min = output_config.get("score_min", numeric_range.get("min"))
    score_max = output_config.get("score_max", numeric_range.get("max"))
    pass_threshold = output_config.get("pass_threshold", numeric_range.get("pass_threshold"))

    try:
        min_value = float(score_min) if score_min is not None else None
        max_value = float(score_max) if score_max is not None else None
        threshold_value = float(pass_threshold) if pass_threshold is not None else None
    except (TypeError, ValueError) as exc:
        raise ValueError("Numeric template config contains invalid score range values.") from exc

    return min_value, max_value, threshold_value


def _validate_template_config(
    *,
    template_type: str,
    output_type: str,
    prompt: str,
    output_config: dict,
) -> None:
    _validate_output_type(output_type)

    if template_type not in _VALID_TEMPLATE_TYPES:
        raise ValueError(
            "Invalid template_type "
            f"'{template_type}'. Must be one of: {', '.join(sorted(_VALID_TEMPLATE_TYPES))}"
        )

    allowed_output_types = {
        "llm_categorical": {"boolean", "categorical"},
        "llm_numeric": {"numeric"},
        "rule_string_match": {"boolean"},
        "rule_text_similarity": {"boolean", "numeric"},
        "manual_categorical": {"categorical"},
    }
    if output_type not in allowed_output_types[template_type]:
        raise ValueError(
            f"template_type '{template_type}' does not support output_type '{output_type}'."
        )

    if template_type in {"llm_categorical", "llm_numeric"} and not prompt.strip():
        raise ValueError("LLM-based templates require a prompt.")

    if template_type in {"llm_categorical", "manual_categorical"}:
        if not _extract_categories(output_config):
            raise ValueError("Categorical templates require at least one configured label.")

    if template_type == "llm_numeric":
        score_min, score_max, pass_threshold = _read_numeric_range(output_config)
        if score_min is None or score_max is None or pass_threshold is None:
            raise ValueError("Numeric templates require score_min, score_max, and pass_threshold.")
        if score_max <= score_min:
            raise ValueError("Numeric templates require score_max to be greater than score_min.")
        if pass_threshold < score_min or pass_threshold > score_max:
            raise ValueError("Numeric templates require pass_threshold to be within the score range.")

    if template_type in {"rule_string_match", "rule_text_similarity"}:
        text_sources = output_config.get("text_sources", {})
        if not isinstance(text_sources, dict):
            raise ValueError("Rule-based templates require text_sources configuration.")
        left_template = text_sources.get("left_template")
        right_template = text_sources.get("right_template")
        if not isinstance(left_template, str) or not left_template.strip():
            raise ValueError("Rule-based templates require left_template.")
        if not isinstance(right_template, str) or not right_template.strip():
            raise ValueError("Rule-based templates require right_template.")

    if template_type == "rule_string_match":
        rule_config = output_config.get("rule_config", {})
        operator = rule_config.get("operator") if isinstance(rule_config, dict) else None
        if not isinstance(operator, str) or not operator.strip():
            raise ValueError("String match templates require a rule operator.")

    if template_type == "rule_text_similarity":
        rule_config = output_config.get("rule_config", {})
        metric = rule_config.get("metric") if isinstance(rule_config, dict) else None
        if not isinstance(metric, str) or not metric.strip():
            raise ValueError("Text similarity templates require a metric.")

        threshold = output_config.get("pass_threshold", output_config.get("similarity_threshold"))
        try:
            float(threshold)
        except (TypeError, ValueError) as exc:
            raise ValueError("Text similarity templates require a numeric threshold.") from exc
