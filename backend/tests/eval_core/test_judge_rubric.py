from __future__ import annotations

import json

from nta_backend.eval_core.api.dataset import Sample
from nta_backend.eval_core.api.model import ModelOutput
from nta_backend.eval_core.metrics.judge_rubric import JudgeRubricMetric


def test_judge_rubric_metric_parses_binary_score(monkeypatch) -> None:
    def fake_chat(**kwargs):
        return ModelOutput(
            sample_id=str(kwargs["sample_id"]),
            text=json.dumps(
                {
                    "rationale": "All rubric items are satisfied.",
                    "requirement_status": ["yes", "yes"],
                    "score": 1,
                }
            ),
        )

    monkeypatch.setattr(
        "nta_backend.eval_core.metrics.judge_rubric.call_openai_compatible_chat",
        fake_chat,
    )

    metric = JudgeRubricMetric(
        api_url="https://example.com/v1",
        api_key="secret",
        model_name="judge-model",
    )
    score = metric.score(
        Sample(
            id="sample-1",
            input="ignored",
            target=["Requirement 1", "Requirement 2"],
        ),
        output=ModelOutput(sample_id="sample-1", text="Student answer"),
    )

    assert score.metric == "judge_rubric"
    assert score.score == 1.0
    assert score.passed is True
    assert score.extra["requirement_status"] == ["yes", "yes"]


def test_judge_rubric_metric_scores_zero_on_failure(monkeypatch) -> None:
    def fake_chat(**kwargs):
        return ModelOutput(
            sample_id=str(kwargs["sample_id"]),
            text=json.dumps(
                {
                    "rationale": "Rubric item 2 not satisfied.",
                    "requirement_status": ["yes", "no"],
                    "score": 0,
                }
            ),
        )

    monkeypatch.setattr(
        "nta_backend.eval_core.metrics.judge_rubric.call_openai_compatible_chat",
        fake_chat,
    )

    metric = JudgeRubricMetric(
        api_url="https://example.com/v1",
        model_name="judge-model",
    )
    score = metric.score(
        Sample(id="sample-2", input="ignored", target=["Req 1", "Req 2"]),
        output=ModelOutput(sample_id="sample-2", text="Incomplete answer"),
    )

    assert score.metric == "judge_rubric"
    assert score.score == 0.0
    assert score.passed is False


def test_judge_rubric_metric_handles_model_error() -> None:
    metric = JudgeRubricMetric(
        api_url="https://example.com/v1",
        model_name="judge-model",
    )
    score = metric.score(
        Sample(id="sample-3", input="ignored", target=["Req"]),
        output=ModelOutput(sample_id="sample-3", text="", error="timeout"),
    )

    assert score.score == 0.0
    assert score.passed is False
    assert "Model generation failed" in score.reason


def test_judge_rubric_metric_handles_empty_output() -> None:
    metric = JudgeRubricMetric(
        api_url="https://example.com/v1",
        model_name="judge-model",
    )
    score = metric.score(
        Sample(id="sample-4", input="ignored", target=["Req"]),
        output=ModelOutput(sample_id="sample-4", text="   "),
    )

    assert score.score == 0.0
    assert "Empty model output" in score.reason
