from __future__ import annotations

import asyncio
from dataclasses import replace

from runtime import compose_runtime
from runtime.policy import ApprovalOutcome, Mode
from runtime.policy.approval import PermissionRequest
from runtime.secrets import ProviderSecretService
from runtime.sessions import SessionRecord


class MemorySessionStore:
    def __init__(self, *records: SessionRecord) -> None:
        self.records = {record.session_id: record for record in records}
        self.touched = []

    def load(self, session_id):
        return self.records.get(session_id)

    def save(self, record):
        self.records[record.session_id] = record

    def list(self, *, workspace=None):
        records = list(self.records.values())
        if workspace is not None:
            records = [record for record in records if record.workspace == workspace]
        return records

    def rename(self, session_id, title):
        record = self.records.get(session_id)
        if record is None:
            return False
        self.records[session_id] = replace(record, title=title)
        return True

    def set_flags(self, session_id, *, pinned=None, archived=None):
        return session_id in self.records

    def delete(self, session_id):
        return self.records.pop(session_id, None) is not None

    def set_extra_roots(self, session_id, extra_roots):
        record = self.records[session_id]
        self.records[session_id] = replace(record, extra_roots=extra_roots)

    def touch_workspace(self, path):
        self.touched.append(path)


class FakeEngine:
    def __init__(self, context):
        self.context = context
        self.messages = list(context.request.messages)
        self.roots = context.roots

    def request_interrupt(self):
        pass


def test_composition_injects_policy_roots_grants_and_session_event_sink(tmp_path):
    workspace = tmp_path / "workspace"
    readonly = tmp_path / "readonly"
    workspace.mkdir()
    readonly.mkdir()
    store = MemorySessionStore(
        SessionRecord(
            session_id="s1",
            workspace=str(workspace),
            model="openai:gpt-test",
            mode="interactive",
            messages=[],
            extra_roots=[{"path": str(readonly), "writable": False}],
            grants={
                "tools": ["write_file"],
                "commands": ["git status"],
            },
        )
    )
    contexts = []
    provider_secrets = ProviderSecretService()
    provider_secrets.set_api_key("openai", "test-secret")
    services = compose_runtime(
        data_dir=tmp_path / "data",
        session_store=store,
        engine_builder=lambda context: contexts.append(context)
        or FakeEngine(context),
        snapshotter=lambda _session_id, _engine: None,
        default_model="openai:gpt-default",
        provider_secrets=provider_secrets,
    )
    events = []

    async def listener(message):
        events.append(message)

    services.events.subscribe_session("s1", listener)
    engine = services.sessions.get_engine("s1")
    context = contexts[0]

    assert engine.context is context
    assert context.secrets is provider_secrets
    assert services.secrets is provider_secrets
    assert context.permissions.mode is Mode.INTERACTIVE
    assert context.permissions.evaluate(
        "write_file", {"path": str(workspace / "ok.py")}
    ).allowed
    assert not context.permissions.evaluate(
        "write_file", {"path": str(readonly / "blocked.py")}
    ).allowed
    assert context.permissions.evaluate(
        "run_shell", {"command": "git status"}
    ).allowed
    assert (
        asyncio.run(
            context.approver(
                PermissionRequest(
                    tool_name="run_shell",
                    arguments={"command": "git status"},
                    risk="exec",
                    reason="requires approval",
                )
            )
        )
        is ApprovalOutcome.DENY
    )

    asyncio.run(context.emit({"type": "turn_done"}))
    assert events == [{"type": "turn_done"}]


def test_new_session_uses_latest_persisted_default_model(tmp_path):
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    contexts = []
    services = compose_runtime(
        data_dir=tmp_path / "data",
        session_store=MemorySessionStore(),
        engine_builder=lambda context: contexts.append(context)
        or FakeEngine(context),
        snapshotter=lambda _session_id, _engine: None,
        default_model="openai:gpt-default",
    )

    services.settings.set_default_model("anthropic:claude-next")
    services.sessions.get_engine("new", workspace=workspace)

    assert contexts[0].request.model == "anthropic:claude-next"
