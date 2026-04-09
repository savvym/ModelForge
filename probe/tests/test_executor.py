import json
from pathlib import Path
from uuid import uuid4

from nta_probe_agent.executor import EvalScopePerfExecutor
from nta_probe_agent.schemas import EvalScopePerfTaskConfig


def test_evalscope_perf_executor_builds_command_and_collects_runs(tmp_path: Path) -> None:
    executor = EvalScopePerfExecutor(work_dir=tmp_path, evalscope_bin="/usr/bin/evalscope")
    task_id = uuid4()
    config = EvalScopePerfTaskConfig(
        model="demo-model",
        url="https://example.com/v1/chat/completions",
        api_key="secret",
        prompt="Say hello",
        number=[4, 8],
        parallel=[1, 2],
        output_name="probe-task",
    )

    command, run_root = executor.build_command(
        task_id=task_id,
        config=config,
        output_parent=tmp_path,
    )

    assert command[:3] == ["/usr/bin/evalscope", "perf", "--model"]
    assert "--api-key" in command
    assert run_root == tmp_path / "probe-task"

    first_run = run_root / "parallel_1_number_4"
    first_run.mkdir(parents=True)
    (first_run / "benchmark_summary.json").write_text(
        json.dumps({"Request throughput (req/s)": 4.2, "Average latency (s)": 0.8}),
        encoding="utf-8",
    )
    (first_run / "benchmark_percentile.json").write_text(
        json.dumps([{"Percentiles": "99%"}]),
        encoding="utf-8",
    )
    (first_run / "benchmark_args.json").write_text(
        json.dumps({"model": "demo-model"}),
        encoding="utf-8",
    )
    (run_root / "perf_report.html").write_text("<html></html>", encoding="utf-8")

    runs = executor.collect_runs(run_root)
    overview = executor._build_overview(run_root)

    assert len(runs) == 1
    assert runs[0]["summary"]["Request throughput (req/s)"] == 4.2
    assert overview["best_request_throughput_run"] == "parallel_1_number_4"
    assert overview["html_report_path"] == str(run_root / "perf_report.html")
