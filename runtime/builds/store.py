"""Owner-only SQLite persistence for plan build selection state."""

from __future__ import annotations

import json
import sqlite3
import threading
from dataclasses import replace
from pathlib import Path

from runtime.storage.migrations import (
    create_private_file,
    prepare_sqlite_database,
    run_sqlite_migrations,
    secure_directory,
    secure_file,
)

from .models import (
    ALLOWED_PLAN_BUILD_TRANSITIONS,
    PlanBuildCandidate,
    PlanBuildRecord,
    PlanBuildState,
    PlanBuildTask,
    TERMINAL_PLAN_BUILD_STATES,
)

_SCHEMA_VERSION = 1
_NOW = "strftime('%Y-%m-%dT%H:%M:%fZ', 'now')"


def _migrate_to_v1(connection: sqlite3.Connection) -> None:
    connection.execute(
        f"""
        CREATE TABLE IF NOT EXISTS plan_builds (
            build_id TEXT PRIMARY KEY,
            parent_session_id TEXT NOT NULL,
            plan_id TEXT NOT NULL,
            tasks TEXT NOT NULL,
            state TEXT NOT NULL,
            error TEXT NOT NULL DEFAULT '',
            created_at TEXT NOT NULL DEFAULT ({_NOW}),
            updated_at TEXT NOT NULL DEFAULT ({_NOW})
        )
        """
    )
    connection.execute(
        """
        CREATE INDEX IF NOT EXISTS plan_builds_parent_created
        ON plan_builds(parent_session_id, created_at, build_id)
        """
    )


class PlanBuildStore:
    def __init__(self, base_dir: str | Path) -> None:
        self.base = Path(base_dir).expanduser().resolve()
        secure_directory(self.base)
        self.db_path = self.base / "plan-builds.db"
        self._lock = threading.RLock()
        previous_version = prepare_sqlite_database(
            self.db_path,
            _SCHEMA_VERSION,
            "plan build",
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
            {1: _migrate_to_v1},
        )
        secure_file(self.db_path)

    def close(self) -> None:
        with self._lock:
            self._connection.close()

    def create(self, record: PlanBuildRecord) -> PlanBuildRecord:
        try:
            with self._lock, self._connection:
                self._connection.execute(
                    f"""
                    INSERT INTO plan_builds (
                        build_id, parent_session_id, plan_id, tasks,
                        state, error, created_at, updated_at
                    )
                    VALUES (?, ?, ?, ?, ?, ?, {_NOW}, {_NOW})
                    """,
                    (
                        record.build_id,
                        record.parent_session_id,
                        record.plan_id,
                        _encode_tasks(record.tasks),
                        record.state.value,
                        record.error,
                    ),
                )
        except sqlite3.IntegrityError:
            raise ValueError("plan build already exists") from None
        created = self.load(record.build_id)
        assert created is not None
        return created

    def load(self, build_id: str) -> PlanBuildRecord | None:
        with self._lock:
            row = self._connection.execute(
                "SELECT * FROM plan_builds WHERE build_id = ?",
                (build_id,),
            ).fetchone()
        return _from_row(row) if row is not None else None

    def list(self, parent_session_id: str) -> list[PlanBuildRecord]:
        with self._lock:
            rows = self._connection.execute(
                """
                SELECT * FROM plan_builds
                WHERE parent_session_id = ?
                ORDER BY created_at, build_id
                LIMIT 100
                """,
                (parent_session_id,),
            ).fetchall()
        return [_from_row(row) for row in rows]

    def list_non_terminal(self) -> list[PlanBuildRecord]:
        terminal = tuple(state.value for state in TERMINAL_PLAN_BUILD_STATES)
        with self._lock:
            rows = self._connection.execute(
                """
                SELECT * FROM plan_builds
                WHERE state NOT IN (?, ?)
                ORDER BY created_at, build_id
                """,
                terminal,
            ).fetchall()
        return [_from_row(row) for row in rows]

    def attach_candidate(
        self,
        build_id: str,
        task_id: str,
        candidate_index: int,
        worker_id: str,
    ) -> PlanBuildRecord:
        record = self._require(build_id)
        if record.state is not PlanBuildState.DISPATCHING:
            raise ValueError("plan build is not dispatching")
        tasks = list(record.tasks)
        try:
            task_index = next(
                index
                for index, task in enumerate(tasks)
                if task.task_id == task_id
            )
            task = tasks[task_index]
            candidate = task.candidates[candidate_index]
        except (StopIteration, IndexError):
            raise ValueError("invalid plan build candidate") from None
        if candidate.worker_id:
            raise ValueError("plan build candidate already attached")
        candidates = list(task.candidates)
        candidates[candidate_index] = replace(candidate, worker_id=worker_id)
        tasks[task_index] = replace(task, candidates=tuple(candidates))
        return self._update_tasks(record, tuple(tasks))

    def select(
        self,
        build_id: str,
        worker_id: str,
    ) -> PlanBuildRecord:
        record = self._require(build_id)
        if record.state not in {
            PlanBuildState.READY,
            PlanBuildState.SELECTED,
        }:
            raise ValueError("plan build is not ready for selection")
        tasks = list(record.tasks)
        for index, task in enumerate(tasks):
            if worker_id in {
                candidate.worker_id for candidate in task.candidates
            }:
                tasks[index] = replace(
                    task,
                    selected_worker_id=worker_id,
                )
                return self._update_tasks(record, tuple(tasks))
        raise ValueError("worker is not a candidate in this plan build")

    def transition(
        self,
        build_id: str,
        *,
        expected: set[PlanBuildState],
        target: PlanBuildState,
        error: str | None = None,
    ) -> PlanBuildRecord | None:
        current = self.load(build_id)
        if current is None or current.state not in expected:
            return None
        if target not in ALLOWED_PLAN_BUILD_TRANSITIONS[current.state]:
            raise ValueError("invalid plan build state transition")
        candidate = replace(
            current,
            state=target,
            error=current.error if error is None else error,
        )
        with self._lock, self._connection:
            cursor = self._connection.execute(
                f"""
                UPDATE plan_builds
                SET state = ?, error = ?, updated_at = {_NOW}
                WHERE build_id = ? AND state IN (
                    {",".join("?" for _ in expected)}
                )
                """,
                (
                    target.value,
                    candidate.error,
                    build_id,
                    *(
                        state.value
                        for state in sorted(expected, key=lambda item: item.value)
                    ),
                ),
            )
        return self.load(build_id) if cursor.rowcount == 1 else None

    def _update_tasks(
        self,
        current: PlanBuildRecord,
        tasks: tuple[PlanBuildTask, ...],
    ) -> PlanBuildRecord:
        candidate = replace(current, tasks=tasks)
        with self._lock, self._connection:
            cursor = self._connection.execute(
                f"""
                UPDATE plan_builds
                SET tasks = ?, updated_at = {_NOW}
                WHERE build_id = ? AND state = ?
                """,
                (
                    _encode_tasks(candidate.tasks),
                    current.build_id,
                    current.state.value,
                ),
            )
        if cursor.rowcount != 1:
            raise ValueError("plan build state changed")
        return self._require(current.build_id)

    def _require(self, build_id: str) -> PlanBuildRecord:
        record = self.load(build_id)
        if record is None:
            raise KeyError(build_id)
        return record


