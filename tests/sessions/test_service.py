from __future__ import annotations

import hashlib
import os
from dataclasses import replace

import pytest

from runtime.sessions import (
    RootDir,
    SessionCleanupError,
    SessionRecord,
    SessionSearchHit,
    SessionService,
    TurnCheckpoint,
)
from runtime.sessions.context import make_project_context_item


class MemorySessionStore:
    def __init__(self, *records: SessionRecord) -> None:
        self.records = {record.session_id: record for record in records}
        self.touched_workspaces = []

    def load(self, session_id: str) -> SessionRecord | None:
        return self.records.get(session_id)

    def save(self, record: SessionRecord) -> None:
        self.records[record.session_id] = record

    def list(self, *, workspace: str | None = None) -> list[SessionRecord]:
        records = list(self.records.values())
        if workspace is not None:
            records = [record for record in records if record.workspace == workspace]
        return records

    def search(
        self,
        query: str,
        *,
        limit: int,
    ) -> list[SessionSearchHit]:
        lowered = query.casefold()
        hits = []
        for record in self.records.values():
            for index, message in enumerate(record.messages):
                content = str(message.get("content", ""))
                if lowered in content.casefold():
                    hits.append(
                        SessionSearchHit(record, content, index)
                    )
                    break
        return hits[:limit]

    def rename(self, session_id: str, title: str) -> bool:
        record = self.records.get(session_id)
        if record is None:
            return False
        self.records[session_id] = replace(record, title=title)
        return True

    def set_flags(
        self,
        session_id: str,
        *,
        pinned: bool | None = None,
        archived: bool | None = None,
    ) -> bool:
        record = self.records.get(session_id)
        if record is None:
            return False
        self.records[session_id] = replace(
            record,
            pinned=record.pinned if pinned is None else pinned,
            archived=record.archived if archived is None else archived,
        )
        return True

    def delete(self, session_id: str) -> bool:
        return self.records.pop(session_id, None) is not None

    def set_extra_roots(
        self, session_id: str, extra_roots: list[dict[str, object]]
    ) -> None:
        record = self.records[session_id]
        self.records[session_id] = replace(record, extra_roots=extra_roots)

    def touch_workspace(self, path: str) -> None:
        self.touched_workspaces.append(path)


def test_session_messages_prefer_live_engine_over_persisted_record(tmp_path):
    record = SessionRecord(
        session_id="s1",
        workspace=str(tmp_path),
        model="test-model",
        mode="interactive",
        messages=[{"role": "user", "content": "persisted"}],
    )
    store = MemorySessionStore(record)
    service = SessionService(store, scratch_base=tmp_path / "scratch")

    class LiveEngine:
        messages = [
            {"role": "user", "content": "persisted"},
            {"role": "assistant", "content": "live"},
        ]

    service.attach_engine("s1", LiveEngine())

    assert service.messages("s1") == [
        {"role": "user", "content": "persisted"},
        {"role": "assistant", "content": "live"},
    ]


def test_get_engine_builds_from_persisted_session_once(tmp_path):
    docs = tmp_path / "docs"
    docs.mkdir()
    docs_stat = docs.stat()
    record = SessionRecord(
        session_id="s1",
        workspace=str(tmp_path),
        model="test-model",
        mode="interactive",
        messages=[{"role": "user", "content": "restore me"}],
        agent="code",
        extra_roots=[
            {
                "path": str(docs),
                "writable": False,
                "_device": docs_stat.st_dev,
                "_inode": docs_stat.st_ino,
            }
        ],
        grants={"tools": ["write_file"]},
    )
    built = []
    engine = object()

    def build(request):
        built.append(request)
        return engine

    service = SessionService(
        MemorySessionStore(record),
        scratch_base=tmp_path / "scratch",
        engine_factory=build,
    )

    assert service.get_engine("s1") is engine
    assert service.get_engine("s1") is engine
    assert len(built) == 1
    assert built[0].record == record
    assert built[0].workspace == tmp_path.resolve()


def test_persisted_engine_does_not_consult_live_default_model(tmp_path):
    record = SessionRecord(
        session_id="s1",
        workspace=str(tmp_path),
        model="persisted:model",
        mode="interactive",
    )
    requests = []
    service = SessionService(
        MemorySessionStore(record),
        scratch_base=tmp_path / "scratch",
        engine_factory=lambda request: requests.append(request) or object(),
        default_model_provider=lambda: (_ for _ in ()).throw(
            RuntimeError("settings unavailable")
        ),
    )

    service.get_engine("s1")

    assert requests[0].model == "persisted:model"


def test_new_engine_requires_existing_workspace_and_touches_it(tmp_path):
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    built = []
    engine = object()
    store = MemorySessionStore()
    service = SessionService(
        store,
        scratch_base=tmp_path / "scratch",
        engine_factory=lambda request: built.append(request) or engine,
    )

    assert service.get_engine("new") is None
    assert service.get_engine("new", workspace=workspace) is engine
    assert built[0].record is None
    assert built[0].workspace == workspace.resolve()
    assert store.touched_workspaces == [str(workspace.resolve())]


def test_new_engine_accepts_selected_model_without_overriding_restore(tmp_path):
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    requests = []
    service = SessionService(
        MemorySessionStore(),
        scratch_base=tmp_path / "scratch",
        engine_factory=lambda request: requests.append(request) or object(),
    )

    service.get_engine(
        "new",
        workspace=workspace,
        model="gemini:gemini-selected",
    )

    assert requests[0].model == "gemini:gemini-selected"


def test_persist_saves_snapshot_from_injected_adapter(tmp_path):
    store = MemorySessionStore()
    engine = object()
    expected = SessionRecord(
        session_id="s1",
        workspace=str(tmp_path),
        model="test-model",
        mode="interactive",
        messages=[{"role": "assistant", "content": "done"}],
    )
    service = SessionService(
        store,
        scratch_base=tmp_path / "scratch",
        snapshotter=lambda session_id, attached: (
            expected if (session_id, attached) == ("s1", engine) else None
        ),
    )
    service.attach_engine("s1", engine)

    assert service.persist("s1") is True
    assert store.load("s1") == expected


def test_persist_checkpoint_atomically_records_recovery_state(tmp_path):
    store = MemorySessionStore()
    engine = object()
    snapshot = SessionRecord(
        session_id="s1",
        workspace=str(tmp_path),
        model="test-model",
        mode="interactive",
        messages=[
                {
                    "role": "assistant",
                "tool_calls": [{"id": "call-1"}],
            }
        ],
    )
    service = SessionService(
        store,
        scratch_base=tmp_path / "scratch",
        snapshotter=lambda _session_id, _engine: snapshot,
    )
    service.attach_engine("s1", engine)

    assert service.persist_checkpoint(
        "s1",
        checkpoint=TurnCheckpoint.executing({"call-1"}),
    )
    assert store.load("s1") == replace(
        snapshot,
        turn_checkpoint=TurnCheckpoint.executing({"call-1"}),
    )
    assert service.recoverable_sessions() == [
        replace(
            snapshot,
            turn_checkpoint=TurnCheckpoint.executing({"call-1"}),
        )
    ]


