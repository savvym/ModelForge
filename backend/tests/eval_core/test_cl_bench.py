from __future__ import annotations

import json

from nta_backend.eval_core.api.dataset import Sample
from nta_backend.eval_core.benchmarks.cl_bench import CLBenchBenchmark
from nta_backend.eval_core.config import EvalTaskConfig
from nta_backend.eval_core.metrics.cl_bench_judge import CLBenchJudgeMetric
from nta_backend.eval_core.models.openai_compatible import call_openai_compatible_chat


def test_cl_bench_loads_evalscope_style_jsonl(tmp_path) -> None:
    dataset_path = tmp_path / "cl-bench.jsonl"
    dataset_path.write_text(
        json.dumps(
            {
                "id": "task-1",
                "messages": [
                    {"role": "system", "content": "Follow the rule book."},
                    {"role": "user", "content": "Question body"},
                ],
                "rubrics": ["Must mention rule A", "Must mention rule B"],
                "metadata": {"task_id": "task-1", "context_category": "rule-system"},
            },
            ensure_ascii=False,
        )
        + "\n",
        encoding="utf-8",
    )

    benchmark = CLBenchBenchmark(
        task_config=EvalTaskConfig(benchmark="cl_bench", model="openai_compatible"),
        dataset_path=str(dataset_path),
    )
    dataset = benchmark.load_dataset()

    assert list(dataset) == ["default"]
    sample = dataset["default"][0]
    assert isinstance(sample, Sample)
    assert sample.id == "task-1"
    assert isinstance(sample.input, list)
    assert sample.target == ["Must mention rule A", "Must mention rule B"]


def test_cl_bench_judge_metric_parses_binary_score(monkeypatch) -> None:
    def fake_chat(**kwargs):
        from nta_backend.eval_core.api.model import ModelOutput

        return ModelOutput(
            sample_id=str(kwargs["sample_id"]),
            text=json.dumps(
                {
                    "Grading Rationale": "All rubric items are satisfied.",
                    "List of Requirement Satisfaction Status": ["yes", "yes"],
                    "Overall Score": 1,
                }
            ),
        )

    monkeypatch.setattr(
        "nta_backend.eval_core.metrics.cl_bench_judge.call_openai_compatible_chat",
        fake_chat,
    )

    metric = CLBenchJudgeMetric(
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
        output=type(
            "Output",
            (),
            {"error": None, "text": "Student answer"},
        )(),
    )

    assert score.metric == "cl_bench_acc"
    assert score.score == 1.0
    assert score.passed is True
    assert score.extra["requirement_status"] == ["yes", "yes"]


def test_openai_compatible_responses_api_parses_output_text(monkeypatch) -> None:
    class DummyResponse:
        def raise_for_status(self) -> None:
            return None

        def json(self) -> dict:
            return {
                "output": [
                    {
                        "type": "message",
                        "content": [
                            {"type": "output_text", "text": "Hello from responses."}
                        ],
                    }
                ],
                "usage": {
                    "input_tokens": 11,
                    "output_tokens": 7,
                    "total_tokens": 18,
                },
            }

    def fake_post(*args, **kwargs):
        return DummyResponse()

    monkeypatch.setattr("nta_backend.eval_core.models.openai_compatible.httpx.post", fake_post)

    output = call_openai_compatible_chat(
        sample_id="sample-1",
        api_url="https://example.com/v1",
        api_key="secret",
        model_name="test-model",
        api_format="responses",
        messages=[{"role": "user", "content": "Say hello"}],
        max_tokens=128,
    )

    assert output.error is None
    assert output.text == "Hello from responses."
    assert output.usage is not None
    assert output.usage.input_tokens == 11
    assert output.usage.output_tokens == 7
    assert output.usage.total_tokens == 18
