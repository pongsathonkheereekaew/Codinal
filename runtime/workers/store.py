"""Owner-only SQLite storage for worker lifecycle state."""

from __future__ import annotations

import json
import sqlite3
import threading
from pathlib import Path

from runtime.storage.migrations import (
    create_private_file,
    prepare_sqlite_database,
    run_sqlite_migrations,
    secure_directory,
    secure_file,
)

from .models import (
    ALLOWED_WORKER_TRANSITIONS,
    WorkerRecord,
    WorkerState,
)

_SCHEMA_VERSION = 2
_NOW = "strftime('%Y-%m-%dT%H:%M:%fZ', 'now')"


def _migrate_to_v1(connection: sqlite3.Connection) -> None:
    connection.execute(
        f"""
        CREATE TABLE IF NOT EXISTS workers (
            worker_id TEXT PRIMARY KEY,
            parent_session_id TEXT NOT NULL,
            child_session_id TEXT NOT NULL UNIQUE,
            task TEXT NOT NULL,
            ownership TEXT NOT NULL,
            dependencies TEXT NOT NULL,
            model TEXT NOT NULL,
            state TEXT NOT NULL,
            worker_kind TEXT NOT NULL,
            protocol_version TEXT NOT NULL,
            capabilities TEXT NOT NULL,
            summary TEXT NOT NULL DEFAULT '',
            error TEXT NOT NULL DEFAULT '',
            commit_hash TEXT NOT NULL DEFAULT '',
            created_at TEXT NOT NULL DEFAULT ({_NOW}),
            updated_at TEXT NOT NULL DEFAULT ({_NOW})
        )
        """
    )
    connection.execute(
        """
        CREATE INDEX IF NOT EXISTS workers_parent_created
        ON workers(parent_session_id, created_at, worker_id)
        """
    )


def _migrate_to_v2(connection: sqlite3.Connection) -> None:
    connection.execute(
        "ALTER TABLE workers ADD COLUMN build_id TEXT NOT NULL DEFAULT ''"
    )
    connection.execute(
        "ALTER TABLE workers ADD COLUMN plan_task_id TEXT NOT NULL DEFAULT ''"
    )
    connection.execute(
        "ALTER TABLE workers ADD COLUMN candidate_index INTEGER NOT NULL DEFAULT -1"
    )
    connection.execute(
        """
        CREATE INDEX IF NOT EXISTS workers_build
        ON workers(build_id, plan_task_id, candidate_index)
        """
    )


