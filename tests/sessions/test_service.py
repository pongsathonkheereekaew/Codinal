from __future__ import annotations

from dataclasses import replace

from runtime.sessions import (
    RootDir,
    SessionCleanupError,
    SessionRecord,
    SessionService,
)


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
    record = SessionRecord(
        session_id="s1",
        workspace=str(tmp_path),
        model="test-model",
        mode="interactive",
        messages=[{"role": "user", "content": "restore me"}],
        agent="code",
        extra_roots=[{"path": str(tmp_path / "docs"), "writable": False}],
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
        }
    ]


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

    class LiveEngine:
        interrupted = False

        def request_interrupt(self):
            self.interrupted = True

    engine = LiveEngine()
    service = SessionService(
        store,
        scratch_base=scratch_base,
        delete_callbacks=[cleaned.append],
    )
    service.attach_engine("s1", engine)

    assert service.delete("s1") == {"ok": True, "session_id": "s1"}
    assert engine.interrupted is True
    assert cleaned == ["s1"]
    assert not scratch_workspace.exists()

    assert service.delete("s2") == {"ok": True, "session_id": "s2"}
    assert project_workspace.is_dir()
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
    service = SessionService(store, scratch_base=tmp_path / "scratch")

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
        }
    ]

    service.remove_root("s1", str(shared))
    assert len(engine.roots) == 1
    assert store.load("s1").extra_roots == []


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
        artifact_opener=lambda path, mode: opened.append((path, mode)),
    )

    assert service.reveal_artifact("s1", "report.md", mode="open") == {"ok": True}
    assert opened == [(artifact.resolve(), "open")]

    escaped = service.reveal_artifact("s1", "../secret.txt")
    assert escaped == {"ok": False, "error": "path escapes workspace"}
    assert len(opened) == 1
