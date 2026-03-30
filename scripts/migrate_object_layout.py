#!/usr/bin/env python3
# ruff: noqa: E402
from __future__ import annotations

import argparse
import asyncio
import logging
import sys
from dataclasses import dataclass, field
from pathlib import Path, PurePosixPath
from typing import Callable
from uuid import UUID

ROOT_DIR = Path(__file__).resolve().parents[1]
BACKEND_SRC = ROOT_DIR / "backend" / "src"
if str(BACKEND_SRC) not in sys.path:
    sys.path.insert(0, str(BACKEND_SRC))

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from nta_backend.core.config import get_settings
from nta_backend.core.db import SessionLocal, engine
from nta_backend.core.object_store import (
    LOCAL_OBJECT_STORE_ROOT,
    delete_object,
    get_object_bytes,
    normalize_object_prefix,
    put_object_bytes,
)
from nta_backend.core.s3 import get_s3_client
from nta_backend.core.storage_layout import (
    SYSTEM_SHARED_PREFIX,
    build_dataset_artifact_key,
    build_dataset_source_key,
    build_project_files_key,
)
from nta_backend.models.auth import Project
from nta_backend.models.dataset import Dataset, DatasetFile, DatasetVersion

LEGACY_DATASET_PREFIX = "nta/dataset/"
LEGACY_SHARED_PREFIX = "shared/"
NORMALIZED_ARTIFACTS = ("eval-samples.jsonl", "schema-report.json")
DEFAULT_MANIFEST_PATH = ROOT_DIR / ".data" / "object-layout-migration-manifest.txt"


@dataclass
class MigrationStats:
    copied_objects: int = 0
    updated_records: int = 0
    deleted_source_objects: int = 0
    shared_objects_migrated: int = 0
    unclaimed_legacy_objects_migrated: int = 0
    dataset_versions_migrated: int = 0
    warnings: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class DatasetMigrationPlan:
    dataset_id: UUID
    version_id: UUID
    project_id: UUID
    source_key_updates: dict[str, str]
    artifact_key_updates: dict[str, str]
    source_uri_updates: dict[str, str]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Migrate legacy object keys into project-scoped prefixes.",
    )
    parser.add_argument(
        "--apply",
        action="store_true",
        help="Execute the migration. Without this flag the script only prints a dry-run plan.",
    )
    parser.add_argument(
        "--delete-source",
        action="store_true",
        help="Delete legacy source objects after their migrated copies are confirmed.",
    )
    parser.add_argument(
        "--shared-project-id",
        type=UUID,
        help="Project ID that should own migrated shared/ and orphaned legacy files.",
    )
    parser.add_argument(
        "--unclaimed-target",
        choices=("project-files", "system-shared", "skip"),
        default="project-files",
        help="Where to place legacy nta/dataset objects that are no longer referenced by the DB.",
    )
    parser.add_argument(
        "--manifest-path",
        type=Path,
        default=DEFAULT_MANIFEST_PATH,
        help="Path used to persist claimed legacy dataset keys between migration phases.",
    )
    return parser.parse_args()


def build_source_uri(bucket: str, object_key: str) -> str:
    return f"s3://{bucket}/{object_key}"


def is_legacy_dataset_key(object_key: str | None) -> bool:
    return bool(object_key and object_key.startswith(LEGACY_DATASET_PREFIX))


def list_object_keys(bucket: str, prefix: str) -> list[str]:
    normalized_prefix = normalize_object_prefix(prefix)
    keys: set[str] = set()

    try:
        client = get_s3_client()
        continuation_token: str | None = None
        while True:
            payload: dict[str, object] = {
                "Bucket": bucket,
                "Prefix": normalized_prefix,
                "MaxKeys": 500,
            }
            if continuation_token:
                payload["ContinuationToken"] = continuation_token

            response = client.list_objects_v2(**payload)
            for item in response.get("Contents", []):
                key = item.get("Key")
                if key and not key.endswith("/"):
                    keys.add(key)

            if not response.get("IsTruncated"):
                break
            continuation_token = response.get("NextContinuationToken")
    except Exception:
        pass

    local_root = LOCAL_OBJECT_STORE_ROOT / bucket
    if local_root.exists():
        prefix_path = local_root / normalized_prefix.rstrip("/")
        if prefix_path.is_file():
            keys.add(prefix_path.relative_to(local_root).as_posix())
        elif prefix_path.exists():
            for path in prefix_path.rglob("*"):
                if path.is_file():
                    keys.add(path.relative_to(local_root).as_posix())

    return sorted(key for key in keys if key.startswith(normalized_prefix))


