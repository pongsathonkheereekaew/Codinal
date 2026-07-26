"""Persistent local code retrieval without storing repository source text."""

from __future__ import annotations

import hashlib
import math
import os
import re
import sqlite3
import stat
import struct
import threading
import time
from pathlib import Path
from typing import Any, Callable

from runtime.search.service import (
    _MAX_FILE_BYTES,
    _MAX_FILES,
    _MAX_RESULTS,
    _MAX_TOTAL_BYTES,
    _candidate_files,
    _open_relative_file,
    _read_file,
)

_SCHEMA_VERSION = 1
_INDEX_SECONDS = 10.0
_QUERY_SECONDS = 2.0
_MAX_CHUNKS = 20_000
_MAX_GLOBAL_CHUNKS = 100_000
_MAX_INDEX_SCOPES = 32
_MAX_DATABASE_BYTES = 128 * 1024 * 1024
_CHUNK_LINES = 40
_CHUNK_BYTES = 4 * 1024
_MAX_VECTOR_FEATURES = 256
_MIN_SCORE = 0.12
_MAX_QUERY_BYTES = 256
_MAX_PREVIEW_CHARS = 500

_SYNONYMS = {
    "add": "create",
    "build": "create",
    "create": "create",
    "generate": "create",
    "delete": "delete",
    "erase": "delete",
    "purge": "delete",
    "remove": "delete",
    "expired": "stale",
    "legacy": "stale",
    "old": "stale",
    "stale": "stale",
    "auth": "auth",
    "authenticate": "auth",
    "authentication": "auth",
    "credential": "auth",
    "credentials": "auth",
    "login": "auth",
    "token": "auth",
    "tokens": "auth",
    "find": "search",
    "lookup": "search",
    "retrieve": "search",
    "search": "search",
    "fix": "fix",
    "repair": "fix",
    "resolve": "fix",
    "persist": "persist",
    "save": "persist",
    "store": "persist",
    "configuration": "config",
    "config": "config",
    "settings": "config",
}

_SCHEMA = """
CREATE TABLE IF NOT EXISTS roots (
    root_key TEXT PRIMARY KEY,
    scope TEXT NOT NULL,
    path TEXT NOT NULL,
    device INTEGER NOT NULL,
    inode INTEGER NOT NULL,
    label TEXT NOT NULL,
    indexed_at REAL NOT NULL,
    files INTEGER NOT NULL,
    chunks INTEGER NOT NULL,
    truncated INTEGER NOT NULL CHECK (truncated IN (0, 1))
);
CREATE TABLE IF NOT EXISTS chunks (
    root_key TEXT NOT NULL REFERENCES roots(root_key) ON DELETE CASCADE,
    path TEXT NOT NULL,
    start_line INTEGER NOT NULL,
    end_line INTEGER NOT NULL,
    digest TEXT NOT NULL,
    vector BLOB NOT NULL,
    PRIMARY KEY (root_key, path, start_line)
);
CREATE INDEX IF NOT EXISTS chunks_root ON chunks(root_key);
CREATE INDEX IF NOT EXISTS roots_scope_path ON roots(scope, path);
"""

_EXPECTED_SCHEMA_SQL = {
    "table:roots": """
        CREATE TABLE roots (
            root_key TEXT PRIMARY KEY,
            scope TEXT NOT NULL,
            path TEXT NOT NULL,
            device INTEGER NOT NULL,
            inode INTEGER NOT NULL,
            label TEXT NOT NULL,
            indexed_at REAL NOT NULL,
            files INTEGER NOT NULL,
            chunks INTEGER NOT NULL,
            truncated INTEGER NOT NULL CHECK (truncated IN (0, 1))
        )
    """,
    "table:chunks": """
        CREATE TABLE chunks (
            root_key TEXT NOT NULL REFERENCES roots(root_key) ON DELETE CASCADE,
            path TEXT NOT NULL,
            start_line INTEGER NOT NULL,
            end_line INTEGER NOT NULL,
            digest TEXT NOT NULL,
            vector BLOB NOT NULL,
            PRIMARY KEY (root_key, path, start_line)
        )
    """,
    "index:chunks_root": "CREATE INDEX chunks_root ON chunks(root_key)",
    "index:roots_scope_path": (
        "CREATE INDEX roots_scope_path ON roots(scope, path)"
    ),
}


def _normalize_schema_sql(value: str) -> str:
    return " ".join(value.split()).casefold()


_EXPECTED_SCHEMA_SQL = {
    key: _normalize_schema_sql(value)
    for key, value in _EXPECTED_SCHEMA_SQL.items()
}


