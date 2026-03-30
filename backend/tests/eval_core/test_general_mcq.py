from __future__ import annotations

import json
import zipfile

from nta_backend.eval_core import benchmarks as _benchmarks  # noqa: F401
from nta_backend.eval_core import metrics as _metrics  # noqa: F401
from nta_backend.eval_core.api.dataset import Sample
from nta_backend.eval_core.api.model import ModelOutput
from nta_backend.eval_core.api.registry import get_benchmark, get_metric
from nta_backend.eval_core.config import EvalTaskConfig

try:
    import pyarrow as pa
    import pyarrow.parquet as pq
except ModuleNotFoundError:  # pragma: no cover - dependency is installed in app env
    pa = None
    pq = None


def test_mcq_accuracy_metric_extracts_answer_letters() -> None:
    metric = get_metric("acc")

    sample = Sample(
        id="s1",
        input="Question",
        choices=["first", "second", "third", "fourth"],
        target="B",
    )

    score = metric.score(sample, ModelOutput(sample_id="s1", text="ANSWER: B"))
    assert score.score == 1.0
    assert score.extra["predicted_answer"] == "B"

    chinese_score = metric.score(sample, ModelOutput(sample_id="s1", text="答案：B"))
    assert chinese_score.score == 1.0

    text_fallback = metric.score(
        sample,
        ModelOutput(sample_id="s1", text="The correct option is second."),
    )
    assert text_fallback.score == 1.0


def test_mmlu_runtime_loads_standardized_mcq_jsonl(tmp_path) -> None:
    dataset_path = tmp_path / "mmlu.jsonl"
    dataset_path.write_text(
        json.dumps(
            {
                "input": [
                    {
                        "id": "abc",
                        "content": (
                            "Answer the following multiple choice question. "
                            "ANSWER: [LETTER]"
                        ),
                    }
                ],
                "choices": ["0", "4", "2", "6"],
                "target": "B",
                "subset_key": "abstract_algebra",
                "metadata": {"subject": "abstract_algebra"},
            },
            ensure_ascii=False,
        )
        + "\n",
        encoding="utf-8",
    )

    benchmark = get_benchmark(
        "mmlu",
        task_config=EvalTaskConfig(
            benchmark="mmlu",
            model="openai_compatible",
            dataset_path=str(dataset_path),
        ),
    )
    dataset = benchmark.load_dataset()

    assert list(dataset.keys()) == ["default"]
    sample = dataset["default"][0]
    assert sample.input.startswith("Answer the following multiple choice question")
    assert sample.choices == ["0", "4", "2", "6"]
    assert sample.target == "B"
    assert sample.metadata["subject"] == "abstract_algebra"


def test_mmlu_runtime_loads_raw_parquet(tmp_path) -> None:
    if pa is None or pq is None:
        return

    dataset_path = tmp_path / "test.parquet"
    table = pa.table(
        {
            "question": ["2 + 2 = ?"],
            "subject": ["abstract_algebra"],
            "choices": [["1", "4", "3", "5"]],
            "answer": [1],
        }
    )
    pq.write_table(table, dataset_path)

    benchmark = get_benchmark(
        "mmlu",
        task_config=EvalTaskConfig(
            benchmark="mmlu",
            model="openai_compatible",
            dataset_path=str(dataset_path),
        ),
    )
    dataset = benchmark.load_dataset()
    sample = dataset["default"][0]

    assert sample.target == "B"
    assert sample.choices == ["1", "4", "3", "5"]
    assert sample.metadata["subject"] == "abstract_algebra"
    assert "2 + 2 = ?" in sample.input


def test_ceval_runtime_loads_raw_parquet_rows_in_jsonl(tmp_path) -> None:
    dataset_path = tmp_path / "ceval.jsonl"
    dataset_path.write_text(
        json.dumps(
            {
                "id": 1,
                "question": "测试题",
                "A": "1",
                "B": "2",
                "C": "3",
                "D": "4",
                "answer": "C",
                "subject": "computer_network",
            },
            ensure_ascii=False,
        )
        + "\n",
        encoding="utf-8",
    )

    benchmark = get_benchmark(
        "ceval",
        task_config=EvalTaskConfig(
            benchmark="ceval",
            model="openai_compatible",
            dataset_path=str(dataset_path),
        ),
    )
    dataset = benchmark.load_dataset()
    sample = dataset["default"][0]

    assert sample.id == "1"
    assert sample.target == "C"
    assert sample.metadata["subject"] == "computer_network"
    assert sample.choices == ["1", "2", "3", "4"]


def test_cmmlu_runtime_loads_raw_zip(tmp_path) -> None:
    dataset_path = tmp_path / "cmmlu.zip"
    csv_content = "Unnamed: 0,Question,A,B,C,D,Answer\n0,农业题,工具,土地,劳动力,资金,B\n"
    with zipfile.ZipFile(dataset_path, "w") as archive:
        archive.writestr("test/agronomy.csv", csv_content)

    benchmark = get_benchmark(
        "cmmlu",
        task_config=EvalTaskConfig(
            benchmark="cmmlu",
            model="openai_compatible",
            dataset_path=str(dataset_path),
        ),
    )
    dataset = benchmark.load_dataset()
    sample = dataset["default"][0]

    assert sample.id == "0"
    assert sample.target == "B"
    assert sample.metadata["subject"] == "agronomy"
    assert sample.choices == ["工具", "土地", "劳动力", "资金"]
