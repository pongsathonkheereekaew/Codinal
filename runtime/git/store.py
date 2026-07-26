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

from .models import (
    CheckpointState,
    CodeCheckpointRecord,
    GitWorkspaceRecord,
    WorktreeState,
)

_SESSION_ID = re.compile(r"[A-Za-z0-9][A-Za-z0-9_-]{0,127}")
_NOW = "strftime('%Y-%m-%dT%H:%M:%fZ', 'now')"
_SCHEMA_VERSION = 2


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


def _migrate_to_v2(connection: sqlite3.Connection) -> None:
    connection.execute(
        f"""
        CREATE TABLE IF NOT EXISTS code_checkpoints (
            checkpoint_id TEXT PRIMARY KEY,
            session_id TEXT NOT NULL,
            before_tree TEXT NOT NULL,
            after_tree TEXT NOT NULL DEFAULT '',
            before_message_count INTEGER NOT NULL,
            after_message_count INTEGER NOT NULL DEFAULT 0,
            state TEXT NOT NULL,
            created_at TEXT NOT NULL DEFAULT ({_NOW}),
            updated_at TEXT NOT NULL DEFAULT ({_NOW}),
            FOREIGN KEY (session_id) REFERENCES git_worktrees(session_id)
                ON DELETE CASCADE
        )
        """
    )
    connection.execute(
        """
        CREATE UNIQUE INDEX IF NOT EXISTS
            one_pending_checkpoint_per_session
        ON code_checkpoints(session_id)
        WHERE state = 'pending'
        """
    )


_MIGRATIONS = {
    1: _migrate_to_v1,
    2: _migrate_to_v2,
}


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
        self._connection.execute("PRAGMA foreign_keys = ON")
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

    def save_checkpoint(
        self,
        record: CodeCheckpointRecord,
    ) -> CodeCheckpointRecord:
        _validate_checkpoint(record)
        with self._lock, self._connection:
            self._connection.execute(
                f"""
                INSERT INTO code_checkpoints (
                    checkpoint_id, session_id, before_tree, after_tree,
                    before_message_count, after_message_count, state,
                    created_at, updated_at
                )
                VALUES (
                    ?, ?, ?, ?, ?, ?, ?,
                    COALESCE(NULLIF(?, ''), {_NOW}),
                    {_NOW}
                )
                ON CONFLICT(checkpoint_id) DO UPDATE SET
                    after_tree = excluded.after_tree,
                    after_message_count = excluded.after_message_count,
                    state = excluded.state,
                    updated_at = excluded.updated_at
                """,
                (
                    record.checkpoint_id,
                    record.session_id,
                    record.before_tree,
                    record.after_tree,
                    record.before_message_count,
                    record.after_message_count,
                    record.state.value,
                    record.created_at,
                ),
            )
            stored = self._load_checkpoint(record.checkpoint_id)
        assert stored is not None
        return stored

    def load_checkpoint(
        self,
        checkpoint_id: str,
    ) -> Optional[CodeCheckpointRecord]:
        _validate_checkpoint_id(checkpoint_id)
        with self._lock:
            return self._load_checkpoint(checkpoint_id)

    def pending_checkpoint(
        self,
        session_id: str,
    ) -> Optional[CodeCheckpointRecord]:
        _validate_session_id(session_id)
        with self._lock:
            row = self._connection.execute(
                """
                SELECT * FROM code_checkpoints
                WHERE session_id = ? AND state = 'pending'
                """,
                (session_id,),
            ).fetchone()
        return _checkpoint_from_row(row) if row is not None else None

    def pending_checkpoints(self) -> list[CodeCheckpointRecord]:
        with self._lock:
            rows = self._connection.execute(
                """
                SELECT * FROM code_checkpoints
                WHERE state = 'pending'
                ORDER BY created_at, rowid
                """
            ).fetchall()
        return [_checkpoint_from_row(row) for row in rows]

    def list_checkpoints(
        self,
        session_id: str,
    ) -> list[CodeCheckpointRecord]:
        _validate_session_id(session_id)
        with self._lock:
            rows = self._connection.execute(
                """
                SELECT * FROM code_checkpoints
                WHERE session_id = ? AND state = 'completed'
                ORDER BY created_at DESC, rowid DESC
                """,
                (session_id,),
            ).fetchall()
        return [_checkpoint_from_row(row) for row in rows]

    def discard_checkpoint_history(
        self,
        session_id: str,
        checkpoint_id: str,
    ) -> list[CodeCheckpointRecord]:
        _validate_session_id(session_id)
        _validate_checkpoint_id(checkpoint_id)
        with self._lock, self._connection:
            rows = self._connection.execute(
                """
                SELECT * FROM code_checkpoints
                WHERE session_id = ? AND state = 'completed'
                ORDER BY created_at DESC, rowid DESC
                """,
                (session_id,),
            ).fetchall()
            records = [_checkpoint_from_row(row) for row in rows]
            try:
                target_index = next(
                    index
                    for index, record in enumerate(records)
                    if record.checkpoint_id == checkpoint_id
                )
            except StopIteration:
                raise ValueError("checkpoint not found") from None
            discarded = records[: target_index + 1]
            for record in discarded:
                self._connection.execute(
                    "DELETE FROM code_checkpoints WHERE checkpoint_id = ?",
                    (record.checkpoint_id,),
                )
        return discarded

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

    def _load_checkpoint(
        self,
        checkpoint_id: str,
    ) -> Optional[CodeCheckpointRecord]:
        row = self._connection.execute(
            """
            SELECT * FROM code_checkpoints WHERE checkpoint_id = ?
            """,
            (checkpoint_id,),
        ).fetchone()
        return _checkpoint_from_row(row) if row is not None else None


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


def _validate_checkpoint_id(checkpoint_id: str) -> None:
    if (
        not isinstance(checkpoint_id, str)
        or re.fullmatch(r"[0-9a-f]{32}", checkpoint_id) is None
    ):
        raise ValueError("invalid checkpoint id")


def _validate_checkpoint(record: CodeCheckpointRecord) -> None:
    _validate_checkpoint_id(record.checkpoint_id)
    _validate_session_id(record.session_id)
    if (
        not re.fullmatch(r"[0-9a-f]{40,64}", record.before_tree)
        or (
            record.after_tree
            and re.fullmatch(r"[0-9a-f]{40,64}", record.after_tree)
            is None
        )
        or not isinstance(record.before_message_count, int)
        or record.before_message_count < 0
        or not isinstance(record.after_message_count, int)
        or record.after_message_count < 0
        or not isinstance(record.state, CheckpointState)
        or (
            record.after_tree
            and record.after_message_count
            < record.before_message_count
        )
        or (
            not record.after_tree
            and record.after_message_count != 0
        )
        or (
            record.state is CheckpointState.COMPLETED
            and not record.after_tree
        )
    ):
        raise ValueError("invalid code checkpoint")


def _checkpoint_from_row(row: sqlite3.Row) -> CodeCheckpointRecord:
    return CodeCheckpointRecord(
        checkpoint_id=row["checkpoint_id"],
        session_id=row["session_id"],
        before_tree=row["before_tree"],
        after_tree=row["after_tree"],
        before_message_count=int(row["before_message_count"]),
        after_message_count=int(row["after_message_count"]),
        state=CheckpointState(row["state"]),
        created_at=row["created_at"],
        updated_at=row["updated_at"],
    )
