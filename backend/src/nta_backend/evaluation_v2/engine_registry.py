from __future__ import annotations

from nta_backend.evaluation_v2.execution import EvalScopeBuiltinExecutor, EvaluationEngineAdapter

_ENGINE_REGISTRY: dict[tuple[str, str], EvaluationEngineAdapter] = {
    ("evalscope", "builtin"): EvalScopeBuiltinExecutor(),
}


def get_engine_adapter(*, engine: str, execution_mode: str) -> EvaluationEngineAdapter:
    key = (engine.strip(), execution_mode.strip())
    adapter = _ENGINE_REGISTRY.get(key)
    if adapter is None:
        raise ValueError(f"Unsupported evaluation engine: {engine}/{execution_mode}")
    return adapter
