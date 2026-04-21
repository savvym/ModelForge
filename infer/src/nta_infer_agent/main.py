import uvicorn

from nta_infer_agent.config import get_settings


def main() -> None:
    settings = get_settings()
    uvicorn.run(
        "nta_infer_agent.api.app:app",
        host=settings.host,
        port=settings.port,
        log_level=settings.log_level.lower(),
    )


if __name__ == "__main__":
    main()