def test_restore_conversation_truncates_persisted_and_live_messages(
    tmp_path,
):
    original = SessionRecord(
        session_id="s1",
        workspace=str(tmp_path),
        model="test-model",
        mode="interactive",
        messages=[
            {"role": "user", "content": "keep"},
            {"role": "assistant", "content": "kept"},
            {"role": "user", "content": "revert"},
            {"role": "assistant", "content": "reverted"},
        ],
    )
    store = MemorySessionStore(original)

    class Engine:
        messages = list(original.messages)

    engine = Engine()
    service = SessionService(
        store,
        scratch_base=tmp_path / "scratch",
    )
    service.attach_engine("s1", engine)

    assert service.restore_conversation("s1", message_count=2)
    assert store.load("s1").messages == original.messages[:2]
    assert engine.messages == original.messages[:2]


def test_recovery_failure_notice_is_idempotent_and_preserves_checkpoint(
    tmp_path,
):
    checkpoint = TurnCheckpoint.executing({"call-1"})
    record = SessionRecord(
        session_id="s1",
        workspace=str(tmp_path),
        model="test-model",
        mode="interactive",
        turn_checkpoint=checkpoint,
    )
    store = MemorySessionStore(record)
    service = SessionService(
        store,
        scratch_base=tmp_path / "scratch",
    )

    assert service.mark_recovery_failed("s1")
    assert service.mark_recovery_failed("s1")

    retained = store.load("s1")
    assert retained is not None
    assert retained.turn_checkpoint == checkpoint
    notices = [
        message
        for message in retained.messages
        if message.get("kind") == "recovery_error"
    ]
    assert len(notices) == 1


def test_list_sessions_returns_public_metadata_and_hides_internal_records(tmp_path):
    visible = SessionRecord(
        session_id="s1",
        workspace=str(tmp_path),
        model="test-model",
        mode="interactive",
        title=None,
        message_count=3,
        pinned=True,
        archived=False,
    )
    internal = replace(visible, session_id="__system")
    service = SessionService(
        MemorySessionStore(visible, internal),
        scratch_base=tmp_path / "scratch",
    )

    assert service.list_sessions() == [
        {
            "session_id": "s1",
            "title": "New session",
            "workspace": str(tmp_path),
            "agent": "code",
            "model": "test-model",
            "mode": "interactive",
            "updated_at": None,
            "messages": 3,
            "pinned": True,
            "archived": False,
                "origin": None,
                "origin_label": None,
                "origin_session_id": None,
        }
    ]


def test_search_sessions_returns_match_location_and_public_metadata(tmp_path):
    record = SessionRecord(
        session_id="s1",
        workspace=str(tmp_path),
        model="test-model",
        mode="interactive",
        title="Retry work",
        messages=[
            {"role": "user", "content": "Find the retry jitter"},
            {"role": "assistant", "content": "Found it"},
        ],
        message_count=2,
    )
    service = SessionService(
        MemorySessionStore(record),
        scratch_base=tmp_path / "scratch",
    )

    assert service.search_sessions("jitter", limit=20) == [
        {
            "session_id": "s1",
            "title": "Retry work",
            "workspace": str(tmp_path),
            "agent": "code",
            "model": "test-model",
            "mode": "interactive",
            "updated_at": None,
            "messages": 2,
            "pinned": False,
            "archived": False,
                "origin": None,
                "origin_label": None,
                "origin_session_id": None,
            "match_excerpt": "Find the retry jitter",
            "match_message_index": 0,
        }
    ]


def test_fork_copies_history_through_selected_message_without_authority(
    tmp_path,
):
    original = SessionRecord(
        session_id="s1",
        workspace=str(tmp_path / "sandbox"),
        source_workspace=str(tmp_path),
        model="test-model",
        mode="plan",
        title="Original",
        agent="review",
        messages=[
            {"role": "user", "content": "one"},
            {"role": "assistant", "content": "two"},
            {"role": "user", "content": "three"},
        ],
        extra_roots=[
            {"path": str(tmp_path / "docs"), "writable": False}
        ],
        grants={"tools": ["shell"]},
        pinned=True,
        archived=True,
        turn_checkpoint=TurnCheckpoint.executing({"call-1"}),
    )
    store = MemorySessionStore(original)
    service = SessionService(store, scratch_base=tmp_path / "scratch")

    result = service.fork(
        "s1",
        message_index=1,
        new_session_id="session-fork",
    )
    forked = store.load("session-fork")

    assert result == {
        "ok": True,
        "session_id": "session-fork",
        "source_session_id": "s1",
        "message_count": 2,
        "session": {
            "session_id": "session-fork",
            "title": "Fork of Original",
            "workspace": str(tmp_path),
            "agent": "review",
            "model": "test-model",
            "mode": "plan",
            "updated_at": None,
            "messages": 2,
            "pinned": False,
            "archived": False,
            "origin": "fork",
            "origin_label": "Original",
            "origin_session_id": None,
        },
    }
    assert forked is not None
    assert forked.messages == original.messages[:2]
    assert forked.messages is not original.messages
    assert forked.workspace == str(tmp_path)
    assert forked.source_workspace == str(tmp_path)
    assert forked.extra_roots == []
    assert forked.grants == {}
    assert forked.pinned is False
    assert forked.archived is False
    assert forked.origin == "fork"
    assert forked.origin_label == "Original"
    assert forked.origin_session_id is None
    assert forked.turn_checkpoint == TurnCheckpoint()


def test_fork_rejects_missing_source_or_invalid_message_index(tmp_path):
    record = SessionRecord(
        session_id="s1",
        workspace=str(tmp_path),
        model="test-model",
        mode="interactive",
        messages=[{"role": "user", "content": "one"}],
    )
    service = SessionService(
        MemorySessionStore(record),
        scratch_base=tmp_path / "scratch",
    )

    assert service.fork("missing", message_index=0)["ok"] is False
    assert service.fork("s1", message_index=1)["ok"] is False


