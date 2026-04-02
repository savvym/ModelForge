from __future__ import annotations

from pathlib import Path

from pydantic import BaseModel, Field


class EvalTaskConfig(BaseModel):
    benchmark: str
    model: str
    evaluator: str = "default"
    dataset_path: str | None = None
    limit: int | None = Field(default=None, ge=1)
    output_dir: str = ".evalruns/latest"
    benchmark_args: dict[str, object] = Field(default_factory=dict)
    model_args: dict[str, object] = Field(default_factory=dict)
    evaluator_args: dict[str, object] = Field(default_factory=dict)

    @property
    def output_path(self) -> Path:
        return Path(self.output_dir)
