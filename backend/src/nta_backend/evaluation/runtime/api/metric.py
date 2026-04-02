from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any

from pydantic import BaseModel, Field

from nta_backend.evaluation.runtime.api.dataset import Sample
from nta_backend.evaluation.runtime.api.model import ModelOutput


class SampleScore(BaseModel):
    sample_id: str
    metric: str
    score: float
    passed: bool | None = None
    reason: str | None = None
    extra: dict[str, Any] = Field(default_factory=dict)


class AggScore(BaseModel):
    metric: str
    value: float
    extra: dict[str, Any] = Field(default_factory=dict)


class Metric(ABC):
    name: str

    @abstractmethod
    def score(self, sample: Sample, output: ModelOutput) -> SampleScore:
        raise NotImplementedError


class Aggregator(ABC):
    name: str

    @abstractmethod
    def aggregate(self, scores: list[SampleScore]) -> AggScore:
        raise NotImplementedError
