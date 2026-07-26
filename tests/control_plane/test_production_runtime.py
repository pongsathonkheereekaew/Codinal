import base64
import copy
import io
import json
import os
import platform
import signal
import sqlite3
import subprocess
import sys
import time
from pathlib import Path
from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient
from pypdf import PdfWriter

from runtime.control_plane import (
    create_control_plane_app,
    websocket_auth_protocol,
)
from runtime.control_plane.server import ServerConfig, build_services
from runtime.git import (
    CheckpointCaptureMode,
    CheckpointRestoreScope,
    CheckpointRestoreState,
    GitWorkspaceRecord,
    GitWorktreeStore,
    WorktreeState,
)
from runtime.providers import AssistantTurn, ModelCapabilities, ProviderClient
from runtime.policy import ApprovalOutcome, ToolCall
from runtime.sessions import SessionRecord, TurnCheckpoint, TurnStatus
from runtime.settings import JsonPreferenceStore
from runtime.storage import ConversationStore


TOKEN = "test-session-token-with-at-least-32-characters"
AUTH = {"Authorization": f"Bearer {TOKEN}"}


def _kill_crash_worker_at_durable_window(
    *,
    mode,
    data_dir,
    workspace,
    ready,
):
    worker = Path(__file__).parents[1] / "fixtures" / (
        "crash_recovery_worker.py"
    )
    repo_root = Path(__file__).parents[2]
    worker_environment = dict(os.environ)
    worker_environment["PYTHONPATH"] = str(repo_root)
    process = subprocess.Popen(
        [
            sys.executable,
            str(worker),
            mode,
            str(data_dir),
            str(workspace),
            str(ready),
        ],
        cwd=repo_root,
        env=worker_environment,
    )
    try:
        for _ in range(500):
            if ready.exists():
                break
            if process.poll() is not None:
                raise AssertionError(
                    f"crash worker exited early: {process.returncode}"
                )
            time.sleep(0.01)
        assert ready.exists()
        os.kill(process.pid, signal.SIGKILL)
        process.wait(timeout=5)
    finally:
        if process.poll() is None:
            process.kill()
            process.wait(timeout=5)


class ReadThenAnswerProvider(ProviderClient):
    def __init__(self):
        self.calls = 0
        self.tool_names = []

    def complete(self, *, tools=None, **_kwargs):
        self.calls += 1
        self.tool_names = [
            tool["function"]["name"] for tool in (tools or [])
        ]
        if self.calls == 1:
            return AssistantTurn(
                tool_calls=[
                    ToolCall(
                        "call_1",
                        "read_file",
                        {"path": "README.md"},
                    )
                ]
            )
        return AssistantTurn(text="workspace inspected")

    def capabilities(self, _model):
        return ModelCapabilities()


class AttachmentCaptureProvider(ProviderClient):
    def __init__(self):
        self.calls = []

    def complete(self, *, model, messages, **_kwargs):
        self.calls.append(
            {
                "model": model,
                "messages": copy.deepcopy(messages),
            }
        )
        return AssistantTurn(text="attachment inspected")

    def capabilities(self, model):
        return ModelCapabilities(
            vision=True,
            pdf=model.startswith("anthropic:"),
        )


def _blank_pdf_url():
    buffer = io.BytesIO()
    writer = PdfWriter()
    writer.add_blank_page(width=72, height=72)
    writer.write(buffer)
    return (
        "data:application/pdf;base64,"
        + base64.b64encode(buffer.getvalue()).decode("ascii")
    )


def test_production_startup_recovers_all_corrupt_durable_state(tmp_path):
    data_dir = tmp_path / "data"
    data_dir.mkdir()
    corrupt = {
        "codinal.db": b"corrupt conversations",
        "git-worktrees.db": b"corrupt worktrees",
        "prefs.json": b'{"corrupt preferences"',
    }
    for name, content in corrupt.items():
        (data_dir / name).write_bytes(content)
    config = ServerConfig(
        token=TOKEN,
        port=43123,
        data_dir=data_dir,
        default_model="openai:gpt-test",
    )

    services = build_services(
        config,
        provider=AttachmentCaptureProvider(),
    )

    assert services.sessions.list_sessions() == []
    assert services.git.load("unused-session") is None
    assert services.settings.view()["model"] == "openai:gpt-test"
    for name, content in corrupt.items():
        preserved = list(
            (data_dir / "recovery").glob(
                f"{name}.corrupt-*.preserved"
            )
        )
        assert len(preserved) == 1
        assert preserved[0].read_bytes() == content
    events = [
        json.loads(line)
        for line in (
            data_dir / "recovery" / "events.jsonl"
        ).read_text(encoding="utf-8").splitlines()
    ]
    assert {event["store"] for event in events} == set(corrupt)
    assert all(event["action"] == "preserved_corrupt_state" for event in events)
    with sqlite3.connect(data_dir / "codinal.db") as conversations:
        assert conversations.execute("PRAGMA integrity_check").fetchone()[0] == "ok"
        assert conversations.execute("PRAGMA user_version").fetchone()[0] == 3
    with sqlite3.connect(data_dir / "git-worktrees.db") as worktrees:
        assert worktrees.execute("PRAGMA integrity_check").fetchone()[0] == "ok"
        assert worktrees.execute("PRAGMA user_version").fetchone()[0] == 5


