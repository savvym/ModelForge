from __future__ import annotations

from typing import Any

from nta_backend.eval_core.adapters.default_adapter import DefaultDataAdapter
from nta_backend.eval_core.config import EvalTaskConfig


class JudgeModelAdapter(DefaultDataAdapter):
    """Adapter for benchmarks scored by an LLM judge model.

    Consolidates the judge-model constructor pattern shared by CL-bench,
    Grounded-Rubric-QA, and similar benchmarks.  Subclasses only need to
    implement ``record_to_sample``.
    """

    def __init__(
        self,
        *,
        task_config: EvalTaskConfig | None = None,
        dataset_path: str | None = None,
        prompt_config: dict[str, object] | None = None,
        judge_model_name: str | None = None,
        judge_api_url: str | None = None,
        judge_api_key: str | None = None,
        judge_api_format: str | None = None,
        judge_timeout_s: float = 180.0,
        **kwargs: object,
    ):
        super().__init__(task_config=task_config, dataset_path=dataset_path, **kwargs)
        self.prompt_config = prompt_config or {}
        self.judge_model_name = judge_model_name or self._as_str(task_config, "judge_model_name")
        self.judge_api_url = (
            judge_api_url
            or self._as_str(task_config, "judge_api_url")
            or self._as_str(task_config, "api_url")
        )
        self.judge_api_key = (
            judge_api_key
            or self._as_str(task_config, "judge_api_key")
            or self._as_str(task_config, "api_key")
        )
        self.judge_api_format = (
            judge_api_format
            or self._as_str(task_config, "judge_api_format")
            or self._as_str(task_config, "api_format")
            or "chat-completions"
        )
        self.judge_timeout_s = judge_timeout_s

    # ------------------------------------------------------------------
    # Template-method hooks
    # ------------------------------------------------------------------

    def _metric_kwargs(self) -> dict[str, Any]:
        if not self.judge_model_name or not self.judge_api_url:
            benchmark_name = self.meta.display_name or self.meta.name
            raise ValueError(
                f"{benchmark_name} requires judge_model_name and judge_api_url. "
                "Pass them via benchmark_args or model_args."
            )
        return {
            "api_url": self.judge_api_url,
            "api_key": self.judge_api_key,
            "api_format": self.judge_api_format,
            "model_name": self.judge_model_name,
            "prompt_template": self._prompt_template_from_config(),
            "timeout_s": self.judge_timeout_s,
        }

    def _prompt_template_from_config(self) -> str | None:
        value = self.prompt_config.get("judge_prompt_template")
        if isinstance(value, str) and value.strip():
            return value.strip()
        return None
