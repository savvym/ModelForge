from __future__ import annotations

import threading
from abc import ABC, abstractmethod
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from nta_backend.schemas.evaluation_v2 import CompiledRunItemPlan


@dataclass(frozen=True)
class ExecutionArtifact:
    artifact_type: str
    path: Path
    content_type: str | None = None
    extra: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class CanonicalMetric:
    metric_name: str
    metric_value: float
    metric_scope: str = "overall"
    metric_unit: str | None = None
    dimension: dict[str, Any] = field(default_factory=dict)
    extra: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class CanonicalSample:
    sample_id: str
    subset_name: str | None = None
    input_preview: str | None = None
    prediction_text: str | None = None
    reference_answers: list[str] = field(default_factory=list)
    score: float | None = None
    raw_score: float | None = None
    passed: bool = False
    reason: str | None = None
    error: str | None = None
    latency_ms: int | None = None
    total_tokens: int | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class CanonicalExecutionResult:
    report_payload: dict[str, Any]
    metrics: list[CanonicalMetric] = field(default_factory=list)
    samples: list[CanonicalSample] = field(default_factory=list)
    artifacts: list[ExecutionArtifact] = field(default_factory=list)


@dataclass(frozen=True)
class ExecutionContext:
    output_dir: Path
    progress_callback: Callable[[int, int], None] | None = None
    cancellation_event: threading.Event | None = None


class ExecutionCancelledError(RuntimeError):
    pass


class EvaluationEngineAdapter(ABC):
    @abstractmethod
    def execute(
        self,
        item_plan: CompiledRunItemPlan,
        context: ExecutionContext,
    ) -> CanonicalExecutionResult:
        raise NotImplementedError
