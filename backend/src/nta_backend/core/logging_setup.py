from __future__ import annotations

import logging
from logging.config import dictConfig
from pathlib import Path

from nta_backend.core.config import get_settings

BACKEND_ROOT = Path(__file__).resolve().parents[3]
DEFAULT_LOG_FORMAT = "%(asctime)s | %(levelname)s | %(process)d | %(name)s | %(message)s"


def _normalize_log_level(log_level: str) -> str:
    normalized = log_level.strip().upper()
    if isinstance(getattr(logging, normalized, None), int):
        return normalized
    return "INFO"


def _resolve_log_dir(log_dir: str) -> Path:
    path = Path(log_dir).expanduser()
    if not path.is_absolute():
        path = BACKEND_ROOT / path
    return path


def configure_logging(service_name: str) -> Path:
    settings = get_settings()
    level = _normalize_log_level(settings.log_level)
    log_dir = _resolve_log_dir(settings.log_dir)
    log_dir.mkdir(parents=True, exist_ok=True)
    log_file = log_dir / f"{service_name}.log"

    dictConfig(
        {
            "version": 1,
            "disable_existing_loggers": False,
            "formatters": {
                "default": {
                    "format": DEFAULT_LOG_FORMAT,
                }
            },
            "handlers": {
                "console": {
                    "class": "logging.StreamHandler",
                    "level": level,
                    "formatter": "default",
                    "stream": "ext://sys.stdout",
                },
                "file": {
                    "class": "logging.handlers.RotatingFileHandler",
                    "level": level,
                    "formatter": "default",
                    "filename": str(log_file),
                    "maxBytes": settings.log_max_bytes,
                    "backupCount": settings.log_backup_count,
                    "encoding": "utf-8",
                    "delay": True,
                },
            },
            "root": {
                "level": level,
                "handlers": ["console", "file"],
            },
            "loggers": {
                "uvicorn": {
                    "level": level,
                    "handlers": ["console", "file"],
                    "propagate": False,
                },
                "uvicorn.error": {
                    "level": level,
                    "handlers": ["console", "file"],
                    "propagate": False,
                },
                "uvicorn.access": {
                    "level": level,
                    "handlers": ["console", "file"],
                    "propagate": False,
                },
                "watchfiles.main": {
                    "level": level,
                    "handlers": ["console", "file"],
                    "propagate": False,
                },
            },
        }
    )
    logging.captureWarnings(True)
    logging.getLogger(__name__).info(
        "File logging enabled for %s at %s", service_name, log_file
    )
    return log_file
