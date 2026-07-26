import json
import os
import sqlite3
import stat
from pathlib import Path

import pytest

from runtime.sessions import (
    SessionRecord,
    TurnCheckpoint,
    TurnStatus,
)
from runtime.storage import (
    ConversationStore,
    ExportTooLargeError,
    UnsupportedSchemaVersionError,
)
from runtime.storage.migrations import (
    restore_latest_backup,
    run_sqlite_migrations,
)


def record(session_id="session-1", **changes):
    values = {
        "session_id": session_id,
        "workspace": "/tmp/workspace",
        "model": "openai:gpt-test",
        "mode": "interactive",
        "messages": [{"role": "user", "content": "hello"}],
        "extra_roots": [],
        "grants": {},
    }
    values.update(changes)
    return SessionRecord(**values)


def test_save_reopen_and_load_preserves_complete_session(tmp_path):
    store = ConversationStore(tmp_path)
    original = record(
        extra_roots=[
            {"path": "/tmp/shared", "writable": False, "label": "shared"}
        ],
        grants={"tools": ["write_file"]},
        pinned=True,
        archived=True,
        origin="desktop",
        origin_label="Codinal",
        turn_checkpoint=TurnCheckpoint.executing(
            {"provider-call-1"}
        ),
    )

    store.save(original)
    store.close()
    reopened = ConversationStore(tmp_path)
    loaded = reopened.load("session-1")

    assert loaded is not None
    assert loaded.workspace == "/tmp/workspace"
    assert loaded.model == "openai:gpt-test"
    assert loaded.messages == original.messages
    assert loaded.message_count == 1
    assert loaded.extra_roots == original.extra_roots
    assert loaded.grants == original.grants
    assert loaded.pinned is True
    assert loaded.archived is True
    assert loaded.origin == "desktop"
    assert loaded.origin_label == "Codinal"
    assert loaded.turn_checkpoint == TurnCheckpoint.executing(
        {"provider-call-1"}
    )


def test_approval_decision_survives_restart_until_tool_finishes(tmp_path):
    store = ConversationStore(tmp_path)
    store.save(record())
    store.save_approval_decision(
        "session-1", "call-1", "a" * 64, "once"
    )
    store.close()

    reopened = ConversationStore(tmp_path)

    assert (
        reopened.load_approval_decision(
            "session-1", "call-1", "a" * 64
        )
        == "once"
    )
    assert (
        reopened.load_approval_decision(
            "session-1", "call-1", "b" * 64
        )
        is None
    )
    reopened.delete_approval_decision("session-1", "call-1")
    assert (
        reopened.load_approval_decision(
            "session-1", "call-1", "a" * 64
        )
        is None
    )


def test_interaction_decision_survives_restart_until_tool_finishes(
    tmp_path,
):
    store = ConversationStore(tmp_path)
    store.save(record())
    response = {"answer": "Use PostgreSQL"}
    store.save_interaction_decision(
        "session-1",
        "call-1",
        "question",
        "a" * 64,
        response,
    )
    store.close()

    reopened = ConversationStore(tmp_path)

    assert reopened.load_interaction_decision(
        "session-1",
        "call-1",
        "question",
        "a" * 64,
    ) == response
    assert (
        reopened.load_interaction_decision(
            "session-1",
            "call-1",
            "question",
            "b" * 64,
        )
        is None
    )
    reopened.save_checkpoint(
        record(
            messages=[
                {"role": "user", "content": "hello"},
                {
                    "role": "tool",
                    "tool_call_id": "call-1",
                    "content": "done",
                },
            ]
        ),
        completed_tool_call_id="call-1",
    )
    assert (
        reopened.load_interaction_decision(
            "session-1",
            "call-1",
            "question",
            "a" * 64,
        )
        is None
    )


def test_checkpoint_and_approval_consumption_commit_atomically(tmp_path):
    store = ConversationStore(tmp_path)
    initial = record(
        turn_checkpoint=TurnCheckpoint.executing({"call-1"})
    )
    store.save(initial)
    store.save_approval_decision(
        "session-1", "call-1", "a" * 64, "once"
    )
    completed = record(
        messages=[
            {"role": "user", "content": "hello"},
            {"role": "tool", "tool_call_id": "call-1", "content": "ok"},
        ],
        turn_checkpoint=TurnCheckpoint(TurnStatus.RUNNING),
    )

    store.save_checkpoint(
        completed,
        completed_tool_call_id="call-1",
    )
    store.close()
    reopened = ConversationStore(tmp_path)

    loaded = reopened.load("session-1")
    assert loaded is not None
    assert loaded.messages == completed.messages
    assert loaded.turn_checkpoint == completed.turn_checkpoint
    assert (
        reopened.load_approval_decision(
            "session-1", "call-1", "a" * 64
        )
        is None
    )


