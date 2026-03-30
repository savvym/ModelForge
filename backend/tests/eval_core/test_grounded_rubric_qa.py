from __future__ import annotations

import json

from nta_backend.eval_core import benchmarks as _benchmarks  # noqa: F401
from nta_backend.eval_core.api.registry import get_benchmark
from nta_backend.eval_core.config import EvalTaskConfig


def test_grounded_rubric_qa_runtime_loads_clean_raw_jsonl(tmp_path) -> None:
    dataset_path = tmp_path / "grounded_rubric_qa.jsonl"
    dataset_path.write_text(
        json.dumps(
            {
                "id": "network-001",
                "context": "云联网支持路由聚合。",
                "question": "请说明支持哪些聚合类型？",
                "rubrics": [
                    "明确指出路由聚合支持两类。",
                ],
                "metadata": {"category": "基础概念理解"},
            },
            ensure_ascii=False,
        )
        + "\n",
        encoding="utf-8",
    )

    benchmark = get_benchmark(
        "nta_bench_network",
        task_config=EvalTaskConfig(
            benchmark="nta_bench_network",
            model="openai_compatible",
            dataset_path=str(dataset_path),
        ),
    )
    dataset = benchmark.load_dataset()
    sample = dataset["default"][0]

    assert sample.id == "network-001"
    assert isinstance(sample.input, list)
    assert sample.input[0].role == "system"
    assert "【背景信息】" in sample.input[1].content
    assert "请说明支持哪些聚合类型？" in sample.input[1].content
    assert sample.target == ["明确指出路由聚合支持两类。"]
    assert sample.metadata["category"] == "基础概念理解"


def test_grounded_rubric_qa_runtime_loads_legacy_messages_jsonl(tmp_path) -> None:
    dataset_path = tmp_path / "grounded_rubric_qa_legacy.jsonl"
    dataset_path.write_text(
        json.dumps(
            {
                "messages": [
                    {"role": "system", "content": "你是一位网络专家。"},
                    {"role": "user", "content": "请根据背景信息回答问题。"},
                ],
                "rubrics": [
                    "回答应准确。",
                    "回答应完整。",
                ],
                "metadata": {"task_id": "legacy-001"},
            },
            ensure_ascii=False,
        )
        + "\n",
        encoding="utf-8",
    )

    benchmark = get_benchmark(
        "nta_bench_network",
        task_config=EvalTaskConfig(
            benchmark="nta_bench_network",
            model="openai_compatible",
            dataset_path=str(dataset_path),
        ),
    )
    dataset = benchmark.load_dataset()
    sample = dataset["default"][0]

    assert sample.id == "legacy-001"
    assert isinstance(sample.input, list)
    assert sample.input[0].content == "你是一位网络专家。"
    assert sample.target == ["回答应准确。", "回答应完整。"]
