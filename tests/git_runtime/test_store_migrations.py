import json
import sqlite3

import pytest

from runtime.git.store import GitWorktreeStore
from runtime.storage import UnsupportedSchemaVersionError


def test_legacy_git_state_is_versioned_and_backed_up(tmp_path):
    database = tmp_path / "git-worktrees.db"
    with sqlite3.connect(database) as connection:
        connection.execute(
            """
            CREATE TABLE git_worktrees (
                session_id TEXT PRIMARY KEY,
                source_root TEXT NOT NULL,
                git_common_dir TEXT NOT NULL,
                source_branch TEXT NOT NULL,
                base_commit TEXT NOT NULL,
                worktree_path TEXT NOT NULL UNIQUE,
                session_branch TEXT NOT NULL,
                source_dirty INTEGER NOT NULL,
                state TEXT NOT NULL,
                created_at TEXT NOT NULL DEFAULT '',
                updated_at TEXT NOT NULL DEFAULT ''
            )
            """
        )
        connection.execute(
            """
            INSERT INTO git_worktrees VALUES (
                'legacy-session', '/source', '/source/.git', 'main',
                'abc123', '/worktree', 'codinal/legacy', 0, 'active',
                'created', 'updated'
            )
            """
        )

    store = GitWorktreeStore(tmp_path)

    assert store.load("legacy-session").source_branch == "main"
    with sqlite3.connect(database) as migrated:
        assert migrated.execute("PRAGMA user_version").fetchone()[0] == 1
    backups = list(
        (tmp_path / "backups").glob(
            "git-worktrees.db.pre-v0-to-v1-*.bak"
        )
    )
    assert len(backups) == 1
    with sqlite3.connect(backups[0]) as backup:
        assert backup.execute(
            "SELECT base_commit FROM git_worktrees"
        ).fetchone()[0] == "abc123"
    store.close()
    corrupt = b"corrupt Git state"
    database.write_bytes(corrupt)

    recovered = GitWorktreeStore(tmp_path)

    assert recovered.load("legacy-session").source_branch == "main"
    assert next(
        (tmp_path / "recovery").glob(
            "git-worktrees.db.corrupt-*.preserved"
        )
    ).read_bytes() == corrupt
    events = [
        json.loads(line)
        for line in (
            tmp_path / "recovery" / "events.jsonl"
        ).read_text(encoding="utf-8").splitlines()
    ]
    assert [event["action"] for event in events] == [
        "preserved_corrupt_state",
        "restored_from_backup",
    ]


def test_newer_git_state_schema_is_refused_without_modification(tmp_path):
    database = tmp_path / "git-worktrees.db"
    with sqlite3.connect(database) as connection:
        connection.execute("CREATE TABLE future_state (value TEXT)")
        connection.execute("INSERT INTO future_state VALUES ('preserve')")
        connection.execute("PRAGMA user_version = 99")
    original = database.read_bytes()

    with pytest.raises(UnsupportedSchemaVersionError):
        GitWorktreeStore(tmp_path)

    assert database.read_bytes() == original
    assert not (tmp_path / "backups").exists()
    assert not (tmp_path / "recovery").exists()