def test_side_conversation_preserves_safe_history_and_resets_authority(tmp_path):
    original = SessionRecord(
        session_id="s1",
        workspace=str(tmp_path),
        model="test-model",
        mode="plan",
        messages=[
            {"role": "user", "content": "question"},
            {"role": "assistant", "content": "answer"},
        ],
        title="Architecture",
        agent="review",
        extra_roots=[{"path": "/private", "writable": True}],
        grants={"tools": ["shell"]},
    )
    store = MemorySessionStore(original)
    service = SessionService(store, scratch_base=tmp_path / "scratch")

    result = service.side_conversation(
        "s1",
        message_index=1,
        new_session_id="session-side",
    )
    side = store.load("session-side")

    assert result["ok"] is True
    assert result["session"]["origin"] == "side_conversation"
    assert result["session"]["title"] == "Side conversation · Architecture"
    assert side is not None
    assert side.messages == original.messages
    assert side.extra_roots == []
    assert side.grants == {}
    assert side.origin == "side_conversation"
    assert side.origin_label == "Architecture"
    assert side.origin_session_id == "s1"


def test_worker_session_starts_empty_and_inherits_no_authority(tmp_path):
    prepared = tmp_path / "prepared"
    prepared.mkdir()
    original = SessionRecord(
        session_id="s1",
        workspace=str(prepared),
        source_workspace=str(tmp_path),
        model="parent-model",
        mode="interactive",
        messages=[{"role": "user", "content": "private context"}],
        title="Parent",
        extra_roots=[{"path": "/private", "writable": True}],
        grants={"tools": ["write_file"], "commands": ["pytest"]},
    )
    store = MemorySessionStore(original)
    service = SessionService(store, scratch_base=tmp_path / "scratch")

    result = service.create_worker_session(
        "s1",
        worker_id="worker-a",
        child_session_id="session-worker-a",
        model="worker-model",
    )
    worker = store.load("session-worker-a")

    assert result["ok"] is True
    assert worker is not None
    assert worker.workspace == str(prepared)
    assert worker.source_workspace == str(prepared)
    assert worker.model == "worker-model"
    assert worker.mode == "auto"
    assert worker.agent == "worker"
    assert worker.messages == []
    assert worker.extra_roots == []
    assert worker.grants == {}
    assert worker.origin == "worker"
    assert worker.origin_label == "worker-a"
    assert worker.origin_session_id == "s1"
    assert all(
        item["session_id"] != "session-worker-a"
        for item in service.list_sessions()
    )
    store.save(
        replace(
            worker,
            messages=[{"role": "assistant", "content": "worker-only secret"}],
        )
    )
    assert service.search_sessions("worker-only secret") == []


def test_markdown_export_contains_only_visible_conversation_content(tmp_path):
    trusted_context = make_project_context_item(
        kind="file",
        root=str(tmp_path),
        path="secret.txt",
        label="secret.txt",
        content="SECRET_CONTEXT",
        truncated=False,
    )["content_part"]
    record = SessionRecord(
        session_id="s1",
        workspace=str(tmp_path),
        model="test-model",
        mode="interactive",
        title='Release / "notes"',
        messages=[
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": "Ship **today**"},
                    {
                        "type": "file",
                        "file": {
                            "filename": "spec.pdf",
                            "file_data": "data:application/pdf;base64,SECRET",
                        },
                    },
                ],
            },
            {
                "role": "assistant",
                "content": "Ready.",
                "tool_calls": [{"id": "call-1", "function": {"arguments": "SECRET"}}],
                },
                {
                    "role": "user",
                    "content": [
                        trusted_context,
                    ],
                },
                {"role": "tool", "tool_call_id": "call-1", "content": "SECRET"},
        ],
    )
    service = SessionService(
        MemorySessionStore(record),
        scratch_base=tmp_path / "scratch",
    )

    result = service.export_markdown("s1")

    assert result == {
        "ok": True,
        "filename": "release-notes.md",
        "content": (
            '# Release / "notes"\n\n'
            "## You\n\n"
            "Ship **today**\n\n"
            "_Attachment: spec.pdf_\n\n"
            "## Codinal\n\n"
            "Ready.\n"
        ),
    }
    assert "SECRET" not in result["content"]
    assert "SECRET_CONTEXT" not in result["content"]


def test_fork_rejects_incomplete_tool_transcript_and_preserves_source_scratch(
    tmp_path,
):
    source = tmp_path / "source"
    source.mkdir()
    scratch = tmp_path / "scratch"
    source_scratch = scratch / "source-session"
    source_scratch.mkdir(parents=True)
    record = SessionRecord(
        session_id="s1",
        workspace=str(source_scratch),
        source_workspace=str(source),
        model="test-model",
        mode="interactive",
        messages=[
            {"role": "user", "content": "inspect"},
            {
                "role": "assistant",
                "content": None,
                "tool_calls": [{"id": "call-1"}],
            },
            {
                "role": "tool",
                "tool_call_id": "call-1",
                "content": "done",
            },
            {"role": "assistant", "content": "complete"},
        ],
        extra_roots=[
            {"path": str(tmp_path / "private"), "writable": True}
        ],
    )
    store = MemorySessionStore(record)
    service = SessionService(store, scratch_base=scratch)

    assert service.fork("s1", message_index=1) == {
        "ok": False,
        "error": "invalid fork boundary",
    }
    result = service.fork(
        "s1",
        message_index=3,
        new_session_id="forked",
    )
    assert result["ok"] is True
    assert store.load("forked").extra_roots == []

    assert service.delete("forked") == {
        "ok": True,
        "session_id": "forked",
    }
    assert source_scratch.is_dir()
    assert store.load("s1") is not None


def test_rename_normalizes_title_and_rejects_internal_session(tmp_path):
    record = SessionRecord(
        session_id="s1",
        workspace=str(tmp_path),
        model="test-model",
        mode="interactive",
    )
    store = MemorySessionStore(record)
    service = SessionService(store, scratch_base=tmp_path / "scratch")

    assert service.rename("s1", "  Release   checklist  ") == {
        "ok": True,
        "session_id": "s1",
        "title": "Release checklist",
    }
    assert store.load("s1").title == "Release checklist"
    assert service.rename("__system", "nope")["ok"] is False


def test_set_flags_updates_public_session_only(tmp_path):
    record = SessionRecord(
        session_id="s1",
        workspace=str(tmp_path),
        model="test-model",
        mode="interactive",
    )
    store = MemorySessionStore(record)
    service = SessionService(store, scratch_base=tmp_path / "scratch")

    assert service.set_flags("s1", pinned=True, archived=True) == {
        "ok": True,
        "session_id": "s1",
    }
    assert store.load("s1").pinned is True
    assert store.load("s1").archived is True
    assert service.set_flags("__system", pinned=True)["ok"] is False


