"""Owner-only transactional store for Git worktree lifecycle state."""

from __future__ import annotations

import re
import sqlite3
import threading
from pathlib import Path
from typing import Optional

from runtime.storage.migrations import (
    create_private_file,
    prepare_sqlite_database,
    run_sqlite_migrations,
    secure_directory,
    secure_file,
)

from .models import GitWorkspaceRecord, WorktreeState

_SESSION_ID = re.compile(r"[A-Za-z0-9][A-Za-z0-9_-]{0,127}")
_NOW = "strftime('%Y-%m-%dT%H:%M:%fZ', 'now')"
_SCHEMA_VERSION = 1


def _migrate_to_v1(connection: sqlite3.Connection) -> None:
    connection.execute(
        f"""
        CREATE TABLE IF NOT EXISTS git_worktrees (
            session_id TEXT PRIMARY KEY,
            source_root TEXT NOT NULL,
            git_common_dir TEXT NOT NULL,
            source_branch TEXT NOT NULL,
            base_commit TEXT NOT NULL,
            worktree_path TEXT NOT NULL UNIQUE,
            session_branch TEXT NOT NULL,
            source_dirty INTEGER NOT NULL,
            state TEXT NOT NULL,
            created_at TEXT NOT NULL DEFAULT ({_NOW}),
            updated_at TEXT NOT NULL DEFAULT ({_NOW})
        )
        """
    )


_MIGRATIONS = {1: _migrate_to_v1}


class GitWorktreeStore:
    def __init__(self, base_dir: str | Path) -> None:
        self.base = Path(base_dir).expanduser().resolve()
        secure_directory(self.base)
        self.db_path = self.base / "git-worktrees.db"
        self._lock = threading.RLock()
        previous_version = prepare_sqlite_database(
            self.db_path,
            _SCHEMA_VERSION,
            "Git worktree",
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
            _MIGRATIONS,
        )
        if previous_version < _SCHEMA_VERSION:
            self._connection.execute("PRAGMA optimize")
        secure_file(self.db_path)

    def close(self) -> None:
        with self._lock:
            self._connection.close()

    def save(self, record: GitWorkspaceRecord) -> GitWorkspaceRecord:
        _validate_record(record)
        with self._lock, self._connection:
            self._connection.execute(
                f"""
                INSERT INTO git_worktrees (
                    session_id, source_root, git_common_dir, source_branch,
                    base_commit, worktree_path, session_branch, source_dirty,
                    state, created_at, updated_at
                )
                VALUES (
                    ?, ?, ?, ?, ?, ?, ?, ?, ?,
                    COALESCE(NULLIF(?, ''), {_NOW}),
                    {_NOW}
                )
                ON CONFLICT(session_id) DO UPDATE SET
                    source_root = excluded.source_root,
                    git_common_dir = excluded.git_common_dir,
                    source_branch = excluded.source_branch,
                    base_commit = excluded.base_commit,
                    worktree_path = excluded.worktree_path,
                    session_branch = excluded.session_branch,
                    source_dirty = excluded.source_dirty,
                    state = excluded.state,
                    updated_at = excluded.updated_at
                """,
                (
                    record.session_id,
                    str(record.source_root),
                    str(record.git_common_dir),
                    record.source_branch,
                    record.base_commit,
                    str(record.worktree_path),
                    record.session_branch,
                    int(record.source_dirty),
                    record.state.value,
                    record.created_at,
                ),
            )
            stored = self._load(record.session_id)
        assert stored is not None
        return stored

    def load(self, session_id: str) -> Optional[GitWorkspaceRecord]:
        _validate_session_id(session_id)
        with self._lock:
            return self._load(session_id)

    def delete(self, session_id: str) -> bool:
        _validate_session_id(session_id)
        with self._lock, self._connection:
            cursor = self._connection.execute(
                "DELETE FROM git_worktrees WHERE session_id = ?",
                (session_id,),
            )
            return cursor.rowcount == 1

    def _load(self, session_id: str) -> Optional[GitWorkspaceRecord]:
        row = self._connection.execute(
            "SELECT * FROM git_worktrees WHERE session_id = ?",
            (session_id,),
        ).fetchone()
        if row is None:
            return None
        return GitWorkspaceRecord(
            session_id=row["session_id"],
            source_root=Path(row["source_root"]),
            git_common_dir=Path(row["git_common_dir"]),
            source_branch=row["source_branch"],
            base_commit=row["base_commit"],
            worktree_path=Path(row["worktree_path"]),
            session_branch=row["session_branch"],
            source_dirty=bool(row["source_dirty"]),
            state=WorktreeState(row["state"]),
            created_at=row["created_at"],
            updated_at=row["updated_at"],
        )


def _validate_session_id(session_id: str) -> None:
    if (
        not isinstance(session_id, str)
        or session_id.startswith("__")
        or _SESSION_ID.fullmatch(session_id) is None
    ):
        raise ValueError("invalid session id")


def _validate_record(record: GitWorkspaceRecord) -> None:
    _validate_session_id(record.session_id)
    paths = (
        record.source_root,
        record.git_common_dir,
        record.worktree_path,
    )
    if any(
        not isinstance(path, Path)
        or not path.is_absolute()
        or len(str(path)) > 4096
        for path in paths
    ):
        raise ValueError("invalid Git workspace path")
    if (
        not isinstance(record.source_branch, str)
        or not 1 <= len(record.source_branch) <= 255
        or not isinstance(record.session_branch, str)
        or not 1 <= len(record.session_branch) <= 255
        or not re.fullmatch(r"[0-9a-f]{40,64}", record.base_commit)
        or not isinstance(record.source_dirty, bool)
        or not isinstance(record.state, WorktreeState)
    ):
        raise ValueError("invalid Git workspace record")