def object_exists(bucket: str, object_key: str) -> bool:
    try:
        client = get_s3_client()
        client.head_object(Bucket=bucket, Key=object_key)
        return True
    except Exception:
        pass

    return (LOCAL_OBJECT_STORE_ROOT / bucket / object_key).exists()


def relative_after_prefix(object_key: str, prefix: str) -> str:
    normalized_prefix = normalize_object_prefix(prefix)
    if not object_key.startswith(normalized_prefix):
        raise ValueError(f"{object_key} 不在前缀 {normalized_prefix} 下")
    return object_key.removeprefix(normalized_prefix)


def print_action(message: str) -> None:
    print(message)


def load_manifest(path: Path) -> set[str]:
    if not path.exists():
        return set()
    return {
        line.strip()
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip() and not line.startswith("#")
    }


def save_manifest(path: Path, claimed_keys: set[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        "".join(f"{key}\n" for key in sorted(claimed_keys)),
        encoding="utf-8",
    )


def migrate_object(
    *,
    bucket: str,
    source_key: str,
    destination_key: str,
    apply: bool,
    delete_source_after_copy: bool,
    stats: MigrationStats,
) -> bool:
    if source_key == destination_key:
        print_action(f"SKIP same key: {source_key}")
        return True

    if not object_exists(bucket, source_key):
        stats.warnings.append(f"missing source object: {source_key}")
        print_action(f"WARN missing source: {source_key}")
        return False

    destination_exists = object_exists(bucket, destination_key)
    if not apply:
        action = "delete-source" if delete_source_after_copy else "copy"
        print_action(f"PLAN {action}: {source_key} -> {destination_key}")
        return True

    if destination_exists:
        print_action(f"SKIP existing destination: {destination_key}")
    else:
        payload = get_object_bytes(bucket, source_key)
        put_object_bytes(
            bucket,
            destination_key,
            payload.body,
            content_type=payload.content_type,
        )
        stats.copied_objects += 1
        print_action(f"COPIED: {source_key} -> {destination_key}")

    if delete_source_after_copy and object_exists(bucket, source_key):
        delete_object(bucket, source_key)
        stats.deleted_source_objects += 1
        print_action(f"DELETED source: {source_key}")

    return True


async def resolve_shared_project_id(
    session: AsyncSession,
    requested_project_id: UUID | None,
) -> UUID:
    if requested_project_id is not None:
        project = await session.get(Project, requested_project_id)
        if project is None:
            raise ValueError(f"项目不存在: {requested_project_id}")
        return requested_project_id

    rows = (await session.execute(select(Project.id).order_by(Project.created_at.asc()))).scalars().all()
    if len(rows) == 1:
        return rows[0]
    raise ValueError("存在多个项目时，必须显式传入 --shared-project-id")


async def build_dataset_plans(
    session: AsyncSession,
    *,
    bucket: str,
) -> tuple[list[DatasetMigrationPlan], set[str]]:
    files = (await session.execute(select(DatasetFile))).scalars().all()
    files_by_version: dict[UUID, list[DatasetFile]] = {}
    for file_item in files:
        files_by_version.setdefault(file_item.dataset_version_id, []).append(file_item)

    rows = (
        await session.execute(
            select(Dataset, DatasetVersion)
            .join(DatasetVersion, DatasetVersion.dataset_id == Dataset.id)
            .order_by(Dataset.created_at.asc(), DatasetVersion.version.asc())
        )
    ).all()

    plans: list[DatasetMigrationPlan] = []
    claimed_legacy_keys: set[str] = set()
    for dataset, version in rows:
        source_key_updates: dict[str, str] = {}
        artifact_key_updates: dict[str, str] = {}
        source_uri_updates: dict[str, str] = {}
        canonical_version_source_key: str | None = None

        version_files = files_by_version.get(version.id, [])
        for file_item in version_files:
            canonical_key = build_dataset_source_key(
                dataset.project_id,
                dataset.id,
                dataset.created_at,
                version.id,
                version.created_at,
                file_item.file_name,
            )
            if file_item.object_key == canonical_key:
                canonical_version_source_key = canonical_version_source_key or canonical_key
                continue
            source_key_updates[file_item.object_key] = canonical_key
            source_uri_updates[build_source_uri(bucket, file_item.object_key)] = build_source_uri(
                bucket,
                canonical_key,
            )
            claimed_legacy_keys.add(file_item.object_key)
            canonical_version_source_key = canonical_key

        current_primary_key = version.object_key
        if current_primary_key:
            canonical_version_source_key = canonical_version_source_key or build_dataset_source_key(
                dataset.project_id,
                dataset.id,
                dataset.created_at,
                version.id,
                version.created_at,
                PurePosixPath(current_primary_key).name or "dataset.jsonl",
            )
            if current_primary_key != canonical_version_source_key:
                source_key_updates.setdefault(current_primary_key, canonical_version_source_key)
                source_uri_updates[build_source_uri(bucket, current_primary_key)] = build_source_uri(
                    bucket,
                    canonical_version_source_key,
                )
                claimed_legacy_keys.add(current_primary_key)

        if canonical_version_source_key is not None:
            for artifact_name in NORMALIZED_ARTIFACTS:
                artifact_source_keys: set[str] = set()
                if current_primary_key:
                    current_parent = PurePosixPath(current_primary_key).parent
                    artifact_source_keys.update(
                        {
                            str(current_parent.parent / "artifacts" / artifact_name),
                            str(current_parent / "_normalized" / artifact_name),
                        }
                    )
                for file_item in version_files:
                    file_parent = PurePosixPath(file_item.object_key).parent
                    artifact_source_keys.update(
                        {
                            str(file_parent.parent / "artifacts" / artifact_name),
                            str(file_parent / "_normalized" / artifact_name),
                        }
                    )
                canonical_artifact_key = build_dataset_artifact_key(
                    dataset.project_id,
                    dataset.id,
                    dataset.created_at,
                    version.id,
                    version.created_at,
                    artifact_name,
                )
                for source_key in sorted(artifact_source_keys):
                    if source_key == canonical_artifact_key or not object_exists(bucket, source_key):
                        continue
                    artifact_key_updates[source_key] = canonical_artifact_key
                    claimed_legacy_keys.add(source_key)
                    break

        if source_key_updates or artifact_key_updates:
            plans.append(
                DatasetMigrationPlan(
                    dataset_id=dataset.id,
                    version_id=version.id,
                    project_id=dataset.project_id,
                    source_key_updates=source_key_updates,
                    artifact_key_updates=artifact_key_updates,
                    source_uri_updates=source_uri_updates,
                )
            )

    return plans, claimed_legacy_keys


async def apply_dataset_plans(
    session: AsyncSession,
    *,
    bucket: str,
    plans: list[DatasetMigrationPlan],
    apply: bool,
    delete_source_after_copy: bool,
    stats: MigrationStats,
) -> None:
    for plan in plans:
        dataset = await session.get(Dataset, plan.dataset_id)
        version = await session.get(DatasetVersion, plan.version_id)
        if dataset is None or version is None:
            stats.warnings.append(
                f"dataset/version disappeared during migration: {plan.dataset_id}/{plan.version_id}"
            )
            continue

        version_files = (
            await session.execute(
                select(DatasetFile).where(DatasetFile.dataset_version_id == version.id)
            )
        ).scalars().all()
        files_by_key = {file_item.object_key: file_item for file_item in version_files}
        version_touched = False

        for source_key, destination_key in plan.source_key_updates.items():
            migrated = migrate_object(
                bucket=bucket,
                source_key=source_key,
                destination_key=destination_key,
                apply=apply,
                delete_source_after_copy=delete_source_after_copy,
                stats=stats,
            )
            if not migrated:
                continue

            file_item = files_by_key.get(source_key)
            if apply and file_item is not None and file_item.object_key != destination_key:
                file_item.object_key = destination_key
                version_touched = True

            if apply and version.object_key == source_key:
                version.object_key = destination_key
                version_touched = True

        for source_key, destination_key in plan.artifact_key_updates.items():
            migrate_object(
                bucket=bucket,
                source_key=source_key,
                destination_key=destination_key,
                apply=apply,
                delete_source_after_copy=delete_source_after_copy,
                stats=stats,
            )

        if apply:
            mapped_version_uri = plan.source_uri_updates.get(version.source_uri or "")
            if mapped_version_uri and version.source_uri != mapped_version_uri:
                version.source_uri = mapped_version_uri
                version_touched = True

            mapped_dataset_uri = plan.source_uri_updates.get(dataset.source_uri or "")
            if mapped_dataset_uri and dataset.source_uri != mapped_dataset_uri:
                dataset.source_uri = mapped_dataset_uri
                version_touched = True

            if version_touched:
                stats.updated_records += 1
                stats.dataset_versions_migrated += 1

    if apply:
        await session.commit()


async def migrate_prefix_objects(
    *,
    bucket: str,
    prefix: str,
    destination_builder: Callable[[str], str],
    apply: bool,
    delete_source_after_copy: bool,
    stats: MigrationStats,
    counter_attr: str,
    skip_keys: set[str] | None = None,
) -> set[str]:
    migrated_keys: set[str] = set()
    skip_keys = skip_keys or set()

    for object_key in list_object_keys(bucket, prefix):
        if object_key in skip_keys:
            continue
        destination_key = destination_builder(object_key)
        migrated = migrate_object(
            bucket=bucket,
            source_key=object_key,
            destination_key=destination_key,
            apply=apply,
            delete_source_after_copy=delete_source_after_copy,
            stats=stats,
        )
        if migrated:
            migrated_keys.add(object_key)
            setattr(stats, counter_attr, getattr(stats, counter_attr) + 1)

    return migrated_keys


async def main() -> int:
    args = parse_args()
    if args.delete_source and not args.apply:
        raise SystemExit("--delete-source 必须和 --apply 一起使用")

    logging.getLogger("sqlalchemy.engine").setLevel(logging.WARNING)
    engine.echo = False

    bucket = get_settings().s3_bucket_main
    stats = MigrationStats()

    async with SessionLocal() as session:
        shared_project_id = await resolve_shared_project_id(session, args.shared_project_id)
        print(f"Using shared/unclaimed project: {shared_project_id}")

        dataset_plans, claimed_legacy_keys = await build_dataset_plans(session, bucket=bucket)
        manifest_claimed_keys = load_manifest(args.manifest_path)
        if manifest_claimed_keys:
            print(f"Loaded claimed manifest: {args.manifest_path}")
            claimed_legacy_keys |= manifest_claimed_keys
        print(f"Legacy dataset records to migrate: {len(dataset_plans)} versions")
        await apply_dataset_plans(
            session,
            bucket=bucket,
            plans=dataset_plans,
            apply=args.apply,
            delete_source_after_copy=args.delete_source,
            stats=stats,
        )
        if args.apply and claimed_legacy_keys:
            save_manifest(args.manifest_path, claimed_legacy_keys)
            print(f"Saved claimed manifest: {args.manifest_path}")

    def build_shared_destination(object_key: str) -> str:
        relative_path = relative_after_prefix(object_key, LEGACY_SHARED_PREFIX)
        return build_project_files_key(
            shared_project_id,
            PurePosixPath(relative_path).name or "asset.bin",
            relative_path=relative_path,
        )

    def build_unclaimed_destination(object_key: str) -> str:
        relative_path = relative_after_prefix(object_key, LEGACY_DATASET_PREFIX)
        if args.unclaimed_target == "system-shared":
            return f"{SYSTEM_SHARED_PREFIX}legacy/nta-dataset/{relative_path}"
        return build_project_files_key(
            shared_project_id,
            PurePosixPath(relative_path).name or "asset.bin",
            prefix="legacy/nta-dataset",
            relative_path=relative_path,
        )

    await migrate_prefix_objects(
        bucket=bucket,
        prefix=LEGACY_SHARED_PREFIX,
        destination_builder=build_shared_destination,
        apply=args.apply,
        delete_source_after_copy=args.delete_source,
        stats=stats,
        counter_attr="shared_objects_migrated",
    )

    if args.unclaimed_target != "skip":
        await migrate_prefix_objects(
            bucket=bucket,
            prefix=LEGACY_DATASET_PREFIX,
            destination_builder=build_unclaimed_destination,
            apply=args.apply,
            delete_source_after_copy=args.delete_source,
            stats=stats,
            counter_attr="unclaimed_legacy_objects_migrated",
            skip_keys=claimed_legacy_keys,
        )
    else:
        remaining = sorted(set(list_object_keys(bucket, LEGACY_DATASET_PREFIX)) - claimed_legacy_keys)
        if remaining:
            print("Skipped unclaimed legacy objects:")
            for key in remaining:
                print(f"  {key}")

    if args.apply and args.delete_source and not list_object_keys(bucket, LEGACY_DATASET_PREFIX):
        if args.manifest_path.exists():
            args.manifest_path.unlink()
            print(f"Removed claimed manifest: {args.manifest_path}")

    print()
    print("Summary")
    print(f"  copied_objects={stats.copied_objects}")
    print(f"  updated_records={stats.updated_records}")
    print(f"  deleted_source_objects={stats.deleted_source_objects}")
    print(f"  dataset_versions_migrated={stats.dataset_versions_migrated}")
    print(f"  shared_objects_migrated={stats.shared_objects_migrated}")
    print(f"  unclaimed_legacy_objects_migrated={stats.unclaimed_legacy_objects_migrated}")
    if stats.warnings:
        print("Warnings")
        for warning in stats.warnings:
            print(f"  {warning}")

    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