def test_production_startup_restores_latest_good_backups(tmp_path):
    data_dir = tmp_path / "data"
    data_dir.mkdir()
    conversations = ConversationStore(data_dir)
    conversations.save(
        SessionRecord(
            session_id="restored-session",
            workspace="/workspace",
            model="openai:gpt-restored",
            mode="interactive",
            messages=[{"role": "user", "content": "restore history"}],
        )
    )
    conversations.close()
    with sqlite3.connect(data_dir / "codinal.db") as connection:
        connection.execute("PRAGMA user_version = 1")
    ConversationStore(data_dir).close()

    git_store = GitWorktreeStore(data_dir)
    git_store.save(
        GitWorkspaceRecord(
            session_id="restored-session",
            source_root=Path("/workspace"),
            git_common_dir=Path("/workspace/.git"),
            source_branch="main",
            base_commit="a" * 40,
            worktree_path=Path("/worktree"),
            session_branch="codinal/restored",
            source_dirty=False,
            state=WorktreeState.ACTIVE,
        )
    )
    git_store.close()
    with sqlite3.connect(data_dir / "git-worktrees.db") as connection:
        connection.execute("PRAGMA user_version = 0")
    GitWorktreeStore(data_dir).close()

    preferences_path = data_dir / "prefs.json"
    preferences_path.write_text(
        json.dumps({"default_model": "anthropic:restored"}),
        encoding="utf-8",
    )
    JsonPreferenceStore(preferences_path).load()
    for name in ("codinal.db", "git-worktrees.db", "prefs.json"):
        (data_dir / name).write_bytes(f"corrupt {name}".encode())

    services = build_services(
        ServerConfig(
            token=TOKEN,
            port=43123,
            data_dir=data_dir,
            default_model="openai:fallback",
        ),
        provider=AttachmentCaptureProvider(),
    )

    assert services.sessions.messages("restored-session") == [
        {"role": "user", "content": "restore history"}
    ]
    assert services.git.load("restored-session").base_commit == "a" * 40
    assert services.settings.view()["model"] == "anthropic:restored"
    events = [
        json.loads(line)
        for line in (
            data_dir / "recovery" / "events.jsonl"
        ).read_text(encoding="utf-8").splitlines()
    ]
    assert sum(
        event["action"] == "restored_from_backup"
        for event in events
    ) == 3


def test_production_attachments_survive_restart_and_model_switch(tmp_path):
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    config = ServerConfig(
        token=TOKEN,
        port=43123,
        data_dir=tmp_path / "data",
        default_model="openai:gpt-test",
    )
    provider = AttachmentCaptureProvider()
    services = build_services(config, provider=provider)
    canonical = [
        {"type": "text", "text": "Inspect both attachments"},
        {
            "type": "image_url",
            "image_url": {
                "url": "data:image/png;base64,iVBORw0KGgo=",
            },
        },
        {
            "type": "file",
            "file": {
                "filename": "design.pdf",
                "file_data": _blank_pdf_url(),
            },
        },
    ]

    with TestClient(
        create_control_plane_app(token=TOKEN, services=services)
    ) as client:
        with client.websocket_connect(
            "/ws/session/attachment-session",
            subprotocols=[
                "codinal.v1",
                websocket_auth_protocol(TOKEN),
            ],
        ) as socket:
            first = client.post(
                "/v1/sessions/attachment-session/turns",
                headers=AUTH,
                json={
                    "input": canonical,
                    "workspace": str(workspace),
                },
            )
            event = socket.receive_json()
            while event["type"] != "turn_end":
                event = socket.receive_json()

            switched = client.patch(
                "/v1/sessions/attachment-session",
                headers=AUTH,
                json={"model": "anthropic:claude-test"},
            )
            second = client.post(
                "/v1/sessions/attachment-session/turns",
                headers=AUTH,
                json={"input": "Review the PDF again"},
            )
            event = socket.receive_json()
            while event["type"] != "turn_end":
                event = socket.receive_json()
        export_response = client.get("/v1/data/export", headers=AUTH)

    assert first.status_code == 202
    assert switched.status_code == 200
    assert second.status_code == 202
    assert export_response.status_code == 200
    first_user = next(
        message
        for message in provider.calls[0]["messages"]
        if message["role"] == "user"
    )
    assert [part["type"] for part in first_user["content"]] == [
        "text",
        "image_url",
        "text",
    ]
    second_first_user = next(
        message
        for message in provider.calls[1]["messages"]
        if message["role"] == "user"
    )
    assert second_first_user["content"] == canonical

    persisted = services.sessions.messages("attachment-session")
    assert next(
        message["content"]
        for message in persisted
        if message["role"] == "user"
        and isinstance(message["content"], list)
    ) == canonical
    exported = export_response.json()
    assert exported["export_version"] == 1
    exported_session = next(
        session
        for session in exported["sessions"]
        if session["session_id"] == "attachment-session"
    )
    assert set(exported_session) == {
        "session_id",
        "workspace",
        "source_workspace",
        "model",
        "mode",
        "messages",
        "title",
        "agent",
        "updated_at",
        "extra_roots",
        "grants",
        "pinned",
        "archived",
        "origin",
        "origin_label",
    }
    assert next(
        message["content"]
        for message in exported_session["messages"]
        if message["role"] == "user"
        and isinstance(message["content"], list)
    ) == canonical
    assert TOKEN not in json.dumps(exported)
    restarted = build_services(
        config,
        provider=AttachmentCaptureProvider(),
    )
    assert restarted.sessions.messages("attachment-session") == persisted


def test_workspace_switch_uses_a_new_session_and_permission_root(tmp_path):
    workspace_a = tmp_path / "workspace-a"
    workspace_b = tmp_path / "workspace-b"
    workspace_a.mkdir()
    workspace_b.mkdir()
    config = ServerConfig(
        token=TOKEN,
        port=43123,
        data_dir=tmp_path / "data",
        default_model="openai:gpt-test",
    )
    services = build_services(
        config,
        provider=AttachmentCaptureProvider(),
    )

    with TestClient(
        create_control_plane_app(token=TOKEN, services=services)
    ) as client:
        for session_id, workspace, prompt in (
            ("session-a", workspace_a, "workspace A"),
            ("session-b", workspace_b, "workspace B"),
        ):
            with client.websocket_connect(
                f"/ws/session/{session_id}",
                subprotocols=[
                    "codinal.v1",
                    websocket_auth_protocol(TOKEN),
                ],
            ) as socket:
                response = client.post(
                    f"/v1/sessions/{session_id}/turns",
                    headers=AUTH,
                    json={
                        "input": prompt,
                        "workspace": str(workspace),
                    },
                )
                event = socket.receive_json()
                while event["type"] != "turn_end":
                    event = socket.receive_json()
                assert response.status_code == 202

    listed = {
        session["session_id"]: session
        for session in services.sessions.list_sessions()
    }
    assert listed["session-a"]["workspace"] == str(workspace_a)
    assert listed["session-b"]["workspace"] == str(workspace_b)
    engine_b = services.sessions.get_engine("session-b")
    assert engine_b is not None
    assert engine_b.source_workspace == workspace_b.resolve()
    assert engine_b.permissions.roots[0].path == workspace_b.resolve()
    assert next(
        message["content"]
        for message in services.sessions.messages("session-a")
        if message["role"] == "user"
    ) == "workspace A"
    assert next(
        message["content"]
        for message in services.sessions.messages("session-b")
        if message["role"] == "user"
    ) == "workspace B"