def test_failed_approval_consumption_rolls_back_checkpoint(tmp_path):
    store = ConversationStore(tmp_path)
    initial = record(
        turn_checkpoint=TurnCheckpoint.executing({"call-1"})
    )
    store.save(initial)
    store.save_approval_decision(
        "session-1", "call-1", "a" * 64, "once"
    )
    with sqlite3.connect(store.db_path) as connection:
        connection.execute(
            """
            CREATE TRIGGER reject_approval_delete
            BEFORE DELETE ON approval_decisions
            BEGIN
                SELECT RAISE(ABORT, 'simulated crash window');
            END
            """
        )

    with pytest.raises(sqlite3.IntegrityError):
        store.save_checkpoint(
            record(
                messages=[
                    {"role": "user", "content": "changed"}
                ],
                turn_checkpoint=TurnCheckpoint(TurnStatus.RUNNING),
            ),
            completed_tool_call_id="call-1",
        )

    loaded = store.load("session-1")
    assert loaded is not None
    assert loaded.messages == initial.messages
    assert loaded.turn_checkpoint == initial.turn_checkpoint
    assert (
        store.load_approval_decision(
            "session-1", "call-1", "a" * 64
        )
        == "once"
    )


def test_isolated_runtime_workspace_keeps_user_source_for_listing(
    tmp_path,
):
    store = ConversationStore(tmp_path)
    isolated = record(
        workspace="/private/codinal/worktree",
        source_workspace="/Users/example/project",
    )

    store.save(isolated)
    loaded = store.load("session-1")

    assert loaded.workspace == "/private/codinal/worktree"
    assert loaded.source_workspace == "/Users/example/project"
    assert [
        item.session_id
        for item in store.list(workspace="/Users/example/project")
    ] == ["session-1"]
    assert store.list(workspace="/private/codinal/worktree") == []


def test_save_appends_and_can_replace_diverged_history_atomically(tmp_path):
    store = ConversationStore(tmp_path)
    store.save(record())
    store.save(
        record(
            messages=[
                {"role": "user", "content": "hello"},
                {"role": "assistant", "content": "first"},
            ]
        )
    )
    store.save(
        record(
            messages=[
                {"role": "user", "content": "replacement"},
                {"role": "assistant", "content": "second"},
            ]
        )
    )

    assert store.load("session-1").messages == [
        {"role": "user", "content": "replacement"},
        {"role": "assistant", "content": "second"},
    ]


def test_rename_flags_roots_list_and_delete(tmp_path):
    store = ConversationStore(tmp_path)
    store.save(record())

    assert store.rename("session-1", "Renamed") is True
    assert store.set_flags(
        "session-1",
        pinned=True,
        archived=True,
    ) is True
    store.set_extra_roots(
        "session-1",
        [{"path": "/tmp/shared", "writable": True}],
    )

    listed = store.list()
    assert len(listed) == 1
    assert listed[0].messages == []
    assert listed[0].message_count == 1
    assert listed[0].title == "Renamed"
    assert listed[0].pinned is True
    assert listed[0].archived is True
    assert store.load("session-1").extra_roots == [
        {"path": "/tmp/shared", "writable": True}
    ]
    assert store.delete("session-1") is True
    assert store.load("session-1") is None


@pytest.mark.parametrize(
    "session_id",
    ["../escape", "__system", "contains/slash", "", "x" * 129],
)
def test_storage_rejects_unsafe_or_internal_session_ids(
    tmp_path,
    session_id,
):
    store = ConversationStore(tmp_path)

    with pytest.raises(ValueError, match="invalid session id"):
        store.save(record(session_id=session_id))
    with pytest.raises(ValueError, match="invalid session id"):
        store.load(session_id)


def test_invalid_serialized_message_rolls_back_metadata_and_history(tmp_path):
    store = ConversationStore(tmp_path)
    store.save(record())

    with pytest.raises(ValueError, match="invalid session data"):
        store.save(
            record(
                model="anthropic:claude-test",
                messages=[{"role": "user", "content": float("nan")}],
            )
        )

    loaded = store.load("session-1")
    assert loaded.model == "openai:gpt-test"
    assert loaded.messages == [{"role": "user", "content": "hello"}]


def test_foreign_key_cascade_removes_message_rows(tmp_path):
    store = ConversationStore(tmp_path)
    store.save(record())
    store.delete("session-1")
    connection = sqlite3.connect(store.db_path)

    count = connection.execute(
        "SELECT COUNT(*) FROM messages WHERE session_id = ?",
        ("session-1",),
    ).fetchone()[0]

    assert count == 0


