import sqlite3
import stat

import pytest

from runtime.sessions import SessionRecord
from runtime.storage import ConversationStore


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
