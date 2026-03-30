from __future__ import annotations

import json

from nta_backend.eval_core.adapters.generic_adapter import (
    GenericBenchmark,
    _render_template,
    _resolve_selector,
)
from nta_backend.eval_core.config import EvalTaskConfig


def test_resolve_selector_dot_notation() -> None:
    data = {"a": {"b": {"c": "deep"}}}
    assert _resolve_selector(data, "a.b.c") == "deep"
    assert _resolve_selector(data, "a.b") == {"c": "deep"}
    assert _resolve_selector(data, "a.x") is None


def test_resolve_selector_array_index() -> None:
    data = ["zero", "one", "two"]
    assert _resolve_selector(data, "[0]") == "zero"
    assert _resolve_selector(data, "[2]") == "two"
    assert _resolve_selector(data, "[-1]") == "two"
    assert _resolve_selector(data, "[10]") is None


def test_resolve_selector_combined() -> None:
    data = {
        "messages": [
            {"role": "system", "content": "You are helpful."},
            {"role": "user", "content": "Hello!"},
        ]
    }
    assert _resolve_selector(data, "messages[-1].content") == "Hello!"
    assert _resolve_selector(data, "messages[0].role") == "system"


def test_resolve_selector_none_passthrough() -> None:
    assert _resolve_selector(None, "a.b") is None
    assert _resolve_selector({"a": None}, "a.b") is None


def test_generic_benchmark_with_selectors(tmp_path) -> None:
    dataset_path = tmp_path / "data.jsonl"
    record = {
        "id": "q1",
        "data": {
            "messages": [
                {"role": "user", "content": "What is 2+2?"}
            ],
            "answer": "4",
        },
    }
    dataset_path.write_text(json.dumps(record) + "\n", encoding="utf-8")

    benchmark = GenericBenchmark(
        task_config=EvalTaskConfig(benchmark="_generic", model="openai_compatible"),
        dataset_path=str(dataset_path),
        field_mapping={
            "input_field": "data",
            "input_selector": "messages[-1].content",
            "target_field": "data",
            "target_selector": "answer",
            "id_field": "id",
        },
    )
    dataset = benchmark.load_dataset()
    sample = dataset["default"][0]

    assert sample.id == "q1"
    assert sample.input == "What is 2+2?"
    assert sample.target == "4"


def test_generic_benchmark_without_selectors(tmp_path) -> None:
    dataset_path = tmp_path / "data.jsonl"
    record = {
        "id": "q1",
        "input": "What is 2+2?",
        "target": "4",
    }
    dataset_path.write_text(json.dumps(record) + "\n", encoding="utf-8")

    benchmark = GenericBenchmark(
        task_config=EvalTaskConfig(benchmark="_generic", model="openai_compatible"),
        dataset_path=str(dataset_path),
        field_mapping={},
    )
    dataset = benchmark.load_dataset()
    sample = dataset["default"][0]

    assert sample.id == "q1"
    assert sample.input == "What is 2+2?"
    assert sample.target == "4"


def test_generic_benchmark_selector_extracts_nested_list(tmp_path) -> None:
    dataset_path = tmp_path / "data.jsonl"
    record = {
        "id": "r1",
        "conversation": {
            "turns": [
                {"role": "system", "content": "Be helpful."},
                {"role": "user", "content": "Explain gravity."},
            ]
        },
        "evaluation": {
            "rubrics": ["Must mention Newton", "Must mention mass"],
        },
    }
    dataset_path.write_text(json.dumps(record) + "\n", encoding="utf-8")

    benchmark = GenericBenchmark(
        task_config=EvalTaskConfig(benchmark="_generic", model="openai_compatible"),
        dataset_path=str(dataset_path),
        field_mapping={
            "input_field": "conversation",
            "input_selector": "turns",
            "target_field": "evaluation",
            "target_selector": "rubrics",
        },
    )
    dataset = benchmark.load_dataset()
    sample = dataset["default"][0]

    # turns is a list of ChatMessage-like dicts -> parsed as ChatMessage list
    assert isinstance(sample.input, list)
    assert sample.input[0].role == "system"
    assert sample.input[1].content == "Explain gravity."
    assert sample.target == ["Must mention Newton", "Must mention mass"]


def test_render_template_basic() -> None:
    record = {"context": "背景内容", "question": "什么是路由聚合？"}
    result = _render_template("背景：{context}\n\n问题：{question}", record)
    assert result == "背景：背景内容\n\n问题：什么是路由聚合？"


def test_render_template_missing_key() -> None:
    record = {"question": "hello"}
    result = _render_template("{context}\n{question}", record)
    assert result == "\nhello"


def test_generic_benchmark_input_template(tmp_path) -> None:
    dataset_path = tmp_path / "data.jsonl"
    record = {
        "id": "net-001",
        "context": "云联网支持路由聚合。",
        "question": "支持哪些聚合类型？",
        "rubrics": ["明确指出两类聚合"],
    }
    dataset_path.write_text(json.dumps(record, ensure_ascii=False) + "\n", encoding="utf-8")

    benchmark = GenericBenchmark(
        task_config=EvalTaskConfig(benchmark="_generic", model="openai_compatible"),
        dataset_path=str(dataset_path),
        field_mapping={
            "input_template": "背景：{context}\n\n问题：{question}",
            "target_field": "rubrics",
        },
    )
    dataset = benchmark.load_dataset()
    sample = dataset["default"][0]

    assert sample.id == "net-001"
    assert "云联网支持路由聚合" in sample.input
    assert "支持哪些聚合类型" in sample.input
    assert sample.target == ["明确指出两类聚合"]
