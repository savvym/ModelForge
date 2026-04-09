from __future__ import annotations

import os
import socket
from dataclasses import dataclass
from pathlib import Path


def _default_probe_name() -> str:
    hostname = socket.gethostname().strip().lower().replace("_", "-")
    if not hostname:
        hostname = "probe"
    return f"{hostname}-{os.getpid()}"


@dataclass(frozen=True)
class ProbeAgentConfig:
    server_base_url: str
    project_id: str | None
    registration_token: str | None
    probe_name: str
    display_name: str
    tags: list[str]
    heartbeat_interval_seconds: int
    poll_interval_seconds: int
    state_path: Path
    work_dir: Path
    evalscope_bin: str | None = None
    request_timeout_seconds: float = 30.0
    stdout_tail_chars: int = 20000

    @classmethod
    def from_env(cls) -> ProbeAgentConfig:
        state_root = Path(os.getenv("NTA_PROBE_STATE_ROOT", Path.home() / ".nta-probe-agent"))
        probe_name = os.getenv("NTA_PROBE_NAME", "").strip() or _default_probe_name()
        display_name = os.getenv("NTA_PROBE_DISPLAY_NAME", "").strip() or probe_name
        tags_value = os.getenv("NTA_PROBE_TAGS", "")
        tags = [item.strip() for item in tags_value.split(",") if item.strip()]
        return cls(
            server_base_url=os.getenv(
                "NTA_PROBE_SERVER_BASE_URL",
                "http://127.0.0.1:8000",
            ).rstrip("/"),
            project_id=os.getenv("NTA_PROBE_PROJECT_ID") or None,
            registration_token=os.getenv("NTA_PROBE_REGISTRATION_TOKEN") or None,
            probe_name=probe_name,
            display_name=display_name,
            tags=tags,
            heartbeat_interval_seconds=int(os.getenv("NTA_PROBE_HEARTBEAT_INTERVAL", "30")),
            poll_interval_seconds=int(os.getenv("NTA_PROBE_POLL_INTERVAL", "10")),
            state_path=Path(os.getenv("NTA_PROBE_STATE_PATH", state_root / "state.json")),
            work_dir=Path(os.getenv("NTA_PROBE_WORK_DIR", state_root / "tasks")),
            evalscope_bin=os.getenv("NTA_PROBE_EVALSCOPE_BIN") or None,
            request_timeout_seconds=float(os.getenv("NTA_PROBE_REQUEST_TIMEOUT", "30")),
            stdout_tail_chars=int(os.getenv("NTA_PROBE_STDOUT_TAIL_CHARS", "20000")),
        )
