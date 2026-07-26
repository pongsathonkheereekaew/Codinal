"""Owner-only transactional store for Git worktree lifecycle state."""

from __future__ import annotations

import hashlib
import re
import sqlite3
import threading
from pathlib import Path
from pathlib import PurePosixPath
from typing import Optional

from runtime.storage.migrations import (
    create_private_file,
    prepare_sqlite_database,
    run_sqlite_migrations,
    secure_directory,
    secure_file,
)

from .models import (
    CheckpointCaptureMode,
    CheckpointFileRecord,
    CheckpointRestoreRecord,
    CheckpointRestoreScope,
    CheckpointRestoreState,
    CheckpointState,
    CodeCheckpointRecord,
    GitWorkspaceRecord,
    WorktreeState,
)

_SESSION_ID = re.compile(r"[A-Za-z0-9][A-Za-z0-9_-]{0,127}")
_NOW = "strftime('%Y-%m-%dT%H:%M:%fZ', 'now')"
_SCHEMA_VERSION = 5


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


def _migrate_to_v3(connection: sqlite3.Connection) -> None:
    checkpoint_columns = {
        row[1]
        for row in connection.execute(
            "PRAGMA table_info(code_checkpoints)"
        )
    }
    if "capture_mode" not in checkpoint_columns:
        connection.execute(
            """
            ALTER TABLE code_checkpoints
            ADD COLUMN capture_mode TEXT NOT NULL DEFAULT 'whole_tree'
            """
        )
    connection.execute(
        """
        CREATE TABLE IF NOT EXISTS checkpoint_files (
            checkpoint_id TEXT NOT NULL,
            path TEXT NOT NULL,
            before_blob TEXT NOT NULL DEFAULT '',
            after_blob TEXT NOT NULL DEFAULT '',
            before_mode INTEGER NOT NULL DEFAULT 0,
            after_mode INTEGER NOT NULL DEFAULT 0,
            PRIMARY KEY (checkpoint_id, path),
            FOREIGN KEY (checkpoint_id)
                REFERENCES code_checkpoints(checkpoint_id)
                ON DELETE CASCADE
        )
        """
    )


def _migrate_to_v4(connection: sqlite3.Connection) -> None:
    connection.execute(
        f"""
        CREATE TABLE IF NOT EXISTS checkpoint_restores (
            operation_id TEXT PRIMARY KEY,
            checkpoint_id TEXT NOT NULL,
            session_id TEXT NOT NULL UNIQUE,
            scope TEXT NOT NULL,
            state TEXT NOT NULL,
            message_count INTEGER NOT NULL,
            code_before_tree TEXT NOT NULL DEFAULT '',
            code_after_tree TEXT NOT NULL DEFAULT '',
            created_at TEXT NOT NULL DEFAULT ({_NOW}),
            updated_at TEXT NOT NULL DEFAULT ({_NOW}),
            FOREIGN KEY (session_id)
                REFERENCES git_worktrees(session_id)
                ON DELETE CASCADE
        )
        """
    )
    connection.execute(
        """
        CREATE TABLE IF NOT EXISTS checkpoint_restore_history (
            operation_id TEXT NOT NULL,
            checkpoint_id TEXT NOT NULL,
            position INTEGER NOT NULL,
            PRIMARY KEY (operation_id, checkpoint_id),
            UNIQUE (operation_id, position),
            FOREIGN KEY (operation_id)
                REFERENCES checkpoint_restores(operation_id)
                ON DELETE CASCADE
        )
        """
    )


