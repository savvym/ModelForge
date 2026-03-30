import asyncio

from nta_backend.core.logging_setup import configure_logging
from nta_backend.core.temporal import run_workers


def main() -> None:
    configure_logging("worker")
    asyncio.run(run_workers())


if __name__ == "__main__":
    main()