def test_set_model_updates_persisted_session_and_validates_value(tmp_path):
    record = SessionRecord(
        session_id="s1",
        workspace=str(tmp_path),
        model="openai:gpt-old",
        mode="interactive",
    )
    store = MemorySessionStore(record)
    service = SessionService(store, scratch_base=tmp_path / "scratch")

    assert service.set_model("s1", " anthropic:claude-new ") == {
        "ok": True,
        "session_id": "s1",
        "model": "anthropic:claude-new",
    }
    assert store.load("s1").model == "anthropic:claude-new"
    assert service.set_model("s1", "\n")["ok"] is False
    assert service.set_model("missing", "openai:gpt")["ok"] is False


def test_set_model_switches_live_engine_and_persists_switch_notice(tmp_path):
    record = SessionRecord(
        session_id="s1",
        workspace=str(tmp_path),
        model="openai:gpt-old",
        mode="interactive",
    )
    store = MemorySessionStore(record)

    class LiveEngine:
        model = "openai:gpt-old"
        messages = []

        def switch_model(self, model):
            self.model = model
            self.messages.append(
                {"role": "notice", "content": f"Switched to {model}"}
            )

    engine = LiveEngine()
    service = SessionService(
        store,
        scratch_base=tmp_path / "scratch",
        snapshotter=lambda session_id, live: replace(
            record,
            session_id=session_id,
            model=live.model,
            messages=list(live.messages),
        ),
    )
    service.attach_engine("s1", engine)

    routing = {
        "profile": "economy",
        "provider": "gemini",
        "selected_model": "gemini:gemini-new",
        "cost_class": "economy",
        "degradations": [],
    }
    assert service.set_model(
        "s1",
        "gemini:gemini-new",
        routing=routing,
    )["ok"] is True
    assert engine.model == "gemini:gemini-new"
    assert store.load("s1").model == "gemini:gemini-new"
    assert store.load("s1").messages[0]["content"] == (
        "Switched to gemini:gemini-new"
    )
    assert store.load("s1").messages[-1]["kind"] == "routing_decision"
    assert store.load("s1").messages[-1]["source"]["routing"] == routing


def test_set_model_atomically_persists_cold_routing_audit(tmp_path):
    record = SessionRecord(
        session_id="s1",
        workspace=str(tmp_path),
        model="openai:gpt-old",
        mode="interactive",
    )
    store = MemorySessionStore(record)
    service = SessionService(store, scratch_base=tmp_path / "scratch")
    routing = {
        "profile": "economy",
        "provider": "gemini",
        "selected_model": "gemini:gemini-new",
        "cost_class": "economy",
        "degradations": [],
    }

    result = service.set_model(
        "s1",
        "gemini:gemini-new",
        routing=routing,
    )

    persisted = store.load("s1")
    assert result["ok"] is True
    assert persisted.model == "gemini:gemini-new"
    assert persisted.message_count == 1
    assert persisted.messages == [
        {
            "role": "notice",
            "kind": "routing_decision",
            "text": (
                "Routing: economy → gemini · gemini:gemini-new · economy"
            ),
            "source": {"routing": routing},
            "ts": persisted.messages[0]["ts"],
        }
    ]


def test_set_model_rolls_back_live_engine_when_persistence_fails(tmp_path):
    record = SessionRecord(
        session_id="s1",
        workspace=str(tmp_path),
        model="openai:gpt-old",
        mode="interactive",
        messages=[{"role": "user", "content": "keep"}],
    )

    class FailingStore(MemorySessionStore):
        def save(self, _record):
            raise OSError("disk unavailable")

    class LiveEngine:
        model = "openai:gpt-old"
        messages = list(record.messages)

        def switch_model(self, model):
            self.model = model
            self.messages.append(
                {"role": "notice", "content": f"Switched to {model}"}
            )

    engine = LiveEngine()
    service = SessionService(
        FailingStore(record),
        scratch_base=tmp_path / "scratch",
        snapshotter=lambda session_id, live: replace(
            record,
            session_id=session_id,
            model=live.model,
            messages=list(live.messages),
        ),
    )
    service.attach_engine("s1", engine)

    result = service.set_model("s1", "gemini:gemini-new")

    assert result == {"ok": False, "error": "model persistence failed"}
    assert engine.model == "openai:gpt-old"
    assert engine.messages == record.messages


def test_routing_requirements_include_durable_attachments(tmp_path):
    record = SessionRecord(
        session_id="s1",
        workspace=str(tmp_path),
        model="openai:gpt-old",
        mode="interactive",
        messages=[
            {
                "role": "user",
                "content": [
                    {"type": "image_url", "image_url": {"url": "data:x"}},
                    {
                        "type": "file",
                        "file": {
                            "filename": "design.pdf",
                            "file_data": "data:application/pdf;base64,AA==",
                        },
                    },
                ],
            }
        ],
    )
    service = SessionService(
        MemorySessionStore(record),
        scratch_base=tmp_path / "scratch",
    )

    assert service.routing_requirements("s1") == [
        "pdf",
        "tools",
        "vision",
    ]


def test_cold_routing_context_loads_large_transcript_once(tmp_path):
    class CountingStore(MemorySessionStore):
        def __init__(self, *records):
            super().__init__(*records)
            self.loads = 0

        def load(self, session_id):
            self.loads += 1
            return super().load(session_id)

    record = SessionRecord(
        session_id="s1",
        workspace=str(tmp_path),
        model="openai:gpt-old",
        mode="interactive",
        messages=[
            {"role": "user", "content": f"message-{index}"}
            for index in range(10_000)
        ],
    )
    store = CountingStore(record)
    service = SessionService(store, scratch_base=tmp_path / "scratch")

    context = service.routing_context("s1")

    assert store.loads == 1
    assert context == {
        "model": "openai:gpt-old",
        "required_capabilities": ["tools"],
    }


def test_delete_interrupts_engine_runs_cleanup_and_removes_only_scratch(tmp_path):
    scratch_base = tmp_path / "scratch"
    scratch_workspace = scratch_base / "s1"
    project_workspace = tmp_path / "project"
    scratch_workspace.mkdir(parents=True)
    project_workspace.mkdir()
    store = MemorySessionStore(
        SessionRecord(
            session_id="s1",
            workspace=str(scratch_workspace),
            model="test-model",
            mode="interactive",
        ),
        SessionRecord(
            session_id="s2",
            workspace=str(project_workspace),
            model="test-model",
            mode="interactive",
        ),
    )
    cleaned = []
    cleared = []

    class RecordingIndex:
        def search(self, *_args, **_kwargs):
            return {"ok": True, "matches": []}

        def clear_scope(self, scope, *, paths=None):
            cleared.append((scope, paths))
            return {"ok": True, "deleted_roots": 1}

    class LiveEngine:
        interrupted = False

        def request_interrupt(self):
            self.interrupted = True

    engine = LiveEngine()
    service = SessionService(
        store,
        scratch_base=scratch_base,
        delete_callbacks=[cleaned.append],
        semantic_index=RecordingIndex(),
    )
    service.attach_engine("s1", engine)

    assert service.delete("s1") == {"ok": True, "session_id": "s1"}
    assert engine.interrupted is True
    assert cleaned == ["s1"]
    assert not scratch_workspace.exists()

    assert service.delete("s2") == {"ok": True, "session_id": "s2"}
    assert project_workspace.is_dir()
    assert cleared == [("s1", None), ("s2", None)]
    assert service.delete("__system")["ok"] is False


