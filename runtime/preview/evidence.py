"""Owner-only SQLite storage for dev-server preview evidence.

Stores console-evidence entries + annotations per session. Same migration /
backup / corruption-recovery primitives as the other domain stores.
"""

from __future__ import annotations

import json
import sqlite3
import threading
import time
from pathlib import Path
from typing import Any, Optional

from runtime.storage.migrations import (
    create_private_file,
    prepare_sqlite_database,
    run_sqlite_migrations,
    secure_directory,
    secure_file,
)

_SCHEMA_VERSION = 1
_NOW = "strftime('%Y-%m-%dT%H:%M:%fZ', 'now')"


def _migrate_to_v1(connection: sqlite3.Connection) -> None:
    connection.execute(
        f"""
        CREATE TABLE IF NOT EXISTS evidence (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            session_id TEXT NOT NULL,
            kind TEXT NOT NULL,
            content TEXT NOT NULL,
            created_at TEXT NOT NULL DEFAULT ({_NOW})
        )
        """
    )
    connection.execute(
        """
        CREATE INDEX IF NOT EXISTS evidence_session
        ON evidence(session_id, id)
        """
    )


class PreviewEvidenceStore:
    def __init__(self, data_dir: str | Path) -> None:
        self.base = Path(data_dir).expanduser().resolve()
        secure_directory(self.base)
        self.db_path = self.base / "preview.db"
        self._lock = threading.RLock()
        previous_version = prepare_sqlite_database(
            self.db_path,
            _SCHEMA_VERSION,
            "preview",
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

    def add_evidence(
        self,
        session_id: str,
        kind: str,
        content: Any,
    ) -> dict[str, Any]:
        if kind not in ("console", "annotation"):
            raise ValueError("kind must be console or annotation")
        if isinstance(content, (dict, list)):
            encoded = json.dumps(content, separators=(",", ":"))
        elif isinstance(content, str):
            encoded = content
        else:
            raise ValueError("content must be a string or JSON object")
        if len(encoded.encode("utf-8")) > 65_536:
            raise ValueError("content too large")
        with self._lock, self._connection:
            cursor = self._connection.execute(
                """
                INSERT INTO evidence (session_id, kind, content)
                VALUES (?, ?, ?)
                """,
                (session_id, kind, encoded),
            )
            evidence_id = cursor.lastrowid
        return {
            "id": evidence_id,
            "session_id": session_id,
            "kind": kind,
            "content": content if isinstance(content, str) else encoded,
        }

    def list_evidence(self, session_id: str) -> list[dict[str, Any]]:
        with self._lock:
            cursor = self._connection.execute(
                """
                SELECT id, session_id, kind, content, created_at
                FROM evidence WHERE session_id = ?
                ORDER BY id ASC
                """,
                (session_id,),
            )
            return [
                {
                    "id": row["id"],
                    "session_id": row["session_id"],
                    "kind": row["kind"],
                    "content": _decode_content(row["content"]),
                    "created_at": row["created_at"],
                }
                for row in cursor.fetchall()
            ]

    def clear_evidence(self, session_id: str) -> int:
        with self._lock, self._connection:
            cursor = self._connection.execute(
                "DELETE FROM evidence WHERE session_id = ?",
                (session_id,),
            )
            return cursor.rowcount


def _decode_content(raw: str) -> Any:
    try:
        return json.loads(raw)
    except (json.JSONDecodeError, TypeError):
        return raw
