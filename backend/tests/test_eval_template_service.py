from uuid import uuid4

from sqlalchemy import delete

from nta_backend.core.db import SessionLocal
from nta_backend.models.eval_template import EvalTemplate
from nta_backend.schemas.eval_template import EvalTemplateCreate, EvalTemplateUpdate
from nta_backend.services.eval_template_service import EvalTemplateService


def _categorical_output_config() -> dict:
    return {
        "label_groups": [
            {
                "key": "pass",
                "label": "Pass",
                "labels": ["Pass"],
                "score_policy": "pass",
            },
            {
                "key": "fail",
                "label": "Fail",
                "labels": ["Fail"],
                "score_policy": "fail",
            },
        ]
    }


async def test_update_template_can_clear_nullable_fields() -> None:
    service = EvalTemplateService()
    template_name = f"template_update_{uuid4().hex[:8]}"

    try:
        created = await service.create_template(
            EvalTemplateCreate(
                name=template_name,
                prompt="Question: {{input}}\nAnswer: {{output}}\nRubric: {{target}}",
                template_type="llm_categorical",
                preset_id="rubric-check",
                output_type="categorical",
                output_config=_categorical_output_config(),
                model="teacher-model",
                provider="teacher-provider",
                model_params={"temperature": 0},
                description="initial description",
            )
        )

        updated = await service.update_template(
            template_name,
            EvalTemplateUpdate(
                preset_id=None,
                model=None,
                provider=None,
                model_params=None,
                description=None,
            ),
        )

        assert updated.version == created.version + 1
        assert updated.preset_id is None
        assert updated.model is None
        assert updated.provider is None
        assert updated.model_params is None
        assert updated.description is None
    finally:
        async with SessionLocal() as session:
            await session.execute(delete(EvalTemplate).where(EvalTemplate.name == template_name))
            await session.commit()
