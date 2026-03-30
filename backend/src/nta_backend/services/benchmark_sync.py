"""Startup synchronization of runtime benchmark metadata into PostgreSQL.

Called once at application startup to ensure the ``benchmark_definitions``
table reflects the currently registered ``BENCHMARK_REGISTRY``.
"""

from __future__ import annotations

import json
import logging
from uuid import uuid4

from sqlalchemy import text

from nta_backend.core.db import SessionLocal
from nta_backend.eval_core.api.benchmark import BenchmarkMeta
from nta_backend.eval_core.api.registry import BENCHMARK_REGISTRY

logger = logging.getLogger(__name__)


def _adapter_class_path(cls: type) -> str:
    return f"{cls.__module__}:{cls.__qualname__}"


def _meta_to_row(meta: BenchmarkMeta, adapter_cls: type) -> dict:
    """Build a dict of column values from runtime BenchmarkMeta."""
    return {
        "id": str(uuid4()),
        "name": meta.name,
        "display_name": meta.display_name or meta.name,
        "description": meta.description or "",
        "family_name": meta.family_name,
        "family_display_name": meta.family_display_name,
        "default_eval_method": meta.default_eval_method,
        "sample_schema_json": json.dumps(meta.sample_schema_json),
        "prompt_schema_json": json.dumps(meta.prompt_schema_json),
        "prompt_config_json": json.dumps(meta.prompt_config_json),
        "requires_judge_model": meta.requires_judge_model,
        "supports_custom_dataset": meta.supports_custom_dataset,
        "metric_names": json.dumps(list(meta.metric_names) if meta.metric_names else []),
        "aggregator_names": json.dumps(list(meta.aggregator_names) if meta.aggregator_names else []),
        "subset_list": json.dumps(list(meta.subset_list) if meta.subset_list else ["default"]),
        "adapter_class": _adapter_class_path(adapter_cls),
        "is_runnable": True,
    }


_UPSERT_SQL = text("""
    INSERT INTO benchmark_definitions (
        id, name, display_name, description,
        default_eval_method, sample_schema_json, prompt_schema_json, prompt_config_json,
        requires_judge_model, supports_custom_dataset,
        family_name, family_display_name,
        metric_names, aggregator_names, subset_list,
        adapter_class, is_runnable
    ) VALUES (
        :id, :name, :display_name, :description,
        :default_eval_method,
        CAST(:sample_schema_json AS jsonb),
        CAST(:prompt_schema_json AS jsonb),
        CAST(:prompt_config_json AS jsonb),
        :requires_judge_model, :supports_custom_dataset,
        :family_name, :family_display_name,
        CAST(:metric_names AS jsonb),
        CAST(:aggregator_names AS jsonb),
        CAST(:subset_list AS jsonb),
        :adapter_class, :is_runnable
    )
    ON CONFLICT (name) DO UPDATE SET
        display_name = EXCLUDED.display_name,
        description = EXCLUDED.description,
        default_eval_method = EXCLUDED.default_eval_method,
        sample_schema_json = EXCLUDED.sample_schema_json,
        prompt_schema_json = EXCLUDED.prompt_schema_json,
        prompt_config_json = EXCLUDED.prompt_config_json,
        requires_judge_model = EXCLUDED.requires_judge_model,
        supports_custom_dataset = EXCLUDED.supports_custom_dataset,
        family_name = EXCLUDED.family_name,
        family_display_name = EXCLUDED.family_display_name,
        metric_names = EXCLUDED.metric_names,
        aggregator_names = EXCLUDED.aggregator_names,
        subset_list = EXCLUDED.subset_list,
        adapter_class = EXCLUDED.adapter_class,
        is_runnable = EXCLUDED.is_runnable
""")

_MARK_UNREGISTERED_SQL = text("""
    UPDATE benchmark_definitions
    SET is_runnable = false, adapter_class = NULL
    WHERE name != ALL(:names) AND is_runnable = true
""")


async def sync_runtime_benchmark_metadata() -> None:
    """Synchronize ``BENCHMARK_REGISTRY`` into ``benchmark_definitions``.

    For each registered benchmark:
    - If a row already exists (by name): update runtime-sourced fields.
    - If no row exists: insert a new row.

    For rows in the DB that are **not** in the registry:
    - Set ``is_runnable=False`` and ``adapter_class=NULL``.
    """
    # Trigger benchmark registration by importing the benchmarks package
    import nta_backend.eval_core.benchmarks  # noqa: F401

    registered_names: set[str] = set()

    async with SessionLocal() as session:
        async with session.begin():
            conn = await session.connection()
            for name, adapter_cls in BENCHMARK_REGISTRY.items():
                registered_names.add(name)
                meta: BenchmarkMeta = adapter_cls.meta
                row = _meta_to_row(meta, adapter_cls)
                await conn.execute(_UPSERT_SQL, row)

            if registered_names:
                await conn.execute(
                    _MARK_UNREGISTERED_SQL,
                    {"names": list(registered_names)},
                )

            # Auto-enable catalog benchmarks that can use the generic adapter.
            # Benchmarks with metric_names containing "acc" and no custom adapter
            # can be served by GenericBenchmark.
            result = await conn.execute(
                text(
                    "UPDATE benchmark_definitions "
                    "SET is_runnable = true "
                    "WHERE is_runnable = false "
                    "  AND adapter_class IS NULL "
                    "  AND metric_names IS NOT NULL "
                    "  AND metric_names @> '\"acc\"'::jsonb"
                )
            )
            generic_count = result.rowcount

        logger.info(
            "Synced %d runtime benchmarks to database. "
            "Enabled %d catalog benchmarks via generic adapter.",
            len(registered_names),
            generic_count,
        )