def test_store_directory_and_database_are_owner_only(tmp_path):
    base = tmp_path / "private"
    store = ConversationStore(base)

    assert stat.S_IMODE(base.stat().st_mode) == 0o700
    assert stat.S_IMODE(store.db_path.stat().st_mode) == 0o600


def test_sqlite_migration_requires_chain_through_declared_target(tmp_path):
    connection = sqlite3.connect(tmp_path / "chain.db")

    with pytest.raises(RuntimeError, match="version gap"):
        run_sqlite_migrations(
            connection,
            current_version=0,
            target_version=2,
            migrations={1: lambda database: database.execute("SELECT 1")},
        )

    assert connection.execute("PRAGMA user_version").fetchone()[0] == 0
    connection.close()


def test_restore_uses_newest_timestamp_across_schema_versions(tmp_path):
    target = tmp_path / "codinal.db"
    target.write_text("corrupt", encoding="utf-8")
    backup_dir = tmp_path / "backups"
    backup_dir.mkdir()
    older = backup_dir / (
        "codinal.db.pre-v1-to-v2-20260101T000000000000Z.bak"
    )
    newer = backup_dir / (
        "codinal.db.pre-v0-to-v2-20260102T000000000000Z.bak"
    )
    older.write_text("older", encoding="utf-8")
    newer.write_text("newer", encoding="utf-8")

    restored = restore_latest_backup(
        target,
        lambda candidate: candidate.read_text(encoding="utf-8")
        in {"older", "newer"},
    )

    assert restored == newer
    assert target.read_text(encoding="utf-8") == "newer"


def test_existing_phase_2_database_migrates_source_workspace_column(
    tmp_path,
):
    connection = sqlite3.connect(tmp_path / "codinal.db")
    connection.execute(
        """
        CREATE TABLE sessions (
            session_id TEXT PRIMARY KEY,
            workspace TEXT NOT NULL,
            model TEXT NOT NULL,
            mode TEXT NOT NULL,
            title TEXT,
            agent TEXT NOT NULL DEFAULT 'code',
            extra_roots TEXT NOT NULL DEFAULT '[]',
            grants TEXT NOT NULL DEFAULT '{}',
            pinned INTEGER NOT NULL DEFAULT 0,
            archived INTEGER NOT NULL DEFAULT 0,
            origin TEXT,
            origin_label TEXT,
            updated_at TEXT NOT NULL DEFAULT ''
        )
        """
    )
    connection.commit()
    connection.close()

    store = ConversationStore(tmp_path)
    store.save(
        record(
            workspace="/private/codinal/worktree",
            source_workspace="/Users/example/project",
        )
    )

    assert store.load("session-1").source_workspace == (
        "/Users/example/project"
    )
    with sqlite3.connect(store.db_path) as migrated:
        assert migrated.execute("PRAGMA user_version").fetchone()[0] == 4
    backups = list((tmp_path / "backups").glob("codinal.db.pre-v0-to-v4-*.bak"))
    assert len(backups) == 1
    assert stat.S_IMODE((tmp_path / "backups").stat().st_mode) == 0o700
    assert stat.S_IMODE(backups[0].stat().st_mode) == 0o600
    with sqlite3.connect(backups[0]) as backup:
        columns = {
            row[1]
            for row in backup.execute("PRAGMA table_info(sessions)")
        }
    assert "source_workspace" not in columns


def test_v1_conversation_schema_migrates_to_v4_without_losing_data(tmp_path):
    database = tmp_path / "codinal.db"
    with sqlite3.connect(database) as connection:
        connection.executescript(
            """
            CREATE TABLE sessions (
                session_id TEXT PRIMARY KEY,
                workspace TEXT NOT NULL,
                model TEXT NOT NULL,
                mode TEXT NOT NULL,
                title TEXT,
                agent TEXT NOT NULL DEFAULT 'code',
                extra_roots TEXT NOT NULL DEFAULT '[]',
                grants TEXT NOT NULL DEFAULT '{}',
                pinned INTEGER NOT NULL DEFAULT 0,
                archived INTEGER NOT NULL DEFAULT 0,
                origin TEXT,
                origin_label TEXT,
                updated_at TEXT NOT NULL DEFAULT ''
            );
            CREATE TABLE messages (
                session_id TEXT NOT NULL,
                sequence INTEGER NOT NULL,
                payload TEXT NOT NULL,
                PRIMARY KEY (session_id, sequence)
            );
            CREATE TABLE workspaces (
                path TEXT PRIMARY KEY,
                last_used TEXT NOT NULL DEFAULT ''
            );
            INSERT INTO sessions (
                session_id, workspace, model, mode, title, agent
            ) VALUES (
                'retained-v1', '/workspace', 'openai:gpt-test',
                'interactive', 'Retained session', 'code'
            );
            INSERT INTO messages VALUES (
                'retained-v1', 0,
                '{"role":"user","content":"preserve this"}'
            );
            PRAGMA user_version = 1;
            """
        )

    store = ConversationStore(tmp_path)
    restored = store.load("retained-v1")

    assert restored is not None
    assert restored.messages == [
        {"role": "user", "content": "preserve this"}
    ]
    assert restored.source_workspace is None
    with sqlite3.connect(database) as migrated:
        assert migrated.execute("PRAGMA user_version").fetchone()[0] == 4
    assert len(
        list(
            (tmp_path / "backups").glob(
                "codinal.db.pre-v1-to-v4-*.bak"
            )
        )
    ) == 1


