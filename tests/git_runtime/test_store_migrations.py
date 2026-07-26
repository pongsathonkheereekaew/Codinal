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
        assert migrated.execute("PRAGMA user_version").fetchone()[0] == 3
        assert {
            row[1]
            for row in migrated.execute(
                "PRAGMA table_info(code_checkpoints)"
            )
        } >= {
            "checkpoint_id",
            "session_id",
            "before_tree",
            "after_tree",
            "before_message_count",
            "after_message_count",
            "state",
            "capture_mode",
        }
        assert {
            row[1]
            for row in migrated.execute(
                "PRAGMA table_info(checkpoint_files)"
            )
        } >= {
            "checkpoint_id",
            "path",
            "before_blob",
            "after_blob",
            "before_mode",
            "after_mode",
        }
    backups = list(
        (tmp_path / "backups").glob(
            "git-worktrees.db.pre-v0-to-v3-*.bak"
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


def test_v1_git_state_adds_durable_code_checkpoints(tmp_path):
    database = tmp_path / "git-worktrees.db"
    with sqlite3.connect(database) as connection:
        connection.executescript(
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
            );
            INSERT INTO git_worktrees VALUES (
                'retained-v1', '/source', '/source/.git', 'main',
                'aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa',
                '/worktree', 'codinal/retained', 0, 'active',
                'created', 'updated'
            );
            PRAGMA user_version = 1;
            """
        )

    store = GitWorktreeStore(tmp_path)

    assert store.load("retained-v1").base_commit == "a" * 40
    assert store.list_checkpoints("retained-v1") == []
    with sqlite3.connect(database) as migrated:
        assert migrated.execute("PRAGMA user_version").fetchone()[0] == 3
    assert len(
        list(
            (tmp_path / "backups").glob(
                "git-worktrees.db.pre-v1-to-v3-*.bak"
            )
        )
    ) == 1


def test_v2_git_state_retains_checkpoints_as_whole_tree(tmp_path):
    database = tmp_path / "git-worktrees.db"
    tree = "a" * 40
    checkpoint_id = "b" * 32
    with sqlite3.connect(database) as connection:
        connection.executescript(
            f"""
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
            );
            CREATE TABLE code_checkpoints (
                checkpoint_id TEXT PRIMARY KEY,
                session_id TEXT NOT NULL,
                before_tree TEXT NOT NULL,
                after_tree TEXT NOT NULL DEFAULT '',
                before_message_count INTEGER NOT NULL,
                after_message_count INTEGER NOT NULL DEFAULT 0,
                state TEXT NOT NULL,
                created_at TEXT NOT NULL DEFAULT '',
                updated_at TEXT NOT NULL DEFAULT '',
                FOREIGN KEY (session_id)
                    REFERENCES git_worktrees(session_id)
                    ON DELETE CASCADE
            );
            INSERT INTO git_worktrees VALUES (
                'retained-v2', '/source', '/source/.git', 'main',
                '{tree}', '/worktree', 'codinal/retained', 0, 'active',
                'created', 'updated'
            );
            INSERT INTO code_checkpoints VALUES (
                '{checkpoint_id}', 'retained-v2', '{tree}', '{tree}',
                0, 2, 'completed', 'created', 'updated'
            );
            PRAGMA user_version = 2;
            """
        )

    store = GitWorktreeStore(tmp_path)

    checkpoint = store.load_checkpoint(checkpoint_id)
    assert checkpoint is not None
    assert checkpoint.capture_mode.value == "whole_tree"
    assert store.list_checkpoint_files(checkpoint_id) == []
    with sqlite3.connect(database) as migrated:
        assert migrated.execute("PRAGMA user_version").fetchone()[0] == 3
    assert len(
        list(
            (tmp_path / "backups").glob(
                "git-worktrees.db.pre-v2-to-v3-*.bak"
            )
        )
    ) == 1