class SemanticIndexService:
    """Build and query a bounded local vector index.

    Only fixed-width vectors, file coordinates, and hashes are persisted.
    Repository source is reopened and fingerprint-verified for every result.
    """

    def __init__(self, data_dir: str | Path) -> None:
        self.base = Path(data_dir).expanduser().resolve()
        self.base.mkdir(mode=0o700, parents=True, exist_ok=True)
        self.path = self.base / "semantic-index.sqlite3"
        self._lock = threading.RLock()
        self._build_lock = threading.Lock()
        self._connection = self._open_database()

    def _open_database(self) -> sqlite3.Connection:
        if self.path.is_symlink():
            self._remove_database_files()
        elif self.path.exists() and not self._compatible_database():
            self._remove_database_files()
        connection = sqlite3.connect(
            self.path,
            check_same_thread=False,
            timeout=2,
        )
        os.chmod(self.path, 0o600)
        connection.execute("PRAGMA foreign_keys = ON")
        connection.execute("PRAGMA secure_delete = ON")
        connection.execute("PRAGMA journal_mode = WAL")
        connection.executescript(_SCHEMA)
        connection.execute(f"PRAGMA user_version = {_SCHEMA_VERSION}")
        connection.commit()
        return connection

    def _compatible_database(self) -> bool:
        stored_bytes = sum(
            candidate.stat().st_size
            for candidate in (
                self.path,
                self.path.with_name(self.path.name + "-wal"),
                self.path.with_name(self.path.name + "-shm"),
            )
            if candidate.exists() and candidate.is_file()
        )
        if stored_bytes > _MAX_DATABASE_BYTES:
            return False
        try:
            existing = sqlite3.connect(
                f"{self.path.as_uri()}?mode=ro",
                uri=True,
            )
            try:
                version = int(
                    existing.execute("PRAGMA user_version").fetchone()[0]
                )
                tables = {
                    str(row[0])
                    for row in existing.execute(
                        """
                        SELECT name FROM sqlite_master
                        WHERE type = 'table' AND name NOT LIKE 'sqlite_%'
                        """
                    )
                }
                root_info = list(
                    existing.execute("PRAGMA table_info(roots)")
                )
                chunk_info = list(
                    existing.execute("PRAGMA table_info(chunks)")
                )
                root_columns = [str(row[1]) for row in root_info]
                chunk_columns = [str(row[1]) for row in chunk_info]
                root_shape = [
                    (str(row[1]), str(row[2]).upper(), int(row[3]), int(row[5]))
                    for row in root_info
                ]
                chunk_shape = [
                    (str(row[1]), str(row[2]).upper(), int(row[3]), int(row[5]))
                    for row in chunk_info
                ]
                foreign_keys = list(
                    existing.execute("PRAGMA foreign_key_list(chunks)")
                )
                schema_sql = {
                    f"{row[0]}:{row[1]}": _normalize_schema_sql(str(row[2]))
                    for row in existing.execute(
                        """
                        SELECT type, name, sql FROM sqlite_master
                        WHERE type IN ('table', 'index')
                          AND name NOT LIKE 'sqlite_%'
                          AND sql IS NOT NULL
                        """
                    )
                }
                integrity = str(
                    existing.execute("PRAGMA quick_check").fetchone()[0]
                )
                foreign_key_errors = list(
                    existing.execute("PRAGMA foreign_key_check")
                )
                chunks = (
                    int(
                        existing.execute(
                            "SELECT COUNT(*) FROM chunks"
                        ).fetchone()[0]
                    )
                    if "chunks" in tables
                    and "vector" in chunk_columns
                    else 0
                )
                scopes = (
                    int(
                        existing.execute(
                            "SELECT COUNT(DISTINCT scope) FROM roots"
                        ).fetchone()[0]
                    )
                    if "roots" in tables
                    and "scope" in root_columns
                    else 0
                )
            finally:
                existing.close()
        except (OSError, sqlite3.DatabaseError):
            return False
        if version == 0:
            return not tables
        return (
            version == _SCHEMA_VERSION
            and tables == {"roots", "chunks"}
            and root_columns
            == [
                "root_key",
                "scope",
                "path",
                "device",
                "inode",
                "label",
                "indexed_at",
                "files",
                "chunks",
                "truncated",
            ]
            and root_shape
            == [
                ("root_key", "TEXT", 0, 1),
                ("scope", "TEXT", 1, 0),
                ("path", "TEXT", 1, 0),
                ("device", "INTEGER", 1, 0),
                ("inode", "INTEGER", 1, 0),
                ("label", "TEXT", 1, 0),
                ("indexed_at", "REAL", 1, 0),
                ("files", "INTEGER", 1, 0),
                ("chunks", "INTEGER", 1, 0),
                ("truncated", "INTEGER", 1, 0),
            ]
            and chunk_columns
            == [
                "root_key",
                "path",
                "start_line",
                "end_line",
                "digest",
                "vector",
            ]
            and chunk_shape
            == [
                ("root_key", "TEXT", 1, 1),
                ("path", "TEXT", 1, 2),
                ("start_line", "INTEGER", 1, 3),
                ("end_line", "INTEGER", 1, 0),
                ("digest", "TEXT", 1, 0),
                ("vector", "BLOB", 1, 0),
            ]
            and schema_sql == _EXPECTED_SCHEMA_SQL
            and [
                (
                    int(row[0]),
                    int(row[1]),
                    str(row[2]),
                    str(row[3]),
                    str(row[4]),
                    str(row[5]).upper(),
                    str(row[6]).upper(),
                    str(row[7]).upper(),
                )
                for row in foreign_keys
            ]
            == [
                (
                    0,
                    0,
                    "roots",
                    "root_key",
                    "root_key",
                    "NO ACTION",
                    "CASCADE",
                    "NONE",
                )
            ]
            and integrity == "ok"
            and not foreign_key_errors
            and chunks <= _MAX_GLOBAL_CHUNKS
            and scopes <= _MAX_INDEX_SCOPES
        )

    def _remove_database_files(self) -> None:
        for candidate in (
            self.path,
            self.path.with_name(self.path.name + "-wal"),
            self.path.with_name(self.path.name + "-shm"),
        ):
            try:
                candidate.unlink()
            except FileNotFoundError:
                pass

    def close(self) -> None:
        with self._lock:
            self._connection.close()

    def status(
        self,
        roots: list[dict[str, Any]],
        *,
        scope: str = "default",
    ) -> dict[str, Any]:
        selected = [_root_descriptor(root, scope=scope) for root in roots]
        selected = [root for root in selected if root is not None]
        views = []
        with self._lock:
            for root in selected:
                row = self._connection.execute(
                    """
                    SELECT indexed_at, files, chunks, truncated
                    FROM roots WHERE root_key = ?
                    """,
                    (root["root_key"],),
                ).fetchone()
                views.append(
                    {
                        "root": root["path"],
                        "label": root["label"],
                        "state": (
                            "empty"
                            if row is None
                            else "partial" if row[3] else "ready"
                        ),
                        "indexed_at": None if row is None else row[0],
                        "files": 0 if row is None else row[1],
                        "chunks": 0 if row is None else row[2],
                        "truncated": False if row is None else bool(row[3]),
                    }
                )
        states = {view["state"] for view in views}
        state = (
            "empty"
            if not views or states == {"empty"}
            else "ready" if states == {"ready"} else "partial"
        )
        return {
            "ok": True,
            "schema_version": _SCHEMA_VERSION,
            "state": state,
            "roots": views,
        }

    def status_scope(self, scope: str) -> dict[str, Any]:
        with self._lock:
            rows = self._connection.execute(
                """
                SELECT path, label, indexed_at, files, chunks, truncated
                FROM roots WHERE scope = ?
                ORDER BY path COLLATE NOCASE, path
                """,
                (scope,),
            ).fetchall()
        views = [
            {
                "root": row[0],
                "label": row[1],
                "state": "partial" if row[5] else "ready",
                "indexed_at": row[2],
                "files": row[3],
                "chunks": row[4],
                "truncated": bool(row[5]),
            }
            for row in rows
        ]
        states = {view["state"] for view in views}
        return {
            "ok": True,
            "schema_version": _SCHEMA_VERSION,
            "state": (
                "empty"
                if not views
                else "ready" if states == {"ready"} else "partial"
            ),
            "roots": views,
        }

    def project_status(
        self,
        roots: list[dict[str, Any]],
        *,
        scope: str,
    ) -> dict[str, Any]:
        current = [
            root
            for root in (
                _root_descriptor(value, scope=scope) for value in roots
            )
            if root is not None
        ]
        persisted = self.status_scope(scope)["roots"]
        persisted_by_path = {view["root"]: view for view in persisted}
        views = []
        current_paths = set()
        with self._lock:
            for root in current:
                current_paths.add(root["path"])
                row = self._connection.execute(
                    """
                    SELECT indexed_at, files, chunks, truncated
                    FROM roots WHERE root_key = ?
                    """,
                    (root["root_key"],),
                ).fetchone()
                views.append(
                    {
                        "root": root["path"],
                        "label": root["label"],
                        "state": (
                            "empty"
                            if row is None
                            else "partial" if row[3] else "ready"
                        ),
                        "indexed_at": None if row is None else row[0],
                        "files": 0 if row is None else row[1],
                        "chunks": 0 if row is None else row[2],
                        "truncated": False if row is None else bool(row[3]),
                    }
                )
        views.extend(
            {**view, "state": "unavailable"}
            for path, view in persisted_by_path.items()
            if path not in current_paths
        )
        states = {view["state"] for view in views}
        state = (
            "empty"
            if not views or states == {"empty"}
            else "ready" if states == {"ready"} else "partial"
        )
        return {
            "ok": True,
            "schema_version": _SCHEMA_VERSION,
            "state": state,
            "roots": views,
        }

    def rebuild(
        self,
        roots: list[dict[str, Any]],
        *,
        scope: str = "default",
        cancelled: Callable[[], bool] | None = None,
        deadline: float | None = None,
    ) -> dict[str, Any]:
        if not self._build_lock.acquire(blocking=False):
            return {
                "ok": False,
                "error": "semantic index build already active",
            }
        try:
            return self._rebuild(
                roots,
                scope=scope,
                cancelled=cancelled,
                deadline=deadline,
            )
        finally:
            self._build_lock.release()

    def _rebuild(
        self,
        roots: list[dict[str, Any]],
        *,
        scope: str,
        cancelled: Callable[[], bool] | None,
        deadline: float | None,
    ) -> dict[str, Any]:
        started = time.monotonic()
        deadline = min(
            deadline if deadline is not None else started + _INDEX_SECONDS,
            started + _INDEX_SECONDS,
        )
        indexed_files = 0
        indexed_chunks = 0
        indexed_roots = 0
        bytes_indexed = 0
        truncated = deadline <= started
        selected_roots = [
            root
            for root in (
                _root_descriptor(value, scope=scope) for value in roots
            )
            if root is not None
        ]
        for root_index, root in enumerate(selected_roots):
            if (
                _stopped(deadline=deadline, cancelled=cancelled)
                or indexed_files >= _MAX_FILES
                or indexed_chunks >= _MAX_CHUNKS
                or bytes_indexed >= _MAX_TOTAL_BYTES
            ):
                truncated = True
                break
            remaining_roots = len(selected_roots) - root_index
            remaining_seconds = max(0.0, deadline - time.monotonic())
            root_deadline = min(
                deadline,
                time.monotonic()
                + max(0.01, remaining_seconds / max(1, remaining_roots)),
            )
            root_file_limit = max(
                1,
                (_MAX_FILES - indexed_files) // max(1, remaining_roots),
            )
            root_chunk_limit = max(
                1,
                (_MAX_CHUNKS - indexed_chunks) // max(1, remaining_roots),
            )
            root_byte_limit = max(
                1,
                (_MAX_TOTAL_BYTES - bytes_indexed)
                // max(1, remaining_roots),
            )
            opened = _open_root(root)
            if opened is None:
                continue
            absolute, root_fd = opened
            root_rows: list[tuple[Any, ...]] = []
            root_files = 0
            root_bytes = 0
            root_truncated = False
            try:
                candidates, candidate_truncated = _candidate_files(
                    absolute,
                    root_fd=root_fd,
                    deadline=root_deadline,
                    max_files=root_file_limit,
                    cancelled=cancelled,
                )
                root_truncated = candidate_truncated
                for relative in candidates:
                    if Path(relative).name in {".gitignore", ".ignore"}:
                        continue
                    if (
                        _stopped(deadline=deadline, cancelled=cancelled)
                        or time.monotonic() >= root_deadline
                        or root_files >= root_file_limit
                        or len(root_rows) >= root_chunk_limit
                        or bytes_indexed >= _MAX_TOTAL_BYTES
                    ):
                        root_truncated = True
                        break
                    descriptor = _open_relative_file(root_fd, relative)
                    if descriptor is None:
                        continue
                    try:
                        metadata = os.fstat(descriptor)
                        if (
                            not stat.S_ISREG(metadata.st_mode)
                            or metadata.st_size > _MAX_FILE_BYTES
                            or bytes_indexed + metadata.st_size
                            > _MAX_TOTAL_BYTES
                            or root_bytes + metadata.st_size > root_byte_limit
                        ):
                            if metadata.st_size > _MAX_FILE_BYTES:
                                continue
                            root_truncated = True
                            break
                        payload = _read_file(descriptor, metadata.st_size)
                    finally:
                        os.close(descriptor)
                    if payload is None:
                        continue
                    try:
                        text = payload.decode("utf-8", errors="strict")
                    except UnicodeDecodeError:
                        continue
                    chunks, chunk_truncated = _chunks(
                        text,
                        deadline=root_deadline,
                        cancelled=cancelled,
                    )
                    root_truncated = root_truncated or chunk_truncated
                    if len(root_rows) + len(chunks) > root_chunk_limit:
                        root_truncated = True
                        break
                    for start_line, end_line, content in chunks:
                        vector = _embed(
                            f"{relative}\n{content}",
                            deadline=root_deadline,
                            cancelled=cancelled,
                        )
                        if vector is None:
                            root_truncated = True
                            break
                        root_rows.append(
                            (
                                root["root_key"],
                                relative,
                                start_line,
                                end_line,
                                _digest(content),
                                _pack_vector(vector),
                            )
                        )
                    if root_truncated and _stopped(
                        deadline=root_deadline,
                        cancelled=cancelled,
                    ):
                        break
                    indexed_files += 1
                    root_files += 1
                    root_bytes += len(payload)
                    bytes_indexed += len(payload)
            finally:
                os.close(root_fd)
            committed = False
            with self._lock:
                self._connection.execute("BEGIN IMMEDIATE")
                try:
                    if cancelled is not None and cancelled():
                        self._connection.rollback()
                    else:
                        self._connection.execute(
                            """
                            DELETE FROM roots
                            WHERE scope = ? AND path = ?
                            """,
                            (scope, root["path"]),
                        )
                        self._connection.execute(
                            """
                            INSERT INTO roots(
                                root_key, scope, path, device, inode, label,
                                indexed_at, files, chunks, truncated
                            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                            """,
                            (
                                root["root_key"],
                                scope,
                                root["path"],
                                root["device"],
                                root["inode"],
                                root["label"],
                                time.time(),
                                root_files,
                                len(root_rows),
                                int(root_truncated),
                            ),
                        )
                        self._connection.executemany(
                            """
                            INSERT INTO chunks(
                                root_key, path, start_line, end_line,
                                digest, vector
                            ) VALUES (?, ?, ?, ?, ?, ?)
                            """,
                            root_rows,
                        )
                        if cancelled is not None and cancelled():
                            self._connection.rollback()
                        else:
                            self._connection.commit()
                            committed = True
                except Exception:
                    self._connection.rollback()
                    raise
            if not committed:
                truncated = True
                break
            indexed_roots += 1
            indexed_chunks += len(root_rows)
            truncated = truncated or root_truncated
        with self._lock:
            self._enforce_storage_budget(protected_scope=scope)
            self._connection.execute("PRAGMA wal_checkpoint(TRUNCATE)")
        return {
            "ok": True,
            "indexed_roots": indexed_roots,
            "indexed_files": indexed_files,
            "indexed_chunks": indexed_chunks,
            "bytes_indexed": bytes_indexed,
            "duration_ms": max(
                0,
                int((time.monotonic() - started) * 1000),
            ),
            "truncated": truncated,
            "cancelled": bool(cancelled is not None and cancelled()),
        }

    def _enforce_storage_budget(self, *, protected_scope: str) -> None:
        # Evict oldest-built scopes deterministically. Read-only searches never
        # write access timestamps merely to influence cache retention.
        evicted = False
        vacuumed = False
        while True:
            chunks = int(
                self._connection.execute(
                    "SELECT COUNT(*) FROM chunks"
                ).fetchone()[0]
            )
            scopes = int(
                self._connection.execute(
                    "SELECT COUNT(DISTINCT scope) FROM roots"
                ).fetchone()[0]
            )
            if (
                chunks <= _MAX_GLOBAL_CHUNKS
                and scopes <= _MAX_INDEX_SCOPES
            ):
                break
            victim = self._connection.execute(
                """
                SELECT scope FROM roots
                WHERE scope != ?
                GROUP BY scope
                ORDER BY MIN(indexed_at), scope
                LIMIT 1
                """,
                (protected_scope,),
            ).fetchone()
            if victim is None:
                break
            self._connection.execute(
                "DELETE FROM roots WHERE scope = ?",
                (victim[0],),
            )
            evicted = True
        self._connection.commit()
        self._connection.execute("PRAGMA wal_checkpoint(TRUNCATE)")
        database_bytes = (
            self.path.stat().st_size if self.path.exists() else 0
        )
        while database_bytes > _MAX_DATABASE_BYTES:
            victim = self._connection.execute(
                """
                SELECT scope FROM roots
                WHERE scope != ?
                GROUP BY scope
                ORDER BY MIN(indexed_at), scope
                LIMIT 1
                """,
                (protected_scope,),
            ).fetchone()
            if victim is None:
                break
            self._connection.execute(
                "DELETE FROM roots WHERE scope = ?",
                (victim[0],),
            )
            self._connection.commit()
            self._connection.execute("VACUUM")
            evicted = True
            vacuumed = True
            database_bytes = self.path.stat().st_size
        if evicted and not vacuumed:
            self._connection.execute("VACUUM")

    def search(
        self,
        roots: list[dict[str, Any]],
        *,
        query: str,
        limit: int = 50,
        mode: str = "semantic",
        scope: str = "default",
        cancelled: Callable[[], bool] | None = None,
        deadline: float | None = None,
    ) -> dict[str, Any]:
        if (
            not isinstance(query, str)
            or not 1 <= len(query.encode("utf-8")) <= _MAX_QUERY_BYTES
            or "\x00" in query
            or mode != "semantic"
            or isinstance(limit, bool)
            or not isinstance(limit, int)
            or not 1 <= limit <= _MAX_RESULTS
        ):
            return {"ok": False, "error": "invalid semantic search"}
        started = time.monotonic()
        deadline = min(
            deadline if deadline is not None else started + _QUERY_SECONDS,
            started + _QUERY_SECONDS,
        )
        descriptors = [
            _root_descriptor(root, scope=scope) for root in roots
        ]
        descriptors = [root for root in descriptors if root is not None]
        root_by_key = {root["root_key"]: root for root in descriptors}
        if not root_by_key:
            return {"ok": False, "error": "project roots unavailable"}
        if deadline <= started:
            return _search_result(
                query,
                started=started,
                truncated=True,
                cancelled=cancelled,
            )
        placeholders = ",".join("?" for _root in root_by_key)
        acquired = self._lock.acquire(
            timeout=max(0.0, deadline - time.monotonic())
        )
        if not acquired:
            return _search_result(
                query,
                started=started,
                truncated=True,
                cancelled=cancelled,
            )
        try:
            rows = self._connection.execute(
                f"""
                SELECT root_key, path, start_line, end_line, digest, vector
                FROM chunks
                WHERE root_key IN ({placeholders})
                LIMIT ?
                """,
                (*root_by_key, _MAX_CHUNKS),
            ).fetchall()
        finally:
            self._lock.release()
        if _stopped(deadline=deadline, cancelled=cancelled):
            return _search_result(
                query,
                started=started,
                truncated=True,
                cancelled=cancelled,
            )
        query_vector = _embed(query)
        assert query_vector is not None
        ranked = []
        truncated = len(rows) >= _MAX_CHUNKS
        for row in rows:
            if _stopped(deadline=deadline, cancelled=cancelled):
                truncated = True
                break
            score = _dot(query_vector, _unpack_vector(row[5]))
            if score >= _MIN_SCORE:
                ranked.append((score, row))
        ranked.sort(
            key=lambda item: (
                -item[0],
                str(item[1][1]).casefold(),
                str(item[1][1]),
                int(item[1][2]),
            )
        )
        matches = []
        stale_chunks = 0
        opened_roots: dict[str, int] = {}
        files: dict[tuple[str, str], list[str] | None] = {}
        files_scanned = 0
        bytes_scanned = 0
        try:
            for score, row in ranked:
                if (
                    len(matches) >= limit
                    or _stopped(deadline=deadline, cancelled=cancelled)
                ):
                    truncated = truncated or len(matches) < min(limit, len(ranked))
                    break
                root_key, relative, start_line, end_line, digest, _vector = row
                root = root_by_key.get(str(root_key))
                if root is None:
                    continue
                if root_key not in opened_roots:
                    opened = _open_root(root)
                    if opened is None:
                        continue
                    _absolute, opened_roots[root_key] = opened
                file_key = (str(root_key), str(relative))
                if file_key not in files:
                    if files_scanned >= _MAX_FILES:
                        truncated = True
                        break
                    descriptor = _open_relative_file(
                        opened_roots[root_key],
                        str(relative),
                    )
                    if descriptor is None:
                        files[file_key] = None
                    else:
                        try:
                            metadata = os.fstat(descriptor)
                            if (
                                not stat.S_ISREG(metadata.st_mode)
                                or metadata.st_size > _MAX_FILE_BYTES
                                or bytes_scanned + metadata.st_size
                                > _MAX_TOTAL_BYTES
                            ):
                                files[file_key] = None
                                if (
                                    bytes_scanned + metadata.st_size
                                    > _MAX_TOTAL_BYTES
                                ):
                                    truncated = True
                            else:
                                payload = _read_file_bounded(
                                    descriptor,
                                    metadata.st_size,
                                    deadline=deadline,
                                    cancelled=cancelled,
                                )
                                files_scanned += 1
                                if payload is None:
                                    files[file_key] = None
                                else:
                                    bytes_scanned += len(payload)
                                    try:
                                        files[file_key] = payload.decode(
                                            "utf-8",
                                            errors="strict",
                                        ).splitlines()
                                    except UnicodeDecodeError:
                                        files[file_key] = None
                        finally:
                            os.close(descriptor)
                lines = files[file_key]
                if lines is None:
                    stale_chunks += 1
                    if _stopped(deadline=deadline, cancelled=cancelled):
                        truncated = True
                        break
                    continue
                preview = _verified_preview_lines(
                    lines,
                    int(start_line),
                    int(end_line),
                    str(digest),
                )
                if preview is None:
                    stale_chunks += 1
                    continue
                line, text = preview
                matches.append(
                    {
                        "root": root["path"],
                        "root_label": root["label"],
                        "path": relative,
                        "line": line,
                        "column": 1,
                        "text": text,
                        "score": round(score, 6),
                    }
                )
        finally:
            for descriptor in opened_roots.values():
                os.close(descriptor)
        return _search_result(
            query,
            started=started,
            matches=matches,
            stale_chunks=stale_chunks,
            files_scanned=files_scanned,
            truncated=truncated or len(ranked) > limit,
            cancelled=cancelled,
        )

    def clear(
        self,
        roots: list[dict[str, Any]],
        *,
        scope: str = "default",
    ) -> dict[str, Any]:
        if not self._build_lock.acquire(blocking=False):
            return {
                "ok": False,
                "error": "semantic index build already active",
            }
        try:
            paths = [
                root["path"]
                for root in (
                    _root_descriptor(value, scope=scope)
                    for value in roots
                )
                if root is not None
            ]
            return self._clear_scope(scope, paths=paths)
        finally:
            self._build_lock.release()

    def clear_scope(
        self,
        scope: str,
        *,
        paths: list[str] | None = None,
    ) -> dict[str, Any]:
        if not self._build_lock.acquire(blocking=False):
            return {
                "ok": False,
                "error": "semantic index build already active",
            }
        try:
            return self._clear_scope(scope, paths=paths)
        finally:
            self._build_lock.release()

    def _clear_scope(
        self,
        scope: str,
        *,
        paths: list[str] | None,
    ) -> dict[str, Any]:
        deleted_roots = 0
        deleted_chunks = 0
        with self._lock:
            parameters: tuple[Any, ...]
            condition = "scope = ?"
            parameters = (scope,)
            if paths is not None:
                normalized = sorted(set(paths))
                if not normalized:
                    return {
                        "ok": True,
                        "deleted_roots": 0,
                        "deleted_chunks": 0,
                    }
                placeholders = ",".join("?" for _path in normalized)
                condition += f" AND path IN ({placeholders})"
                parameters = (scope, *normalized)
            row = self._connection.execute(
                f"""
                SELECT COUNT(*) FROM chunks
                WHERE root_key IN (
                    SELECT root_key FROM roots WHERE {condition}
                )
                """,
                parameters,
            ).fetchone()
            deleted_chunks = int(row[0])
            cursor = self._connection.execute(
                f"DELETE FROM roots WHERE {condition}",
                parameters,
            )
            deleted_roots = cursor.rowcount
            self._connection.commit()
            self._connection.execute("PRAGMA wal_checkpoint(TRUNCATE)")
            self._connection.execute("VACUUM")
        return {
            "ok": True,
            "deleted_roots": deleted_roots,
            "deleted_chunks": deleted_chunks,
        }