def test_production_sidecar_turn_streams_tools_and_survives_restart(
    tmp_path,
):
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    (workspace / "README.md").write_text(
        "Codinal workspace",
        encoding="utf-8",
    )
    config = ServerConfig(
        token=TOKEN,
        port=43123,
        data_dir=tmp_path / "data",
        default_model="openai:gpt-test",
    )
    provider = ReadThenAnswerProvider()
    services = build_services(config, provider=provider)
    events = []

    with TestClient(
        create_control_plane_app(token=TOKEN, services=services)
    ) as client:
        with client.websocket_connect(
            "/ws/session/session-1",
            subprotocols=[
                "codinal.v1",
                websocket_auth_protocol(TOKEN),
            ],
        ) as socket:
            accepted = client.post(
                "/v1/sessions/session-1/turns",
                headers=AUTH,
                json={
                    "input": "inspect README",
                    "workspace": str(workspace),
                },
            )
            while not events or events[-1]["type"] != "turn_end":
                events.append(socket.receive_json())
    deadline = time.monotonic() + 1
    while not services.sessions.list_sessions():
        assert time.monotonic() < deadline
        time.sleep(0.01)

    assert accepted.status_code == 202
    assert provider.tool_names == [
        "read_file",
        "list_files",
        "grep",
        "write_file",
        "replace_in_file",
        "run_shell",
    ]
    assert [event["type"] for event in events] == [
        "turn_start",
        "assistant_message",
        "tool_proposed",
        "tool_started",
        "tool_finished",
        "iteration_end",
        "assistant_message",
        "turn_end",
    ]
    tool_result = [
        message
        for message in services.sessions.messages("session-1")
        if message.get("role") == "tool"
    ][0]
    assert "Codinal workspace" in tool_result["content"]

    restarted = build_services(
        config,
        provider=ReadThenAnswerProvider(),
    )
    persisted = restarted.sessions.messages("session-1")

    assert persisted == services.sessions.messages("session-1")
    assert persisted[-1]["content"] == "workspace inspected"


def test_production_mutation_requires_approval_and_persists_result(
    tmp_path,
):
    class WriteThenAnswerProvider(ProviderClient):
        def __init__(self):
            self.calls = 0

        def complete(self, **_kwargs):
            self.calls += 1
            if self.calls == 1:
                return AssistantTurn(
                    tool_calls=[
                        ToolCall(
                            "write_call_1",
                            "write_file",
                            {
                                "path": "generated.txt",
                                "content": "approved mutation\n",
                            },
                        )
                    ]
                )
            return AssistantTurn(text="mutation complete")

        def capabilities(self, _model):
            return ModelCapabilities()

    approvals = []

    async def approve_once(request):
        approvals.append(request)
        return ApprovalOutcome.ONCE

    workspace = tmp_path / "workspace"
    workspace.mkdir()
    config = ServerConfig(
        token=TOKEN,
        port=43123,
        data_dir=tmp_path / "data",
        default_model="openai:gpt-test",
    )
    services = build_services(
        config,
        provider=WriteThenAnswerProvider(),
        approver=approve_once,
    )
    events = []

    with TestClient(
        create_control_plane_app(token=TOKEN, services=services)
    ) as client:
        with client.websocket_connect(
            "/ws/session/session-write",
            subprotocols=[
                "codinal.v1",
                websocket_auth_protocol(TOKEN),
            ],
        ) as socket:
            accepted = client.post(
                "/v1/sessions/session-write/turns",
                headers=AUTH,
                json={
                    "input": "create generated.txt",
                    "workspace": str(workspace),
                },
            )
            while not events or events[-1]["type"] != "turn_end":
                events.append(socket.receive_json())
        tool_message = next(
            message
            for message in services.sessions.messages("session-write")
            if message.get("role") == "tool"
        )
        sandbox_directories = list((config.data_dir / "sandbox").iterdir())
        deleted = services.sessions.delete("session-write")

    assert accepted.status_code == 202
    assert [approval.tool_name for approval in approvals] == ["write_file"]
    assert "permission_required" in [event["type"] for event in events]
    assert (workspace / "generated.txt").read_text(
        encoding="utf-8"
    ) == "approved mutation\n"
    assert '"ok": true' in tool_message["content"]
    assert len(sandbox_directories) == 1

    assert deleted == {"ok": True, "session_id": "session-write"}
    assert not sandbox_directories[0].exists()


def test_production_default_approval_broker_resumes_turn(tmp_path):
    class WriteThenAnswerProvider(ProviderClient):
        def __init__(self):
            self.calls = 0

        def complete(self, **_kwargs):
            self.calls += 1
            if self.calls == 1:
                return AssistantTurn(
                    tool_calls=[
                        ToolCall(
                            "provider/call 1",
                            "write_file",
                            {
                                "path": "broker-approved.txt",
                                "content": "approved through UI\n",
                            },
                        )
                    ]
                )
            return AssistantTurn(text="mutation complete")

        def capabilities(self, _model):
            return ModelCapabilities()

    workspace = tmp_path / "workspace"
    workspace.mkdir()
    config = ServerConfig(
        token=TOKEN,
        port=43123,
        data_dir=tmp_path / "data",
        default_model="openai:gpt-test",
    )
    services = build_services(
        config,
        provider=WriteThenAnswerProvider(),
    )
    events = []

    with TestClient(
        create_control_plane_app(token=TOKEN, services=services)
    ) as client:
        with client.websocket_connect(
            "/ws/session/session-broker",
            subprotocols=[
                "codinal.v1",
                websocket_auth_protocol(TOKEN),
            ],
        ) as socket:
            accepted = client.post(
                "/v1/sessions/session-broker/turns",
                headers=AUTH,
                json={
                    "input": "create broker-approved.txt",
                    "workspace": str(workspace),
                },
            )
            while not events or events[-1]["type"] != "turn_end":
                event = socket.receive_json()
                events.append(event)
                if event["type"] == "permission_required":
                    resolved = client.post(
                        (
                            "/v1/sessions/session-broker/approvals/"
                            f"{event['approval_id']}"
                        ),
                        headers=AUTH,
                        json={"outcome": "once"},
                    )
                    assert resolved.status_code == 200

    assert accepted.status_code == 202
    assert (workspace / "broker-approved.txt").read_text(
        encoding="utf-8"
    ) == "approved through UI\n"
    approval_event = next(
        event
        for event in events
        if event["type"] == "permission_required"
    )
    assert approval_event["approval_id"] == services.approvals.approval_id(
        "session-broker",
        "provider/call 1",
    )


