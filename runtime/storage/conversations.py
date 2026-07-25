# SPDX-License-Identifier: MIT
# Copyright (c) 2024 Andrew Ng
# Adapted from andrewyng/openworker:
# coworker/conversations.py @ 54b4bfd82d75704a4079ecea4f8f622aa152dbde.
"""Transactional SQLite conversation and session metadata store."""

from __future__ import annotations

import json
import re
import sqlite3
import threading
from pathlib import Path
from typing import Any, Optional

from runtime.sessions import SessionRecord

from .errors import ExportTooLargeError
from .migrations import (
    create_private_file,
    prepare_sqlite_database,
    run_sqlite_migrations,
    secure_directory,
    secure_file,
)

_SESSION_ID = re.compile(r"[A-Za-z0-9][A-Za-z0-9_-]{0,127}")
_NOW = "strftime('%Y-%m-%dT%H:%M:%fZ', 'now')"
_SCHEMA_VERSION = 2
MAX_EXPORT_STORED_BYTES = 32 * 1024 * 1024


def _migrate_to_v1(connection: sqlite3.Connection) -> None:
    connection.execute(
        f"""
        CREATE TABLE IF NOT EXISTS sessions (
            session_id TEXT PRIMARY KEY,
            workspace TEXT NOT NULL,
            model TEXT NOT NULL,
            mode TEXT NOT NULL,
            title TEXT,
            agent TEXT NOT NULL DEFAULT 'code',
            extra_roots TEXT NOT NULL DEFAULT '[]',
            grants TEXT NOT NULL DEFAULT '{{}}',
            pinned INTEGER NOT NULL DEFAULT 0,
            archived INTEGER NOT NULL DEFAULT 0,
            origin TEXT,
            origin_label TEXT,
            updated_at TEXT NOT NULL DEFAULT ({_NOW})
        )
        """
    )
    connection.execute(
        """
        CREATE TABLE IF NOT EXISTS messages (
            session_id TEXT NOT NULL,
            sequence INTEGER NOT NULL,
            payload TEXT NOT NULL,
            PRIMARY KEY (session_id, sequence),
            FOREIGN KEY (session_id) REFERENCES sessions(session_id)
                ON DELETE CASCADE
        )
        """
    )
    connection.execute(
        f"""
        CREATE TABLE IF NOT EXISTS workspaces (
            path TEXT PRIMARY KEY,
            last_used TEXT NOT NULL DEFAULT ({_NOW})
        )
        """
    )


def _migrate_to_v2(connection: sqlite3.Connection) -> None:
    columns = {
        row["name"]
        for row in connection.execute("PRAGMA table_info(sessions)")
    }
    if "source_workspace" not in columns:
        connection.execute(
            "ALTER TABLE sessions ADD COLUMN source_workspace TEXT"
        )


_MIGRATIONS = {
    1: _migrate_to_v1,
    2: _migrate_to_v2,
}


