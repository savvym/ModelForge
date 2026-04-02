from __future__ import annotations

import json
from abc import abstractmethod
from pathlib import Path
from typing import Any

from nta_backend.evaluation.runtime.api.benchmark import DataAdapter
from nta_backend.evaluation.runtime.api.dataset import DatasetDict, Sample
from nta_backend.evaluation.runtime.api.metric import Aggregator, AggScore, Metric, SampleScore
from nta_backend.evaluation.runtime.api.model import ModelOutput
from nta_backend.evaluation.runtime.api.registry import get_aggregator, get_metric
from nta_backend.evaluation.runtime.config import EvalTaskConfig


class DefaultDataAdapter(DataAdapter):
    """Base adapter with standard JSONL loading, metric scoring, and aggregation.

    Subclasses must implement ``record_to_sample`` to convert raw JSON records
    into :class:`Sample` objects.  Everything else has sensible defaults driven
    by ``meta.metric_names`` and ``meta.aggregator_names``.
    """

    def __init__(
        self,
        *,
        task_config: EvalTaskConfig | None = None,
        dataset_path: str | None = None,
        **kwargs: object,
    ):
        super().__init__(task_config=task_config, **kwargs)
        task_dataset_path = task_config.dataset_path if task_config else None
        self.dataset_path = dataset_path or task_dataset_path
        self._metrics: list[Metric] | None = None
        self._aggregators: list[Aggregator] | None = None

    # ------------------------------------------------------------------
    # Dataset loading
    # ------------------------------------------------------------------

    def load_dataset(self) -> DatasetDict:
        path = self._require_dataset_path()
        samples = list(self._load_jsonl(path))
        if not samples:
            benchmark_name = self.meta.display_name or self.meta.name
            raise ValueError(f"{benchmark_name} dataset is empty.")
        return {"default": samples}

    def _load_jsonl(self, path: Path) -> list[Sample]:
        samples: list[Sample] = []
        raw_lines = path.read_text(encoding="utf-8").splitlines()
        for line_number, raw_line in enumerate(raw_lines, start=1):
            line = raw_line.strip()
            if not line:
                continue
            try:
                record = json.loads(line)
            except json.JSONDecodeError as exc:
                benchmark_name = self.meta.display_name or self.meta.name
                raise ValueError(
                    f"Invalid {benchmark_name} JSONL at line {line_number}."
                ) from exc
            if not isinstance(record, dict):
                benchmark_name = self.meta.display_name or self.meta.name
                raise ValueError(
                    f"{benchmark_name} sample at line {line_number} must be a JSON object."
                )
            samples.append(self.record_to_sample(record, line_number))
        return samples

    @abstractmethod
    def record_to_sample(self, record: dict[str, Any], line_number: int) -> Sample:
        """Convert a raw JSON record into a :class:`Sample`.

        Each concrete benchmark must implement this hook.
        """
        raise NotImplementedError

    # ------------------------------------------------------------------
    # Scoring
    # ------------------------------------------------------------------

    def review(self, sample: Sample, output: ModelOutput) -> list[SampleScore]:
        metrics = self._ensure_metrics()
        return [metric.score(sample, output) for metric in metrics]

    def aggregate(self, sample_scores: list[SampleScore]) -> list[AggScore]:
        aggregators = self._ensure_aggregators()
        return [aggregator.aggregate(sample_scores) for aggregator in aggregators]

    # ------------------------------------------------------------------
    # Metric / aggregator lifecycle (template-method hooks)
    # ------------------------------------------------------------------

    def _ensure_metrics(self) -> list[Metric]:
        if self._metrics is None:
            self._metrics = self._build_metrics()
        return self._metrics

    def _build_metrics(self) -> list[Metric]:
        kwargs = self._metric_kwargs()
        return [get_metric(name, **kwargs) for name in self.meta.metric_names]

    def _metric_kwargs(self) -> dict[str, Any]:
        """Return extra kwargs passed to ``get_metric``.

        Subclasses (e.g. ``GenericBenchmark``) override this to inject
        judge-model parameters.
        """
        return {}

    def _ensure_aggregators(self) -> list[Aggregator]:
        if self._aggregators is None:
            names = self.meta.aggregator_names or ["mean"]
            self._aggregators = [get_aggregator(name) for name in names]
        return self._aggregators

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _require_dataset_path(self) -> Path:
        if not self.dataset_path:
            benchmark_name = self.meta.display_name or self.meta.name
            raise ValueError(
                f"{benchmark_name} requires dataset_path pointing to a local dataset file."
            )
        return Path(self.dataset_path)

    @staticmethod
    def _as_str(task_config: EvalTaskConfig | None, key: str) -> str | None:
        """Read a string value from ``task_config.model_args``."""
        if task_config is None:
            return None
        value = task_config.model_args.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()
        return None
