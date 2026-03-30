from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any

from pydantic import BaseModel, Field

from nta_backend.eval_core.api.dataset import Sample


class ModelUsage(BaseModel):
    input_tokens: int | None = None
    output_tokens: int | None = None
    total_tokens: int | None = None


class ModelOutput(BaseModel):
    sample_id: str
    text: str = ""
    error: str | None = None
    latency_ms: int | None = None
    usage: ModelUsage | None = None
    raw: dict[str, Any] = Field(default_factory=dict)


class ModelAPI(ABC):
    def __init__(self, *, model_id: str, **_: object):
        self.model_id = model_id

    @abstractmethod
    def generate(self, sample: Sample) -> ModelOutput:
        raise NotImplementedError

    def batch_generate(self, samples: list[Sample]) -> list[ModelOutput]:
        return [self.generate(sample) for sample in samples]
