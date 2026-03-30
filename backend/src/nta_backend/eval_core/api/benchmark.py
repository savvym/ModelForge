from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any

from pydantic import BaseModel, Field

from nta_backend.eval_core.api.dataset import DatasetDict, Sample
from nta_backend.eval_core.api.metric import AggScore, SampleScore
from nta_backend.eval_core.api.model import ModelOutput
from nta_backend.eval_core.config import EvalTaskConfig


class BenchmarkMeta(BaseModel):
    name: str
    display_name: str | None = None
    family_name: str | None = None
    family_display_name: str | None = None
    description: str | None = None
    default_eval_method: str = "judge-model"
    requires_judge_model: bool = False
    supports_custom_dataset: bool = False
    sample_schema_json: dict[str, Any] = Field(default_factory=lambda: {"type": "object"})
    prompt_schema_json: dict[str, Any] = Field(default_factory=lambda: {"type": "object"})
    prompt_config_json: dict[str, Any] = Field(default_factory=dict)
    metric_names: list[str] = Field(default_factory=list)
    aggregator_names: list[str] = Field(default_factory=list)
    subset_list: list[str] = Field(default_factory=lambda: ["default"])


class DataAdapter(ABC):
    meta: BenchmarkMeta

    def __init__(self, *, task_config: EvalTaskConfig | None = None, **_: object):
        self.task_config = task_config

    @abstractmethod
    def load_dataset(self) -> DatasetDict:
        raise NotImplementedError

    def prepare_sample(self, sample: Sample) -> Sample:
        return sample

    @abstractmethod
    def review(self, sample: Sample, output: ModelOutput) -> list[SampleScore]:
        raise NotImplementedError

    @abstractmethod
    def aggregate(self, sample_scores: list[SampleScore]) -> list[AggScore]:
        raise NotImplementedError
