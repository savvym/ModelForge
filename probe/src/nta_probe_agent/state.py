from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from pathlib import Path


@dataclass
class ProbeAgentState:
    probe_id: str | None = None
    auth_token: str | None = None
    probe_name: str | None = None


class ProbeAgentStateStore:
    def __init__(self, path: Path):
        self.path = path

    def load(self) -> ProbeAgentState:
        if not self.path.exists():
            return ProbeAgentState()
        data = json.loads(self.path.read_text(encoding="utf-8"))
        return ProbeAgentState(
            probe_id=data.get("probe_id"),
            auth_token=data.get("auth_token"),
            probe_name=data.get("probe_name"),
        )

    def save(self, state: ProbeAgentState) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(
            json.dumps(asdict(state), ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
