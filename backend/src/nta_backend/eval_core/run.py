from __future__ import annotations

from nta_backend.eval_core import benchmarks, evaluators, metrics, models
from nta_backend.eval_core.adapters import generic_adapter as _generic  # noqa: F401 — registers _generic
from nta_backend.eval_core.api.registry import create_evaluator, get_benchmark, get_model
from nta_backend.eval_core.config import EvalTaskConfig

_REGISTRATION_MODULES = (benchmarks, evaluators, metrics, models)


def run_task(task_config: EvalTaskConfig | dict[str, object]) -> object:
    config = _coerce_task_config(task_config)
    benchmark = get_benchmark(
        config.benchmark,
        task_config=config,
        **config.benchmark_args,
    )
    model = get_model(
        config.model,
        model_id=str(config.model_args.get("model_name") or config.model),
        **config.model_args,
    )
    evaluator = create_evaluator(
        config.evaluator,
        benchmark=benchmark,
        model=model,
        task_config=config,
        output_dir=config.output_path,
        **config.evaluator_args,
    )
    return evaluator.eval()


def _coerce_task_config(task_config: EvalTaskConfig | dict[str, object]) -> EvalTaskConfig:
    if isinstance(task_config, EvalTaskConfig):
        return task_config
    return EvalTaskConfig.model_validate(task_config)
