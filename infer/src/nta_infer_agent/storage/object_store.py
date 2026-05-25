from __future__ import annotations

import asyncio
import hashlib
import json
import os
import subprocess
import sys
import tempfile
import threading
from collections.abc import Callable
from contextlib import suppress
from dataclasses import dataclass
from fnmatch import fnmatch
from pathlib import Path
from urllib.parse import urlparse

import boto3
from botocore.client import Config
from huggingface_hub import HfApi

from nta_infer_agent.config import AgentSettings
from nta_infer_agent.schemas import (
    HuggingFaceSource,
    LoraAdapterBinding,
    ModelBinding,
    ObjectStorageSource,
)

DOWNLOAD_WORKER_POLL_SECONDS = 0.2
DOWNLOAD_WORKER_TERMINATE_TIMEOUT_SECONDS = 10.0


@dataclass(frozen=True)
class DownloadProgress:
    completed: int
    total: int | None
    unit: str
    message: str | None = None


@dataclass(frozen=True)
class ObjectStorageObject:
    key: str
    size: int


DownloadProgressCallback = Callable[[DownloadProgress], None]


class DownloadCancelled(RuntimeError):
    """Raised when a model download is cancelled by a newer desired state."""


class ModelCache:
    def __init__(self, root: Path) -> None:
        self.root = root

    def path_for_model(self, model: ModelBinding | LoraAdapterBinding) -> Path:
        digest = hashlib.sha256(model.source.uri.encode()).hexdigest()[:16]
        artifact_id = model.model_id if isinstance(model, ModelBinding) else model.adapter_id
        safe_model_id = "".join(ch if ch.isalnum() or ch in "-_" else "-" for ch in artifact_id)
        return self.root / "models" / f"{safe_model_id}-{digest}"

    def ready_marker(self, path: Path) -> Path:
        return path / ".nta-ready"

    def is_ready(self, path: Path) -> bool:
        return path.exists() and self.ready_marker(path).exists()


def parse_object_storage_uri(uri: str) -> tuple[str, str, str]:
    parsed = urlparse(uri)
    if parsed.scheme.lower() not in {"s3", "cos"}:
        raise ValueError("model source must use s3:// or cos://")
    bucket = parsed.netloc
    key = parsed.path.lstrip("/")
    if not bucket or not key:
        raise ValueError("object storage uri must include bucket and key")
    return parsed.scheme.lower(), bucket, key