def _root_descriptor(
    root: object,
    *,
    scope: str,
) -> dict[str, Any] | None:
    if not isinstance(root, dict) or root.get("available") is False:
        return None
    path = root.get("path")
    device = root.get("_device")
    inode = root.get("_inode")
    if (
        not isinstance(path, str)
        or not Path(path).is_absolute()
        or not isinstance(device, int)
        or not isinstance(inode, int)
    ):
        return None
    absolute = str(Path(path).expanduser().absolute())
    if not isinstance(scope, str) or not 1 <= len(scope) <= 256:
        return None
    identity = f"{scope}\0{absolute}\0{device}\0{inode}".encode("utf-8")
    return {
        "root_key": hashlib.sha256(identity).hexdigest(),
        "path": absolute,
        "label": str(root.get("label") or Path(absolute).name),
        "device": device,
        "inode": inode,
    }


def _open_root(root: dict[str, Any]) -> tuple[Path, int] | None:
    absolute = Path(root["path"])
    try:
        if (
            absolute.is_symlink()
            or absolute.resolve(strict=True) != absolute
        ):
            return None
        descriptor = os.open(
            absolute,
            os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW,
        )
        metadata = os.fstat(descriptor)
        if (
            int(metadata.st_dev) != root["device"]
            or int(metadata.st_ino) != root["inode"]
        ):
            os.close(descriptor)
            return None
    except (OSError, RuntimeError):
        return None
    return absolute, descriptor


