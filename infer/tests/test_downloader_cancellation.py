import asyncio
import threading
import time
from pathlib import Path

import pytest

from nta_infer_agent.config import AgentSettings
from nta_infer_agent.schemas import ModelBinding, ModelSource
from nta_infer_agent.storage.object_store import (
    DownloadCancelled,
    ModelCache,
    ModelDownloader,
    _object_download_callback,
)


def _settings(tmp_path: Path) -> AgentSettings:
    return AgentSettings(
        INFER_AGENT_TOKEN="test-token",
        model_cache_dir=tmp_path / "cache",
        runtime_dir=tmp_path / "runtime",
        _env_file=None,
    )


def _model() -> ModelBinding:
    return ModelBinding(
        model_id="model-id",
        name="Qwen",
        served_name="qwen",
        source=ModelSource(type="huggingface", uri="hf://qwen/model"),
    )


def test_object_download_callback_checks_cancel_without_progress() -> None:
    cancel_event = threading.Event()
    callback = _object_download_callback(
        progress=None,
        completed_getter=lambda: 0,
        total=100,
        name="model.safetensors",
        cancel_event=cancel_event,
    )

    assert callback is not None
    callback(10)

    cancel_event.set()
    with pytest.raises(DownloadCancelled):
        callback(10)


@pytest.mark.asyncio
async def test_ensure_downloaded_cancels_running_downloader_and_removes_staging(
    tmp_path: Path,
) -> None:
    settings = _settings(tmp_path)
    downloader = ModelDownloader(ModelCache(settings.model_cache_root), settings)
    model = _model()
    cancel_event = threading.Event()
    started = threading.Event()

    def blocking_downloader(staging: Path) -> None:
        started.set()
        (staging / "partial.bin").write_text("partial", encoding="utf-8")
        while not cancel_event.is_set():
            time.sleep(0.01)
        raise DownloadCancelled("stopped")

    task = asyncio.create_task(
        downloader._ensure_downloaded(
            model,
            blocking_downloader,
            cancel_event=cancel_event,
        )
    )

    assert await asyncio.to_thread(started.wait, 1.0)

    task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await task

    destination = downloader.cache.path_for_model(model)
    staging = destination.with_name(f".{destination.name}.partial")
    assert cancel_event.is_set()
    assert not staging.exists()
    assert not destination.exists()
