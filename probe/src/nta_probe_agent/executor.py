from __future__ import annotations

import asyncio
import json
import os
import shutil
import sys
import time
from pathlib import Path
from typing import Any
from uuid import UUID

from nta_probe_agent.schemas import EvalScopePerfTaskConfig


class EvalScopePerfExecutionError(RuntimeError):
    pass


def _tail_text(value: str, limit: int) -> str:
    if len(value) <= limit:
        return value
    return value[-limit:]


class EvalScopePerfExecutor:
    def __init__(
        self,
        *,
        work_dir: Path,
        evalscope_bin: str | None = None,
        stdout_tail_chars: int = 20000,
    ):
        self._work_dir = work_dir
        self._evalscope_bin = evalscope_bin or self._resolve_evalscope_bin()
        self._stdout_tail_chars = stdout_tail_chars

    def build_command(
        self,
        *,
        task_id: UUID,
        config: EvalScopePerfTaskConfig,
        output_parent: Path,
    ) -> tuple[list[str], Path]:
        output_name = config.output_name or f"task-{task_id}"
        run_root = output_parent / output_name
        command = [
            self._evalscope_bin,
            "perf",
            "--model",
            config.model,
            "--url",
            config.url,
            "--api",
            config.api,
            "--outputs-dir",
            str(output_parent),
            "--no-timestamp",
            "--name",
            output_name,
        ]
        if config.headers:
            header_items = [f"{key}={value}" for key, value in config.headers.items()]
            command.extend(["--headers", *header_items])
        api_key = self._resolve_api_key(config)
        if api_key:
            command.extend(["--api-key", api_key])
        if config.prompt:
            command.extend(["--prompt", config.prompt])
        if config.query_template:
            command.extend(["--query-template", config.query_template])
        if config.dataset:
            command.extend(["--dataset", config.dataset])
        if config.dataset_path:
            command.extend(["--dataset-path", config.dataset_path])
        command.extend(["--number", *self._coerce_list(config.number)])
        command.extend(["--parallel", *self._coerce_list(config.parallel)])
        if config.rate != -1:
            command.extend(["--rate", str(config.rate)])
        if config.max_tokens is not None:
            command.extend(["--max-tokens", str(config.max_tokens)])
        if config.min_tokens is not None:
            command.extend(["--min-tokens", str(config.min_tokens)])
        command.append("--stream" if config.stream else "--no-stream")
        command.extend(["--temperature", str(config.temperature)])
        if config.top_p is not None:
            command.extend(["--top-p", str(config.top_p)])
        if config.top_k is not None:
            command.extend(["--top-k", str(config.top_k)])
        if config.seed is not None:
            command.extend(["--seed", str(config.seed)])
        if config.connect_timeout is not None:
            command.extend(["--connect-timeout", str(config.connect_timeout)])
        if config.read_timeout is not None:
            command.extend(["--read-timeout", str(config.read_timeout)])
        if config.total_timeout is not None:
            command.extend(["--total-timeout", str(config.total_timeout)])
        if config.no_test_connection:
            command.append("--no-test-connection")
        if config.enable_progress_tracker:
            command.append("--enable-progress-tracker")
        if config.extra_args:
            command.extend(["--extra-args", json.dumps(config.extra_args, ensure_ascii=False)])
        return command, run_root

    async def execute(
        self,
        *,
        task_id: UUID,
        config: EvalScopePerfTaskConfig,
        timeout_seconds: int,
    ) -> dict[str, Any]:
        self._work_dir.mkdir(parents=True, exist_ok=True)
        task_dir = self._work_dir / str(task_id)
        task_dir.mkdir(parents=True, exist_ok=True)
        command, run_root = self.build_command(
            task_id=task_id,
            config=config,
            output_parent=task_dir,
        )
        started = time.perf_counter()
        process = await asyncio.create_subprocess_exec(
            *command,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        try:
            stdout, stderr = await asyncio.wait_for(process.communicate(), timeout=timeout_seconds)
        except TimeoutError as exc:
            process.kill()
            await process.communicate()
            raise EvalScopePerfExecutionError(
                f"evalscope perf timed out after {timeout_seconds} seconds."
            ) from exc
        duration_ms = int((time.perf_counter() - started) * 1000)
        stdout_text = _tail_text(stdout.decode("utf-8", errors="replace"), self._stdout_tail_chars)
        stderr_text = _tail_text(stderr.decode("utf-8", errors="replace"), self._stdout_tail_chars)
        if process.returncode != 0:
            raise EvalScopePerfExecutionError(
                f"evalscope perf exited with code {process.returncode}: "
                f"{stderr_text or stdout_text}"
            )
        return {
            "runtime_kind": "evalscope-perf",
            "command": self._redact_command(command),
            "run_root": str(run_root),
            "duration_ms": duration_ms,
            "stdout_tail": stdout_text,
            "stderr_tail": stderr_text,
            "artifacts": self._list_artifacts(run_root),
            "runs": self.collect_runs(run_root),
            "overview": self._build_overview(run_root),
        }

    def collect_runs(self, run_root: Path) -> list[dict[str, Any]]:
        runs: list[dict[str, Any]] = []
        if not run_root.exists():
            return runs
        for run_dir in sorted(run_root.iterdir()):
            if not run_dir.is_dir() or not run_dir.name.startswith("parallel_"):
                continue
            runs.append(
                {
                    "directory": run_dir.name,
                    "summary": self._load_json(run_dir / "benchmark_summary.json"),
                    "percentiles": self._load_json(run_dir / "benchmark_percentile.json"),
                    "args": self._load_json(run_dir / "benchmark_args.json"),
                }
            )
        return runs

    def _build_overview(self, run_root: Path) -> dict[str, Any]:
        runs = self.collect_runs(run_root)
        if not runs:
            return {}
        best_rps: float | None = None
        best_rps_dir: str | None = None
        lowest_latency: float | None = None
        lowest_latency_dir: str | None = None
        for run in runs:
            summary = run.get("summary") or {}
            throughput = self._to_float(summary.get("Request throughput (req/s)"))
            latency = self._to_float(summary.get("Average latency (s)"))
            if throughput is not None and (best_rps is None or throughput > best_rps):
                best_rps = throughput
                best_rps_dir = run["directory"]
            if latency is not None and (lowest_latency is None or latency < lowest_latency):
                lowest_latency = latency
                lowest_latency_dir = run["directory"]
        return {
            "run_count": len(runs),
            "best_request_throughput": best_rps,
            "best_request_throughput_run": best_rps_dir,
            "lowest_average_latency": lowest_latency,
            "lowest_average_latency_run": lowest_latency_dir,
            "html_report_path": (
                str(run_root / "perf_report.html")
                if (run_root / "perf_report.html").exists()
                else None
            ),
        }

    def _list_artifacts(self, run_root: Path) -> list[dict[str, Any]]:
        artifacts: list[dict[str, Any]] = []
        if not run_root.exists():
            return artifacts
        for path in sorted(run_root.rglob("*")):
            if not path.is_file():
                continue
            artifacts.append(
                {
                    "path": path.relative_to(run_root).as_posix(),
                    "size_bytes": path.stat().st_size,
                }
            )
        return artifacts

    def _resolve_evalscope_bin(self) -> str:
        executable = shutil.which("evalscope")
        if executable:
            return executable
        candidate = Path(sys.executable).with_name("evalscope")
        if candidate.exists():
            return str(candidate)
        raise EvalScopePerfExecutionError("Unable to locate evalscope executable.")

    def _resolve_api_key(self, config: EvalScopePerfTaskConfig) -> str | None:
        if config.api_key:
            return config.api_key
        if config.api_key_env:
            value = os.getenv(config.api_key_env)
            if not value:
                raise EvalScopePerfExecutionError(
                    f"Environment variable {config.api_key_env} is required for this task."
                )
            return value
        return None

    def _coerce_list(self, value: int | list[int]) -> list[str]:
        if isinstance(value, list):
            return [str(item) for item in value]
        return [str(value)]

    def _load_json(self, path: Path) -> Any:
        if not path.exists():
            return None
        return json.loads(path.read_text(encoding="utf-8"))

    def _redact_command(self, command: list[str]) -> list[str]:
        redacted: list[str] = []
        mask_next = False
        for part in command:
            if mask_next:
                redacted.append("***")
                mask_next = False
                continue
            redacted.append(part)
            if part == "--api-key":
                mask_next = True
        return redacted

    def _to_float(self, value: Any) -> float | None:
        if value is None:
            return None
        try:
            return float(value)
        except (TypeError, ValueError):
            return None