class ModelDownloader:
    def __init__(self, cache: ModelCache, settings: AgentSettings) -> None:
        self.cache = cache
        self.settings = settings

    async def ensure_cached(
        self,
        model: ModelBinding | LoraAdapterBinding,
        progress: DownloadProgressCallback | None = None,
        cancel_event: threading.Event | None = None,
    ) -> tuple[Path, bool]:
        if model.source.type == "local":
            return self._local_path(model), True

        _raise_if_cancelled(cancel_event)
        if model.source.type == "object_storage":
            if model.source.object_storage is None:
                raise ValueError("object_storage source details are required")
            return await self._ensure_downloaded(
                model,
                lambda destination: self._download_object_storage(
                    model.source.object_storage, destination, progress, cancel_event
                ),
                cancel_event=cancel_event,
            )

        if model.source.type == "huggingface":
            if model.source.huggingface is None:
                raise ValueError("huggingface source details are required")
            return await self._ensure_downloaded(
                model,
                lambda destination: self._download_huggingface(
                    model.source.huggingface, destination, progress, cancel_event
                ),
                cancel_event=cancel_event,
            )

        raise ValueError(f"unsupported model source type: {model.source.type}")

    async def _ensure_downloaded(
        self,
        model: ModelBinding | LoraAdapterBinding,
        downloader,
        *,
        cancel_event: threading.Event | None = None,
    ) -> tuple[Path, bool]:
        destination = self.cache.path_for_model(model)
        if self.cache.is_ready(destination):
            return destination, True

        staging = destination.with_name(f".{destination.name}.partial")
        if staging.exists():
            await asyncio.to_thread(_remove_tree, staging)
        staging.mkdir(parents=True, exist_ok=True)

        _raise_if_cancelled(cancel_event)
        loop = asyncio.get_running_loop()
        download_future = loop.run_in_executor(None, downloader, staging)
        try:
            await asyncio.shield(download_future)
        except asyncio.CancelledError:
            if cancel_event is not None:
                cancel_event.set()
            with suppress(Exception):
                await asyncio.wait_for(
                    asyncio.shield(download_future),
                    timeout=DOWNLOAD_WORKER_TERMINATE_TIMEOUT_SECONDS,
                )
            if not download_future.done():
                download_future.add_done_callback(_consume_future_result)
            with suppress(Exception):
                await asyncio.to_thread(_remove_tree, staging)
            raise
        except DownloadCancelled:
            with suppress(Exception):
                await asyncio.to_thread(_remove_tree, staging)
            raise

        try:
            _raise_if_cancelled(cancel_event)
            self.cache.ready_marker(staging).write_text("ready\n", encoding="utf-8")
            if destination.exists():
                await asyncio.to_thread(_remove_tree, destination)
            staging.rename(destination)
        except DownloadCancelled:
            with suppress(Exception):
                await asyncio.to_thread(_remove_tree, staging)
            raise
        return destination, False

    def _local_path(self, model: ModelBinding | LoraAdapterBinding) -> Path:
        uri = model.source.uri
        if uri.startswith("local://"):
            path = Path(uri.removeprefix("local://"))
        elif uri.startswith("file://"):
            path = Path(urlparse(uri).path)
        else:
            path = Path(uri)
        if not path.exists():
            raise FileNotFoundError(f"local model path does not exist: {path}")
        return path

    def _download_huggingface(
        self,
        source: HuggingFaceSource,
        destination: Path,
        progress: DownloadProgressCallback | None = None,
        cancel_event: threading.Event | None = None,
    ) -> None:
        _raise_if_cancelled(cancel_event)
        token = None
        if source.token is not None:
            token = source.token.get_secret_value()
        elif self.settings.huggingface_token is not None:
            token = self.settings.huggingface_token.get_secret_value()
        else:
            token = os.environ.get("HF_TOKEN") or os.environ.get("HUGGINGFACE_TOKEN")

        total_bytes = self._estimate_huggingface_size(source, token)
        _raise_if_cancelled(cancel_event)
        stop_watcher = threading.Event()
        watcher: threading.Thread | None = None
        if progress is not None:
            progress(
                DownloadProgress(
                    completed=0,
                    total=total_bytes,
                    unit="bytes",
                    message="开始下载 Hugging Face 模型文件",
                )
            )
            watcher = threading.Thread(
                target=_watch_directory_size,
                args=(destination, total_bytes, progress, stop_watcher),
                daemon=True,
            )
            watcher.start()

        kwargs = {
            "repo_id": source.repo_id,
            "repo_type": source.repo_type,
            "revision": source.revision,
            "local_dir": str(destination),
        }
        if token:
            kwargs["token"] = token
        if source.endpoint_url or self.settings.huggingface_endpoint_url:
            kwargs["endpoint"] = source.endpoint_url or self.settings.huggingface_endpoint_url
        if source.allow_patterns:
            kwargs["allow_patterns"] = source.allow_patterns
        if source.ignore_patterns:
            kwargs["ignore_patterns"] = source.ignore_patterns

        completed_successfully = False
        try:
            self._run_huggingface_worker(kwargs, cancel_event)
            completed_successfully = True
        finally:
            stop_watcher.set()
            if watcher is not None:
                watcher.join(timeout=2.0)
            if completed_successfully and progress is not None:
                completed = _directory_size(destination)
                progress(
                    DownloadProgress(
                        completed=min(completed, total_bytes) if total_bytes else completed,
                        total=total_bytes,
                        unit="bytes",
                        message="Hugging Face 模型文件下载完成",
                    )
                )

    def _download_object_storage(
        self,
        source: ObjectStorageSource,
        destination: Path,
        progress: DownloadProgressCallback | None = None,
        cancel_event: threading.Event | None = None,
    ) -> None:
        _raise_if_cancelled(cancel_event)
        _, bucket, key = parse_object_storage_uri(source.uri)
        client = self._build_client(source)

        normalized_prefix = key if key.endswith("/") else f"{key}/"
        objects = self._list_objects(client, bucket, normalized_prefix)
        _raise_if_cancelled(cancel_event)

        if objects:
            files = [
                item
                for item in objects
                if item.key != normalized_prefix and not item.key.endswith("/")
            ]
            total_size = sum(item.size for item in files)
            completed_size = 0
            for item in files:
                _raise_if_cancelled(cancel_event)
                relative = item.key[len(normalized_prefix) :]
                if not relative or relative.endswith("/"):
                    continue
                target = destination / relative
                target.parent.mkdir(parents=True, exist_ok=True)
                base_completed = completed_size
                callback = _object_download_callback(
                    progress=progress,
                    completed_getter=lambda base=base_completed: base,
                    total=total_size,
                    name=relative,
                    cancel_event=cancel_event,
                )
                client.download_file(bucket, item.key, str(target), Callback=callback)
                _raise_if_cancelled(cancel_event)
                completed_size += item.size
                if progress is not None:
                    progress(
                        DownloadProgress(
                            completed=completed_size,
                            total=total_size,
                            unit="bytes",
                            message=f"已下载 {relative}",
                        )
                    )
            return

        target = destination / Path(key).name
        total_size = self._object_size(client, bucket, key)
        _raise_if_cancelled(cancel_event)
        completed_size = 0

        def callback(chunk_size: int) -> None:
            _raise_if_cancelled(cancel_event)
            nonlocal completed_size
            completed_size += int(chunk_size)
            if progress is not None:
                progress(
                    DownloadProgress(
                        completed=completed_size,
                        total=total_size,
                        unit="bytes",
                        message=f"已下载 {Path(key).name}",
                    )
                )

        client.download_file(bucket, key, str(target), Callback=callback)

    def _run_huggingface_worker(
        self,
        kwargs: dict[str, object],
        cancel_event: threading.Event | None,
    ) -> None:
        _raise_if_cancelled(cancel_event)
        self.settings.runtime_root.mkdir(parents=True, exist_ok=True)
        config_path: Path | None = None
        process: subprocess.Popen[str] | None = None
        try:
            with tempfile.NamedTemporaryFile(
                "w",
                delete=False,
                dir=self.settings.runtime_root,
                encoding="utf-8",
                prefix="hf-download-",
                suffix=".json",
            ) as config_file:
                os.chmod(config_file.name, 0o600)
                config_path = Path(config_file.name)
                json.dump(kwargs, config_file, ensure_ascii=False)

            process = subprocess.Popen(
                [
                    sys.executable,
                    "-m",
                    "nta_infer_agent.download_worker",
                    str(config_path),
                ],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
            )
            while True:
                if cancel_event is not None and cancel_event.is_set():
                    _terminate_process(process)
                    raise DownloadCancelled("model download cancelled")
                try:
                    stdout, stderr = process.communicate(timeout=DOWNLOAD_WORKER_POLL_SECONDS)
                    break
                except subprocess.TimeoutExpired:
                    continue

            if process.returncode:
                message = (stderr or stdout or "").strip()
                raise RuntimeError(
                    message or f"huggingface download failed with code {process.returncode}"
                )
        finally:
            if process is not None and process.poll() is None:
                _terminate_process(process)
            if config_path is not None:
                try:
                    config_path.unlink()
                except FileNotFoundError:
                    pass

    def _build_client(self, source: ObjectStorageSource):
        credentials = source.credentials
        kwargs = {
            "endpoint_url": source.endpoint_url,
            "region_name": source.region,
            "config": Config(
                signature_version="s3v4",
                s3={"addressing_style": source.addressing_style},
            ),
        }
        if credentials is not None:
            kwargs.update(
                {
                    "aws_access_key_id": credentials.access_key_id,
                    "aws_secret_access_key": credentials.secret_access_key.get_secret_value(),
                    "aws_session_token": credentials.session_token,
                }
            )
        return boto3.client("s3", **kwargs)

    def _list_objects(self, client, bucket: str, prefix: str) -> list[ObjectStorageObject]:
        paginator = client.get_paginator("list_objects_v2")
        objects: list[ObjectStorageObject] = []
        for page in paginator.paginate(Bucket=bucket, Prefix=prefix):
            for item in page.get("Contents", []):
                key = item.get("Key")
                size = item.get("Size", 0)
                if isinstance(key, str):
                    objects.append(
                        ObjectStorageObject(
                            key=key,
                            size=int(size) if isinstance(size, int | float) else 0,
                        )
                    )
        return objects

    def _object_size(self, client, bucket: str, key: str) -> int | None:
        response = client.head_object(Bucket=bucket, Key=key)
        content_length = response.get("ContentLength")
        return int(content_length) if isinstance(content_length, int | float) else None

    def _estimate_huggingface_size(
        self,
        source: HuggingFaceSource,
        token: str | None,
    ) -> int | None:
        try:
            api = HfApi(endpoint=source.endpoint_url or self.settings.huggingface_endpoint_url)
            info = api.model_info(
                source.repo_id,
                revision=source.revision,
                files_metadata=True,
                token=token,
            )
        except Exception:
            return None

        total = 0
        for sibling in info.siblings:
            filename = getattr(sibling, "rfilename", None)
            size = getattr(sibling, "size", None)
            if not isinstance(filename, str) or not _matches_patterns(
                filename,
                allow_patterns=source.allow_patterns,
                ignore_patterns=source.ignore_patterns,
            ):
                continue
            if isinstance(size, int | float):
                total += int(size)
        return total or None


