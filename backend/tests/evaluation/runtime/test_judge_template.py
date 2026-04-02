from __future__ import annotations

import json

from nta_backend.evaluation.runtime.api.dataset import Sample
from nta_backend.evaluation.runtime.api.model import ModelOutput
from nta_backend.evaluation.runtime.metrics.judge_template import JudgeTemplateMetric
from nta_backend.evaluation.runtime.template_utils import (
    build_output_instruction,
    collect_template_vars,
    compile_template,
    extract_template_vars,
)

# ---------------------------------------------------------------------------
# Template utility tests
# ---------------------------------------------------------------------------


def test_extract_template_vars() -> None:
    prompt = "Evaluate {{output}} against {{target}} for {{input}}"
    assert extract_template_vars(prompt) == ["output", "target", "input"]


def test_extract_template_vars_deduplicates() -> None:
    prompt = "{{input}} and again {{input}} plus {{output}}"
    assert extract_template_vars(prompt) == ["input", "output"]


def test_compile_template() -> None:
    prompt = "Question: {{input}}\nAnswer: {{output}}"
    result = compile_template(prompt, {"input": "What is 2+2?", "output": "4"})
    assert result == "Question: What is 2+2?\nAnswer: 4"


def test_compile_template_missing_var() -> None:
    prompt = "{{input}} and {{missing}}"
    result = compile_template(prompt, {"input": "hello"})
    assert result == "hello and "


def test_collect_template_vars_reads_rule_templates() -> None:
    vars_ = collect_template_vars(
        "",
        {
            "text_sources": {
                "left_template": "{{output}}",
                "right_template": "{{target}} and {{metadata_field}}",
            }
        },
    )
    assert vars_ == ["output", "target", "metadata_field"]


def test_build_output_instruction_numeric() -> None:
    instruction = build_output_instruction("numeric", {"score_min": 1, "score_max": 10})
    assert "1-10" in instruction
    assert "JSON" in instruction


def test_build_output_instruction_boolean() -> None:
    instruction = build_output_instruction("boolean", {})
    assert "true or false" in instruction


def test_build_output_instruction_categorical() -> None:
    instruction = build_output_instruction(
        "categorical", {"categories": ["good", "bad", "neutral"]}
    )
    assert '"good"' in instruction
    assert '"bad"' in instruction


def test_build_output_instruction_uses_label_groups_for_categorical() -> None:
    instruction = build_output_instruction(
        "categorical",
        {
            "label_groups": [
                {"key": "pass", "labels": ["Pass", "Relevant"]},
                {"key": "fail", "labels": ["Fail"]},
            ]
        },
    )
    assert '"Pass"' in instruction
    assert '"Relevant"' in instruction
    assert '"Fail"' in instruction


# ---------------------------------------------------------------------------
# JudgeTemplateMetric tests
# ---------------------------------------------------------------------------


def _make_metric(output_type: str, output_config: dict, fake_response: dict, monkeypatch):
    def fake_chat(**kwargs):
        return ModelOutput(
            sample_id=str(kwargs["sample_id"]),
            text=json.dumps(fake_response),
        )

    monkeypatch.setattr(
        "nta_backend.evaluation.runtime.metrics.judge_template.call_openai_compatible_chat",
        fake_chat,
    )

    def compiled_prompt_fn(sample, output):
        return f"Evaluate: {output.text}"

    return JudgeTemplateMetric(
        api_url="https://example.com/v1",
        model_name="judge-model",
        compiled_prompt_fn=compiled_prompt_fn,
        output_type=output_type,
        output_config=output_config,
    )


def test_numeric_scoring(monkeypatch) -> None:
    metric = _make_metric(
        "numeric",
        {"score_min": 1, "score_max": 5, "pass_threshold": 3},
        {"reasoning": "Good answer.", "score": 4},
        monkeypatch,
    )
    score = metric.score(
        Sample(id="s1", input="Q"),
        ModelOutput(sample_id="s1", text="A"),
    )
    assert score.metric == "judge_template"
    assert score.score == (4 - 1) / (5 - 1)  # 0.75
    assert score.passed is True
    assert score.extra["raw_score"] == 4


def test_numeric_below_threshold(monkeypatch) -> None:
    metric = _make_metric(
        "numeric",
        {"score_min": 1, "score_max": 5, "pass_threshold": 3},
        {"reasoning": "Poor.", "score": 2},
        monkeypatch,
    )
    score = metric.score(
        Sample(id="s1", input="Q"),
        ModelOutput(sample_id="s1", text="A"),
    )
    assert score.score == (2 - 1) / (5 - 1)  # 0.25
    assert score.passed is False


def test_boolean_true(monkeypatch) -> None:
    metric = _make_metric(
        "boolean", {},
        {"reasoning": "All correct.", "score": True},
        monkeypatch,
    )
    score = metric.score(
        Sample(id="s1", input="Q"),
        ModelOutput(sample_id="s1", text="A"),
    )
    assert score.score == 1.0
    assert score.passed is True


def test_boolean_false(monkeypatch) -> None:
    metric = _make_metric(
        "boolean", {},
        {"reasoning": "Wrong.", "score": False},
        monkeypatch,
    )
    score = metric.score(
        Sample(id="s1", input="Q"),
        ModelOutput(sample_id="s1", text="A"),
    )
    assert score.score == 0.0
    assert score.passed is False


def test_categorical_scoring(monkeypatch) -> None:
    metric = _make_metric(
        "categorical",
        {"categories": ["wrong", "partial", "correct"]},
        {"reasoning": "Mostly right.", "score": "correct"},
        monkeypatch,
    )
    score = metric.score(
        Sample(id="s1", input="Q"),
        ModelOutput(sample_id="s1", text="A"),
    )
    assert score.score == 1.0  # index 2 / (3-1) = 1.0
    assert score.extra["category"] == "correct"


def test_categorical_partial(monkeypatch) -> None:
    metric = _make_metric(
        "categorical",
        {"categories": ["wrong", "partial", "correct"]},
        {"reasoning": "Some issues.", "score": "partial"},
        monkeypatch,
    )
    score = metric.score(
        Sample(id="s1", input="Q"),
        ModelOutput(sample_id="s1", text="A"),
    )
    assert score.score == 0.5  # index 1 / (3-1) = 0.5


def test_categorical_label_groups_use_pass_fail_policy(monkeypatch) -> None:
    metric = _make_metric(
        "categorical",
        {
            "label_groups": [
                {"key": "pass", "score_policy": "pass", "labels": ["Relevant"]},
                {"key": "fail", "score_policy": "fail", "labels": ["Irrelevant"]},
            ]
        },
        {"reasoning": "Off topic.", "score": "Irrelevant"},
        monkeypatch,
    )
    score = metric.score(
        Sample(id="s1", input="Q"),
        ModelOutput(sample_id="s1", text="A"),
    )
    assert score.score == 0.0
    assert score.passed is False
    assert score.extra["label_group"] == "fail"


def test_model_error_returns_zero() -> None:
    metric = JudgeTemplateMetric(
        api_url="https://example.com/v1",
        model_name="judge-model",
        compiled_prompt_fn=lambda s, o: "test",
        output_type="numeric",
    )
    score = metric.score(
        Sample(id="s1", input="Q"),
        ModelOutput(sample_id="s1", text="", error="timeout"),
    )
    assert score.score == 0.0
    assert score.passed is False
