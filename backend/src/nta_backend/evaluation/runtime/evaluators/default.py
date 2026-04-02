from __future__ import annotations

import json
from collections.abc import Callable
from pathlib import Path
from threading import Event

from nta_backend.evaluation.runtime.api.benchmark import DataAdapter
from nta_backend.evaluation.runtime.api.evaluator import EvalCancelledError, Evaluator, TaskState
from nta_backend.evaluation.runtime.api.metric import SampleScore
from nta_backend.evaluation.runtime.api.model import ModelAPI
from nta_backend.evaluation.runtime.api.registry import register_evaluator
from nta_backend.evaluation.runtime.api.report import EvalReport, SubsetReport
from nta_backend.evaluation.runtime.config import EvalTaskConfig


@register_evaluator("default")
class DefaultEvaluator(Evaluator):
    def __init__(
        self,
        *,
        benchmark: DataAdapter,
        model: ModelAPI,
        task_config: EvalTaskConfig,
        output_dir: Path | None = None,
        progress_callback: Callable[[int, int], None] | None = None,
        cancellation_event: Event | None = None,
        **kwargs: object,
    ):
        super().__init__(output_dir=output_dir, **kwargs)
        self.benchmark = benchmark
        self.model = model
        self.task_config = task_config
        self.progress_callback = progress_callback
        self.cancellation_event = cancellation_event

    def eval(self) -> EvalReport:
        dataset_dict = self.benchmark.load_dataset()
        subset_reports: list[SubsetReport] = []
        total_samples = sum(len(self._limit_samples(samples)) for samples in dataset_dict.values())
        completed_samples = 0
        self._publish_progress(completed_samples, total_samples)

        for subset, samples in dataset_dict.items():
            limited_samples = self._limit_samples(samples)
            task_states: list[TaskState] = []
            for sample in limited_samples:
                self._raise_if_cancelled()
                task_states.append(self._run_sample(sample))
                completed_samples += 1
                self._publish_progress(completed_samples, total_samples)
            sample_scores = self._collect_scores(task_states)
            subset_reports.append(
                SubsetReport(
                    subset=subset,
                    sample_count=len(limited_samples),
                    metrics=self.benchmark.aggregate(sample_scores),
                    sample_scores=sample_scores,
                )
            )

        report = EvalReport(
            benchmark_name=self.benchmark.meta.name,
            model_name=self.model.model_id,
            subset_reports=subset_reports,
        )
        self._persist_report(report)
        return report

    def _run_sample(self, sample) -> TaskState:
        self._raise_if_cancelled()
        prepared_sample = self.benchmark.prepare_sample(sample)
        output = self.model.generate(prepared_sample)
        self._raise_if_cancelled()
        scores = self.benchmark.review(sample, output)
        return TaskState(
            sample=sample,
            prepared_sample=prepared_sample,
            output=output,
            scores=scores,
        )

    def _collect_scores(self, task_states: list[TaskState]) -> list[SampleScore]:
        scores: list[SampleScore] = []
        for task_state in task_states:
            scores.extend(task_state.scores)
        return scores

    def _limit_samples(self, samples: list) -> list:
        if self.task_config.limit is None:
            return list(samples)
        return list(samples[: self.task_config.limit])

    def _persist_report(self, report: EvalReport) -> None:
        if self.output_dir is None:
            return
        self.output_dir.mkdir(parents=True, exist_ok=True)
        report_path = self.output_dir / "report.json"
        report_path.write_text(
            json.dumps(report.model_dump(mode="json"), ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

    def _publish_progress(self, progress_done: int, progress_total: int) -> None:
        if self.progress_callback is None:
            return
        self.progress_callback(progress_done, progress_total)

    def _raise_if_cancelled(self) -> None:
        if self.cancellation_event is not None and self.cancellation_event.is_set():
            raise EvalCancelledError("Eval job was cancelled.")
