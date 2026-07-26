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

from runtime.plans import PlanApproval, PlanArtifact, PlanContent
from runtime.sessions import (
    SessionRecord,
    SessionSearchHit,
    TurnCheckpoint,
    TurnStatus,
)
from runtime.sessions.context import is_project_context_part

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
_SCHEMA_VERSION = 7
MAX_EXPORT_STORED_BYTES = 32 * 1024 * 1024
MAX_PLAN_RESPONSE_BYTES = 128 * 1024
MAX_LISTED_PLAN_ARTIFACTS = 100


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


def _migrate_to_v3(connection: sqlite3.Connection) -> None:
    columns = {
        row["name"]
        for row in connection.execute("PRAGMA table_info(sessions)")
    }
    if "turn_status" not in columns:
        connection.execute(
            "ALTER TABLE sessions "
            "ADD COLUMN turn_status TEXT NOT NULL DEFAULT 'idle'"
        )
    if "active_tool_call_ids" not in columns:
        connection.execute(
            "ALTER TABLE sessions "
            "ADD COLUMN active_tool_call_ids TEXT NOT NULL DEFAULT '[]'"
        )
    connection.execute(
        f"""
        CREATE TABLE IF NOT EXISTS approval_decisions (
            session_id TEXT NOT NULL,
            tool_call_id TEXT NOT NULL,
            request_fingerprint TEXT NOT NULL,
            outcome TEXT NOT NULL,
            updated_at TEXT NOT NULL DEFAULT ({_NOW}),
            PRIMARY KEY (session_id, tool_call_id),
            FOREIGN KEY (session_id) REFERENCES sessions(session_id)
                ON DELETE CASCADE
        )
        """
    )
    approval_columns = {
        row["name"]
        for row in connection.execute(
            "PRAGMA table_info(approval_decisions)"
        )
    }
    if "request_fingerprint" not in approval_columns:
        connection.execute(
            "ALTER TABLE approval_decisions "
            "ADD COLUMN request_fingerprint TEXT NOT NULL DEFAULT ''"
        )


def _migrate_to_v4(connection: sqlite3.Connection) -> None:
    connection.execute(
        f"""
        CREATE TABLE IF NOT EXISTS interaction_decisions (
            session_id TEXT NOT NULL,
            tool_call_id TEXT NOT NULL,
            kind TEXT NOT NULL,
            request_fingerprint TEXT NOT NULL,
            response TEXT NOT NULL,
            updated_at TEXT NOT NULL DEFAULT ({_NOW}),
            PRIMARY KEY (session_id, tool_call_id),
            FOREIGN KEY (session_id) REFERENCES sessions(session_id)
                ON DELETE CASCADE
        )
        """
    )


def _migrate_to_v5(connection: sqlite3.Connection) -> None:
    columns = {
        row["name"]
        for row in connection.execute("PRAGMA table_info(sessions)")
    }
    if "workspace_device" not in columns:
        connection.execute(
            "ALTER TABLE sessions ADD COLUMN workspace_device INTEGER"
        )
    if "workspace_inode" not in columns:
        connection.execute(
            "ALTER TABLE sessions ADD COLUMN workspace_inode INTEGER"
        )


def _migrate_to_v6(connection: sqlite3.Connection) -> None:
    columns = {
        row["name"]
        for row in connection.execute("PRAGMA table_info(sessions)")
    }
    if "origin_session_id" not in columns:
        connection.execute(
            "ALTER TABLE sessions ADD COLUMN origin_session_id TEXT"
        )


def _migrate_to_v7(connection: sqlite3.Connection) -> None:
    connection.execute(
        f"""
        CREATE TABLE IF NOT EXISTS plan_artifacts (
            session_id TEXT NOT NULL,
            plan_id TEXT NOT NULL,
            tool_call_id TEXT NOT NULL,
            plan TEXT NOT NULL,
            tasks TEXT NOT NULL DEFAULT '[]',
            selected_task_ids TEXT NOT NULL DEFAULT '[]',
            status TEXT NOT NULL DEFAULT 'draft',
            revision INTEGER NOT NULL DEFAULT 1,
            updated_at TEXT NOT NULL DEFAULT ({_NOW}),
            PRIMARY KEY (session_id, plan_id),
            UNIQUE (session_id, tool_call_id),
            FOREIGN KEY (session_id) REFERENCES sessions(session_id)
                ON DELETE CASCADE
        )
        """
    )


