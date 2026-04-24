from __future__ import annotations

import math
import re
from dataclasses import dataclass

from nta_infer_agent.schemas import RuntimeMetricSample

PROMETHEUS_LINE_RE = re.compile(
    r"^([a-zA-Z_:][a-zA-Z0-9_:]*)"
    r"(?:\{(.*)\})?\s+"
    r"([-+]?(?:\d+(?:\.\d*)?|\.\d+)(?:[eE][-+]?\d+)?|NaN|Inf|-Inf)"
    r"(?:\s+\d+)?$"
)
LABEL_RE = re.compile(r'([a-zA-Z_][a-zA-Z0-9_]*)="((?:\\.|[^"\\])*)"')
SUMMARY_METRICS = {
    "vllm:num_requests_running": "requests_running",
    "vllm:num_requests_waiting": "requests_waiting",
    "vllm:num_requests_swapped": "requests_swapped",
    "vllm:gpu_cache_usage_perc": "gpu_cache_usage_pct",
    "vllm:cpu_cache_usage_perc": "cpu_cache_usage_pct",
    "vllm:prefix_cache_hit_rate": "prefix_cache_hit_rate",
    "vllm:prompt_tokens_total": "prompt_tokens_total",
    "vllm:generation_tokens_total": "generation_tokens_total",
    "vllm:request_success_total": "request_success_total",
    "vllm:request_failure_total": "request_failure_total",
}
AVERAGE_METRICS = {
    "e2e_latency_avg_ms": (
        "vllm:e2e_request_latency_seconds_sum",
        "vllm:e2e_request_latency_seconds_count",
        1000.0,
    ),
    "time_to_first_token_avg_ms": (
        "vllm:time_to_first_token_seconds_sum",
        "vllm:time_to_first_token_seconds_count",
        1000.0,
    ),
    "time_per_output_token_avg_ms": (
        "vllm:time_per_output_token_seconds_sum",
        "vllm:time_per_output_token_seconds_count",
        1000.0,
    ),
}
MAX_VALUE_SUMMARY_KEYS = {
    "gpu_cache_usage_pct",
    "cpu_cache_usage_pct",
    "prefix_cache_hit_rate",
}
MAX_SELECTED_SAMPLES = 240


@dataclass(frozen=True)
class ParsedRuntimeMetrics:
    metric_count: int
    summary: dict[str, float]
    samples: list[RuntimeMetricSample]


def parse_vllm_metrics(text: str) -> ParsedRuntimeMetrics:
    samples = _parse_prometheus_samples(text)
    selected = _select_vllm_samples(samples)
    return ParsedRuntimeMetrics(
        metric_count=len(samples),
        summary=_build_summary(samples),
        samples=selected[:MAX_SELECTED_SAMPLES],
    )


def _parse_prometheus_samples(text: str) -> list[RuntimeMetricSample]:
    samples: list[RuntimeMetricSample] = []
    for raw_line in text.splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        match = PROMETHEUS_LINE_RE.match(line)
        if match is None:
            continue
        value = _parse_float(match.group(3))
        if value is None:
            continue
        samples.append(
            RuntimeMetricSample(
                name=match.group(1),
                labels=_parse_labels(match.group(2) or ""),
                value=value,
            )
        )
    return samples


def _parse_float(value: str) -> float | None:
    try:
        parsed = float(value.replace("Inf", "inf"))
    except ValueError:
        return None
    return parsed if math.isfinite(parsed) else None


def _parse_labels(value: str) -> dict[str, str]:
    if not value:
        return {}
    labels: dict[str, str] = {}
    for match in LABEL_RE.finditer(value):
        labels[match.group(1)] = _unescape_label_value(match.group(2))
    return labels


def _unescape_label_value(value: str) -> str:
    return (
        value.replace(r"\\", "\\")
        .replace(r"\"", '"')
        .replace(r"\n", "\n")
    )


def _select_vllm_samples(samples: list[RuntimeMetricSample]) -> list[RuntimeMetricSample]:
    return [
        sample
        for sample in samples
        if sample.name.startswith("vllm:") and not sample.name.endswith("_bucket")
    ]


def _build_summary(samples: list[RuntimeMetricSample]) -> dict[str, float]:
    summary: dict[str, float] = {}
    for metric_name, summary_key in SUMMARY_METRICS.items():
        values = [sample.value for sample in samples if sample.name == metric_name]
        if not values:
            continue
        if summary_key in MAX_VALUE_SUMMARY_KEYS:
            summary[summary_key] = max(values)
        else:
            summary[summary_key] = sum(values)

    for summary_key, (sum_name, count_name, multiplier) in AVERAGE_METRICS.items():
        total = sum(sample.value for sample in samples if sample.name == sum_name)
        count = sum(sample.value for sample in samples if sample.name == count_name)
        if count > 0:
            summary[summary_key] = total / count * multiplier

    return summary
