from __future__ import annotations

from nta_backend.evaluation_v2.execution.evalscope_dataset import _normalize_legacy_report
from nta_backend.schemas.evaluation_v2 import CompiledRunItemPlan, ModelBindingSnapshot


def _item_plan() -> CompiledRunItemPlan:
    return CompiledRunItemPlan(
        item_key="judge-template-demo",
        display_name="Judge Template Demo",
        engine="evalscope",
        execution_mode="dataset",
        spec_name="judge-template-demo",
        spec_version="v1",
        model_binding=ModelBindingSnapshot(
            model_name="demo-model",
            display_name="Demo Model",
            api_url="https://example.com/v1",
            api_format="chat-completions",
        ),
    )


def test_normalize_legacy_report_coerces_categorical_raw_score() -> None:
    report_payload, _, samples = _normalize_legacy_report(
        legacy_report={
            "generated_at": "2026-04-24T00:00:00Z",
            "subset_reports": [
                {
                    "subset": "default",
                    "metrics": [{"metric": "judge_template", "value": 0.0}],
                    "sample_scores": [
                        {
                            "sample_id": "sample-1",
                            "metric": "judge_template",
                            "score": 0.0,
                            "raw_score": "Fail",
                            "passed": False,
                            "reason": "incorrect answer",
                            "category": "Fail",
                            "label_group": "fail",
                        }
                    ],
                }
            ],
        },
        item_plan=_item_plan(),
        dataset_files=[],
    )

    canonical_sample = samples[0]
    assert canonical_sample.score == 0.0
    assert canonical_sample.raw_score == 0.0
    assert canonical_sample.metadata["category"] == "Fail"
    assert canonical_sample.metadata["label_group"] == "fail"

    report_sample = report_payload["samples"][0]
    assert report_sample["raw_score"] == 0.0
    assert report_sample["metadata"]["category"] == "Fail"
    assert report_sample["metadata"]["label_group"] == "fail"

    subset_sample = report_payload["subset_reports"][0]["sample_scores"][0]
    assert subset_sample["raw_score"] == 0.0
    assert subset_sample["category"] == "Fail"
    assert subset_sample["label_group"] == "fail"


def test_normalize_legacy_report_preserves_non_numeric_raw_score_label() -> None:
    report_payload, _, samples = _normalize_legacy_report(
        legacy_report={
            "generated_at": "2026-04-24T00:00:00Z",
            "subset_reports": [
                {
                    "subset": "default",
                    "metrics": [{"metric": "judge_template", "value": 0.0}],
                    "sample_scores": [
                        {
                            "sample_id": "sample-1",
                            "metric": "judge_template",
                            "score": 0.0,
                            "raw_score": "Fail",
                            "passed": False,
                            "reason": "incorrect answer",
                        }
                    ],
                }
            ],
        },
        item_plan=_item_plan(),
        dataset_files=[],
    )

    canonical_sample = samples[0]
    assert canonical_sample.raw_score == 0.0
    assert canonical_sample.metadata["raw_score_label"] == "Fail"

    report_sample = report_payload["samples"][0]
    assert report_sample["raw_score"] == 0.0
    assert report_sample["metadata"]["raw_score_label"] == "Fail"