def _migrate_to_v5(connection: sqlite3.Connection) -> None:
    connection.execute(
        """
        CREATE TABLE IF NOT EXISTS plain_workspaces (
            session_id TEXT PRIMARY KEY,
            workspace_path TEXT NOT NULL,
            FOREIGN KEY (session_id) REFERENCES git_worktrees(session_id)
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

    def save_plain_workspace(
        self,
        session_id: str,
        workspace_path: Path,
    ) -> Path:
        _validate_session_id(session_id)
        workspace = Path(workspace_path)
        if (
            not workspace.is_absolute()
            or not workspace.is_dir()
            or len(str(workspace)) > 4096
        ):
            raise ValueError("invalid plain workspace path")
        identity = hashlib.sha256(
            session_id.encode("utf-8")
        ).hexdigest()
        marker = self.base / "plain-workspaces" / identity
        with self._lock, self._connection:
            self._connection.execute(
                f"""
                INSERT INTO git_worktrees (
                    session_id, source_root, git_common_dir, source_branch,
                    base_commit, worktree_path, session_branch, source_dirty,
                    state, created_at, updated_at
                )
                VALUES (
                    ?, ?, ?, 'codinal-plain',
                    '0000000000000000000000000000000000000000',
                    ?, 'codinal-plain', 0, 'active', {_NOW}, {_NOW}
                )
                """,
                (
                    session_id,
                    str(workspace),
                    str(marker),
                    str(marker),
                ),
            )
            self._connection.execute(
                """
                INSERT INTO plain_workspaces (
                    session_id, workspace_path
                )
                VALUES (?, ?)
                """,
                (session_id, str(workspace)),
            )
        return workspace

    def load_plain_workspace(self, session_id: str) -> Path | None:
        _validate_session_id(session_id)
        with self._lock:
            row = self._connection.execute(
                """
                SELECT workspace_path
                FROM plain_workspaces
                WHERE session_id = ?
                """,
                (session_id,),
            ).fetchone()
        return Path(row["workspace_path"]) if row is not None else None

    def is_plain_workspace(self, session_id: str) -> bool:
        return self.load_plain_workspace(session_id) is not None

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
                    capture_mode, created_at, updated_at
                )
                VALUES (
                    ?, ?, ?, ?, ?, ?, ?, ?,
                    COALESCE(NULLIF(?, ''), {_NOW}),
                    {_NOW}
                )
                ON CONFLICT(checkpoint_id) DO UPDATE SET
                    before_tree = excluded.before_tree,
                    after_tree = excluded.after_tree,
                    after_message_count = excluded.after_message_count,
                    state = excluded.state,
                    capture_mode = excluded.capture_mode,
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
                    record.capture_mode.value,
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

    def save_checkpoint_file(
        self,
        record: CheckpointFileRecord,
    ) -> CheckpointFileRecord:
        _validate_checkpoint_file(record)
        with self._lock, self._connection:
            self._connection.execute(
                """
                INSERT INTO checkpoint_files (
                    checkpoint_id, path, before_blob, after_blob,
                    before_mode, after_mode
                )
                VALUES (?, ?, ?, ?, ?, ?)
                ON CONFLICT(checkpoint_id, path) DO UPDATE SET
                    after_blob = excluded.after_blob,
                    after_mode = excluded.after_mode
                """,
                (
                    record.checkpoint_id,
                    record.path,
                    record.before_blob,
                    record.after_blob,
                    record.before_mode,
                    record.after_mode,
                ),
            )
            row = self._connection.execute(
                """
                SELECT * FROM checkpoint_files
                WHERE checkpoint_id = ? AND path = ?
                """,
                (record.checkpoint_id, record.path),
            ).fetchone()
        assert row is not None
        return _checkpoint_file_from_row(row)

    def list_checkpoint_files(
        self,
        checkpoint_id: str,
    ) -> list[CheckpointFileRecord]:
        _validate_checkpoint_id(checkpoint_id)
        with self._lock:
            rows = self._connection.execute(
                """
                SELECT * FROM checkpoint_files
                WHERE checkpoint_id = ?
                ORDER BY path
                """,
                (checkpoint_id,),
            ).fetchall()
        return [_checkpoint_file_from_row(row) for row in rows]

    def delete_checkpoint_files(
        self,
        checkpoint_id: str,
        paths: tuple[str, ...],
    ) -> int:
        _validate_checkpoint_id(checkpoint_id)
        for path in paths:
            _validate_checkpoint_file(
                CheckpointFileRecord(
                    checkpoint_id=checkpoint_id,
                    path=path,
                )
            )
        with self._lock, self._connection:
            deleted = 0
            for path in paths:
                cursor = self._connection.execute(
                    """
                    DELETE FROM checkpoint_files
                    WHERE checkpoint_id = ? AND path = ?
                    """,
                    (checkpoint_id, path),
                )
                deleted += cursor.rowcount
            return deleted

    def save_restore(
        self,
        record: CheckpointRestoreRecord,
    ) -> CheckpointRestoreRecord:
        _validate_restore(record)
        with self._lock, self._connection:
            self._connection.execute(
                f"""
                INSERT INTO checkpoint_restores (
                    operation_id, checkpoint_id, session_id, scope,
                    state, message_count, code_before_tree,
                    code_after_tree, created_at, updated_at
                )
                VALUES (
                    ?, ?, ?, ?, ?, ?, ?, ?,
                    COALESCE(NULLIF(?, ''), {_NOW}), {_NOW}
                )
                ON CONFLICT(operation_id) DO UPDATE SET
                    state = excluded.state,
                    code_before_tree = excluded.code_before_tree,
                    code_after_tree = excluded.code_after_tree,
                    updated_at = excluded.updated_at
                """,
                (
                    record.operation_id,
                    record.checkpoint_id,
                    record.session_id,
                    record.scope.value,
                    record.state.value,
                    record.message_count,
                    record.code_before_tree,
                    record.code_after_tree,
                    record.created_at,
                ),
            )
            for position, checkpoint_id in enumerate(
                record.discard_checkpoint_ids
            ):
                self._connection.execute(
                    """
                    INSERT OR IGNORE INTO checkpoint_restore_history (
                        operation_id, checkpoint_id, position
                    )
                    VALUES (?, ?, ?)
                    """,
                    (
                        record.operation_id,
                        checkpoint_id,
                        position,
                    ),
                )
            stored = self._load_restore(record.operation_id)
        assert stored is not None
        return stored

    def load_restore(
        self,
        operation_id: str,
    ) -> Optional[CheckpointRestoreRecord]:
        _validate_checkpoint_id(operation_id)
        with self._lock:
            return self._load_restore(operation_id)

    def pending_restore(
        self,
        session_id: str,
    ) -> Optional[CheckpointRestoreRecord]:
        _validate_session_id(session_id)
        with self._lock:
            row = self._connection.execute(
                """
                SELECT * FROM checkpoint_restores
                WHERE session_id = ?
                """,
                (session_id,),
            ).fetchone()
        return self._restore_record(row) if row is not None else None

    def pending_restores(self) -> list[CheckpointRestoreRecord]:
        with self._lock:
            rows = self._connection.execute(
                """
                SELECT * FROM checkpoint_restores
                ORDER BY created_at, rowid
                """
            ).fetchall()
        return [self._restore_record(row) for row in rows]

    def delete_restore(self, operation_id: str) -> bool:
        _validate_checkpoint_id(operation_id)
        with self._lock, self._connection:
            cursor = self._connection.execute(
                """
                DELETE FROM checkpoint_restores
                WHERE operation_id = ?
                """,
                (operation_id,),
            )
            return cursor.rowcount == 1

    def delete_checkpoints(
        self,
        session_id: str,
        checkpoint_ids: tuple[str, ...],
    ) -> int:
        _validate_session_id(session_id)
        for checkpoint_id in checkpoint_ids:
            _validate_checkpoint_id(checkpoint_id)
        with self._lock, self._connection:
            deleted = 0
            for checkpoint_id in checkpoint_ids:
                cursor = self._connection.execute(
                    """
                    DELETE FROM code_checkpoints
                    WHERE checkpoint_id = ? AND session_id = ?
                    """,
                    (checkpoint_id, session_id),
                )
                deleted += cursor.rowcount
            return deleted

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

    def _load_restore(
        self,
        operation_id: str,
    ) -> Optional[CheckpointRestoreRecord]:
        row = self._connection.execute(
            """
            SELECT * FROM checkpoint_restores
            WHERE operation_id = ?
            """,
            (operation_id,),
        ).fetchone()
        return self._restore_record(row) if row is not None else None

    def _restore_record(
        self,
        row: sqlite3.Row,
    ) -> CheckpointRestoreRecord:
        history = self._connection.execute(
            """
            SELECT checkpoint_id
            FROM checkpoint_restore_history
            WHERE operation_id = ?
            ORDER BY position
            """,
            (row["operation_id"],),
        ).fetchall()
        return _restore_from_row(
            row,
            tuple(item["checkpoint_id"] for item in history),
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
        (
            record.before_tree
            and re.fullmatch(r"[0-9a-f]{40,64}", record.before_tree)
            is None
        )
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
        or not isinstance(
            record.capture_mode,
            CheckpointCaptureMode,
        )
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
            and (
                not record.before_tree
                or not record.after_tree
            )
        )
        or (
            record.capture_mode is CheckpointCaptureMode.WHOLE_TREE
            and not record.before_tree
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
        capture_mode=CheckpointCaptureMode(row["capture_mode"]),
        created_at=row["created_at"],
        updated_at=row["updated_at"],
    )


def _validate_checkpoint_file(record: CheckpointFileRecord) -> None:
    _validate_checkpoint_id(record.checkpoint_id)
    path = PurePosixPath(record.path)
    valid_modes = {0, 0o100644, 0o100755}
    if (
        not isinstance(record.path, str)
        or not 1 <= len(record.path.encode("utf-8")) <= 4096
        or path.is_absolute()
        or ".." in path.parts
        or str(path) != record.path
        or record.before_mode not in valid_modes
        or record.after_mode not in valid_modes
        or bool(record.before_blob) != bool(record.before_mode)
        or bool(record.after_blob) != bool(record.after_mode)
        or (
            record.before_blob
            and re.fullmatch(
                r"[0-9a-f]{40,64}",
                record.before_blob,
            )
            is None
        )
        or (
            record.after_blob
            and re.fullmatch(
                r"[0-9a-f]{40,64}",
                record.after_blob,
            )
            is None
        )
    ):
        raise ValueError("invalid checkpoint file")


def _checkpoint_file_from_row(
    row: sqlite3.Row,
) -> CheckpointFileRecord:
    return CheckpointFileRecord(
        checkpoint_id=row["checkpoint_id"],
        path=row["path"],
        before_blob=row["before_blob"],
        after_blob=row["after_blob"],
        before_mode=int(row["before_mode"]),
        after_mode=int(row["after_mode"]),
    )


def _validate_restore(record: CheckpointRestoreRecord) -> None:
    _validate_checkpoint_id(record.operation_id)
    _validate_checkpoint_id(record.checkpoint_id)
    _validate_session_id(record.session_id)
    if (
        not isinstance(record.scope, CheckpointRestoreScope)
        or not isinstance(record.state, CheckpointRestoreState)
    ):
        raise ValueError("invalid checkpoint restore")
    allowed_states = {
        CheckpointRestoreScope.CODE: {
            CheckpointRestoreState.PREPARED,
            CheckpointRestoreState.CODE_RESTORED,
        },
        CheckpointRestoreScope.CONVERSATION: {
            CheckpointRestoreState.PREPARED,
            CheckpointRestoreState.CONVERSATION_RESTORED,
        },
        CheckpointRestoreScope.BOTH: set(CheckpointRestoreState),
    }
    requires_code = (
        record.scope is not CheckpointRestoreScope.CONVERSATION
    )
    requires_history_discard = record.scope is not (
        CheckpointRestoreScope.CODE
    )
    trees = (record.code_before_tree, record.code_after_tree)
    if (
        record.state not in allowed_states[record.scope]
        or not isinstance(record.message_count, int)
        or record.message_count < 0
        or any(
            tree
            and re.fullmatch(r"[0-9a-f]{40,64}", tree) is None
            for tree in trees
        )
        or (requires_code and not all(trees))
        or (not requires_code and any(trees))
        or (
            requires_history_discard
            != bool(record.discard_checkpoint_ids)
        )
        or len(set(record.discard_checkpoint_ids))
        != len(record.discard_checkpoint_ids)
    ):
        raise ValueError("invalid checkpoint restore")
    for checkpoint_id in record.discard_checkpoint_ids:
        _validate_checkpoint_id(checkpoint_id)


def _restore_from_row(
    row: sqlite3.Row,
    discard_checkpoint_ids: tuple[str, ...],
) -> CheckpointRestoreRecord:
    return CheckpointRestoreRecord(
        operation_id=row["operation_id"],
        checkpoint_id=row["checkpoint_id"],
        session_id=row["session_id"],
        scope=CheckpointRestoreScope(row["scope"]),
        state=CheckpointRestoreState(row["state"]),
        message_count=int(row["message_count"]),
        code_before_tree=row["code_before_tree"],
        code_after_tree=row["code_after_tree"],
        discard_checkpoint_ids=discard_checkpoint_ids,
        created_at=row["created_at"],
        updated_at=row["updated_at"],
    )