def _object_download_callback(
    *,
    progress: DownloadProgressCallback | None,
    completed_getter: Callable[[], int],
    total: int,
    name: str,
    cancel_event: threading.Event | None,
) -> Callable[[int], None] | None:
    if progress is None and cancel_event is None:
        return None
    file_completed = 0

    def callback(chunk_size: int) -> None:
        nonlocal file_completed
        _raise_if_cancelled(cancel_event)
        if progress is None:
            return
        file_completed += int(chunk_size)
        progress(
            DownloadProgress(
                completed=completed_getter() + file_completed,
                total=total,
                unit="bytes",
                message=f"正在下载 {name}",
            )
        )

    return callback


def _raise_if_cancelled(cancel_event: threading.Event | None) -> None:
    if cancel_event is not None and cancel_event.is_set():
        raise DownloadCancelled("model download cancelled")


def _consume_future_result(future: asyncio.Future) -> None:
    try:
        future.result()
    except asyncio.CancelledError:
        pass
    except Exception:
        pass


def _terminate_process(process: subprocess.Popen[str]) -> None:
    if process.poll() is not None:
        return
    process.terminate()
    try:
        process.wait(timeout=DOWNLOAD_WORKER_TERMINATE_TIMEOUT_SECONDS)
    except subprocess.TimeoutExpired:
        process.kill()
        with suppress(subprocess.TimeoutExpired):
            process.wait(timeout=DOWNLOAD_WORKER_TERMINATE_TIMEOUT_SECONDS)


