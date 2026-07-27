"""Owner-only SQLite storage for durable MCP server connections."""

from __future__ import annotations

import json
import sqlite3
import threading
import time
from dataclasses import asdict
from pathlib import Path
from typing import Any, Optional

from runtime.storage.migrations import (
    create_private_file,
    prepare_sqlite_database,
    run_sqlite_migrations,
    secure_directory,
    secure_file,
)

from .config import MCPServerDef

_SCHEMA_VERSION = 1


def _migrate_to_v1(connection: sqlite3.Connection) -> None:
    connection.execute(
        """
        CREATE TABLE IF NOT EXISTS connections (
            session_id TEXT NOT NULL,
            name TEXT NOT NULL,
            transport TEXT NOT NULL,
            definition TEXT NOT NULL,
            enabled INTEGER NOT NULL DEFAULT 1,
            connected_at REAL NOT NULL,
            PRIMARY KEY (session_id, name)
        )
        """
    )
    connection.execute(
        """
        CREATE INDEX IF NOT EXISTS connections_enabled
        ON connections(enabled, session_id)
        """
    )


class MCPStore:
    def __init__(self, data_dir: str | Path) -> None:
        self.base = Path(data_dir).expanduser().resolve()
        secure_directory(self.base)
        self.db_path = self.base / "mcp.db"
        self._lock = threading.RLock()
        previous_version = prepare_sqlite_database(
            self.db_path,
            _SCHEMA_VERSION,
            "mcp",
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

    def upsert(
        self,
        session_id: str,
        server: MCPServerDef,
        *,
        enabled: bool = True,
    ) -> None:
        definition = json.dumps(asdict(server), separators=(",", ":"))
        with self._lock, self._connection:
            self._connection.execute(
                """
                INSERT INTO connections
                    (session_id, name, transport, definition, enabled, connected_at)
                VALUES
                    (:session_id, :name, :transport, :definition, :enabled, :connected_at)
                ON CONFLICT(session_id, name) DO UPDATE SET
                    transport = excluded.transport,
                    definition = excluded.definition,
                    enabled = excluded.enabled
                """,
                {
                    "session_id": session_id,
                    "name": server.name,
                    "transport": server.transport,
                    "definition": definition,
                    "enabled": 1 if enabled else 0,
                    "connected_at": time.time(),
                },
            )

    def _row_to_server(self, row: sqlite3.Row) -> MCPServerDef:
        data = json.loads(row["definition"])
        return MCPServerDef(**data)

    def list(self, session_id: str) -> list[tuple[MCPServerDef, bool]]:
        with self._lock:
            cursor = self._connection.execute(
                """
                SELECT definition, enabled FROM connections
                WHERE session_id = ? ORDER BY name
                """,
                (session_id,),
            )
            return [
                (self._row_to_server(row), bool(row["enabled"]))
                for row in cursor.fetchall()
            ]

    def list_all_enabled(self) -> list[tuple[str, MCPServerDef]]:
        with self._lock:
            cursor = self._connection.execute(
                """
                SELECT session_id, definition FROM connections
                WHERE enabled = 1 ORDER BY session_id, name
                """
            )
            return [
                (row["session_id"], self._row_to_server(row))
                for row in cursor.fetchall()
            ]

    def is_enabled(self, session_id: str, name: str) -> Optional[bool]:
        with self._lock:
            row = self._connection.execute(
                """
                SELECT enabled FROM connections
                WHERE session_id = ? AND name = ?
                """,
                (session_id, name),
            ).fetchone()
        return bool(row["enabled"]) if row is not None else None

    def set_enabled(
        self,
        session_id: str,
        name: str,
        enabled: bool,
    ) -> bool:
        with self._lock, self._connection:
            cursor = self._connection.execute(
                """
                UPDATE connections SET enabled = ?
                WHERE session_id = ? AND name = ?
                """,
                (1 if enabled else 0, session_id, name),
            )
            return cursor.rowcount > 0

    def delete(self, session_id: str, name: str) -> bool:
        with self._lock, self._connection:
            cursor = self._connection.execute(
                """
                DELETE FROM connections
                WHERE session_id = ? AND name = ?
                """,
                (session_id, name),
            )
            return cursor.rowcount > 0

    def delete_session(self, session_id: str) -> int:
        with self._lock, self._connection:
            cursor = self._connection.execute(
                "DELETE FROM connections WHERE session_id = ?",
                (session_id,),
            )
            return cursor.rowcount
