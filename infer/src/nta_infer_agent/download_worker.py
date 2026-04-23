from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

from huggingface_hub import snapshot_download


def main(argv: list[str] | None = None) -> int:
    args = sys.argv[1:] if argv is None else argv
    if len(args) != 1:
        print("usage: python -m nta_infer_agent.download_worker <config.json>", file=sys.stderr)
        return 2

    config_path = Path(args[0])
    kwargs: dict[str, Any] = json.loads(config_path.read_text(encoding="utf-8"))
    snapshot_download(**kwargs)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