def _encode_tasks(tasks: tuple[PlanBuildTask, ...]) -> str:
    return json.dumps(
        [
            {
                "task_id": task.task_id,
                "title": task.title,
                "description": task.description,
                "verification": task.verification,
                "ownership": list(task.ownership),
                "selected_worker_id": task.selected_worker_id,
                "candidates": [
                    {
                        "model": candidate.model,
                        "instruction": candidate.instruction,
                        "worker_id": candidate.worker_id,
                    }
                    for candidate in task.candidates
                ],
            }
            for task in tasks
        ],
        allow_nan=False,
        ensure_ascii=False,
        separators=(",", ":"),
    )


def _decode_tasks(value: str) -> tuple[PlanBuildTask, ...]:
    try:
        decoded = json.loads(value)
        return tuple(
            PlanBuildTask(
                task_id=item["task_id"],
                title=item["title"],
                description=item["description"],
                verification=item["verification"],
                ownership=tuple(item["ownership"]),
                selected_worker_id=item["selected_worker_id"],
                candidates=tuple(
                    PlanBuildCandidate(
                        model=candidate["model"],
                        instruction=candidate["instruction"],
                        worker_id=candidate["worker_id"],
                    )
                    for candidate in item["candidates"]
                ),
            )
            for item in decoded
        )
    except (KeyError, TypeError, ValueError, json.JSONDecodeError):
        raise ValueError("corrupt plan build store") from None


def _from_row(row: sqlite3.Row) -> PlanBuildRecord:
    return PlanBuildRecord(
        build_id=row["build_id"],
        parent_session_id=row["parent_session_id"],
        plan_id=row["plan_id"],
        tasks=_decode_tasks(row["tasks"]),
        state=PlanBuildState(row["state"]),
        error=row["error"],
        created_at=row["created_at"],
        updated_at=row["updated_at"],
    )