def test_delete_preserves_session_when_cleanup_blocks(tmp_path):
    record = SessionRecord(
        session_id="s1",
        workspace=str(tmp_path),
        model="test-model",
        mode="interactive",
    )
    store = MemorySessionStore(record)

    def block(_session_id):
        raise SessionCleanupError("unapplied commits")

    service = SessionService(
        store,
        scratch_base=tmp_path / "scratch",
        delete_callbacks=[block],
    )

    assert service.delete("s1") == {
        "ok": False,
        "session_id": "s1",
        "cleanup_errors": ["unapplied commits"],
    }
    assert store.load("s1") is record


def test_add_and_remove_persisted_root_without_mutating_primary(tmp_path):
    workspace = tmp_path / "workspace"
    shared = tmp_path / "shared"
    workspace.mkdir()
    shared.mkdir()
    store = MemorySessionStore(
        SessionRecord(
            session_id="s1",
            workspace=str(workspace),
            model="test-model",
            mode="interactive",
        )
    )
    class RecordingIndex:
        def __init__(self):
            self.cleared = []

        def search(self, *_args, **_kwargs):
            return {"ok": True, "matches": []}

        def clear_scope(self, scope, *, paths=None):
            self.cleared.append((scope, paths))
            return {"ok": True, "deleted_roots": 1, "deleted_chunks": 1}

    semantic_index = RecordingIndex()
    service = SessionService(
        store,
        scratch_base=tmp_path / "scratch",
        semantic_index=semantic_index,
    )

    added = service.add_root("s1", str(shared), writable=False)
    assert added["ok"] is True
    assert added["roots"][1] == {
        "path": str(shared.resolve()),
        "writable": False,
        "label": "shared",
        "primary": False,
        "exists": True,
    }
    assert store.touched_workspaces == [str(shared.resolve())]

    assert service.remove_root("s1", str(workspace))["ok"] is False
    removed = service.remove_root("s1", str(shared))
    assert removed["ok"] is True
    assert len(removed["roots"]) == 1
    assert semantic_index.cleared == [
        ("s1", [str(shared.resolve())])
    ]


def test_add_root_does_not_duplicate_or_downgrade_primary_workspace(tmp_path):
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    store = MemorySessionStore(
        SessionRecord(
            session_id="s1",
            workspace=str(workspace),
            model="test-model",
            mode="interactive",
        )
    )
    service = SessionService(store, scratch_base=tmp_path / "scratch")

    result = service.add_root("s1", str(workspace), writable=False)

    assert result["ok"] is True
    assert result["roots"] == [
        {
            "path": str(workspace.resolve()),
            "writable": True,
            "label": "workspace",
            "primary": True,
            "exists": True,
        }
    ]
    assert store.load("s1").extra_roots == []


def test_root_changes_update_live_engine_and_persist_adapter_state(tmp_path):
    workspace = tmp_path / "workspace"
    shared = tmp_path / "shared"
    workspace.mkdir()
    shared.mkdir()
    store = MemorySessionStore(
        SessionRecord(
            session_id="s1",
            workspace=str(workspace),
            model="test-model",
            mode="interactive",
        )
    )

    class LiveEngine:
        messages = []
        roots = [RootDir(workspace, writable=True)]

    engine = LiveEngine()
    service = SessionService(store, scratch_base=tmp_path / "scratch")
    service.attach_engine("s1", engine)

    service.add_root("s1", str(shared), writable=True)
    assert engine.roots[1].path == shared.resolve()
    assert engine.roots[1].writable is True
    assert store.load("s1").extra_roots == [
        {
            "path": str(shared.resolve()),
            "writable": True,
            "label": "shared",
            "_device": shared.stat().st_dev,
            "_inode": shared.stat().st_ino,
        }
    ]

    service.remove_root("s1", str(shared))
    assert len(engine.roots) == 1
    assert store.load("s1").extra_roots == []


def test_tree_lists_one_bounded_level_without_following_symlinks(tmp_path):
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    (workspace / "src").mkdir()
    (workspace / "src" / "app.py").write_text("print('ok')")
    (workspace / "README.md").write_text("read me")
    (workspace / ".GIT").mkdir()
    (workspace / ".GIT" / "config").write_text("also secret")
    # On case-sensitive filesystems (Linux CI) `.git` and `.GIT` are distinct;
    # create the lowercase one too so the reserved-root assertions below hold.
    # On case-insensitive filesystems (macOS default) this is a no-op.
    try:
        (workspace / ".git").mkdir()
        (workspace / ".git" / "config").write_text("also secret")
    except FileExistsError:
        pass
    outside = tmp_path / "outside"
    outside.mkdir()
    (outside / "secret.txt").write_text("secret")
    (workspace / "linked").symlink_to(outside, target_is_directory=True)
    store = MemorySessionStore(
        SessionRecord(
            session_id="s1",
            workspace=str(workspace),
            model="test-model",
            mode="interactive",
        )
    )
    service = SessionService(store, scratch_base=tmp_path / "scratch")

    root = service.tree("s1", root=str(workspace), path="", limit=20)
    nested = service.tree(
        "s1",
        root=str(workspace),
        path="src",
        limit=20,
    )

    assert root == {
        "ok": True,
        "root": str(workspace.resolve()),
        "path": "",
        "entries": [
            {"name": "src", "path": "src", "kind": "directory"},
            {"name": "linked", "path": "linked", "kind": "symlink"},
            {"name": "README.md", "path": "README.md", "kind": "file"},
        ],
        "truncated": False,
    }
    assert nested["entries"] == [
        {"name": "app.py", "path": "src/app.py", "kind": "file"}
    ]
    assert service.tree(
        "s1",
        root=str(workspace),
        path="linked",
        limit=20,
    ) == {"ok": False, "error": "directory is unavailable"}
    assert service.tree(
        "s1",
        root=str(workspace),
        path="linked/subdirectory",
        limit=20,
    ) == {"ok": False, "error": "directory is unavailable"}
    assert service.tree(
        "s1",
        root=str(workspace),
        path=".git",
        limit=20,
    ) == {"ok": False, "error": "invalid tree path"}
    assert service.tree(
        "s1",
        root=str(workspace),
        path=".GIT",
        limit=20,
    ) == {"ok": False, "error": "invalid tree path"}
    assert service.tree(
        "s1",
        root=str(workspace),
        path="../outside",
        limit=20,
    ) == {"ok": False, "error": "invalid tree path"}
    assert service.tree(
        "s1",
        root=str(outside),
        path="",
        limit=20,
    ) == {"ok": False, "error": "root is not part of the session"}
    assert service.add_root("s1", str(workspace / ".git")) == {
        "ok": False,
        "error": "directory cannot be added",
    }
    assert service.add_root("s1", str(workspace / ".GIT")) == {
        "ok": False,
        "error": "directory cannot be added",
    }


