from __future__ import annotations

import json

from nta_backend.eval_core.api.dataset import Sample
from nta_backend.eval_core.api.model import ModelOutput
from nta_backend.eval_core.metrics.judge_quality import JudgeQualityMetric


def test_judge_quality_metric_parses_score(monkeypatch) -> None:
    def fake_chat(**kwargs):
        return ModelOutput(
            sample_id=str(kwargs["sample_id"]),
            text=json.dumps({"score": 4, "reason": "Mostly correct with minor issues."}),
        )

    monkeypatch.setattr(
        "nta_backend.eval_core.metrics.judge_quality.call_openai_compatible_chat",
        fake_chat,
    )

    metric = JudgeQualityMetric(
        api_url="https://example.com/v1",
        api_key="secret",
        model_name="judge-model",
    )
    score = metric.score(
        Sample(id="sample-1", input="What is 2+2?"),
        output=ModelOutput(sample_id="sample-1", text="The answer is 4."),
    )

    assert score.metric == "judge_quality"
    assert score.score == 4 / 5  # normalized to 0-1
    assert score.passed is True  # score >= 3
    assert score.extra["raw_score"] == 4


def test_judge_quality_metric_low_score_not_passed(monkeypatch) -> None:
    def fake_chat(**kwargs):
        return ModelOutput(
            sample_id=str(kwargs["sample_id"]),
            text=json.dumps({"score": 2, "reason": "Mostly wrong."}),
        )

    monkeypatch.setattr(
        "nta_backend.eval_core.metrics.judge_quality.call_openai_compatible_chat",
        fake_chat,
    )

    metric = JudgeQualityMetric(
        api_url="https://example.com/v1",
        model_name="judge-model",
    )
    score = metric.score(
        Sample(id="sample-2", input="Explain quantum physics."),
        output=ModelOutput(sample_id="sample-2", text="It's about atoms."),
    )

    assert score.score == 2 / 5
    assert score.passed is False
    assert score.extra["raw_score"] == 2


def test_judge_quality_metric_clamps_out_of_range(monkeypatch) -> None:
    def fake_chat(**kwargs):
        return ModelOutput(
            sample_id=str(kwargs["sample_id"]),
            text=json.dumps({"score": 10, "reason": "Out of range."}),
        )

    monkeypatch.setattr(
        "nta_backend.eval_core.metrics.judge_quality.call_openai_compatible_chat",
        fake_chat,
    )

    metric = JudgeQualityMetric(
        api_url="https://example.com/v1",
        model_name="judge-model",
    )
    score = metric.score(
        Sample(id="sample-3", input="Test"),
        output=ModelOutput(sample_id="sample-3", text="Answer"),
    )

    assert score.score == 5 / 5  # clamped to max
    assert score.extra["raw_score"] == 5


def test_judge_quality_metric_handles_model_error() -> None:
    metric = JudgeQualityMetric(
        api_url="https://example.com/v1",
        model_name="judge-model",
    )
    score = metric.score(
        Sample(id="sample-4", input="Test"),
        output=ModelOutput(sample_id="sample-4", text="", error="timeout"),
    )

    assert score.score == 0.0
    assert score.passed is False


def test_judge_quality_metric_with_chat_messages(monkeypatch) -> None:
    from nta_backend.eval_core.api.dataset import ChatMessage

    def fake_chat(**kwargs):
        return ModelOutput(
            sample_id=str(kwargs["sample_id"]),
            text=json.dumps({"score": 5, "reason": "Perfect."}),
        )

    monkeypatch.setattr(
        "nta_backend.eval_core.metrics.judge_quality.call_openai_compatible_chat",
        fake_chat,
    )

    metric = JudgeQualityMetric(
        api_url="https://example.com/v1",
        model_name="judge-model",
    )
    score = metric.score(
        Sample(
            id="sample-5",
            input=[
                ChatMessage(role="system", content="You are helpful."),
                ChatMessage(role="user", content="Hello?"),
            ],
        ),
        output=ModelOutput(sample_id="sample-5", text="Hi there!"),
    )

    assert score.score == 1.0
    assert score.extra["raw_score"] == 5
