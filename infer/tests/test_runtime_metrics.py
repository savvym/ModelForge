from nta_infer_agent.runtime.metrics import parse_vllm_metrics


def test_parse_vllm_metrics_builds_summary_and_filters_histogram_buckets() -> None:
    payload = """
# HELP vllm:num_requests_running Number of requests currently running.
vllm:num_requests_running{model_name="qwen"} 2
vllm:num_requests_waiting{model_name="qwen"} 3
vllm:gpu_cache_usage_perc{gpu="0"} 0.42
vllm:gpu_cache_usage_perc{gpu="1"} 0.56
vllm:prompt_tokens_total{model_name="qwen"} 128
vllm:generation_tokens_total{model_name="qwen"} 64
vllm:e2e_request_latency_seconds_sum{model_name="qwen"} 4
vllm:e2e_request_latency_seconds_count{model_name="qwen"} 2
vllm:e2e_request_latency_seconds_bucket{le="1.0"} 1
process_cpu_seconds_total 7
"""

    parsed = parse_vllm_metrics(payload)

    assert parsed.metric_count == 10
    assert parsed.summary["requests_running"] == 2
    assert parsed.summary["requests_waiting"] == 3
    assert parsed.summary["gpu_cache_usage_pct"] == 0.56
    assert parsed.summary["prompt_tokens_total"] == 128
    assert parsed.summary["generation_tokens_total"] == 64
    assert parsed.summary["e2e_latency_avg_ms"] == 2000
    assert all(sample.name.startswith("vllm:") for sample in parsed.samples)
    assert all(not sample.name.endswith("_bucket") for sample in parsed.samples)