class WorkerStore:
    def __init__(self, base_dir: str | Path) -> None:
        self.base = Path(base_dir).expanduser().resolve()
        secure_directory(self.base)
        self.db_path = self.base / "workers.db"
        self._lock = threading.RLock()
        previous_version = prepare_sqlite_database(
            self.db_path,
            _SCHEMA_VERSION,
            "worker",
        )
        if not self.db_path.exists():
            create_private_file(self.db_path)
        secure_file(self.db_path)
        self._connection = sqlite3.connect(
            self.db_path,
            check_same_thread=False,
        )
        self._connection.row_factory = sqlite3.Row
        self._connection.execute("PRAGMA journal_mode = DELETE")
        self._connection.execute("PRAGMA synchronous = FULL")
        run_sqlite_migrations(
            self._connection,
            previous_version,
            _SCHEMA_VERSION,
            {1: _migrate_to_v1, 2: _migrate_to_v2},
        )
        secure_file(self.db_path)

    def close(self) -> None:
        with self._lock:
            self._connection.close()

    def create(self, record: WorkerRecord) -> WorkerRecord:
        with self._lock:
            for dependency_id in record.dependencies:
                dependency = self._connection.execute(
                    """
                    SELECT parent_session_id
                    FROM workers
                    WHERE worker_id = ?
                    """,
                    (dependency_id,),
                ).fetchone()
                if dependency is None:
                    raise ValueError("worker dependency does not exist")
                if dependency["parent_session_id"] != record.parent_session_id:
                    raise ValueError(
                        "worker dependency belongs to another parent"
                    )
            try:
                with self._connection:
                    self._connection.execute(
                        f"""
                        INSERT INTO workers (
                            worker_id, parent_session_id, child_session_id,
                            task, ownership, dependencies, model, state,
                            worker_kind, protocol_version, capabilities,
                            summary, error, commit_hash, build_id,
                            plan_task_id, candidate_index,
                            created_at, updated_at
                        )
                        VALUES (
                            ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?,
                            {_NOW}, {_NOW}
                        )
                        """,
                        _record_values(record),
                    )
            except sqlite3.IntegrityError:
                raise ValueError("worker already exists") from None
        created = self.load(record.worker_id)
        assert created is not None
        return created

    def load(self, worker_id: str) -> WorkerRecord | None:
        with self._lock:
            row = self._connection.execute(
                "SELECT * FROM workers WHERE worker_id = ?",
                (worker_id,),
            ).fetchone()
        return _from_row(row) if row is not None else None

    def load_by_child_session(
        self,
        child_session_id: str,
    ) -> WorkerRecord | None:
        with self._lock:
            row = self._connection.execute(
                "SELECT * FROM workers WHERE child_session_id = ?",
                (child_session_id,),
            ).fetchone()
        return _from_row(row) if row is not None else None

    def list_non_terminal(self) -> list[WorkerRecord]:
        terminal = (
            WorkerState.SUCCEEDED.value,
            WorkerState.ADOPTED.value,
            WorkerState.FAILED.value,
            WorkerState.CANCELLED.value,
        )
        with self._lock:
            rows = self._connection.execute(
                """
                SELECT * FROM workers
                WHERE state NOT IN (?, ?, ?, ?)
                ORDER BY created_at, worker_id
                """,
                terminal,
            ).fetchall()
        return [_from_row(row) for row in rows]

    def list(self, parent_session_id: str) -> list[WorkerRecord]:
        with self._lock:
            rows = self._connection.execute(
                """
                SELECT * FROM workers
                WHERE parent_session_id = ?
                ORDER BY created_at, worker_id
                """,
                (parent_session_id,),
            ).fetchall()
        return [_from_row(row) for row in rows]

    def transition(
        self,
        worker_id: str,
        *,
        expected: set[WorkerState],
        target: WorkerState,
        summary: str | None = None,
        error: str | None = None,
        commit: str | None = None,
    ) -> WorkerRecord | None:
        current = self.load(worker_id)
        if current is None or current.state not in expected:
            return None
        if target not in ALLOWED_WORKER_TRANSITIONS[current.state]:
            raise ValueError("invalid worker state transition")
        candidate = WorkerRecord(
            **{
                **current.__dict__,
                "state": target,
                "summary": current.summary if summary is None else summary,
                "error": current.error if error is None else error,
                "commit": current.commit if commit is None else commit,
            }
        )
        with self._lock, self._connection:
            cursor = self._connection.execute(
                f"""
                UPDATE workers
                SET state = ?, summary = ?, error = ?, commit_hash = ?,
                    updated_at = {_NOW}
                WHERE worker_id = ? AND state IN (
                    {",".join("?" for _ in expected)}
                )
                """,
                (
                    target.value,
                    candidate.summary,
                    candidate.error,
                    candidate.commit,
                    worker_id,
                    *(state.value for state in sorted(expected, key=str)),
                ),
            )
        return self.load(worker_id) if cursor.rowcount == 1 else None

    def transition_many(
        self,
        worker_ids: tuple[str, ...],
        *,
        expected: set[WorkerState],
        target: WorkerState,
    ) -> tuple[WorkerRecord, ...] | None:
        if (
            not worker_ids
            or len(worker_ids) != len(set(worker_ids))
            or not expected
        ):
            raise ValueError("invalid worker batch transition")
        placeholders = ",".join("?" for _ in worker_ids)
        expected_values = tuple(
            state.value for state in sorted(expected, key=str)
        )
        with self._lock, self._connection:
            rows = self._connection.execute(
                f"""
                SELECT worker_id, state
                FROM workers
                WHERE worker_id IN ({placeholders})
                """,
                worker_ids,
            ).fetchall()
            if (
                len(rows) != len(worker_ids)
                or any(
                    WorkerState(row["state"]) not in expected
                    for row in rows
                )
            ):
                return None
            if any(
                target
                not in ALLOWED_WORKER_TRANSITIONS[
                    WorkerState(row["state"])
                ]
                for row in rows
            ):
                raise ValueError("invalid worker state transition")
            cursor = self._connection.execute(
                f"""
                UPDATE workers
                SET state = ?, updated_at = {_NOW}
                WHERE worker_id IN ({placeholders})
                  AND state IN (
                    {",".join("?" for _ in expected_values)}
                  )
                """,
                (target.value, *worker_ids, *expected_values),
            )
            if cursor.rowcount != len(worker_ids):
                raise RuntimeError("worker batch transition failed")
        records = tuple(self.load(worker_id) for worker_id in worker_ids)
        if any(record is None for record in records):
            raise RuntimeError("worker batch transition disappeared")
        return tuple(record for record in records if record is not None)


def _record_values(record: WorkerRecord) -> tuple[object, ...]:
    return (
        record.worker_id,
        record.parent_session_id,
        record.child_session_id,
        record.task,
        _encode(record.ownership),
        _encode(record.dependencies),
        record.model,
        record.state.value,
        record.worker_kind,
        record.protocol_version,
        _encode(sorted(record.capabilities)),
        record.summary,
        record.error,
        record.commit,
        record.build_id,
        record.plan_task_id,
        record.candidate_index,
    )


def _encode(value: object) -> str:
    return json.dumps(
        value,
        allow_nan=False,
        ensure_ascii=False,
        separators=(",", ":"),
    )


def _decode(value: str, expected: type) -> object:
    try:
        decoded = json.loads(value)
    except (TypeError, json.JSONDecodeError):
        raise ValueError("corrupt worker store") from None
    if not isinstance(decoded, expected):
        raise ValueError("corrupt worker store")
    return decoded


def _from_row(row: sqlite3.Row) -> WorkerRecord:
    return WorkerRecord(
        worker_id=row["worker_id"],
        parent_session_id=row["parent_session_id"],
        child_session_id=row["child_session_id"],
        task=row["task"],
        ownership=tuple(_decode(row["ownership"], list)),
        dependencies=tuple(_decode(row["dependencies"], list)),
        model=row["model"],
        state=WorkerState(row["state"]),
        worker_kind=row["worker_kind"],
        protocol_version=row["protocol_version"],
        capabilities=frozenset(_decode(row["capabilities"], list)),
        summary=row["summary"],
        error=row["error"],
        commit=row["commit_hash"],
        build_id=row["build_id"],
        plan_task_id=row["plan_task_id"],
        candidate_index=int(row["candidate_index"]),
        created_at=row["created_at"],
        updated_at=row["updated_at"],
    )