def _chunks(
    text: str,
    *,
    deadline: float,
    cancelled: Callable[[], bool] | None,
) -> tuple[list[tuple[int, int, str]], bool]:
    lines = text.splitlines()
    chunks = []
    truncated = False
    start = 0
    while start < len(lines):
        if _stopped(deadline=deadline, cancelled=cancelled):
            return chunks, True
        first_size = len(lines[start].encode("utf-8"))
        if first_size > _CHUNK_BYTES:
            truncated = True
            start += 1
            continue
        end = start
        size = 0
        while end < len(lines) and end - start < _CHUNK_LINES:
            encoded = lines[end].encode("utf-8")
            if end > start and size + len(encoded) + 1 > _CHUNK_BYTES:
                break
            size += len(encoded) + 1
            end += 1
        content = "\n".join(lines[start:end])
        if content.strip():
            chunks.append((start + 1, end, content))
        start = max(end, start + 1)
    return chunks, truncated


def _tokens(text: str) -> list[str]:
    expanded = re.sub(r"([a-z0-9])([A-Z])", r"\1 \2", text)
    return [
        _SYNONYMS.get(token, token)
        for token in re.findall(r"[A-Za-z0-9]+", expanded.casefold())
        if len(token) > 1
    ]


def _embed(
    text: str,
    *,
    deadline: float | None = None,
    cancelled: Callable[[], bool] | None = None,
) -> tuple[tuple[int, float], ...] | None:
    values: dict[int, float] = {}
    tokens = _tokens(text)
    checked = 0

    def add(feature: str, weight: float) -> bool:
        nonlocal checked
        checked += 1
        if (
            checked % 128 == 0
            and deadline is not None
            and _stopped(deadline=deadline, cancelled=cancelled)
        ):
            return False
        digest = hashlib.blake2b(
            feature.encode("utf-8"),
            digest_size=8,
            person=b"codinal",
        ).digest()
        key = int.from_bytes(digest, "little")
        values[key] = values.get(key, 0.0) + weight
        return True

    for token in tokens:
        if not add(token, 1.0):
            return None
    for left, right in zip(tokens, tokens[1:]):
        if not add(f"{left}:{right}", 0.65):
            return None
    selected = sorted(
        values.items(),
        key=lambda item: (-item[1], item[0]),
    )[:_MAX_VECTOR_FEATURES]
    magnitude = math.sqrt(sum(value * value for _key, value in selected))
    if magnitude:
        selected = [
            (key, value / magnitude) for key, value in selected
        ]
    return tuple(sorted(selected))


