"""Owner-only SQLite storage for durable goals."""

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

from .models import GoalEvidence, GoalRecord, GoalRequirement, GoalState

_SCHEMA_VERSION = 1
_NOW = "strftime('%Y-%m-%dT%H:%M:%fZ', 'now')"


def _migrate_to_v1(connection: sqlite3.Connection) -> None:
    connection.execute(
        f"""
        CREATE TABLE IF NOT EXISTS goals (
            goal_id TEXT PRIMARY KEY,
            session_id TEXT NOT NULL,
            objective TEXT NOT NULL,
            requirements TEXT NOT NULL,
            continuation_prompt TEXT NOT NULL,
            token_budget INTEGER,
            time_budget_seconds INTEGER,
            state TEXT NOT NULL,
            tokens_used INTEGER NOT NULL,
            continuation_count INTEGER NOT NULL,
            continuation_running INTEGER NOT NULL,
            baseline_message_count INTEGER NOT NULL,
            continuation_turn_id TEXT NOT NULL,
            turn_started_at TEXT NOT NULL,
            evidence TEXT NOT NULL,
            audit_summary TEXT NOT NULL,
            requirement_evidence TEXT NOT NULL,
            created_at TEXT NOT NULL DEFAULT ({_NOW}),
            updated_at TEXT NOT NULL DEFAULT ({_NOW}),
            version INTEGER NOT NULL DEFAULT 0
        )
        """
    )
    connection.execute(
        """
        CREATE INDEX IF NOT EXISTS goals_session_created
        ON goals(session_id, created_at, goal_id)
        """
    )


class GoalStore:
    def __init__(self, data_dir: str | Path) -> None:
        self.base = Path(data_dir).expanduser().resolve()
        secure_directory(self.base)
        self.db_path = self.base / "goals.db"
        self._lock = threading.RLock()
        previous_version = prepare_sqlite_database(
            self.db_path,
            _SCHEMA_VERSION,
            "goal",
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

    def create(self, record: GoalRecord) -> GoalRecord:
        try:
            with self._lock, self._connection:
                self._connection.execute(
                    f"""
                    INSERT INTO goals (
                        goal_id, session_id, objective, requirements,
                        continuation_prompt, token_budget,
                        time_budget_seconds, state, tokens_used,
                        continuation_count, continuation_running,
                        baseline_message_count, continuation_turn_id,
                        turn_started_at, evidence,
                        audit_summary, requirement_evidence,
                        created_at, updated_at, version
                    )
                    VALUES (
                        ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?,
                        {_NOW}, {_NOW}, 0
                    )
                    """,
                    _values(record),
                )
        except sqlite3.IntegrityError:
            raise ValueError("goal already exists") from None
        created = self.load(record.goal_id)
        assert created is not None
        return created

    def load(self, goal_id: str) -> GoalRecord | None:
        with self._lock:
            row = self._connection.execute(
                "SELECT * FROM goals WHERE goal_id = ?",
                (goal_id,),
            ).fetchone()
        return _from_row(row) if row is not None else None

    def list(self, session_id: str) -> list[GoalRecord]:
        with self._lock:
            rows = self._connection.execute(
                """
                SELECT * FROM goals
                WHERE session_id = ?
                ORDER BY created_at, goal_id
                LIMIT 100
                """,
                (session_id,),
            ).fetchall()
        return [_from_row(row) for row in rows]

    def list_running(self) -> list[GoalRecord]:
        with self._lock:
            rows = self._connection.execute(
                """
                SELECT * FROM goals
                WHERE continuation_running = 1
                ORDER BY created_at, goal_id
                """
            ).fetchall()
        return [_from_row(row) for row in rows]

    def save(
        self,
        record: GoalRecord,
        *,
        expected_version: int,
    ) -> GoalRecord | None:
        candidate = replace(record, version=expected_version + 1)
        with self._lock, self._connection:
            cursor = self._connection.execute(
                f"""
                UPDATE goals
                SET objective = ?, requirements = ?,
                    continuation_prompt = ?, token_budget = ?,
                    time_budget_seconds = ?, state = ?, tokens_used = ?,
                    continuation_count = ?, continuation_running = ?,
                    baseline_message_count = ?, continuation_turn_id = ?,
                    turn_started_at = ?,
                    evidence = ?, audit_summary = ?,
                    requirement_evidence = ?, updated_at = {_NOW},
                    version = ?
                WHERE goal_id = ? AND version = ?
                """,
                (
                    candidate.objective,
                    _requirements(candidate.requirements),
                    candidate.continuation_prompt,
                    candidate.token_budget,
                    candidate.time_budget_seconds,
                    candidate.state.value,
                    candidate.tokens_used,
                    candidate.continuation_count,
                    int(candidate.continuation_running),
                    candidate.baseline_message_count,
                    candidate.continuation_turn_id,
                    candidate.turn_started_at,
                    _evidence(candidate.evidence),
                    candidate.audit_summary,
                    _mapping(candidate.requirement_evidence),
                    candidate.version,
                    candidate.goal_id,
                    expected_version,
                ),
            )
        return self.load(record.goal_id) if cursor.rowcount == 1 else None


def _values(record: GoalRecord) -> tuple[object, ...]:
    return (
        record.goal_id,
        record.session_id,
        record.objective,
        _requirements(record.requirements),
        record.continuation_prompt,
        record.token_budget,
        record.time_budget_seconds,
        record.state.value,
        record.tokens_used,
        record.continuation_count,
        int(record.continuation_running),
        record.baseline_message_count,
        record.continuation_turn_id,
        record.turn_started_at,
        _evidence(record.evidence),
        record.audit_summary,
        _mapping(record.requirement_evidence),
    )


def _requirements(items: tuple[GoalRequirement, ...]) -> str:
    return _encode(
        [
            {
                "requirement_id": item.requirement_id,
                "text": item.text,
            }
            for item in items
        ]
    )


def _evidence(items: tuple[GoalEvidence, ...]) -> str:
    return _encode([item.__dict__ for item in items])


def _mapping(items: tuple[tuple[str, tuple[str, ...]], ...]) -> str:
    return _encode(
        {
            requirement_id: list(evidence)
            for requirement_id, evidence in items
        }
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
        raise ValueError("corrupt goal store") from None
    if not isinstance(decoded, expected):
        raise ValueError("corrupt goal store")
    return decoded


def _from_row(row: sqlite3.Row) -> GoalRecord:
    requirements = _decode(row["requirements"], list)
    evidence = _decode(row["evidence"], list)
    mapping = _decode(row["requirement_evidence"], dict)
    return GoalRecord(
        goal_id=row["goal_id"],
        session_id=row["session_id"],
        objective=row["objective"],
        requirements=tuple(
            GoalRequirement(
                requirement_id=item["requirement_id"],
                text=item["text"],
            )
            for item in requirements
        ),
        continuation_prompt=row["continuation_prompt"],
        token_budget=row["token_budget"],
        time_budget_seconds=row["time_budget_seconds"],
        state=GoalState(row["state"]),
        tokens_used=row["tokens_used"],
        continuation_count=row["continuation_count"],
        continuation_running=bool(row["continuation_running"]),
        baseline_message_count=row["baseline_message_count"],
        continuation_turn_id=row["continuation_turn_id"],
        turn_started_at=row["turn_started_at"],
        evidence=tuple(GoalEvidence(**item) for item in evidence),
        audit_summary=row["audit_summary"],
        requirement_evidence=tuple(
            (str(requirement_id), tuple(items))
            for requirement_id, items in sorted(mapping.items())
        ),
        created_at=row["created_at"],
        updated_at=row["updated_at"],
        version=row["version"],
    )