class ConversationStore:
    def __init__(self, base_dir: str | Path) -> None:
        self.base = Path(base_dir).expanduser().resolve()
        secure_directory(self.base)
        self.db_path = self.base / "codinal.db"
        self._lock = threading.RLock()
        previous_version = prepare_sqlite_database(
            self.db_path,
            _SCHEMA_VERSION,
            "conversation",
        )
        if not self.db_path.exists():
            create_private_file(self.db_path)
        secure_file(self.db_path)
        self._connection = sqlite3.connect(
            self.db_path,
            check_same_thread=False,
        )
        self._connection.row_factory = sqlite3.Row
        self._connection.execute("PRAGMA foreign_keys = ON")
        # One sidecar owns this database and serializes access with _lock.
        # DELETE journaling avoids leaving a persistent WAL with weaker
        # filesystem permissions beside private conversation content.
        self._connection.execute("PRAGMA journal_mode = DELETE")
        self._connection.execute("PRAGMA synchronous = FULL")
        run_sqlite_migrations(
            self._connection,
            previous_version,
            _SCHEMA_VERSION,
            _MIGRATIONS,
        )
        if previous_version < _SCHEMA_VERSION:
            self._connection.execute("PRAGMA optimize")
        secure_file(self.db_path)

    def close(self) -> None:
        with self._lock:
            self._connection.close()

    def save(self, record: SessionRecord) -> None:
        _validate_session_id(record.session_id)
        _validate_record(record)
        messages = [_encode_json(message) for message in record.messages]
        extra_roots = _encode_json(record.extra_roots or [])
        grants = _encode_json(record.grants or {})
        title = record.title or _title_from(record.messages)

        with self._lock, self._connection:
            self._connection.execute(
                f"""
                INSERT INTO sessions (
                    session_id, workspace, source_workspace, model, mode,
                    title, agent,
                    extra_roots, grants, pinned, archived, origin,
                    origin_label, updated_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, {_NOW})
                ON CONFLICT(session_id) DO UPDATE SET
                    workspace = excluded.workspace,
                    source_workspace = excluded.source_workspace,
                    model = excluded.model,
                    mode = excluded.mode,
                    title = excluded.title,
                    agent = excluded.agent,
                    extra_roots = excluded.extra_roots,
                    grants = excluded.grants,
                    pinned = excluded.pinned,
                    archived = excluded.archived,
                    origin = excluded.origin,
                    origin_label = excluded.origin_label,
                    updated_at = excluded.updated_at
                """,
                (
                    record.session_id,
                    record.workspace,
                    record.source_workspace,
                    record.model,
                    record.mode,
                    title,
                    record.agent,
                    extra_roots,
                    grants,
                    int(record.pinned),
                    int(record.archived),
                    record.origin,
                    record.origin_label,
                ),
            )
            existing = [
                row["payload"]
                for row in self._connection.execute(
                    """
                    SELECT payload FROM messages
                    WHERE session_id = ?
                    ORDER BY sequence
                    """,
                    (record.session_id,),
                )
            ]
            if messages[: len(existing)] == existing:
                for sequence, payload in enumerate(
                    messages[len(existing) :],
                    start=len(existing),
                ):
                    self._connection.execute(
                        """
                        INSERT INTO messages (session_id, sequence, payload)
                        VALUES (?, ?, ?)
                        """,
                        (record.session_id, sequence, payload),
                    )
            elif messages != existing:
                self._connection.execute(
                    "DELETE FROM messages WHERE session_id = ?",
                    (record.session_id,),
                )
                self._connection.executemany(
                    """
                    INSERT INTO messages (session_id, sequence, payload)
                    VALUES (?, ?, ?)
                    """,
                    (
                        (record.session_id, sequence, payload)
                        for sequence, payload in enumerate(messages)
                    ),
                )
            self._touch_workspace(
                record.source_workspace or record.workspace
            )

    def load(self, session_id: str) -> Optional[SessionRecord]:
        _validate_session_id(session_id)
        with self._lock:
            row = self._connection.execute(
                "SELECT * FROM sessions WHERE session_id = ?",
                (session_id,),
            ).fetchone()
            if row is None:
                return None
            messages = [
                _decode_json(message["payload"], expected=dict)
                for message in self._connection.execute(
                    """
                    SELECT payload FROM messages
                    WHERE session_id = ?
                    ORDER BY sequence
                    """,
                    (session_id,),
                )
            ]
        return _record_from_row(row, messages=messages)

    def list(
        self,
        *,
        workspace: Optional[str] = None,
    ) -> list[SessionRecord]:
        with self._lock:
            if workspace is None:
                rows = self._connection.execute(
                    """
                    SELECT sessions.*,
                        COUNT(messages.sequence) AS message_count
                    FROM sessions
                    LEFT JOIN messages USING (session_id)
                    GROUP BY sessions.session_id
                    ORDER BY pinned DESC, updated_at DESC
                    """
                ).fetchall()
            else:
                rows = self._connection.execute(
                    """
                    SELECT sessions.*,
                        COUNT(messages.sequence) AS message_count
                    FROM sessions
                    LEFT JOIN messages USING (session_id)
                    WHERE COALESCE(source_workspace, workspace) = ?
                    GROUP BY sessions.session_id
                    ORDER BY pinned DESC, updated_at DESC
                    """,
                    (workspace,),
                ).fetchall()
        return [
            _record_from_row(
                row,
                messages=[],
                message_count=int(row["message_count"]),
            )
            for row in rows
        ]

    def export_records(self) -> list[SessionRecord]:
        """Read complete records under one lock for a consistent export."""
        with self._lock:
            session_bytes = self._connection.execute(
                """
                SELECT COALESCE(SUM(
                    LENGTH(CAST(session_id AS BLOB))
                    + LENGTH(CAST(workspace AS BLOB))
                    + COALESCE(
                        LENGTH(CAST(source_workspace AS BLOB)), 0
                    )
                    + LENGTH(CAST(model AS BLOB))
                    + LENGTH(CAST(mode AS BLOB))
                    + COALESCE(LENGTH(CAST(title AS BLOB)), 0)
                    + LENGTH(CAST(agent AS BLOB))
                    + LENGTH(CAST(extra_roots AS BLOB))
                    + LENGTH(CAST(grants AS BLOB))
                    + COALESCE(LENGTH(CAST(origin AS BLOB)), 0)
                    + COALESCE(LENGTH(CAST(origin_label AS BLOB)), 0)
                    + LENGTH(CAST(updated_at AS BLOB))
                ), 0)
                FROM sessions
                WHERE substr(session_id, 1, 2) != '__'
                """
            ).fetchone()[0]
            message_bytes = self._connection.execute(
                """
                SELECT COALESCE(
                    SUM(LENGTH(CAST(messages.payload AS BLOB))),
                    0
                )
                FROM messages
                JOIN sessions USING (session_id)
                WHERE substr(sessions.session_id, 1, 2) != '__'
                """
            ).fetchone()[0]
            if session_bytes + message_bytes > MAX_EXPORT_STORED_BYTES:
                raise ExportTooLargeError(
                    "conversation export exceeds its safety limit"
                )
            rows = self._connection.execute(
                """
                SELECT * FROM sessions
                WHERE substr(session_id, 1, 2) != '__'
                ORDER BY pinned DESC, updated_at DESC
                """
            ).fetchall()
            return [
                _record_from_row(
                    row,
                    messages=[
                        _decode_json(message["payload"], expected=dict)
                        for message in self._connection.execute(
                            """
                            SELECT payload FROM messages
                            WHERE session_id = ?
                            ORDER BY sequence
                            """,
                            (row["session_id"],),
                        )
                    ],
                )
                for row in rows
            ]

    def rename(self, session_id: str, title: str) -> bool:
        _validate_session_id(session_id)
        with self._lock, self._connection:
            cursor = self._connection.execute(
                f"""
                UPDATE sessions
                SET title = ?, updated_at = {_NOW}
                WHERE session_id = ?
                """,
                (title, session_id),
            )
            return cursor.rowcount == 1

    def set_flags(
        self,
        session_id: str,
        *,
        pinned: Optional[bool] = None,
        archived: Optional[bool] = None,
    ) -> bool:
        _validate_session_id(session_id)
        assignments = []
        values: list[Any] = []
        if pinned is not None:
            assignments.append("pinned = ?")
            values.append(int(pinned))
        if archived is not None:
            assignments.append("archived = ?")
            values.append(int(archived))
        if not assignments:
            return self.load(session_id) is not None
        values.append(session_id)
        with self._lock, self._connection:
            cursor = self._connection.execute(
                f"""
                UPDATE sessions
                SET {", ".join(assignments)}, updated_at = {_NOW}
                WHERE session_id = ?
                """,
                values,
            )
            return cursor.rowcount == 1

    def delete(self, session_id: str) -> bool:
        _validate_session_id(session_id)
        with self._lock, self._connection:
            cursor = self._connection.execute(
                "DELETE FROM sessions WHERE session_id = ?",
                (session_id,),
            )
            return cursor.rowcount == 1

    def set_extra_roots(
        self,
        session_id: str,
        extra_roots: list[dict[str, Any]],
    ) -> None:
        _validate_session_id(session_id)
        encoded = _encode_json(extra_roots)
        with self._lock, self._connection:
            self._connection.execute(
                f"""
                UPDATE sessions
                SET extra_roots = ?, updated_at = {_NOW}
                WHERE session_id = ?
                """,
                (encoded, session_id),
            )

    def touch_workspace(self, path: str) -> None:
        if not isinstance(path, str) or not path:
            raise ValueError("invalid workspace")
        with self._lock, self._connection:
            self._touch_workspace(path)

    def _touch_workspace(self, path: str) -> None:
        self._connection.execute(
            f"""
            INSERT INTO workspaces (path, last_used)
            VALUES (?, {_NOW})
            ON CONFLICT(path) DO UPDATE SET last_used = excluded.last_used
            """,
            (path,),
        )