def _pack_vector(vector: tuple[tuple[int, float], ...]) -> bytes:
    return (
        struct.pack("<H", len(vector))
        + b"".join(
            struct.pack("<Qf", key, weight)
            for key, weight in vector
        )
    )


def _unpack_vector(payload: bytes) -> tuple[tuple[int, float], ...]:
    if len(payload) < 2:
        return ()
    count = struct.unpack("<H", payload[:2])[0]
    if count > _MAX_VECTOR_FEATURES or len(payload) != 2 + count * 12:
        return ()
    return tuple(
        struct.unpack("<Qf", payload[offset : offset + 12])
        for offset in range(2, len(payload), 12)
    )


def _dot(
    left: tuple[tuple[int, float], ...],
    right: tuple[tuple[int, float], ...],
) -> float:
    left_index = 0
    right_index = 0
    score = 0.0
    while left_index < len(left) and right_index < len(right):
        left_key, left_weight = left[left_index]
        right_key, right_weight = right[right_index]
        if left_key == right_key:
            score += left_weight * right_weight
            left_index += 1
            right_index += 1
        elif left_key < right_key:
            left_index += 1
        else:
            right_index += 1
    return score


def _digest(content: str) -> str:
    return hashlib.sha256(content.encode("utf-8")).hexdigest()