def test_restart_restores_awaiting_approval_without_losing_tool_call(
    tmp_path,
):
    class RecoveryProvider(ProviderClient):
        def __init__(self):
            self.calls = 0

        def complete(self, **_kwargs):
            self.calls += 1
            return AssistantTurn(text="recovered mutation complete")

        def capabilities(self, _model):
            return ModelCapabilities()

    workspace = tmp_path / "workspace"
    workspace.mkdir()
    data_dir = tmp_path / "data"
    store = ConversationStore(data_dir)
    store.save(
        SessionRecord(
            session_id="session-recovery",
            workspace=str(workspace),
            source_workspace=str(workspace),
            model="openai:gpt-test",
            mode="interactive",
            messages=[
                {"role": "user", "content": "create recovered.txt"},
                {
                    "role": "assistant",
                    "content": None,
                    "tool_calls": [
                        {
                            "id": "provider/call-recovery",
                            "type": "function",
                            "function": {
                                "name": "write_file",
                                "arguments": json.dumps(
                                    {
                                        "path": "recovered.txt",
                                        "content": "restored once\n",
                                    }
                                ),
                            },
                        }
                    ],
                },
            ],
            turn_checkpoint=TurnCheckpoint(
                TurnStatus.AWAITING_APPROVAL
            ),
        )
    )
    store.close()
    provider = RecoveryProvider()
    config = ServerConfig(
        token=TOKEN,
        port=43123,
        data_dir=data_dir,
        default_model="openai:gpt-test",
    )
    services = build_services(config, provider=provider)

    with TestClient(
        create_control_plane_app(token=TOKEN, services=services)
    ) as client:
        pending = []
        for _ in range(100):
            pending = client.get(
                "/v1/sessions/session-recovery/approvals",
                headers=AUTH,
            ).json()
            if pending:
                break
            time.sleep(0.01)
        assert len(pending) == 1
        resolved = client.post(
            (
                "/v1/sessions/session-recovery/approvals/"
                f"{pending[0]['approval_id']}"
            ),
            headers=AUTH,
            json={"outcome": "once"},
        )
        assert resolved.status_code == 200
        for _ in range(100):
            if not services.turns.is_active("session-recovery"):
                break
            time.sleep(0.01)

    assert provider.calls == 1
    assert (workspace / "recovered.txt").read_text(
        encoding="utf-8"
    ) == "restored once\n"
    recovered = ConversationStore(data_dir).load("session-recovery")
    assert recovered is not None
    assert recovered.turn_checkpoint == TurnCheckpoint()
    assert [
        message.get("tool_call_id")
        for message in recovered.messages
        if message.get("role") == "tool"
    ] == ["provider/call-recovery"]


def test_restart_never_replays_tool_that_may_have_completed(tmp_path):
    class RecoveryProvider(ProviderClient):
        def __init__(self):
            self.calls = 0

        def complete(self, **_kwargs):
            self.calls += 1
            return AssistantTurn(text="workspace inspection required")

        def capabilities(self, _model):
            return ModelCapabilities()

    workspace = tmp_path / "workspace"
    workspace.mkdir()
    target = workspace / "uncertain.txt"
    target.write_text("already completed\n", encoding="utf-8")
    data_dir = tmp_path / "data"
    store = ConversationStore(data_dir)
    store.save(
        SessionRecord(
            session_id="session-uncertain",
            workspace=str(workspace),
            source_workspace=str(workspace),
            model="openai:gpt-test",
            mode="interactive",
            messages=[
                {"role": "user", "content": "update uncertain.txt"},
                {
                    "role": "assistant",
                    "content": None,
                    "tool_calls": [
                        {
                            "id": "provider/call-uncertain",
                            "type": "function",
                            "function": {
                                "name": "write_file",
                                "arguments": json.dumps(
                                    {
                                        "path": "uncertain.txt",
                                        "content": "DANGEROUS REPLAY\n",
                                    }
                                ),
                            },
                        }
                    ],
                },
            ],
            turn_checkpoint=TurnCheckpoint.executing(
                {"provider/call-uncertain"}
            ),
        )
    )
    store.close()
    provider = RecoveryProvider()
    config = ServerConfig(
        token=TOKEN,
        port=43123,
        data_dir=data_dir,
        default_model="openai:gpt-test",
    )
    services = build_services(config, provider=provider)

    with TestClient(
        create_control_plane_app(token=TOKEN, services=services)
    ):
        for _ in range(100):
            if not services.turns.is_active("session-uncertain"):
                break
            time.sleep(0.01)

    assert provider.calls == 1
    assert target.read_text(encoding="utf-8") == "already completed\n"
    recovered = ConversationStore(data_dir).load("session-uncertain")
    assert recovered is not None
    assert recovered.turn_checkpoint == TurnCheckpoint()
    tool_result = next(
        message
        for message in recovered.messages
        if message.get("role") == "tool"
    )
    assert tool_result["tool_call_id"] == "provider/call-uncertain"
    assert "outcome is unknown" in tool_result["content"]


