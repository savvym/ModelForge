from pathlib import Path

from watchfiles import Change, run_process

from apps.worker.main import main as run_worker

BACKEND_ROOT = Path(__file__).resolve().parents[2]
WATCH_PATHS = [
    BACKEND_ROOT / "apps",
    BACKEND_ROOT / "src",
    BACKEND_ROOT / "migrations",
]


def _watch_filter(change: Change, path: str) -> bool:
    return Path(path).suffix == ".py"


def main() -> None:
    run_process(
        *(str(path) for path in WATCH_PATHS),
        target=run_worker,
        watch_filter=_watch_filter,
        debounce=300,
    )


if __name__ == "__main__":
    main()
