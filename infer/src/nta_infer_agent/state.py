from __future__ import annotations

import asyncio
import json
import sqlite3
from collections.abc import AsyncIterator
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from pydantic import BaseModel, SecretStr

from nta_infer_agent.schemas import DeploymentEvent, DeploymentSpec, DeploymentStatus


def utc_now() -> datetime:
    return datetime.now(UTC)


def _json_default(value: object) -> str:
    if isinstance(value, datetime):
        return value.isoformat()
    raise TypeError(f"Object of type {type(value)!r} is not JSON serializable")


def _jsonable_with_secrets(value: Any) -> Any:
    if isinstance(value, SecretStr):
        return value.get_secret_value()
    if isinstance(value, BaseModel):
        return _jsonable_with_secrets(value.model_dump(mode="python"))
    if isinstance(value, datetime):
        return value.isoformat()
    if isinstance(value, dict):
        return {str(key): _jsonable_with_secrets(item) for key, item in value.items()}
    if isinstance(value, list | tuple):
        return [_jsonable_with_secrets(item) for item in value]
    return value


def _deployment_spec_json(spec: DeploymentSpec) -> str:
    return json.dumps(_jsonable_with_secrets(spec), ensure_ascii=False)


class EventBus:
    def __init__(self) -> None:
        self._subscribers: set[asyncio.Queue[DeploymentEvent]] = set()

    async def publish(self, event: DeploymentEvent) -> None:
        stale: list[asyncio.Queue[DeploymentEvent]] = []
        for queue in self._subscribers:
            try:
                queue.put_nowait(event)
            except asyncio.QueueFull:
                stale.append(queue)
        for queue in stale:
            self._subscribers.discard(queue)

    async def subscribe(self) -> AsyncIterator[DeploymentEvent]:
        queue: asyncio.Queue[DeploymentEvent] = asyncio.Queue(maxsize=256)
        self._subscribers.add(queue)
        try:
            while True:
                yield await queue.get()
        finally:
            self._subscribers.discard(queue)


