from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache

import tiktoken

from nta_backend.evaluation.canonical import EvalSample

TIKTOKEN_ENCODING_NAME = "cl100k_base"
TOKENIZER_NAME = f"tiktoken:{TIKTOKEN_ENCODING_NAME}"
CHAT_MESSAGE_OVERHEAD_TOKENS = 3
CHAT_REPLY_PRIMER_TOKENS = 3


@dataclass(frozen=True)
class TokenEstimate:
    token_count: int
    tokenizer_name: str


@lru_cache(maxsize=1)
def _encoding() -> tiktoken.Encoding:
    return tiktoken.get_encoding(TIKTOKEN_ENCODING_NAME)


def estimate_text_tokens(text: str) -> TokenEstimate:
    token_count = len(_encoding().encode(text, disallowed_special=()))
    return TokenEstimate(token_count=token_count, tokenizer_name=TOKENIZER_NAME)


def estimate_eval_sample_tokens(samples: list[EvalSample]) -> TokenEstimate:
    token_count = sum(_estimate_chat_sample_tokens(sample) for sample in samples)
    return TokenEstimate(token_count=token_count, tokenizer_name=TOKENIZER_NAME)


def _estimate_chat_sample_tokens(sample: EvalSample) -> int:
    messages: list[tuple[str, str]] = []
    if sample.input.system:
        messages.append(("system", sample.input.system))
    messages.extend((message.role, message.content) for message in sample.input.messages)
    if not messages and sample.input.prompt:
        messages.append(("user", sample.input.prompt))

    if not messages:
        return 0

    token_count = CHAT_REPLY_PRIMER_TOKENS
    for role, content in messages:
        token_count += CHAT_MESSAGE_OVERHEAD_TOKENS
        token_count += len(_encoding().encode(role, disallowed_special=()))
        token_count += len(_encoding().encode(content, disallowed_special=()))
    return token_count