def test_primary_tree_root_rejects_retargeted_workspace(tmp_path):
    workspace = tmp_path / "workspace"
    outside = tmp_path / "outside"
    workspace.mkdir()
    outside.mkdir()
    (outside / "secret.txt").write_text("secret")
    store = MemorySessionStore(
        SessionRecord(
            session_id="s1",
            workspace=str(workspace),
            model="test-model",
            mode="interactive",
        )
    )
    service = SessionService(store, scratch_base=tmp_path / "scratch")
    assert service.roots("s1")

    workspace.rename(tmp_path / "moved-workspace")
    workspace.symlink_to(outside, target_is_directory=True)

    assert service.roots("s1") == []
    result = service.tree("s1", root=str(workspace), path="", limit=20)
    assert result == {"ok": False, "error": "root is unavailable"}
    assert "secret" not in str(result)


def test_primary_tree_root_rejects_real_directory_replacement(tmp_path):
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    store = MemorySessionStore(
        SessionRecord(
            session_id="s1",
            workspace=str(workspace),
            model="test-model",
            mode="interactive",
        )
    )
    service = SessionService(store, scratch_base=tmp_path / "scratch")
    assert service.roots("s1")
    bound = store.load("s1")
    assert bound.workspace_device == workspace.stat().st_dev
    assert bound.workspace_inode == workspace.stat().st_ino

    workspace.rename(tmp_path / "moved-workspace")
    workspace.mkdir()
    (workspace / "secret.txt").write_text("replacement secret")
    restarted = SessionService(store, scratch_base=tmp_path / "scratch")

    assert restarted.roots("s1") == []
    result = restarted.tree(
        "s1",
        root=str(workspace),
        path="",
        limit=20,
    )
    assert result == {
        "ok": False,
        "error": "root is not part of the session",
    }
    assert "secret" not in str(result)


def test_extra_root_identity_blocks_retarget_after_restart(tmp_path):
    workspace = tmp_path / "workspace"
    shared = tmp_path / "shared"
    outside = tmp_path / "outside"
    workspace.mkdir()
    shared.mkdir()
    outside.mkdir()
    store = MemorySessionStore(
        SessionRecord(
            session_id="s1",
            workspace=str(workspace),
            model="test-model",
            mode="interactive",
        )
    )
    service = SessionService(store, scratch_base=tmp_path / "scratch")
    assert service.add_root("s1", str(shared))["ok"] is True

    moved = tmp_path / "moved-shared"
    shared.rename(moved)
    shared.symlink_to(outside, target_is_directory=True)
    restarted = SessionService(store, scratch_base=tmp_path / "scratch")

    roots = restarted.roots("s1")
    assert len(roots) == 2
    assert roots[1]["path"] == str(shared)
    assert roots[1]["available"] is False
    assert restarted.tree(
        "s1",
        root=str(outside),
        path="",
    ) == {"ok": False, "error": "root is not part of the session"}


def test_legacy_extra_root_is_bound_once_and_persisted(tmp_path):
    workspace = tmp_path / "workspace"
    shared = tmp_path / "legacy-shared"
    workspace.mkdir()
    shared.mkdir()
    store = MemorySessionStore(
        SessionRecord(
            session_id="s1",
            workspace=str(workspace),
            model="test-model",
            mode="interactive",
            extra_roots=[
                {
                    "path": str(shared),
                    "writable": False,
                    "label": "legacy",
                }
            ],
        )
    )
    service = SessionService(store, scratch_base=tmp_path / "scratch")

    roots = service.roots("s1")

    assert [root["path"] for root in roots] == [
        str(workspace),
        str(shared),
    ]
    persisted = store.load("s1").extra_roots
    assert persisted == [
        {
            "path": str(shared),
            "writable": False,
            "label": "legacy",
            "_device": shared.stat().st_dev,
            "_inode": shared.stat().st_ino,
        }
    ]

    shared.rename(tmp_path / "legacy-moved")
    shared.mkdir()
    restarted = SessionService(store, scratch_base=tmp_path / "scratch")
    restarted_roots = restarted.roots("s1")
    assert [root["path"] for root in restarted_roots] == [
        str(workspace),
        str(shared),
    ]
    assert restarted_roots[1]["available"] is False
    assert store.load("s1").extra_roots == persisted


def test_bound_extra_root_survives_temporary_unavailability(tmp_path):
    workspace = tmp_path / "workspace"
    shared = tmp_path / "shared"
    workspace.mkdir()
    shared.mkdir()
    store = MemorySessionStore(
        SessionRecord(
            session_id="s1",
            workspace=str(workspace),
            model="test-model",
            mode="interactive",
        )
    )
    service = SessionService(store, scratch_base=tmp_path / "scratch")
    assert service.add_root("s1", str(shared))["ok"] is True
    persisted = list(store.load("s1").extra_roots)

    moved = tmp_path / "shared-offline"
    shared.rename(moved)
    unavailable = service.roots("s1")
    assert [root["path"] for root in unavailable] == [
        str(workspace),
        str(shared),
    ]
    assert unavailable[1]["available"] is False
    assert store.load("s1").extra_roots == persisted

    moved.rename(shared)
    assert [root["path"] for root in service.roots("s1")] == [
        str(workspace),
        str(shared),
    ]
    assert store.load("s1").extra_roots == persisted


def test_remove_unavailable_symlink_root_matches_configured_path(
    tmp_path,
):
    workspace = tmp_path / "workspace"
    first = tmp_path / "first"
    second = tmp_path / "second"
    workspace.mkdir()
    first.mkdir()
    second.mkdir()
    store = MemorySessionStore(
        SessionRecord(
            session_id="s1",
            workspace=str(workspace),
            model="test-model",
            mode="interactive",
        )
    )
    service = SessionService(store, scratch_base=tmp_path / "scratch")
    assert service.add_root("s1", str(first))["ok"] is True
    assert service.add_root("s1", str(second))["ok"] is True
    first.rename(tmp_path / "first-moved")
    first.symlink_to(second, target_is_directory=True)

    result = service.remove_root("s1", str(first))

    assert result["ok"] is True
    assert [root["path"] for root in result["roots"]] == [
        str(workspace),
        str(second),
    ]
    assert [root["path"] for root in store.load("s1").extra_roots] == [
        str(second)
    ]


