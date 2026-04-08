from __future__ import annotations

import threading
from abc import ABC, abstractmethod
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


class EvalExecutionCancelledError(RuntimeError):
    pass


@dataclass(frozen=True)
class ExecutorModelConfig:
    model_name: str
    display_name: str
    api_url: str
    api_key: str | None
    api_format: str
    organization: str | None = None
    headers: dict[str, str] = field(default_factory=dict)


@dataclass(frozen=True)
class ExecutorTemplateConfig:
    prompt: str
    vars: list[str] = field(default_factory=list)
    output_type: str | None = None
    output_config: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class EvalExecutionRequest:
    benchmark_name: str
    dataset_path: str
    output_dir: Path
    eval_method: str
    eval_model: ExecutorModelConfig
    judge_model: ExecutorModelConfig | None = None
    field_mapping: dict[str, Any] = field(default_factory=dict)
    prompt_config: dict[str, Any] = field(default_factory=dict)
    template_config: ExecutorTemplateConfig | None = None
    limit: int | None = None
    progress_callback: Callable[[int, int], None] | None = None
    cancellation_event: threading.Event | None = None


@dataclass(frozen=True)
class EvalExecutionResult:
    report_payload: dict[str, Any]


class EvalExecutor(ABC):
    @abstractmethod
    def execute(self, request: EvalExecutionRequest) -> EvalExecutionResult:
        raise NotImplementedError