def _validate_session_id(session_id: str) -> None:
    if (
        not isinstance(session_id, str)
        or session_id.startswith("__")
        or _SESSION_ID.fullmatch(session_id) is None
    ):
        raise ValueError("invalid session id")


def _validate_record(record: SessionRecord) -> None:
    bounded = (
        (record.workspace, 4096),
        (record.model, 256),
        (record.mode, 32),
        (record.agent, 32),
    )
    if (
        any(
            not isinstance(value, str) or not 1 <= len(value) <= maximum
            for value, maximum in bounded
        )
        or not isinstance(record.messages, list)
        or not all(isinstance(message, dict) for message in record.messages)
        or not isinstance(record.extra_roots, list)
        or not isinstance(record.grants, dict)
    ):
        raise ValueError("invalid session data")
    if record.source_workspace is not None and (
        not isinstance(record.source_workspace, str)
        or not 1 <= len(record.source_workspace) <= 4096
    ):
        raise ValueError("invalid session data")


def _encode_json(value: Any) -> str:
    try:
        return json.dumps(
            value,
            allow_nan=False,
            ensure_ascii=False,
            separators=(",", ":"),
            sort_keys=True,
        )
    except (TypeError, ValueError, OverflowError):
        raise ValueError("invalid session data") from None


def _decode_json(value: str, *, expected: type) -> Any:
    try:
        decoded = json.loads(value)
    except (TypeError, json.JSONDecodeError):
        raise ValueError("corrupt conversation store") from None
    if not isinstance(decoded, expected):
        raise ValueError("corrupt conversation store")
    return decoded