@pytest.mark.skipif(
    platform.system() == "Windows",
    reason="requires SIGSTOP/SIGKILL process semantics",
)
def test_sigkill_after_approval_ack_resumes_without_reprompt(tmp_path):
    class RecoveryProvider(ProviderClient):
        def __init__(self):
            self.calls = 0

        def complete(self, **_kwargs):
            self.calls += 1
            return AssistantTurn(text="recovered after process kill")

        def capabilities(self, _model):
            return ModelCapabilities()

    workspace = tmp_path / "workspace"
    workspace.mkdir()
    data_dir = tmp_path / "data"
    ready = tmp_path / "approval-committed.json"
    _kill_crash_worker_at_durable_window(
        mode="approval",
        data_dir=data_dir,
        workspace=workspace,
        ready=ready,
    )

    provider = RecoveryProvider()
    services = build_services(
        ServerConfig(
            token=TOKEN,
            port=43123,
            data_dir=data_dir,
            default_model="openai:gpt-test",
        ),
        provider=provider,
    )
    with TestClient(
        create_control_plane_app(token=TOKEN, services=services)
    ) as client:
        for _ in range(200):
            if not services.turns.is_active("session-kill"):
                break
            time.sleep(0.01)
        pending = client.get(
            "/v1/sessions/session-kill/approvals",
            headers=AUTH,
        )

    assert pending.json() == []
    assert provider.calls == 1
    assert (workspace / "recovered-after-kill.txt").read_text(
        encoding="utf-8"
    ) == "executed once after restart\n"
    recovered = ConversationStore(data_dir).load("session-kill")
    assert recovered is not None
    assert recovered.turn_checkpoint == TurnCheckpoint()


@pytest.mark.skipif(
    platform.system() == "Windows",
    reason="requires SIGSTOP/SIGKILL process semantics",
)
def test_sigkill_during_parallel_tools_never_replays_either_call(
    tmp_path,
):
    class RecoveryProvider(ProviderClient):
        def __init__(self):
            self.calls = 0

        def complete(self, **_kwargs):
            self.calls += 1
            return AssistantTurn(text="parallel recovery complete")

        def capabilities(self, _model):
            return ModelCapabilities()

    workspace = tmp_path / "workspace"
    workspace.mkdir()
    data_dir = tmp_path / "data"
    ready = tmp_path / "parallel-checkpoint.txt"
    _kill_crash_worker_at_durable_window(
        mode="parallel",
        data_dir=data_dir,
        workspace=workspace,
        ready=ready,
    )

    provider = RecoveryProvider()
    services = build_services(
        ServerConfig(
            token=TOKEN,
            port=43123,
            data_dir=data_dir,
            default_model="openai:gpt-test",
        ),
        provider=provider,
    )
    with TestClient(
        create_control_plane_app(token=TOKEN, services=services)
    ):
        for _ in range(200):
            if not services.turns.is_active("session-kill"):
                break
            time.sleep(0.01)

    assert provider.calls == 1
    recovered = ConversationStore(data_dir).load("session-kill")
    assert recovered is not None
    assert recovered.turn_checkpoint == TurnCheckpoint()
    unknown = {
        message.get("tool_call_id")
        for message in recovered.messages
        if message.get("role") == "tool"
        and "outcome is unknown" in message.get("content", "")
    }
    assert unknown == {"call-1", "call-2"}


@pytest.mark.skipif(
    platform.system() == "Windows",
    reason="requires SIGSTOP/SIGKILL process semantics",
)
def test_sigkill_during_streaming_resumes_one_answer(tmp_path):
    class RecoveryProvider(ProviderClient):
        def __init__(self):
            self.calls = 0

        def complete(self, **_kwargs):
            self.calls += 1
            return AssistantTurn(text="single recovered answer")

        def capabilities(self, _model):
            return ModelCapabilities()

    workspace = tmp_path / "workspace"
    workspace.mkdir()
    data_dir = tmp_path / "data"
    ready = tmp_path / "stream-checkpoint.txt"
    _kill_crash_worker_at_durable_window(
        mode="streaming",
        data_dir=data_dir,
        workspace=workspace,
        ready=ready,
    )

    provider = RecoveryProvider()
    services = build_services(
        ServerConfig(
            token=TOKEN,
            port=43123,
            data_dir=data_dir,
            default_model="openai:gpt-test",
        ),
        provider=provider,
    )
    with TestClient(
        create_control_plane_app(token=TOKEN, services=services)
    ):
        for _ in range(200):
            if not services.turns.is_active("session-kill"):
                break
            time.sleep(0.01)

    assert provider.calls == 1
    recovered = ConversationStore(data_dir).load("session-kill")
    assert recovered is not None
    assert recovered.turn_checkpoint == TurnCheckpoint()
    assistant_messages = [
        message
        for message in recovered.messages
        if message.get("role") == "assistant"
    ]
    assert [message.get("content") for message in assistant_messages] == [
        "single recovered answer"
    ]