class StateStore:
    def __init__(self, path: Path, event_bus: EventBus) -> None:
        self.path = path
        self.event_bus = event_bus
        self._lock = asyncio.Lock()

    async def init(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        async with self._lock:
            conn = self._connect()
            try:
                conn.executescript(
                    """
                    PRAGMA journal_mode=WAL;
                    CREATE TABLE IF NOT EXISTS desired_state (
                        id INTEGER PRIMARY KEY CHECK (id = 1),
                        spec_json TEXT NOT NULL,
                        generation INTEGER NOT NULL,
                        updated_at TEXT NOT NULL
                    );
                    CREATE TABLE IF NOT EXISTS observed_state (
                        id INTEGER PRIMARY KEY CHECK (id = 1),
                        status_json TEXT NOT NULL,
                        updated_at TEXT NOT NULL
                    );
                    CREATE TABLE IF NOT EXISTS events (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        deployment_id TEXT,
                        generation INTEGER NOT NULL,
                        event_type TEXT NOT NULL,
                        level TEXT NOT NULL,
                        message TEXT NOT NULL,
                        progress INTEGER,
                        payload_json TEXT NOT NULL,
                        created_at TEXT NOT NULL
                    );
                    """
                )
                row = conn.execute("SELECT id FROM observed_state WHERE id = 1").fetchone()
                if row is None:
                    status = DeploymentStatus(observed_at=utc_now())
                    conn.execute(
                        """
                        INSERT INTO observed_state (id, status_json, updated_at)
                        VALUES (1, ?, ?)
                        """,
                        (
                            status.model_dump_json(),
                            utc_now().isoformat(),
                        ),
                    )
                conn.commit()
            finally:
                conn.close()

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.path)
        conn.row_factory = sqlite3.Row
        return conn

    async def get_desired(self) -> DeploymentSpec | None:
        async with self._lock:
            conn = self._connect()
            try:
                row = conn.execute("SELECT spec_json FROM desired_state WHERE id = 1").fetchone()
                if row is None:
                    return None
                return DeploymentSpec.model_validate_json(row["spec_json"])
            finally:
                conn.close()

    async def set_desired(self, spec: DeploymentSpec) -> DeploymentStatus:
        async with self._lock:
            conn = self._connect()
            try:
                row = conn.execute("SELECT generation FROM desired_state WHERE id = 1").fetchone()
                if row is not None and spec.generation < int(row["generation"]):
                    raise ValueError("stale_generation")

                now = utc_now().isoformat()
                conn.execute(
                    """
                    INSERT INTO desired_state (id, spec_json, generation, updated_at)
                    VALUES (1, ?, ?, ?)
                    ON CONFLICT(id) DO UPDATE SET
                        spec_json = excluded.spec_json,
                        generation = excluded.generation,
                        updated_at = excluded.updated_at
                    """,
                    (_deployment_spec_json(spec), spec.generation, now),
                )
                status = DeploymentStatus(
                    deployment_id=spec.deployment_id,
                    generation=spec.generation,
                    phase="pending" if spec.desired_phase == "running" else "stopping",
                    progress=0,
                    active_model_name=spec.model.served_name,
                    last_event="desired state accepted",
                    observed_at=utc_now(),
                )
                conn.execute(
                    """
                    INSERT INTO observed_state (id, status_json, updated_at)
                    VALUES (1, ?, ?)
                    ON CONFLICT(id) DO UPDATE SET
                        status_json = excluded.status_json,
                        updated_at = excluded.updated_at
                    """,
                    (status.model_dump_json(), now),
                )
                conn.commit()
                return status
            finally:
                conn.close()

    async def get_status(self) -> DeploymentStatus:
        async with self._lock:
            conn = self._connect()
            try:
                row = conn.execute("SELECT status_json FROM observed_state WHERE id = 1").fetchone()
                if row is None:
                    return DeploymentStatus(observed_at=utc_now())
                return DeploymentStatus.model_validate_json(row["status_json"])
            finally:
                conn.close()

    async def set_status(self, status: DeploymentStatus) -> DeploymentStatus:
        status.observed_at = utc_now()
        async with self._lock:
            conn = self._connect()
            try:
                conn.execute(
                    """
                    INSERT INTO observed_state (id, status_json, updated_at)
                    VALUES (1, ?, ?)
                    ON CONFLICT(id) DO UPDATE SET
                        status_json = excluded.status_json,
                        updated_at = excluded.updated_at
                    """,
                    (status.model_dump_json(), status.observed_at.isoformat()),
                )
                conn.commit()
                return status
            finally:
                conn.close()

    async def add_event(
        self,
        *,
        event_type: str,
        message: str,
        deployment_id: str | None,
        generation: int,
        level: str = "info",
        progress: int | None = None,
        payload: dict[str, Any] | None = None,
    ) -> DeploymentEvent:
        event = DeploymentEvent(
            deployment_id=deployment_id,
            generation=generation,
            event_type=event_type,
            level=level,  # type: ignore[arg-type]
            message=message,
            progress=progress,
            payload=payload or {},
            created_at=utc_now(),
        )
        async with self._lock:
            conn = self._connect()
            try:
                cursor = conn.execute(
                    """
                    INSERT INTO events (
                        deployment_id, generation, event_type, level,
                        message, progress, payload_json, created_at
                    )
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        event.deployment_id,
                        event.generation,
                        event.event_type,
                        event.level,
                        event.message,
                        event.progress,
                        json.dumps(event.payload, default=_json_default),
                        event.created_at.isoformat(),
                    ),
                )
                event.id = int(cursor.lastrowid)
                conn.commit()
            finally:
                conn.close()
        await self.event_bus.publish(event)
        return event

    async def list_events(
        self,
        *,
        deployment_id: str | None = None,
        limit: int = 200,
    ) -> list[DeploymentEvent]:
        bounded_limit = max(1, min(limit, 1000))
        async with self._lock:
            conn = self._connect()
            try:
                if deployment_id:
                    rows = conn.execute(
                        """
                        SELECT * FROM events
                        WHERE deployment_id = ?
                        ORDER BY id DESC
                        LIMIT ?
                        """,
                        (deployment_id, bounded_limit),
                    ).fetchall()
                else:
                    rows = conn.execute(
                        "SELECT * FROM events ORDER BY id DESC LIMIT ?",
                        (bounded_limit,),
                    ).fetchall()
                events = [
                    DeploymentEvent(
                        id=row["id"],
                        deployment_id=row["deployment_id"],
                        generation=row["generation"],
                        event_type=row["event_type"],
                        level=row["level"],
                        message=row["message"],
                        progress=row["progress"],
                        payload=json.loads(row["payload_json"]),
                        created_at=datetime.fromisoformat(row["created_at"]),
                    )
                    for row in rows
                ]
                events.reverse()
                return events
            finally:
                conn.close()
