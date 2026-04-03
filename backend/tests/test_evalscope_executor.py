import json
import threading
from pathlib import Path

import pytest
from evalscope.api.model import ModelOutput, ModelUsage

from nta_backend.evaluation.executors import (
    EvalExecutionCancelledError,
    EvalExecutionRequest,
    EvalScopeExecutor,
    ExecutorModelConfig,
    ExecutorTemplateConfig,
)
from nta_backend.evaluation.executors.evalscope_executor import NTAOpenAICompatibleAPI


def _model_config(name: str) -> ExecutorModelConfig:
    return ExecutorModelConfig(
        model_name=name,
        display_name=name.upper(),
        api_url="https://example.com",
        api_key=None,
        api_format="chat-completions",
    )


def test_evalscope_executor_runs_accuracy_pipeline(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    dataset_path = tmp_path / "dataset.jsonl"
    output_dir = tmp_path / "out"
    dataset_path.write_text(
        json.dumps({"input": "Question?", "target": "A", "id": "sample-1"}) + "\n",
        encoding="utf-8",
    )

    def fake_generate(self, input, tools, tool_choice, config):
        del tools, tool_choice, config
        prompt = "\n".join(message.text for message in input)
        assert "Question?" in prompt
        return ModelOutput.from_content(model=self.model_name, content="A").model_copy(
            update={"usage": ModelUsage(total_tokens=11)}
        )

    monkeypatch.setattr(NTAOpenAICompatibleAPI, "generate", fake_generate)

    result = EvalScopeExecutor().execute(
        EvalExecutionRequest(
            benchmark_name="demo-benchmark",
            dataset_path=str(dataset_path),
            output_dir=output_dir,
            eval_method="accuracy",
            eval_model=_model_config("eval-model"),
            judge_model=_model_config("judge-model"),
        )
    )

    subset_report = result.report_payload["subset_reports"][0]
    assert subset_report["metrics"][0]["metric"] == "acc"
    assert subset_report["metrics"][0]["value"] == 1.0
    assert subset_report["sample_scores"][0]["sample_id"] == "sample-1"
    assert subset_report["sample_scores"][0]["passed"] is True
    assert (output_dir / "report.json").exists() is True


def test_evalscope_executor_runs_template_judge_pipeline(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    dataset_path = tmp_path / "dataset.jsonl"
    output_dir = tmp_path / "out"
    dataset_path.write_text(
        json.dumps({"question": "2 + 2 = ?", "answer": "4", "uid": "q-1"}) + "\n",
        encoding="utf-8",
    )

    def fake_generate(self, input, tools, tool_choice, config):
        del tools, tool_choice, config
        prompt = "\n".join(message.text for message in input)
        if "Return only valid JSON" in prompt:
            return ModelOutput.from_content(
                model=self.model_name,
                content='{"reasoning":"matches reference","score":"Pass"}',
            ).model_copy(update={"usage": ModelUsage(total_tokens=17)})
        return ModelOutput.from_content(
            model=self.model_name,
            content="The answer is 4.",
        ).model_copy(update={"usage": ModelUsage(total_tokens=9)})

    monkeypatch.setattr(NTAOpenAICompatibleAPI, "generate", fake_generate)

    result = EvalScopeExecutor().execute(
        EvalExecutionRequest(
            benchmark_name="template-benchmark",
            dataset_path=str(dataset_path),
            output_dir=output_dir,
            eval_method="judge-template",
            eval_model=_model_config("eval-model"),
            judge_model=_model_config("judge-model"),
            field_mapping={
                "input_field": "question",
                "target_field": "answer",
                "id_field": "uid",
            },
            template_config=ExecutorTemplateConfig(
                prompt="Question: {{input}}\nReference: {{target}}\nAnswer: {{output}}",
                vars=["input", "target", "output"],
                output_type="categorical",
                output_config={
                    "label_groups": [
                        {"key": "pass", "labels": ["Pass"], "score_policy": "pass"},
                        {"key": "fail", "labels": ["Fail"], "score_policy": "fail"},
                    ]
                },
            ),
        )
    )

    sample_score = result.report_payload["subset_reports"][0]["sample_scores"][0]
    assert sample_score["sample_id"] == "q-1"
    assert sample_score["metric"] == "judge_template"
    assert sample_score["passed"] is True
    assert sample_score["prediction_text"] == "The answer is 4."


def test_evalscope_executor_respects_cancellation(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    dataset_path = tmp_path / "dataset.jsonl"
    output_dir = tmp_path / "out"
    cancel_event = threading.Event()
    cancel_event.set()
    dataset_path.write_text(
        json.dumps({"input": "Question?", "target": "A", "id": "sample-1"}) + "\n",
        encoding="utf-8",
    )

    def fake_generate(self, input, tools, tool_choice, config):
        raise AssertionError("generate should not run when cancellation is already requested")

    monkeypatch.setattr(NTAOpenAICompatibleAPI, "generate", fake_generate)

    with pytest.raises(EvalExecutionCancelledError):
        EvalScopeExecutor().execute(
            EvalExecutionRequest(
                benchmark_name="cancelled-benchmark",
                dataset_path=str(dataset_path),
                output_dir=output_dir,
                eval_method="accuracy",
                eval_model=_model_config("eval-model"),
                judge_model=_model_config("judge-model"),
                cancellation_event=cancel_event,
            )
        )
