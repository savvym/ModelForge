import pytest

from nta_backend.evaluation import (
    evaluate_predictions,
    load_eval_samples_jsonl,
    normalize_eval_dataset_bytes,
    score_eval_samples,
)


def test_load_eval_samples_jsonl_rejects_duplicate_sample_ids() -> None:
    payload = b"""
{"sample_id":"dup-1","input":{"messages":[{"role":"user","content":"Q1"}]},"reference":{"answer":"A"},"scoring":{"method":"accuracy"}}
{"sample_id":"dup-1","input":{"messages":[{"role":"user","content":"Q2"}]},"reference":{"answer":"B"},"scoring":{"method":"accuracy"}}
"""
    with pytest.raises(ValueError, match="sample_id 重复"):
        load_eval_samples_jsonl(payload)


def test_normalize_eval_dataset_bytes_rejects_accuracy_without_reference() -> None:
    payload = (
        b'{"sample_id":"s1","input":{"messages":[{"role":"user","content":"Q1"}]},'
        b'"scoring":{"method":"accuracy"}}\n'
    )

    with pytest.raises(ValueError, match="缺少参考答案"):
        normalize_eval_dataset_bytes("eval.jsonl", payload)


def test_score_eval_samples_dispatches_by_sample_method() -> None:
    samples = load_eval_samples_jsonl(
        b'{"sample_id":"acc-1","input":{"messages":[{"role":"user","content":"Question 1"}]},'
        b'"reference":{"answer":"B"},"scoring":{"method":"accuracy","weight":2.0}}\n'
        b'{"sample_id":"rule-1","input":{"messages":[{"role":"user","content":"Question 2"}]},'
        b'"reference":{"answers":["network timeout","gateway ip"]},'
        b'"scoring":{"method":"rule-based","weight":1.0}}\n'
    )
    predictions = [
        {"sample_id": "rule-1", "output_text": "需要检查 gateway ip 并处理 network timeout。"},
        {"sample_id": "acc-1", "output_text": "最终答案是 B"},
    ]

    scored_rows = score_eval_samples(samples, predictions)

    assert [row["sample_id"] for row in scored_rows] == ["acc-1", "rule-1"]
    assert scored_rows[0]["method"] == "accuracy"
    assert scored_rows[0]["passed"] is True
    assert scored_rows[0]["weight"] == 2.0
    assert scored_rows[1]["method"] == "rule-based"
    assert scored_rows[1]["passed"] is True
    assert scored_rows[1]["matched_keywords"] == ["network timeout", "gateway ip"]


def test_evaluate_predictions_aggregates_weighted_metrics() -> None:
    samples = load_eval_samples_jsonl(
        b'{"sample_id":"s1","input":{"messages":[{"role":"user","content":"Question 1"}]},'
        b'"reference":{"answer":"A"},"scoring":{"method":"accuracy","weight":2.0}}\n'
        b'{"sample_id":"s2","input":{"messages":[{"role":"user","content":"Question 2"}]},'
        b'"reference":{"answer":"B"},"scoring":{"method":"exact-match","weight":1.0}}\n'
    )
    predictions = [
        {"sample_id": "s1", "output_text": "A"},
        {"sample_id": "s2", "output_text": "C", "error": "mismatch"},
    ]

    result = evaluate_predictions(samples, predictions)

    assert len(result["scored_samples"]) == 2
    assert result["metrics"] == {
        "full_score_rate": 66.7,
        "availability_rate": 66.7,
        "consistency_score": 66.7,
    }