def test_v2_conversation_schema_adds_idle_recovery_state(tmp_path):
    database = tmp_path / "codinal.db"
    with sqlite3.connect(database) as connection:
        connection.executescript(
            """
            CREATE TABLE sessions (
                session_id TEXT PRIMARY KEY,
                workspace TEXT NOT NULL,
                source_workspace TEXT,
                model TEXT NOT NULL,
                mode TEXT NOT NULL,
                title TEXT,
                agent TEXT NOT NULL DEFAULT 'code',
                extra_roots TEXT NOT NULL DEFAULT '[]',
                grants TEXT NOT NULL DEFAULT '{}',
                pinned INTEGER NOT NULL DEFAULT 0,
                archived INTEGER NOT NULL DEFAULT 0,
                origin TEXT,
                origin_label TEXT,
                updated_at TEXT NOT NULL DEFAULT ''
            );
            CREATE TABLE messages (
                session_id TEXT NOT NULL,
                sequence INTEGER NOT NULL,
                payload TEXT NOT NULL,
                PRIMARY KEY (session_id, sequence)
            );
            CREATE TABLE workspaces (
                path TEXT PRIMARY KEY,
                last_used TEXT NOT NULL DEFAULT ''
            );
            INSERT INTO sessions (
                session_id, workspace, model, mode, agent
            ) VALUES (
                'retained-v2', '/workspace', 'openai:gpt-test',
                'interactive', 'code'
            );
            PRAGMA user_version = 2;
            """
        )

    store = ConversationStore(tmp_path)
    restored = store.load("retained-v2")

    assert restored is not None
    assert restored.turn_checkpoint == TurnCheckpoint(
        TurnStatus.IDLE
    )
    with sqlite3.connect(database) as migrated:
        assert migrated.execute("PRAGMA user_version").fetchone()[0] == 4
    assert len(
        list(
            (tmp_path / "backups").glob(
                "codinal.db.pre-v2-to-v4-*.bak"
            )
        )
    ) == 1


def test_v3_conversation_schema_adds_interaction_decisions(tmp_path):
    store = ConversationStore(tmp_path)
    store.save(record())
    store.close()
    database = tmp_path / "codinal.db"
    with sqlite3.connect(database) as connection:
        connection.execute("DROP TABLE interaction_decisions")
        connection.execute("PRAGMA user_version = 3")

    migrated = ConversationStore(tmp_path)

    migrated.save_interaction_decision(
        "session-1",
        "call-1",
        "plan",
        "a" * 64,
        {"approved": True, "mode": "interactive"},
    )
    assert migrated.load_interaction_decision(
        "session-1",
        "call-1",
        "plan",
        "a" * 64,
    ) == {"approved": True, "mode": "interactive"}
    with sqlite3.connect(database) as connection:
        assert connection.execute("PRAGMA user_version").fetchone()[0] == 4
    assert len(
        list(
            (tmp_path / "backups").glob(
                "codinal.db.pre-v3-to-v4-*.bak"
            )
        )
    ) == 1


def test_corrupt_database_is_preserved_before_empty_recovery(tmp_path):
    corrupt = b"not a sqlite database\x00private conversation bytes"
    database = tmp_path / "codinal.db"
    database.write_bytes(corrupt)

    store = ConversationStore(tmp_path)

    assert store.list() == []
    preserved = list(
        (tmp_path / "recovery").glob("codinal.db.corrupt-*.preserved")
    )
    assert len(preserved) == 1
    assert preserved[0].read_bytes() == corrupt
    assert stat.S_IMODE((tmp_path / "recovery").stat().st_mode) == 0o700
    assert stat.S_IMODE(preserved[0].stat().st_mode) == 0o600
    assert stat.S_IMODE(
        (tmp_path / "recovery" / "events.jsonl").stat().st_mode
    ) == 0o600
    assert database.read_bytes() != corrupt
    with sqlite3.connect(database) as recovered:
        assert recovered.execute("PRAGMA integrity_check").fetchone()[0] == "ok"
        assert recovered.execute("PRAGMA user_version").fetchone()[0] == 4