def _record_from_row(
    row: sqlite3.Row,
    *,
    messages: list[dict[str, Any]],
    message_count: Optional[int] = None,
) -> SessionRecord:
    return SessionRecord(
        session_id=row["session_id"],
        workspace=row["workspace"],
        source_workspace=row["source_workspace"],
        model=row["model"],
        mode=row["mode"],
        messages=messages,
        title=row["title"],
        agent=row["agent"],
        message_count=(
            len(messages) if message_count is None else message_count
        ),
        updated_at=row["updated_at"],
        extra_roots=_decode_json(row["extra_roots"], expected=list),
        grants=_decode_json(row["grants"], expected=dict),
        pinned=bool(row["pinned"]),
        archived=bool(row["archived"]),
        origin=row["origin"],
        origin_label=row["origin_label"],
    )


def _title_from(messages: list[dict[str, Any]]) -> str:
    for message in messages:
        if message.get("role") != "user":
            continue
        content = message.get("content")
        if isinstance(content, str):
            text = content
        elif isinstance(content, list):
            text = " ".join(
                str(part.get("text", ""))
                for part in content
                if isinstance(part, dict) and part.get("type") == "text"
            )
        else:
            text = ""
        normalized = " ".join(text.split())
        if normalized:
            return normalized[:60]
    return "New session"