def _read_file_bounded(
    descriptor: int,
    size: int,
    *,
    deadline: float,
    cancelled: Callable[[], bool] | None,
) -> bytes | None:
    payload = bytearray()
    while len(payload) < size:
        if _stopped(deadline=deadline, cancelled=cancelled):
            return None
        try:
            chunk = os.read(
                descriptor,
                min(64 * 1024, size - len(payload)),
            )
        except (BlockingIOError, OSError):
            return None
        if not chunk:
            break
        if b"\x00" in chunk or any(
            byte < 9 or 13 < byte < 32 for byte in chunk
        ):
            return None
        payload.extend(chunk)
    return bytes(payload)


def _verified_preview_lines(
    lines: list[str],
    start_line: int,
    end_line: int,
    expected_digest: str,
) -> tuple[int, str] | None:
    content = "\n".join(lines[start_line - 1 : end_line])
    if _digest(content) != expected_digest:
        return None
    for offset, line in enumerate(lines[start_line - 1 : end_line]):
        if line.strip():
            return start_line + offset, line[:_MAX_PREVIEW_CHARS]
    return start_line, ""


def _stopped(
    *,
    deadline: float,
    cancelled: Callable[[], bool] | None,
) -> bool:
    return (
        time.monotonic() >= deadline
        or cancelled is not None
        and cancelled()
    )


def _search_result(
    query: str,
    *,
    started: float,
    matches: list[dict[str, Any]] | None = None,
    stale_chunks: int = 0,
    files_scanned: int = 0,
    truncated: bool = False,
    cancelled: Callable[[], bool] | None = None,
) -> dict[str, Any]:
    selected = matches or []
    return {
        "ok": True,
        "query": query,
        "mode": "semantic",
        "count": len(selected),
        "matches": selected,
        "files_scanned": files_scanned,
        "stale_chunks": stale_chunks,
        "duration_ms": max(0, int((time.monotonic() - started) * 1000)),
        "truncated": truncated,
        "cancelled": bool(cancelled is not None and cancelled()),
    }