@pytest.mark.skipif(
    platform.system() != "Darwin",
    reason="production worktree creation uses macOS Seatbelt",
)
def test_production_git_session_mutates_only_isolated_worktree(
    tmp_path,
):
    class IsolatedWriteProvider(ProviderClient):
        def __init__(self):
            self.calls = 0

        def complete(self, **_kwargs):
            self.calls += 1
            if self.calls == 1:
                return AssistantTurn(
                    tool_calls=[
                        ToolCall(
                            "isolated_write",
                            "write_file",
                            {
                                "path": "generated.txt",
                                "content": "isolated\n",
                            },
                        )
                    ]
                )
            if self.calls == 2:
                return AssistantTurn(
                    tool_calls=[
                        ToolCall(
                            "isolated_stage",
                            "git_stage",
                            {"path": "generated.txt"},
                        )
                    ]
                )
            if self.calls == 3:
                return AssistantTurn(
                    tool_calls=[
                        ToolCall(
                            "isolated_commit",
                            "git_commit",
                            {"message": "Add generated file"},
                        )
                    ]
                )
            return AssistantTurn(text="isolated mutation complete")

        def capabilities(self, _model):
            return ModelCapabilities()

    async def approve_once(_request):
        return ApprovalOutcome.ONCE

    source = tmp_path / "source"
    source.mkdir()
    subprocess.run(
        ["git", "init", "-b", "feature", str(source)],
        check=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    for key, value in (
        ("user.name", "Codinal Test"),
        ("user.email", "codinal@example.invalid"),
    ):
        subprocess.run(
            ["git", "-C", str(source), "config", key, value],
            check=True,
        )
    (source / "tracked.txt").write_text("base\n", encoding="utf-8")
    subprocess.run(
        ["git", "-C", str(source), "add", "tracked.txt"],
        check=True,
    )
    subprocess.run(
        ["git", "-C", str(source), "commit", "-m", "base"],
        check=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    source_head = subprocess.run(
        ["git", "-C", str(source), "rev-parse", "HEAD"],
        check=True,
        stdout=subprocess.PIPE,
        text=True,
    ).stdout.strip()
    config = ServerConfig(
        token=TOKEN,
        port=43123,
        data_dir=tmp_path / "data",
        default_model="openai:gpt-test",
    )
    services = build_services(
        config,
        provider=IsolatedWriteProvider(),
        approver=approve_once,
    )

    with TestClient(
        create_control_plane_app(token=TOKEN, services=services)
    ) as client:
        with client.websocket_connect(
            "/ws/session/session-isolated",
            subprotocols=[
                "codinal.v1",
                websocket_auth_protocol(TOKEN),
            ],
        ) as socket:
            accepted = client.post(
                "/v1/sessions/session-isolated/turns",
                headers=AUTH,
                json={
                    "input": "create generated.txt",
                    "workspace": str(source),
                },
            )
            event = socket.receive_json()
            while event["type"] != "turn_end":
                event = socket.receive_json()
        assert accepted.status_code == 202
        git_record = services.git.load("session-isolated")
        listed = services.sessions.list_sessions()
        source_untouched_before_apply = not (
            source / "generated.txt"
        ).exists()
        git_status = client.get(
            "/v1/sessions/session-isolated/git/status",
            headers=AUTH,
        )
        unauthorized_status = client.get(
            "/v1/sessions/session-isolated/git/status"
        )
        review_diff = client.get(
            (
                "/v1/sessions/session-isolated/git/diff"
                "?against_base=true"
            ),
            headers=AUTH,
        )
        applied = client.post(
            "/v1/sessions/session-isolated/git/apply",
            headers=AUTH,
        )
        applied_record = services.git.load("session-isolated")

    assert git_record is not None
    assert source_untouched_before_apply is True
    assert (git_record.worktree_path / "generated.txt").read_text(
        encoding="utf-8"
    ) == "isolated\n"
    session_commit = subprocess.run(
        [
            "git",
            "-C",
            str(git_record.worktree_path),
            "rev-parse",
            "HEAD",
        ],
        check=True,
        stdout=subprocess.PIPE,
        text=True,
    ).stdout.strip()
    assert git_status.status_code == 200
    assert unauthorized_status.status_code == 401
    assert git_status.json()["clean"] is True
    assert review_diff.status_code == 200
    assert "+isolated" in review_diff.json()["diff"]
    assert applied.status_code == 200
    assert applied.json() == {
        "ok": True,
        "strategy": "fast-forward",
        "commit": session_commit,
    }
    assert applied_record.state.value == "applied"
    assert (source / "generated.txt").read_text(
        encoding="utf-8"
    ) == "isolated\n"
    assert listed[0]["workspace"] == str(source.resolve())
    assert subprocess.run(
        ["git", "-C", str(source), "branch", "--show-current"],
        check=True,
        stdout=subprocess.PIPE,
        text=True,
    ).stdout.strip() == "feature"
    assert subprocess.run(
        ["git", "-C", str(source), "rev-parse", "HEAD"],
        check=True,
        stdout=subprocess.PIPE,
        text=True,
    ).stdout.strip() == session_commit
    assert source_head != session_commit

    restarted = build_services(
        config,
        provider=IsolatedWriteProvider(),
        approver=approve_once,
    )
    engine = restarted.sessions.get_engine("session-isolated")

    assert engine.source_workspace == source.resolve()
    assert engine.roots[0].path == git_record.worktree_path
    restarted.git.close()


@pytest.mark.skipif(
    platform.system() != "Darwin",
    reason="production worktree creation uses macOS Seatbelt",
)
@pytest.mark.parametrize(
    "crash_window",
    [
        "after_code_apply",
        "after_conversation_save",
    ],
)
def test_turn_checkpoint_reconciles_ambiguous_restore_after_restart(
    tmp_path,
    crash_window,
):
    class WriteThenAnswerProvider(ProviderClient):
        def __init__(self):
            self.calls = 0

        def complete(self, **_kwargs):
            self.calls += 1
            if self.calls == 1:
                return AssistantTurn(
                    tool_calls=[
                        ToolCall(
                            "checkpoint-write",
                            "write_file",
                            {
                                "path": ".agent-cache",
                                "content": "agent change\n",
                            },
                        )
                    ]
                )
            if self.calls == 2:
                return AssistantTurn(
                    tool_calls=[
                        ToolCall(
                            "checkpoint-shell",
                            "run_shell",
                            {
                                "command": (
                                    "/usr/bin/perl -e "
                                    "\"open(F,'>shell-output.txt'); "
                                    "print F qq(shell\\\\n); close(F)\""
                                ),
                            },
                        )
                    ]
                )
            return AssistantTurn(text="checkpointed")

        def capabilities(self, _model):
            return ModelCapabilities()

    async def approve_once(_request):
        return ApprovalOutcome.ONCE

    source = tmp_path / "source"
    source.mkdir()
    subprocess.run(
        ["git", "init", "-b", "feature", str(source)],
        check=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    subprocess.run(
        [
            "git",
            "-C",
            str(source),
            "config",
            "user.name",
            "Codinal Test",
        ],
        check=True,
    )
    subprocess.run(
        [
            "git",
            "-C",
            str(source),
            "config",
            "user.email",
            "codinal@example.invalid",
        ],
        check=True,
    )
    (source / "tracked.txt").write_text("base\n", encoding="utf-8")
    (source / ".gitignore").write_text(
        ".agent-cache\n",
        encoding="utf-8",
    )
    subprocess.run(
        [
            "git",
            "-C",
            str(source),
            "add",
            "tracked.txt",
            ".gitignore",
        ],
        check=True,
    )
    subprocess.run(
        ["git", "-C", str(source), "commit", "-m", "base"],
        check=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    config = ServerConfig(
        token=TOKEN,
        port=43123,
        data_dir=tmp_path / "data",
        default_model="openai:gpt-test",
    )
    services = build_services(
        config,
        provider=WriteThenAnswerProvider(),
        approver=approve_once,
    )

    with TestClient(
        create_control_plane_app(token=TOKEN, services=services)
    ) as client:
        with client.websocket_connect(
            "/ws/session/checkpoint-e2e",
            subprotocols=[
                "codinal.v1",
                websocket_auth_protocol(TOKEN),
            ],
        ) as socket:
            accepted = client.post(
                "/v1/sessions/checkpoint-e2e/turns",
                headers=AUTH,
                json={
                    "input": "create ignored agent cache",
                    "workspace": str(source),
                },
            )
            event = socket.receive_json()
            while event["type"] != "turn_end":
                event = socket.receive_json()
        git_record = services.git.load("checkpoint-e2e")
        checkpoints = client.get(
            "/v1/sessions/checkpoint-e2e/checkpoints",
            headers=AUTH,
        )
        checkpoint_id = checkpoints.json()[0]["checkpoint_id"]
        captured_checkpoint = services.git.load_checkpoint(
            checkpoint_id
        )
        attributed_paths = {
            item.path
            for item in services.git.store.list_checkpoint_files(
                checkpoint_id
            )
        }
    (git_record.worktree_path / "manual.txt").write_text(
        "manual after checkpoint\n",
        encoding="utf-8",
    )
    interrupted = build_services(
        config,
        provider=WriteThenAnswerProvider(),
        approver=approve_once,
    )
    operation = interrupted.git.begin_restore(
        "checkpoint-e2e",
        checkpoint_id,
        CheckpointRestoreScope.BOTH,
    )
    interrupted.git.resume_restore_code(operation.operation_id)
    if crash_window == "after_conversation_save":
        interrupted.git.advance_restore(
            operation.operation_id,
            CheckpointRestoreState.CODE_RESTORED,
        )
        assert interrupted.sessions.restore_conversation(
            "checkpoint-e2e",
            message_count=operation.message_count,
        )
    interrupted.git.close()

    restarted = build_services(
        config,
        provider=WriteThenAnswerProvider(),
        approver=approve_once,
    )
    with TestClient(
        create_control_plane_app(
            token=TOKEN,
            services=restarted,
        )
    ) as client:
        restarted_checkpoints = client.get(
            "/v1/sessions/checkpoint-e2e/checkpoints",
            headers=AUTH,
        )
        restored_messages = restarted.sessions.messages(
            "checkpoint-e2e"
        )

    assert accepted.status_code == 202
    assert checkpoints.status_code == 200
    assert len(checkpoints.json()) == 1
    assert (
        captured_checkpoint.capture_mode
        is CheckpointCaptureMode.ATTRIBUTED
    )
    assert attributed_paths == {
        ".agent-cache",
        "shell-output.txt",
    }
    assert restarted_checkpoints.json() == []
    assert not (git_record.worktree_path / ".agent-cache").exists()
    assert not (git_record.worktree_path / "shell-output.txt").exists()
    assert (git_record.worktree_path / "manual.txt").read_text(
        encoding="utf-8"
    ) == "manual after checkpoint\n"
    assert [message["role"] for message in restored_messages] == [
        "system"
    ]


@pytest.mark.skipif(
    platform.system() != "Darwin",
    reason="transactional shell requires macOS Seatbelt",
)
def test_plain_workspace_checkpoint_restores_after_restart(
    tmp_path,
):
    class PlainWriteProvider(ProviderClient):
        def __init__(self):
            self.calls = 0

        def complete(self, **_kwargs):
            self.calls += 1
            if self.calls == 1:
                return AssistantTurn(
                    tool_calls=[
                        ToolCall(
                            "plain-write",
                            "write_file",
                            {
                                "path": "agent.txt",
                                "content": "direct\n",
                            },
                        )
                    ]
                )
            if self.calls == 2:
                return AssistantTurn(
                    tool_calls=[
                        ToolCall(
                            "plain-shell",
                            "run_shell",
                            {
                                "command": (
                                    "/usr/bin/perl -e "
                                    "\"mkdir 'generated'; "
                                    "open(F,'>generated/output.txt'); "
                                    "print F qq(shell\\\\n); close(F)\""
                                ),
                            },
                        )
                    ]
                )
            return AssistantTurn(text="plain checkpointed")

        def capabilities(self, _model):
            return ModelCapabilities()

    async def approve_once(_request):
        return ApprovalOutcome.ONCE

    workspace = tmp_path / "plain-workspace"
    workspace.mkdir()
    (workspace / "baseline.txt").write_text(
        "baseline\n",
        encoding="utf-8",
    )
    config = ServerConfig(
        token=TOKEN,
        port=43123,
        data_dir=tmp_path / "plain-data",
        default_model="openai:gpt-test",
    )
    services = build_services(
        config,
        provider=PlainWriteProvider(),
        approver=approve_once,
    )

    with TestClient(
        create_control_plane_app(token=TOKEN, services=services)
    ) as client:
        with client.websocket_connect(
            "/ws/session/plain-checkpoint",
            subprotocols=[
                "codinal.v1",
                websocket_auth_protocol(TOKEN),
            ],
        ) as socket:
            accepted = client.post(
                "/v1/sessions/plain-checkpoint/turns",
                headers=AUTH,
                json={
                    "input": "write in the plain workspace",
                    "workspace": str(workspace),
                },
            )
            event = socket.receive_json()
            while event["type"] != "turn_end":
                event = socket.receive_json()
        checkpoints = client.get(
            "/v1/sessions/plain-checkpoint/checkpoints",
            headers=AUTH,
        )
        checkpoint_id = checkpoints.json()[0]["checkpoint_id"]
        attributed_paths = {
            item.path
            for item in services.git.store.list_checkpoint_files(
                checkpoint_id
            )
        }
        plain_has_no_git = services.git.load("plain-checkpoint") is None
        plain_has_checkpoints = services.git.has_checkpoint_session(
            "plain-checkpoint"
        )
    assert plain_has_no_git
    assert plain_has_checkpoints
    manual = workspace / "manual.txt"
    manual.write_text("manual\n", encoding="utf-8")
    interrupted = build_services(
        config,
        provider=PlainWriteProvider(),
        approver=approve_once,
    )
    operation = interrupted.git.begin_restore(
        "plain-checkpoint",
        checkpoint_id,
        CheckpointRestoreScope.BOTH,
    )
    interrupted.git.resume_restore_code(operation.operation_id)
    interrupted.git.close()

    restarted = build_services(
        config,
        provider=PlainWriteProvider(),
        approver=approve_once,
    )
    with TestClient(
        create_control_plane_app(
            token=TOKEN,
            services=restarted,
        )
    ) as client:
        remaining = client.get(
            "/v1/sessions/plain-checkpoint/checkpoints",
            headers=AUTH,
        )

    assert accepted.status_code == 202
    assert checkpoints.status_code == 200
    assert attributed_paths == {
        "agent.txt",
        "generated/output.txt",
    }
    assert remaining.json() == []
    assert not (workspace / "agent.txt").exists()
    assert not (workspace / "generated/output.txt").exists()
    assert manual.read_text(encoding="utf-8") == "manual\n"
    assert not (workspace / ".git").exists()


@pytest.mark.skipif(
    platform.system() != "Darwin",
    reason="Seatbelt is a macOS release boundary",
)
def test_production_interrupt_kills_active_sandbox_command(tmp_path):
    class SleepingProvider(ProviderClient):
        def complete(self, **_kwargs):
            return AssistantTurn(
                tool_calls=[
                    ToolCall(
                        "shell_call_1",
                        "run_shell",
                        {
                            "command": (
                                f"{Path(sys.executable).resolve()} -c "
                                "\"import time; time.sleep(10)\""
                            ),
                        },
                    )
                ]
            )

        def capabilities(self, _model):
            return ModelCapabilities()

    async def approve_once(_request):
        return ApprovalOutcome.ONCE

    workspace = tmp_path / "workspace"
    workspace.mkdir()
    config = ServerConfig(
        token=TOKEN,
        port=43123,
        data_dir=tmp_path / "data",
        default_model="openai:gpt-test",
    )
    services = build_services(
        config,
        provider=SleepingProvider(),
        approver=approve_once,
    )
    started_at = time.monotonic()
    events = []

    with TestClient(
        create_control_plane_app(token=TOKEN, services=services)
    ) as client:
        with client.websocket_connect(
            "/ws/session/session-shell",
            subprotocols=[
                "codinal.v1",
                websocket_auth_protocol(TOKEN),
            ],
        ) as socket:
            client.post(
                "/v1/sessions/session-shell/turns",
                headers=AUTH,
                json={
                    "input": "run the long command",
                    "workspace": str(workspace),
                },
            )
            while not events or events[-1]["type"] != "tool_started":
                events.append(socket.receive_json())
            interrupted = client.post(
                "/v1/sessions/session-shell/interrupt",
                headers=AUTH,
            )
            while events[-1]["type"] != "interrupted":
                events.append(socket.receive_json())

    assert interrupted.status_code == 200
    assert interrupted.json()["ok"] is True
    assert time.monotonic() - started_at < 2
    assert events[-1]["type"] == "interrupted"
    shell_result = next(
        message
        for message in services.sessions.messages("session-shell")
        if message.get("role") == "tool"
    )
    assert '"interrupted": true' in shell_result["content"]


def test_explicit_mcp_connect_registers_policy_gated_session_tool(
    tmp_path,
):
    class MCPProvider(ProviderClient):
        def __init__(self):
            self.calls = 0

        def complete(self, *, tools=None, **_kwargs):
            self.calls += 1
            if self.calls == 1:
                return AssistantTurn(text="session ready")
            if self.calls == 2:
                mcp_name = next(
                    tool["function"]["name"]
                    for tool in tools
                    if tool["function"]["name"].startswith("mcp__")
                )
                return AssistantTurn(
                    tool_calls=[
                        ToolCall(
                            "mcp_call_1",
                            mcp_name,
                            {"query": "policy"},
                        )
                    ]
                )
            return AssistantTurn(text="remote result used")

        def capabilities(self, _model):
            return ModelCapabilities()

    class FakeMCPManager:
        def __init__(self):
            self.connected = []
            self.called = []
            self.closed = False

        async def connect(self, server, *, approved):
            self.connected.append((server.name, approved))
            return [
                SimpleNamespace(
                    name="search",
                    description="Search remote docs",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "query": {"type": "string"}
                        },
                        "required": ["query"],
                    },
                )
            ]

        async def call(self, server, tool, arguments):
            self.called.append((server, tool, arguments))
            return {"matches": ["policy.md"]}

        async def aclose(self):
            self.closed = True

    async def approve_once(_request):
        return ApprovalOutcome.ONCE

    workspace = tmp_path / "workspace"
    workspace.mkdir()
    config = ServerConfig(
        token=TOKEN,
        port=43123,
        data_dir=tmp_path / "data",
        default_model="openai:gpt-test",
    )
    manager = FakeMCPManager()
    services = build_services(
        config,
        provider=MCPProvider(),
        mcp_manager=manager,
        approver=approve_once,
    )

    with TestClient(
        create_control_plane_app(token=TOKEN, services=services)
    ) as client:
        with client.websocket_connect(
            "/ws/session/session-1",
            subprotocols=[
                "codinal.v1",
                websocket_auth_protocol(TOKEN),
            ],
        ) as socket:
            unauthorized_connect = client.post(
                "/v1/sessions/session-1/mcp/connect",
                json={
                    "server": {
                        "name": "docs",
                        "transport": "http",
                        "url": "https://mcp.example.com/v1",
                    }
                },
            )
            first = client.post(
                "/v1/sessions/session-1/turns",
                headers=AUTH,
                json={
                    "input": "prepare",
                    "workspace": str(workspace),
                },
            )
            while socket.receive_json()["type"] != "turn_end":
                pass
            connected = client.post(
                "/v1/sessions/session-1/mcp/connect",
                headers=AUTH,
                json={
                    "server": {
                        "name": "docs",
                        "transport": "http",
                        "url": "https://mcp.example.com/v1",
                    }
                },
            )
            second = client.post(
                "/v1/sessions/session-1/turns",
                headers=AUTH,
                json={"input": "search policy"},
            )
            second_events = []
            while (
                not second_events
                or second_events[-1]["type"] != "turn_end"
            ):
                second_events.append(socket.receive_json())

    assert unauthorized_connect.status_code == 401
    assert first.status_code == 202
    assert connected.status_code == 200
    assert connected.json()["tools"][0].startswith("mcp__docs__search")
    assert second.status_code == 202
    assert manager.connected == [("docs", True)]
    assert manager.called == [
        ("docs", "search", {"query": "policy"})
    ]
    assert "permission_required" in [
        event["type"] for event in second_events
    ]
    assert second_events[-1]["type"] == "turn_end"
    assert manager.closed is True