def test_live_engine_reactivates_returned_durable_root(tmp_path):
    workspace = tmp_path / "workspace"
    shared = tmp_path / "shared"
    workspace.mkdir()
    shared.mkdir()
    metadata = shared.stat()
    durable = {
        "path": str(shared),
        "writable": False,
        "label": "shared",
        "_device": metadata.st_dev,
        "_inode": metadata.st_ino,
    }
    store = MemorySessionStore(
        SessionRecord(
            session_id="s1",
            workspace=str(workspace),
            model="test-model",
            mode="interactive",
            extra_roots=[durable],
        )
    )
    moved = tmp_path / "shared-offline"
    shared.rename(moved)

    class LiveEngine:
        messages = []
        roots = [RootDir(workspace, writable=True)]
        durable_extra_roots = [durable]

    engine = LiveEngine()
    service = SessionService(store, scratch_base=tmp_path / "scratch")
    service.attach_engine("s1", engine)
    unavailable = service.roots("s1")
    assert unavailable[1]["available"] is False
    assert len(engine.roots) == 1

    moved.rename(shared)
    assert service.get_engine("s1") is engine
    assert len(engine.roots) == 2
    restored = service.roots("s1")

    assert restored[1]["path"] == str(shared)
    assert restored[1].get("available", True) is True


def test_live_root_mutation_waits_for_durable_persistence(tmp_path):
    workspace = tmp_path / "workspace"
    shared = tmp_path / "shared"
    workspace.mkdir()
    shared.mkdir()

    class FailingStore(MemorySessionStore):
        def set_extra_roots(self, *_args, **_kwargs):
            raise OSError("disk full")

    store = FailingStore(
        SessionRecord(
            session_id="s1",
            workspace=str(workspace),
            model="test-model",
            mode="interactive",
        )
    )

    class LiveEngine:
        messages = []
        roots = [RootDir(workspace, writable=True)]

    engine = LiveEngine()
    service = SessionService(store, scratch_base=tmp_path / "scratch")
    service.attach_engine("s1", engine)

    with pytest.raises(OSError, match="disk full"):
        service.add_root("s1", str(shared), writable=True)
    assert len(engine.roots) == 1

    shared_stat = shared.stat()
    engine.roots.append(
        RootDir(
            shared,
            writable=True,
            device=shared_stat.st_dev,
            inode=shared_stat.st_ino,
        )
    )
    with pytest.raises(OSError, match="disk full"):
        service.remove_root("s1", str(shared))
    assert len(engine.roots) == 2

def test_read_artifact_returns_text_and_blocks_workspace_escape(tmp_path):
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    (workspace / "notes.md").write_text("hello", encoding="utf-8")
    (tmp_path / "secret.txt").write_text("secret", encoding="utf-8")
    service = SessionService(
        MemorySessionStore(
            SessionRecord(
                session_id="s1",
                workspace=str(workspace),
                model="test-model",
                mode="interactive",
            )
        ),
        scratch_base=tmp_path / "scratch",
    )

    assert service.read_artifact("s1", "notes.md") == {
        "ok": True,
        "path": "notes.md",
        "kind": "markdown",
        "content": "hello",
        "truncated": False,
    }
    escaped = service.read_artifact("s1", "../secret.txt")
    assert escaped == {"ok": False, "error": "path escapes workspace"}


def test_write_artifact_creates_and_overwrites(tmp_path):
    """write_artifact creates new files, overwrites existing ones, and
    creates parent directories as needed (Phase 49 editor save)."""
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    (workspace / "existing.py").write_text("old", encoding="utf-8")
    service = SessionService(
        MemorySessionStore(
            SessionRecord(
                session_id="s1",
                workspace=str(workspace),
                model="test-model",
                mode="interactive",
            )
        ),
        scratch_base=tmp_path / "scratch",
    )

    # Overwrite existing.
    result = service.write_artifact("s1", "existing.py", "new content")
    assert result == {"ok": True, "path": "existing.py"}
    assert (workspace / "existing.py").read_text() == "new content"

    # Create new file in nested dir.
    result = service.write_artifact("s1", "src/new_file.ts", "export const x = 1;")
    assert result["ok"] is True
    assert (workspace / "src" / "new_file.ts").read_text() == "export const x = 1;"


def test_write_artifact_blocks_workspace_escape(tmp_path):
    """write_artifact must enforce the same sandbox as read_artifact."""
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    (tmp_path / "secret.txt").write_text("secret", encoding="utf-8")
    service = SessionService(
        MemorySessionStore(
            SessionRecord(
                session_id="s1",
                workspace=str(workspace),
                model="test-model",
                mode="interactive",
            )
        ),
        scratch_base=tmp_path / "scratch",
    )

    result = service.write_artifact("s1", "../evil.txt", "pwned")
    assert result == {"ok": False, "error": "path escapes workspace"}
    assert not (tmp_path / "evil.txt").exists()


def test_list_artifacts_filters_hidden_build_and_unsupported_files(tmp_path):
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    (workspace / "report.md").write_text("report", encoding="utf-8")
    (workspace / ".hidden.md").write_text("hidden", encoding="utf-8")
    (workspace / "payload.bin").write_bytes(b"\x00")
    (workspace / "node_modules").mkdir()
    (workspace / "node_modules" / "bundle.js").write_text(
        "ignored", encoding="utf-8"
    )
    service = SessionService(
        MemorySessionStore(
            SessionRecord(
                session_id="s1",
                workspace=str(workspace),
                model="test-model",
                mode="interactive",
            )
        ),
        scratch_base=tmp_path / "scratch",
    )

    artifacts = service.list_artifacts("s1")
    assert len(artifacts) == 1
    assert artifacts[0]["path"] == "report.md"
    assert artifacts[0]["abs_path"] == str((workspace / "report.md").resolve())
    assert artifacts[0]["kind"] == "markdown"
    assert artifacts[0]["size"] == 6


def test_read_artifact_encodes_binary_preview_and_caps_large_files(tmp_path):
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    (workspace / "pixel.png").write_bytes(b"PNG")
    with (workspace / "large.pdf").open("wb") as large:
        large.truncate(25 * 1024 * 1024 + 1)
    (workspace / "slides.pptx").write_bytes(b"office")
    service = SessionService(
        MemorySessionStore(
            SessionRecord(
                session_id="s1",
                workspace=str(workspace),
                model="test-model",
                mode="interactive",
            )
        ),
        scratch_base=tmp_path / "scratch",
    )

    assert service.read_artifact("s1", "pixel.png") == {
        "ok": True,
        "path": "pixel.png",
        "kind": "image",
        "data_url": "data:image/png;base64,UE5H",
    }
    assert service.read_artifact("s1", "large.pdf") == {
        "ok": False,
        "error": "file too large to preview",
    }
    assert service.read_artifact("s1", "slides.pptx") == {
        "ok": True,
        "path": "slides.pptx",
        "kind": "office",
    }