def _matches_patterns(
    path: str,
    *,
    allow_patterns: list[str] | None,
    ignore_patterns: list[str] | None,
) -> bool:
    if allow_patterns and not any(fnmatch(path, pattern) for pattern in allow_patterns):
        return False
    if ignore_patterns and any(fnmatch(path, pattern) for pattern in ignore_patterns):
        return False
    return True


def _watch_directory_size(
    path: Path,
    total: int | None,
    progress: DownloadProgressCallback,
    stop_event: threading.Event,
) -> None:
    last_completed = -1
    while not stop_event.wait(1.0):
        completed = _directory_size(path)
        if completed == last_completed:
            continue
        last_completed = completed
        progress(
            DownloadProgress(
                completed=min(completed, total) if total else completed,
                total=total,
                unit="bytes",
                message="正在下载 Hugging Face 模型文件",
            )
        )


def _directory_size(path: Path) -> int:
    if not path.exists():
        return 0
    if path.is_file():
        return path.stat().st_size
    total = 0
    for child in path.rglob("*"):
        try:
            if child.is_file():
                total += child.stat().st_size
        except OSError:
            continue
    return total


def _remove_tree(path: Path) -> None:
    if not path.exists():
        return
    if path.is_file() or path.is_symlink():
        path.unlink()
        return
    for child in path.iterdir():
        _remove_tree(child)
    path.rmdir()


ObjectStorageDownloader = ModelDownloader
