import json

import tiktoken

from nta_backend.evaluation.canonical import normalize_eval_dataset_bytes
from nta_backend.services.dataset_service import _dataset_body_metrics
from nta_backend.services.dataset_token_estimator import (
    CHAT_MESSAGE_OVERHEAD_TOKENS,
    CHAT_REPLY_PRIMER_TOKENS,
    TIKTOKEN_ENCODING_NAME,
    TOKENIZER_NAME,
    estimate_eval_sample_tokens,
    estimate_text_tokens,
)


def test_estimate_text_tokens_uses_configured_tiktoken_encoding() -> None:
    text = "腾讯云 VPC 使用 VXLAN Overlay 网络。"
    encoding = tiktoken.get_encoding(TIKTOKEN_ENCODING_NAME)

    estimate = estimate_text_tokens(text)

    assert estimate.tokenizer_name == TOKENIZER_NAME
    assert estimate.token_count == len(encoding.encode(text, disallowed_special=()))


def test_estimate_eval_dataset_tokens_counts_normalized_chat_input() -> None:
    body = (
        json.dumps(
            {
                "sample_id": "case-1",
                "input": {
                    "system": "你是一位云网络专家。",
                    "messages": [{"role": "user", "content": "解释 VPC 的 Overlay 网络。"}],
                },
                "reference": {"answer": "VXLAN"},
            },
            ensure_ascii=False,
        )
        + "\n"
    ).encode()
    normalized = normalize_eval_dataset_bytes("cases.jsonl", body)
    encoding = tiktoken.get_encoding(TIKTOKEN_ENCODING_NAME)
    expected = (
        CHAT_REPLY_PRIMER_TOKENS
        + CHAT_MESSAGE_OVERHEAD_TOKENS
        + len(encoding.encode("system", disallowed_special=()))
        + len(encoding.encode("你是一位云网络专家。", disallowed_special=()))
        + CHAT_MESSAGE_OVERHEAD_TOKENS
        + len(encoding.encode("user", disallowed_special=()))
        + len(encoding.encode("解释 VPC 的 Overlay 网络。", disallowed_special=()))
    )

    estimate = estimate_eval_sample_tokens(normalized.samples)

    assert estimate.tokenizer_name == TOKENIZER_NAME
    assert estimate.token_count == expected


def test_dataset_body_metrics_include_record_count_and_token_estimate() -> None:
    body = b'{"input":"hello"}\n{"input":"world"}\n'

    metrics = _dataset_body_metrics(
        file_name="train.jsonl",
        body=body,
        purpose="finetune",
        use_case="finetune",
    )

    assert metrics.record_count == 2
    assert metrics.tokenizer_name == TOKENIZER_NAME
    assert metrics.token_count == estimate_text_tokens(body.decode()).token_count