def test_reveal_artifact_delegates_validated_path_to_host_port(tmp_path):
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    artifact = workspace / "report.md"
    artifact.write_text("report", encoding="utf-8")
    opened = []
    service = SessionService(
        MemorySessionStore(
            SessionRecord(
                session_id="s1",
                workspace=str(workspace),
                model="test-model",
                mode="interactive",
            )
        ),
        scratch_base=tmp_path / "scratch",
        artifact_opener=lambda path, mode, _fd: opened.append((path, mode)),
    )

    assert service.reveal_artifact("s1", "report.md", mode="open") == {"ok": True}
    assert opened == [(artifact.resolve(), "open")]

    escaped = service.reveal_artifact("s1", "../secret.txt")
    assert escaped == {"ok": False, "error": "invalid project path"}
    assert len(opened) == 1


def test_project_file_context_is_bounded_identity_safe_and_provider_ready(
    tmp_path,
):
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    (workspace / "src").mkdir()
    (workspace / "src" / "main.py").write_text(
        "print('codinal')\n",
        encoding="utf-8",
    )
    (tmp_path / "secret.txt").write_text("secret", encoding="utf-8")
    (workspace / "src" / "escape.txt").symlink_to(tmp_path / "secret.txt")
    service = SessionService(
        MemorySessionStore(
            SessionRecord(
                session_id="s1",
                workspace=str(workspace),
                model="test-model",
                mode="interactive",
            )
        ),
        scratch_base=tmp_path / "scratch",
    )

    result = service.project_context(
        "s1",
        root=str(workspace),
        path="src/main.py",
        kind="file",
    )
    escaped = service.project_context(
        "s1",
        root=str(workspace),
        path="src/escape.txt",
        kind="file",
    )

    assert result["ok"] is True
    item = result["item"]
    assert item["kind"] == "file"
    assert item["root"] == str(workspace)
    assert item["path"] == "src/main.py"
    assert item["label"] == "workspace/src/main.py"
    assert item["truncated"] is False
    assert item["content_part"]["type"] == "text"
    assert "print('codinal')" in item["content_part"]["text"]
    assert '"kind":"file"' in item["content_part"]["text"]
    assert item["fingerprint"] == hashlib.sha256(
        item["content_part"]["text"].encode("utf-8")
    ).hexdigest()
    assert escaped == {"ok": False, "error": "path is unavailable"}


def test_project_folder_context_and_open_actions_stay_inside_approved_root(
    tmp_path,
):
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    docs = workspace / "docs"
    docs.mkdir()
    (docs / "guide.md").write_text("guide", encoding="utf-8")
    (docs / "assets").mkdir()
    (docs / "assets" / "nested.txt").write_text(
        "nested-v1",
        encoding="utf-8",
    )
    (docs / ".git").mkdir()
    opened = []
    service = SessionService(
        MemorySessionStore(
            SessionRecord(
                session_id="s1",
                workspace=str(workspace),
                model="test-model",
                mode="interactive",
            )
        ),
        scratch_base=tmp_path / "scratch",
        artifact_opener=lambda path, mode, _fd: opened.append((path, mode)),
    )

    context = service.project_context(
        "s1",
        root=str(workspace),
        path="docs",
        kind="folder",
    )
    opened_file = service.open_project_path(
        "s1",
        root=str(workspace),
        path="docs/guide.md",
        mode="open",
    )
    revealed_folder = service.open_project_path(
        "s1",
        root=str(workspace),
        path="docs",
        mode="reveal",
    )
    escaped = service.open_project_path(
        "s1",
        root=str(workspace),
        path="../secret",
        mode="open",
    )

    assert context["ok"] is True
    item = context["item"]
    assert item["kind"] == "folder"
    assert item["path"] == "docs"
    assert "directory assets/" in item["content_part"]["text"]
    assert "file guide.md" in item["content_part"]["text"]
    assert "file assets/nested.txt" in item["content_part"]["text"]
    assert "nested-v1" in item["content_part"]["text"]
    assert ".git" not in item["content_part"]["text"]
    assert opened_file == {"ok": True}
    assert revealed_folder == {"ok": True}
    assert opened == [
        ((docs / "guide.md").resolve(), "open"),
        (docs.resolve(), "reveal"),
    ]
    assert escaped == {"ok": False, "error": "invalid project path"}

    (docs / "assets" / "nested.txt").write_text(
        "nested-v2",
        encoding="utf-8",
    )
    refreshed = service.project_context(
        "s1",
        root=str(workspace),
        path="docs",
        kind="folder",
    )
    assert refreshed["item"]["fingerprint"] != item["fingerprint"]


def test_open_project_path_keeps_validated_identity_during_ancestor_swap(
    tmp_path,
):
    workspace = tmp_path / "workspace"
    docs = workspace / "docs"
    docs.mkdir(parents=True)
    (docs / "guide.md").write_text("allowed", encoding="utf-8")
    outside = tmp_path / "outside"
    outside.mkdir()
    (outside / "guide.md").write_text("outside", encoding="utf-8")
    observed = []

    def swap_ancestor(_path, _mode, descriptor):
        original = workspace / "docs-original"
        docs.rename(original)
        docs.symlink_to(outside, target_is_directory=True)
        observed.append(os.read(descriptor, 32).decode("utf-8"))

    service = SessionService(
        MemorySessionStore(
            SessionRecord(
                session_id="s1",
                workspace=str(workspace),
                model="test-model",
                mode="interactive",
            )
        ),
        scratch_base=tmp_path / "scratch",
        artifact_opener=swap_ancestor,
    )

    result = service.open_project_path(
        "s1",
        root=str(workspace),
        path="docs/guide.md",
        mode="open",
    )

    assert result == {"ok": True}
    assert observed == ["allowed"]


def test_folder_context_marks_large_directory_truncated_at_scan_bound(
    tmp_path,
):
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    for index in range(250):
        (workspace / f"file-{index:03}.txt").write_text(
            str(index),
            encoding="utf-8",
        )
    service = SessionService(
        MemorySessionStore(
            SessionRecord(
                session_id="s1",
                workspace=str(workspace),
                model="test-model",
                mode="interactive",
            )
        ),
        scratch_base=tmp_path / "scratch",
    )

    result = service.project_context(
        "s1",
        root=str(workspace),
        path="",
        kind="folder",
    )

    assert result["ok"] is True
    assert result["item"]["truncated"] is True
    assert result["item"]["content_part"]["text"].count("\nfile ") <= 200
