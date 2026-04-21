from __future__ import annotations

import asyncio
import hashlib
import os
from pathlib import Path
from urllib.parse import urlparse

import boto3
from botocore.client import Config
from huggingface_hub import snapshot_download

from nta_infer_agent.config import AgentSettings
from nta_infer_agent.schemas import HuggingFaceSource, ModelBinding, ObjectStorageSource


class ModelCache:
    def __init__(self, root: Path) -> None:
        self.root = root

    def path_for_model(self, model: ModelBinding) -> Path:
        digest = hashlib.sha256(model.source.uri.encode()).hexdigest()[:16]
        safe_model_id = "".join(ch if ch.isalnum() or ch in "-_" else "-" for ch in model.model_id)
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

    async def ensure_cached(self, model: ModelBinding) -> tuple[Path, bool]:
        if model.source.type == "local":
            return self._local_path(model), True

        if model.source.type == "object_storage":
            if model.source.object_storage is None:
                raise ValueError("object_storage source details are required")
            return await self._ensure_downloaded(
                model,
                lambda destination: self._download_object_storage(
                    model.source.object_storage, destination
                ),
            )

        if model.source.type == "huggingface":
            if model.source.huggingface is None:
                raise ValueError("huggingface source details are required")
            return await self._ensure_downloaded(
                model,
                lambda destination: self._download_huggingface(
                    model.source.huggingface, destination
                ),
            )

        raise ValueError(f"unsupported model source type: {model.source.type}")

    async def _ensure_downloaded(
        self,
        model: ModelBinding,
        downloader,
    ) -> tuple[Path, bool]:
        destination = self.cache.path_for_model(model)
        if self.cache.is_ready(destination):
            return destination, True

        staging = destination.with_name(f".{destination.name}.partial")
        if staging.exists():
            await asyncio.to_thread(_remove_tree, staging)
        staging.mkdir(parents=True, exist_ok=True)

        await asyncio.to_thread(downloader, staging)
        self.cache.ready_marker(staging).write_text("ready\n", encoding="utf-8")
        if destination.exists():
            await asyncio.to_thread(_remove_tree, destination)
        staging.rename(destination)
        return destination, False

    def _local_path(self, model: ModelBinding) -> Path:
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

    def _download_huggingface(self, source: HuggingFaceSource, destination: Path) -> None:
        token = None
        if source.token is not None:
            token = source.token.get_secret_value()
        elif self.settings.huggingface_token is not None:
            token = self.settings.huggingface_token.get_secret_value()
        else:
            token = os.environ.get("HF_TOKEN") or os.environ.get("HUGGINGFACE_TOKEN")

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

        snapshot_download(**kwargs)

    def _download_object_storage(self, source: ObjectStorageSource, destination: Path) -> None:
        _, bucket, key = parse_object_storage_uri(source.uri)
        client = self._build_client(source)

        normalized_prefix = key if key.endswith("/") else f"{key}/"
        objects = self._list_objects(client, bucket, normalized_prefix)

        if objects:
            for object_key in objects:
                relative = object_key[len(normalized_prefix) :]
                if not relative or relative.endswith("/"):
                    continue
                target = destination / relative
                target.parent.mkdir(parents=True, exist_ok=True)
                client.download_file(bucket, object_key, str(target))
            return

        target = destination / Path(key).name
        client.download_file(bucket, key, str(target))

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

    def _list_objects(self, client, bucket: str, prefix: str) -> list[str]:
        paginator = client.get_paginator("list_objects_v2")
        keys: list[str] = []
        for page in paginator.paginate(Bucket=bucket, Prefix=prefix):
            for item in page.get("Contents", []):
                key = item.get("Key")
                if isinstance(key, str):
                    keys.append(key)
        return keys


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
