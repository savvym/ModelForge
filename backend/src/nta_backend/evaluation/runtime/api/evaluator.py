from __future__ import annotations

from abc import ABC, abstractmethod
from pathlib import Path

from pydantic import BaseModel, Field

from nta_backend.evaluation.runtime.api.dataset import Sample
from nta_backend.evaluation.runtime.api.metric import SampleScore
from nta_backend.evaluation.runtime.api.model import ModelOutput
from nta_backend.evaluation.runtime.api.report import EvalReport


class TaskState(BaseModel):
    sample: Sample
    prepared_sample: Sample
    output: ModelOutput | None = None
    scores: list[SampleScore] = Field(default_factory=list)


class EvalCancelledError(RuntimeError):
    pass


class Evaluator(ABC):
    def __init__(self, *, output_dir: Path | None = None, **_: object):
        self.output_dir = output_dir

    @abstractmethod
    def eval(self) -> EvalReport:
        raise NotImplementedError