def test_corrupt_database_restores_latest_valid_backup(tmp_path):
    first = ConversationStore(tmp_path)
    first.save(
        record(
            session_id="recover-me",
            messages=[{"role": "user", "content": "durable history"}],
        )
    )
    first.close()
    with sqlite3.connect(tmp_path / "codinal.db") as connection:
        connection.execute("PRAGMA user_version = 1")
    migrated = ConversationStore(tmp_path)
    migrated.close()
    database = tmp_path / "codinal.db"
    corrupt = b"corrupt active database"
    database.write_bytes(corrupt)

    recovered = ConversationStore(tmp_path)

    assert recovered.load("recover-me").messages == [
        {"role": "user", "content": "durable history"}
    ]
    preserved = list(
        (tmp_path / "recovery").glob(
            "codinal.db.corrupt-*.preserved"
        )
    )
    assert len(preserved) == 1
    assert preserved[0].read_bytes() == corrupt
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


def test_newer_database_schema_is_refused_without_modification(tmp_path):
    database = tmp_path / "codinal.db"
    with sqlite3.connect(database) as connection:
        connection.execute("CREATE TABLE future_data (value TEXT)")
        connection.execute("INSERT INTO future_data VALUES ('preserve me')")
        connection.execute("PRAGMA user_version = 99")
    original = database.read_bytes()

    with pytest.raises(UnsupportedSchemaVersionError):
        ConversationStore(tmp_path)

    assert database.read_bytes() == original
    assert not (tmp_path / "backups").exists()
    assert not (tmp_path / "recovery").exists()


def test_negative_database_schema_is_refused_without_modification(tmp_path):
    database = tmp_path / "codinal.db"
    with sqlite3.connect(database) as connection:
        connection.execute("CREATE TABLE retained (value TEXT)")
        connection.execute("INSERT INTO retained VALUES ('preserve me')")
        connection.execute("PRAGMA user_version = -1")
    original = database.read_bytes()

    with pytest.raises(UnsupportedSchemaVersionError):
        ConversationStore(tmp_path)

    assert database.read_bytes() == original
    assert not (tmp_path / "backups").exists()
    assert not (tmp_path / "recovery").exists()


def test_export_refuses_records_above_safe_stored_size(
    tmp_path,
    monkeypatch,
):
    store = ConversationStore(tmp_path)
    store.save(
        record(
            messages=[
                {"role": "user", "content": "bounded export payload"}
            ]
        )
    )
    monkeypatch.setattr(
        "runtime.storage.conversations.MAX_EXPORT_STORED_BYTES",
        8,
    )

    with pytest.raises(ExportTooLargeError):
        store.export_records()


def test_locked_database_is_never_misclassified_as_corrupt(tmp_path):
    database = tmp_path / "codinal.db"
    store = ConversationStore(tmp_path)
    store.close()
    original = database.read_bytes()
    locker = sqlite3.connect(database)
    locker.execute("BEGIN EXCLUSIVE")
    try:
        with pytest.raises(sqlite3.OperationalError):
            ConversationStore(tmp_path)
    finally:
        locker.rollback()
        locker.close()

    assert database.read_bytes() == original
    assert not (tmp_path / "recovery").exists()


def test_migration_fails_closed_when_backup_permissions_cannot_be_secured(
    tmp_path,
    monkeypatch,
):
    database = tmp_path / "codinal.db"
    with sqlite3.connect(database) as connection:
        connection.execute("CREATE TABLE retained (value TEXT)")
        connection.execute("INSERT INTO retained VALUES ('private')")
        connection.execute("PRAGMA user_version = 1")
    original = database.read_bytes()
    real_chmod = os.chmod

    def deny_backup_chmod(path, mode):
        if Path(path).name == "backups":
            raise PermissionError("simulated permission failure")
        real_chmod(path, mode)

    monkeypatch.setattr(
        "runtime.storage.migrations.os.chmod",
        deny_backup_chmod,
    )

    with pytest.raises(PermissionError, match="simulated"):
        ConversationStore(tmp_path)

    assert database.read_bytes() == original
    assert not list((tmp_path / "backups").glob("*.bak"))