_MIGRATIONS = {
    1: _migrate_to_v1,
    2: _migrate_to_v2,
    3: _migrate_to_v3,
    4: _migrate_to_v4,
    5: _migrate_to_v5,
    6: _migrate_to_v6,
    7: _migrate_to_v7,
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
        self._connection.create_function(
            "codinal_message_text",
            1,
            _message_search_text,
            deterministic=True,
        )
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

    def save(
        self,
        record: SessionRecord,
        *,
        completed_tool_call_id: str | None = None,
    ) -> None:
        _validate_session_id(record.session_id)
        _validate_record(record)
        messages = [_encode_json(message) for message in record.messages]
        extra_roots = _encode_json(record.extra_roots or [])
        grants = _encode_json(record.grants or {})
        active_tool_call_ids = _encode_json(
            record.turn_checkpoint.active_tool_call_ids
        )
        title = record.title or _title_from(record.messages)

        with self._lock, self._connection:
            self._connection.execute(
                f"""
                INSERT INTO sessions (
                    session_id, workspace, source_workspace, model, mode,
                    workspace_device, workspace_inode, title, agent,
                    extra_roots, grants, pinned, archived, origin,
                    origin_label, origin_session_id, turn_status,
                    active_tool_call_ids,
                    updated_at
                )
                VALUES (
                    ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?,
                    {_NOW}
                )
                ON CONFLICT(session_id) DO UPDATE SET
                    workspace = excluded.workspace,
                    source_workspace = excluded.source_workspace,
                    model = excluded.model,
                    mode = excluded.mode,
                    workspace_device = excluded.workspace_device,
                    workspace_inode = excluded.workspace_inode,
                    title = excluded.title,
                    agent = excluded.agent,
                    extra_roots = excluded.extra_roots,
                    grants = excluded.grants,
                    pinned = excluded.pinned,
                    archived = excluded.archived,
                    origin = excluded.origin,
                    origin_label = excluded.origin_label,
                    origin_session_id = excluded.origin_session_id,
                    turn_status = excluded.turn_status,
                    active_tool_call_ids = excluded.active_tool_call_ids,
                    updated_at = excluded.updated_at
                """,
                (
                    record.session_id,
                    record.workspace,
                    record.source_workspace,
                    record.model,
                    record.mode,
                    record.workspace_device,
                    record.workspace_inode,
                    title,
                    record.agent,
                    extra_roots,
                    grants,
                    int(record.pinned),
                    int(record.archived),
                    record.origin,
                    record.origin_label,
                    record.origin_session_id,
                    record.turn_checkpoint.status.value,
                    active_tool_call_ids,
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
            if completed_tool_call_id is not None:
                _validate_tool_call_id(completed_tool_call_id)
                self._connection.execute(
                    """
                    DELETE FROM approval_decisions
                    WHERE session_id = ? AND tool_call_id = ?
                    """,
                    (record.session_id, completed_tool_call_id),
                )
                self._connection.execute(
                    """
                    DELETE FROM interaction_decisions
                    WHERE session_id = ? AND tool_call_id = ?
                    """,
                    (record.session_id, completed_tool_call_id),
                )

    def save_checkpoint(
        self,
        record: SessionRecord,
        *,
        completed_tool_call_id: str | None = None,
    ) -> None:
        self.save(
            record,
            completed_tool_call_id=completed_tool_call_id,
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

    def load_approval_decision(
        self,
        session_id: str,
        tool_call_id: str,
        request_fingerprint: str,
    ) -> str | None:
        _validate_session_id(session_id)
        _validate_tool_call_id(tool_call_id)
        _validate_request_fingerprint(request_fingerprint)
        with self._lock:
            row = self._connection.execute(
                """
                SELECT outcome FROM approval_decisions
                WHERE session_id = ? AND tool_call_id = ?
                    AND request_fingerprint = ?
                """,
                (session_id, tool_call_id, request_fingerprint),
            ).fetchone()
        return str(row["outcome"]) if row is not None else None

    def save_approval_decision(
        self,
        session_id: str,
        tool_call_id: str,
        request_fingerprint: str,
        outcome: str,
    ) -> None:
        _validate_session_id(session_id)
        _validate_tool_call_id(tool_call_id)
        _validate_request_fingerprint(request_fingerprint)
        if outcome not in {
            "once",
            "always_tool",
            "always_command",
            "deny",
        }:
            raise ValueError("invalid approval outcome")
        with self._lock, self._connection:
            self._connection.execute(
                f"""
                INSERT INTO approval_decisions (
                    session_id, tool_call_id, request_fingerprint,
                    outcome, updated_at
                )
                VALUES (?, ?, ?, ?, {_NOW})
                ON CONFLICT(session_id, tool_call_id) DO UPDATE SET
                    request_fingerprint = excluded.request_fingerprint,
                    outcome = excluded.outcome,
                    updated_at = excluded.updated_at
                """,
                (
                    session_id,
                    tool_call_id,
                    request_fingerprint,
                    outcome,
                ),
            )

    def delete_approval_decision(
        self,
        session_id: str,
        tool_call_id: str,
    ) -> None:
        _validate_session_id(session_id)
        _validate_tool_call_id(tool_call_id)
        with self._lock, self._connection:
            self._connection.execute(
                """
                DELETE FROM approval_decisions
                WHERE session_id = ? AND tool_call_id = ?
                """,
                (session_id, tool_call_id),
            )

    def load_interaction_decision(
        self,
        session_id: str,
        tool_call_id: str,
        kind: str,
        request_fingerprint: str,
    ) -> dict[str, Any] | None:
        _validate_session_id(session_id)
        _validate_tool_call_id(tool_call_id)
        _validate_interaction_kind(kind)
        _validate_request_fingerprint(request_fingerprint)
        with self._lock:
            row = self._connection.execute(
                """
                SELECT response FROM interaction_decisions
                WHERE session_id = ? AND tool_call_id = ?
                    AND kind = ? AND request_fingerprint = ?
                """,
                (
                    session_id,
                    tool_call_id,
                    kind,
                    request_fingerprint,
                ),
            ).fetchone()
        return (
            _decode_json(row["response"], expected=dict)
            if row is not None
            else None
        )

    def save_interaction_decision(
        self,
        session_id: str,
        tool_call_id: str,
        kind: str,
        request_fingerprint: str,
        response: dict[str, Any],
    ) -> None:
        _validate_session_id(session_id)
        _validate_tool_call_id(tool_call_id)
        _validate_interaction_kind(kind)
        _validate_request_fingerprint(request_fingerprint)
        encoded = _encode_json(response)
        if len(encoded.encode("utf-8")) > 32 * 1024:
            raise ValueError("interaction response exceeds limit")
        with self._lock, self._connection:
            self._connection.execute(
                f"""
                INSERT INTO interaction_decisions (
                    session_id, tool_call_id, kind,
                    request_fingerprint, response, updated_at
                )
                VALUES (?, ?, ?, ?, ?, {_NOW})
                ON CONFLICT(session_id, tool_call_id) DO UPDATE SET
                    kind = excluded.kind,
                    request_fingerprint = excluded.request_fingerprint,
                    response = excluded.response,
                    updated_at = excluded.updated_at
                """,
                (
                    session_id,
                    tool_call_id,
                    kind,
                    request_fingerprint,
                    encoded,
                ),
            )

    def ensure_plan_artifact(
        self,
        session_id: str,
        plan_id: str,
        tool_call_id: str,
        arguments: dict[str, Any],
    ) -> dict[str, Any]:
        _validate_session_id(session_id)
        _validate_plan_id(plan_id)
        _validate_tool_call_id(tool_call_id)
        content = PlanContent.parse(arguments)
        with self._lock, self._connection:
            existing = self._connection.execute(
                """
                SELECT * FROM plan_artifacts
                WHERE session_id = ? AND plan_id = ?
                """,
                (session_id, plan_id),
            ).fetchone()
            if existing is None:
                self._connection.execute(
                    f"""
                    INSERT INTO plan_artifacts (
                        session_id, plan_id, tool_call_id, plan, tasks,
                        selected_task_ids, status, revision, updated_at
                    )
                    VALUES (?, ?, ?, ?, ?, '[]', 'draft', 1, {_NOW})
                    """,
                    (
                        session_id,
                        plan_id,
                        tool_call_id,
                        content.plan,
                        _encode_json(content.to_dict()["tasks"]),
                    ),
                )
                existing = self._connection.execute(
                    """
                    SELECT * FROM plan_artifacts
                    WHERE session_id = ? AND plan_id = ?
                    """,
                    (session_id, plan_id),
                ).fetchone()
        if existing is None:
            raise RuntimeError("plan artifact was not saved")
        if (
            str(existing["tool_call_id"]) != tool_call_id
            or str(existing["status"]) != "draft"
        ):
            raise ValueError("plan artifact identity is unavailable")
        return _plan_from_row(existing)

    def save_plan_interaction_decision(
        self,
        session_id: str,
        tool_call_id: str,
        request_fingerprint: str,
        response: dict[str, Any],
        plan_id: str,
    ) -> None:
        _validate_session_id(session_id)
        _validate_tool_call_id(tool_call_id)
        _validate_request_fingerprint(request_fingerprint)
        _validate_plan_id(plan_id)
        encoded_response = _encode_json(response)
        if len(encoded_response.encode("utf-8")) > MAX_PLAN_RESPONSE_BYTES:
            raise ValueError("interaction response exceeds limit")
        approved = response.get("approved")
        if not isinstance(approved, bool):
            raise ValueError("invalid plan response")
        with self._lock, self._connection:
            row = self._connection.execute(
                """
                SELECT * FROM plan_artifacts
                WHERE session_id = ? AND plan_id = ?
                    AND tool_call_id = ?
                """,
                (session_id, plan_id, tool_call_id),
            ).fetchone()
            if row is None:
                raise ValueError("plan artifact is unavailable")
            if str(row["status"]) != "draft":
                raise ValueError("plan artifact is already resolved")
            if approved:
                approval = PlanApproval.parse(
                    response,
                    {
                        "plan": str(row["plan"]),
                        "tasks": _decode_json(
                            row["tasks"],
                            expected=list,
                        ),
                    },
                )
                plan = approval.content.plan
                tasks = approval.content.to_dict()["tasks"]
                selected = list(approval.selected_task_ids)
                status = "approved"
            else:
                plan = str(row["plan"])
                tasks = _decode_json(row["tasks"], expected=list)
                selected = []
                status = "revision_requested"
            self._connection.execute(
                f"""
                INSERT INTO interaction_decisions (
                    session_id, tool_call_id, kind,
                    request_fingerprint, response, updated_at
                )
                VALUES (?, ?, 'plan', ?, ?, {_NOW})
                ON CONFLICT(session_id, tool_call_id) DO UPDATE SET
                    kind = excluded.kind,
                    request_fingerprint = excluded.request_fingerprint,
                    response = excluded.response,
                    updated_at = excluded.updated_at
                """,
                (
                    session_id,
                    tool_call_id,
                    request_fingerprint,
                    encoded_response,
                ),
            )
            self._connection.execute(
                f"""
                UPDATE plan_artifacts
                SET plan = ?, tasks = ?, selected_task_ids = ?,
                    status = ?, revision = revision + 1,
                    updated_at = {_NOW}
                WHERE session_id = ? AND plan_id = ?
                    AND tool_call_id = ?
                """,
                (
                    plan,
                    _encode_json(tasks),
                    _encode_json(selected),
                    status,
                    session_id,
                    plan_id,
                    tool_call_id,
                ),
            )

    def list_plan_artifacts(
        self,
        session_id: str,
    ) -> list[dict[str, Any]]:
        _validate_session_id(session_id)
        with self._lock:
            rows = self._connection.execute(
                """
                SELECT * FROM plan_artifacts
                WHERE session_id = ?
                ORDER BY updated_at DESC, plan_id
                LIMIT ?
                """,
                (session_id, MAX_LISTED_PLAN_ARTIFACTS),
            ).fetchall()
        return [_plan_from_row(row) for row in rows]

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

    def search(
        self,
        query: str,
        *,
        limit: int = 50,
    ) -> list[SessionSearchHit]:
        if (
            not isinstance(query, str)
            or not 1 <= len(query.strip()) <= 256
            or isinstance(limit, bool)
            or not isinstance(limit, int)
            or not 1 <= limit <= 100
        ):
            raise ValueError("invalid session search")
        normalized = query.strip()
        with self._lock:
            rows = self._connection.execute(
                """
                SELECT sessions.*,
                    COUNT(messages.sequence) AS message_count
                FROM sessions
                LEFT JOIN messages USING (session_id)
                WHERE substr(sessions.session_id, 1, 2) != '__'
                    AND (
                        instr(
                            lower(COALESCE(sessions.title, '')),
                            lower(?)
                        ) > 0
                        OR instr(
                            lower(COALESCE(
                                sessions.source_workspace,
                                sessions.workspace
                            )),
                            lower(?)
                        ) > 0
                        OR EXISTS (
                            SELECT 1
                            FROM messages AS matched
                            WHERE matched.session_id = sessions.session_id
                                AND json_extract(
                                    matched.payload,
                                    '$.role'
                                ) IN ('user', 'assistant')
                                AND instr(
                                    lower(codinal_message_text(
                                        matched.payload
                                    )),
                                    lower(?)
                                ) > 0
                        )
                    )
                GROUP BY sessions.session_id
                ORDER BY sessions.pinned DESC, sessions.updated_at DESC
                LIMIT ?
                """,
                (normalized, normalized, normalized, limit),
            ).fetchall()
            hits = []
            for row in rows:
                matched = self._connection.execute(
                    """
                    SELECT sequence, payload
                    FROM messages
                    WHERE session_id = ?
                        AND json_extract(
                            payload,
                            '$.role'
                        ) IN ('user', 'assistant')
                        AND instr(
                            lower(codinal_message_text(payload)),
                            lower(?)
                        ) > 0
                    ORDER BY sequence
                    LIMIT 1
                    """,
                    (row["session_id"], normalized),
                ).fetchone()
                excerpt = None
                message_index = None
                if matched is not None:
                    message = _decode_json(
                        matched["payload"],
                        expected=dict,
                    )
                    excerpt = _message_excerpt(message)
                    message_index = int(matched["sequence"])
                hits.append(
                    SessionSearchHit(
                        record=_record_from_row(
                            row,
                            messages=[],
                            message_count=int(row["message_count"]),
                        ),
                        excerpt=excerpt,
                        message_index=message_index,
                    )
                )
        return hits

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
                    + COALESCE(
                        LENGTH(CAST(origin_session_id AS BLOB)), 0
                    )
                    + LENGTH(CAST(turn_status AS BLOB))
                    + LENGTH(CAST(active_tool_call_ids AS BLOB))
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


def _message_visible_text(message: dict[str, Any]) -> str:
    content = message.get("content")
    if isinstance(content, str):
        text = content
    elif isinstance(content, list):
        parts = []
        for part in content:
            if not isinstance(part, dict):
                continue
            if part.get("type") == "text" and isinstance(
                part.get("text"), str
            ) and not is_project_context_part(part):
                parts.append(part["text"])
            elif part.get("type") == "file":
                file = part.get("file")
                if isinstance(file, dict) and isinstance(
                    file.get("filename"), str
                ):
                    parts.append(file["filename"])
        text = " ".join(parts)
    else:
        text = ""
    return " ".join(text.split())


def _message_search_text(payload: str) -> str:
    try:
        message = json.loads(payload)
    except (json.JSONDecodeError, TypeError):
        return ""
    return _message_visible_text(message) if isinstance(message, dict) else ""


def _message_excerpt(message: dict[str, Any]) -> str | None:
    normalized = _message_visible_text(message)
    return normalized[:240] if normalized else None


def _validate_session_id(session_id: str) -> None:
    if (
        not isinstance(session_id, str)
        or session_id.startswith("__")
        or _SESSION_ID.fullmatch(session_id) is None
    ):
        raise ValueError("invalid session id")


def _validate_tool_call_id(tool_call_id: str) -> None:
    if (
        not isinstance(tool_call_id, str)
        or not 1 <= len(tool_call_id) <= 256
        or "\x00" in tool_call_id
    ):
        raise ValueError("invalid tool call id")


def _validate_plan_id(plan_id: str) -> None:
    if (
        not isinstance(plan_id, str)
        or re.fullmatch(r"[a-f0-9]{32}", plan_id) is None
    ):
        raise ValueError("invalid plan id")


def _validate_request_fingerprint(request_fingerprint: str) -> None:
    if (
        not isinstance(request_fingerprint, str)
        or re.fullmatch(r"[0-9a-f]{64}", request_fingerprint) is None
    ):
        raise ValueError("invalid approval request fingerprint")


def _validate_interaction_kind(kind: str) -> None:
    if kind not in {"directory", "plan", "question"}:
        raise ValueError("invalid interaction kind")


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
        or not isinstance(record.turn_checkpoint, TurnCheckpoint)
        or (
            (record.workspace_device is None)
            != (record.workspace_inode is None)
        )
        or (
            record.workspace_device is not None
            and (
                isinstance(record.workspace_device, bool)
                or not isinstance(record.workspace_device, int)
                or isinstance(record.workspace_inode, bool)
                or not isinstance(record.workspace_inode, int)
            )
        )
    ):
        raise ValueError("invalid session data")
    if record.source_workspace is not None and (
        not isinstance(record.source_workspace, str)
        or not 1 <= len(record.source_workspace) <= 4096
    ):
        raise ValueError("invalid session data")
    if record.origin_session_id is not None:
        _validate_session_id(record.origin_session_id)


def _plan_from_row(row: sqlite3.Row) -> dict[str, Any]:
    content = PlanContent.parse(
        {
            "plan": str(row["plan"]),
            "tasks": _decode_json(row["tasks"], expected=list),
        }
    )
    selected = _decode_json(
        row["selected_task_ids"],
        expected=list,
    )
    if any(not isinstance(task_id, str) for task_id in selected):
        raise ValueError("corrupt conversation store")
    return PlanArtifact(
        plan_id=str(row["plan_id"]),
        session_id=str(row["session_id"]),
        tool_call_id=str(row["tool_call_id"]),
        content=content,
        selected_task_ids=tuple(selected),
        status=str(row["status"]),
        revision=int(row["revision"]),
        updated_at=str(row["updated_at"]),
    ).to_dict()


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
        workspace_device=row["workspace_device"],
        workspace_inode=row["workspace_inode"],
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
        origin_session_id=row["origin_session_id"],
        turn_checkpoint=TurnCheckpoint(
            status=TurnStatus(row["turn_status"]),
            active_tool_call_ids=tuple(
                _decode_json(
                    row["active_tool_call_ids"],
                    expected=list,
                )
            ),
        ),
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
                if (
                    isinstance(part, dict)
                    and part.get("type") == "text"
                    and not is_project_context_part(part)
                )
            )
        else:
            text = ""
        normalized = " ".join(text.split())
        if normalized:
            return normalized[:60]
    return "New session"
