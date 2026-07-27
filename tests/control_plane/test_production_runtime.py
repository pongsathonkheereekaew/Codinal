import base64
import copy
import hashlib
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


def _unfence(content):
    """Strip the untrusted-content fence from a tool result in provider captures.

    Phase 29 wraps every tool result the provider receives in a
    <tool_result><content>...</content></tool_result> fence. Tests that assert
    on provider-received JSON unwrap it here so the assertion reads the real
    payload. The fence itself is exercised by the adversarial suite.
    """
    if not isinstance(content, str):
        return content
    open_tag = "<tool_result>\n<content>\n"
    close_tag = "\n</content>\n</tool_result>"
    if content.startswith(open_tag) and content.endswith(close_tag):
        return content[len(open_tag) : -len(close_tag)].replace(
            "&lt;/content&gt;", "</content>"
        )
    return content

# This module is the production integration suite: it drives the full control
# plane against real subprocess-spawning mechanics (sandbox-exec seatbelt for
# isolated mutations, the isolated pdf_worker over the embedded-Python bundle,
# git worktree lifecycle, crash-recovery workers). These pass on a developer
# macOS host but hang on CI runners (Linux lacks sandbox-exec entirely; macOS
# CI runners restrict the seatbelt/entitlement environment and the embedded
# bundle is absent). Collect-only skip on CI keeps the unit lane green; the
# suite still runs in full locally and in the release smoke lane.
pytestmark = pytest.mark.skipif(
    os.environ.get("CI") == "true",
    reason=(
        "production integration suite spawns sandbox-exec / pdf_worker / "
        "crash-recovery subprocesses that need a real macOS host; skipped on "
        "CI runners (run locally or in the release smoke lane)"
    ),
)

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


def _plan(plan: str) -> dict:
    return {
        "plan": plan,
        "tasks": [
            {
                "id": "execute",
                "title": plan.splitlines()[0],
                "verification": "The requested implementation test passes",
            }
        ],
    }


def _selective_plan() -> dict:
    return {
        "plan": "Implement and document",
        "tasks": [
            {
                "id": "implement",
                "title": "Implement feature",
                "verification": "Focused suite passes",
            },
            {
                "id": "docs",
                "title": "Update documentation",
                "verification": "Documentation contract passes",
            },
        ],
    }


def _selective_plan_approval() -> dict:
    return {
        "approved": True,
        "mode": "interactive",
        "plan": "Implement only",
        "tasks": [
            {
                "id": "implement",
                "title": "Implement safely",
                "verification": "Restart E2E passes",
            },
            {
                "id": "docs",
                "title": "Update documentation",
                "verification": "Documentation contract passes",
            },
        ],
        "selected_task_ids": ["implement"],
    }


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
        assert conversations.execute("PRAGMA user_version").fetchone()[0] == 8
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
    with TestClient(
        create_control_plane_app(token=TOKEN, services=restarted)
    ) as client:
        markdown = client.get(
            "/v1/sessions/attachment-session/export.md",
            headers=AUTH,
        )
    assert markdown.status_code == 200
    assert "Review the PDF again" in markdown.text
    assert "_Attachment: design.pdf_" in markdown.text
    assert "data:application/pdf;base64" not in markdown.text


def test_production_routing_selects_and_persists_visible_concrete_model(
    tmp_path,
):
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    provider = AttachmentCaptureProvider()
    services = build_services(
        ServerConfig(
            token=TOKEN,
            port=43123,
            data_dir=tmp_path / "data",
            default_model="openai:gpt-test",
        ),
        provider=provider,
    )
    services.secrets.set_api_key("gemini", "fixture-gemini-key")
    payload = [
        {"type": "text", "text": "Review this design"},
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
        configured = client.patch(
            "/v1/settings/routing",
            headers=AUTH,
            json={"profile": "quality"},
        )
        with client.websocket_connect(
            "/ws/session/routing-session",
            subprotocols=[
                "codinal.v1",
                websocket_auth_protocol(TOKEN),
            ],
        ) as socket:
            started = client.post(
                "/v1/sessions/routing-session/turns",
                headers=AUTH,
                json={
                    "input": payload,
                    "workspace": str(workspace),
                },
            )
            event = socket.receive_json()
            while event["type"] != "turn_end":
                event = socket.receive_json()

    assert configured.status_code == 200
    assert started.status_code == 202
    resolution = started.json()["routing"]
    assert resolution["selected_model"] == "gemini:gemini-2.5-flash"
    assert resolution["provider"] == "gemini"
    assert resolution["cost_class"] == "economy"
    assert resolution["degradations"] == []
    assert provider.calls[0]["model"] == "gemini:gemini-2.5-flash"
    assert services.sessions.list_sessions()[0]["model"] == (
        "gemini:gemini-2.5-flash"
    )
    user_message = next(
        message
        for message in services.sessions.messages("routing-session")
        if message.get("role") == "user"
    )
    assert user_message["source"]["routing"] == resolution


def test_production_project_context_matches_exact_provider_part(
    tmp_path,
    monkeypatch,
):
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    (workspace / "main.py").write_text(
        "VALUE = 17\n",
        encoding="utf-8",
    )
    config = ServerConfig(
        token=TOKEN,
        port=43123,
        data_dir=tmp_path / "data",
        default_model="openai:gpt-test",
    )
    provider = AttachmentCaptureProvider()
    opened_commands = []

    def open_item(command, **kwargs):
        opened_commands.append((command, kwargs))
        return SimpleNamespace(returncode=0)

    monkeypatch.setattr(
        "runtime.control_plane.server.subprocess.run",
        open_item,
    )
    helper = tmp_path / "codinal-helper"
    helper.write_text("#!/bin/sh\n", encoding="utf-8")
    helper.chmod(0o700)
    monkeypatch.setenv("CODINAL_HOST_HELPER", str(helper))
    services = build_services(config, provider=provider)

    with TestClient(
        create_control_plane_app(token=TOKEN, services=services)
    ) as client:
        with client.websocket_connect(
            "/ws/session/context-session",
            subprotocols=[
                "codinal.v1",
                websocket_auth_protocol(TOKEN),
            ],
        ) as socket:
            initialized = client.post(
                "/v1/sessions/context-session/turns",
                headers=AUTH,
                json={
                    "input": "Initialize context",
                    "workspace": str(workspace),
                },
            )
            event = socket.receive_json()
            while event["type"] != "turn_end":
                event = socket.receive_json()
            roots = client.get(
                "/v1/sessions/context-session/roots",
                headers=AUTH,
            ).json()
            descriptor = {
                "kind": "file",
                "root": roots[0]["path"],
                "path": "main.py",
            }
            selected = client.post(
                "/v1/sessions/context-session/context",
                headers=AUTH,
                json=descriptor,
            )
            item = selected.json()["item"]
            opened = client.post(
                "/v1/sessions/context-session/project/open",
                headers=AUTH,
                json={**descriptor, "mode": "reveal"},
            )
            sent = client.post(
                "/v1/sessions/context-session/turns",
                headers=AUTH,
                json={
                    "input": "Use the selected file",
                    "context": [
                        {
                            **descriptor,
                            "fingerprint": item["fingerprint"],
                        }
                    ],
                },
            )
            event = socket.receive_json()
            while event["type"] != "turn_end":
                event = socket.receive_json()

    assert initialized.status_code == 202
    assert selected.status_code == 200
    assert opened.status_code == 200
    assert sent.status_code == 202
    provider_users = [
        message
        for message in provider.calls[-1]["messages"]
        if message["role"] == "user"
    ]
    assert provider_users[-1]["content"][0] == item["provider_part"]
    assert provider_users[-1]["content"][1] == {
        "type": "text",
        "text": "Use the selected file",
    }
    assert len(opened_commands) == 1
    command, options = opened_commands[0]
    assert command[:3] == [
        str(helper),
        "--codinal-open-fd",
        "reveal",
    ]
    assert options["pass_fds"] == (int(command[3]),)


def test_production_search_fork_and_side_conversation_survive_restart(tmp_path):
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    data_dir = tmp_path / "data"
    store = ConversationStore(data_dir)
    store.save(
        SessionRecord(
            session_id="search-source",
            workspace=str(workspace),
            model="openai:gpt-test",
            mode="interactive",
            title="Retry investigation",
            messages=[
                {"role": "user", "content": "Find retry jitter"},
                {"role": "assistant", "content": "Inspect backoff.py"},
                {"role": "user", "content": "Now change it"},
            ],
            grants={"tools": ["shell"]},
        )
    )
    store.close()
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

    with TestClient(
        create_control_plane_app(token=TOKEN, services=services)
    ) as client:
        found = client.get(
            "/v1/sessions/search",
            headers=AUTH,
            params={"q": "jitter"},
        )
        forked = client.post(
            "/v1/sessions/search-source/fork",
            headers=AUTH,
            json={"message_index": 1},
        )
        side = client.post(
            "/v1/sessions/search-source/side-conversations",
            headers=AUTH,
            json={"message_index": 1},
        )

    assert found.status_code == 200
    assert found.json()[0]["match_message_index"] == 0
    assert found.json()[0]["match_excerpt"] == "Find retry jitter"
    assert forked.status_code == 200
    fork_id = forked.json()["session_id"]
    assert side.status_code == 200
    side_id = side.json()["session_id"]

    restarted = build_services(
        config,
        provider=AttachmentCaptureProvider(),
    )
    with TestClient(
        create_control_plane_app(token=TOKEN, services=restarted)
    ) as client:
        persisted_search = client.get(
            "/v1/sessions/search",
            headers=AUTH,
            params={"q": "backoff.py"},
        )
        persisted_messages = client.get(
            f"/v1/sessions/{fork_id}/messages",
            headers=AUTH,
        )
        persisted_sessions = client.get("/v1/sessions", headers=AUTH)

    assert fork_id in {
        result["session_id"] for result in persisted_search.json()
    }
    assert persisted_messages.json() == [
        {"role": "user", "content": "Find retry jitter"},
        {"role": "assistant", "content": "Inspect backoff.py"},
    ]
    persisted_side = next(
        session
        for session in persisted_sessions.json()
        if session["session_id"] == side_id
    )
    assert persisted_side["origin"] == "side_conversation"
    assert persisted_side["origin_session_id"] == "search-source"
    reopened_store = ConversationStore(data_dir)
    fork_record = reopened_store.load(fork_id)
    reopened_store.close()
    assert fork_record is not None
    assert fork_record.grants == {}
    assert fork_record.turn_checkpoint == TurnCheckpoint()


def test_production_project_roots_and_tree_survive_restart(tmp_path):
    workspace = tmp_path / "workspace"
    shared = tmp_path / "shared"
    workspace.mkdir()
    shared.mkdir()
    (shared / "docs").mkdir()
    (shared / "docs" / "guide.md").write_text(
        "class DurableGuide:\n    pass\n",
        encoding="utf-8",
    )
    data_dir = tmp_path / "data"
    store = ConversationStore(data_dir)
    store.save(
        SessionRecord(
            session_id="context-session",
            workspace=str(workspace),
            model="openai:gpt-test",
            mode="interactive",
            messages=[{"role": "user", "content": "inspect project"}],
        )
    )
    store.close()
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

    with TestClient(
        create_control_plane_app(token=TOKEN, services=services)
    ) as client:
        added = client.post(
            "/v1/sessions/context-session/roots",
            headers=AUTH,
            json={"path": str(shared), "writable": False},
        )
        tree = client.get(
            "/v1/sessions/context-session/tree",
            headers=AUTH,
            params={"root": str(shared), "path": "docs"},
        )
        search = client.get(
            "/v1/sessions/context-session/project/search",
            headers=AUTH,
            params={"q": "DurableGuide", "mode": "symbol"},
        )
        indexed = client.post(
            "/v1/sessions/context-session/project/index",
            headers=AUTH,
        )

    assert added.status_code == 200
    assert added.json()["roots"][1]["writable"] is False
    assert tree.status_code == 200
    assert tree.json()["entries"] == [
        {"name": "guide.md", "path": "docs/guide.md", "kind": "file"}
    ]
    assert search.status_code == 200
    assert search.json()["matches"][0]["path"] == "docs/guide.md"
    assert search.json()["matches"][0]["kind"] == "class"
    assert indexed.status_code == 200
    assert indexed.json()["indexed_chunks"] >= 1

    restarted = build_services(
        config,
        provider=AttachmentCaptureProvider(),
    )
    with TestClient(
        create_control_plane_app(token=TOKEN, services=restarted)
    ) as client:
        roots = client.get(
            "/v1/sessions/context-session/roots",
            headers=AUTH,
        )
        persisted_search = client.get(
            "/v1/sessions/context-session/project/search",
            headers=AUTH,
            params={"q": "DurableGuide", "mode": "text"},
        )
        index_status = client.get(
            "/v1/sessions/context-session/project/index",
            headers=AUTH,
        )
        semantic = client.get(
            "/v1/sessions/context-session/project/search",
            headers=AUTH,
            params={"q": "durable guide", "mode": "semantic"},
        )
        cleared = client.delete(
            "/v1/sessions/context-session/project/index",
            headers=AUTH,
        )
        removed = client.request(
            "DELETE",
            "/v1/sessions/context-session/roots",
            headers=AUTH,
            json={"path": str(shared)},
        )

    assert roots.status_code == 200
    assert roots.json()[1]["path"] == str(shared.resolve())
    assert persisted_search.status_code == 200
    assert persisted_search.json()["count"] == 1
    assert index_status.json()["state"] == "ready"
    assert semantic.status_code == 200
    assert semantic.json()["matches"][0]["path"] == "docs/guide.md"
    assert cleared.json()["deleted_chunks"] >= 1
    assert removed.status_code == 200
    assert len(removed.json()["roots"]) == 1


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
        "ask_user",
        "propose_plan",
        "request_directory",
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


def test_restart_restores_awaiting_question_and_resumes_once(tmp_path):
    class RecoveryProvider(ProviderClient):
        def __init__(self):
            self.calls = 0

        def complete(self, **_kwargs):
            self.calls += 1
            return AssistantTurn(text="answer received")

        def capabilities(self, _model):
            return ModelCapabilities()

    workspace = tmp_path / "workspace"
    workspace.mkdir()
    data_dir = tmp_path / "data"
    store = ConversationStore(data_dir)
    store.save(
        SessionRecord(
            session_id="session-question-recovery",
            workspace=str(workspace),
            source_workspace=str(workspace),
            model="openai:gpt-test",
            mode="interactive",
            messages=[
                {"role": "user", "content": "choose a database"},
                {
                    "role": "assistant",
                    "content": None,
                    "tool_calls": [
                        {
                            "id": "provider/question-recovery",
                            "type": "function",
                            "function": {
                                "name": "ask_user",
                                "arguments": json.dumps(
                                    {
                                        "question": "Which database?",
                                        "options": [
                                            "PostgreSQL",
                                            "SQLite",
                                        ],
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
                (
                    "/v1/sessions/session-question-recovery/"
                    "interactions"
                ),
                headers=AUTH,
            ).json()
            if pending:
                break
            time.sleep(0.01)
        assert len(pending) == 1
        assert pending[0]["kind"] == "question"
        resolved = client.post(
            (
                "/v1/sessions/session-question-recovery/"
                f"interactions/{pending[0]['interaction_id']}"
            ),
            headers=AUTH,
            json={"answer": "PostgreSQL"},
        )
        assert resolved.status_code == 200
        for _ in range(100):
            if not services.turns.is_active(
                "session-question-recovery"
            ):
                break
            time.sleep(0.01)

    assert provider.calls == 1
    recovered = ConversationStore(data_dir).load(
        "session-question-recovery"
    )
    assert recovered is not None
    assert recovered.turn_checkpoint == TurnCheckpoint()
    results = [
        message
        for message in recovered.messages
        if message.get("role") == "tool"
    ]
    assert len(results) == 1
    assert results[0]["tool_call_id"] == "provider/question-recovery"
    assert "PostgreSQL" in results[0]["content"]


@pytest.mark.parametrize(
    ("kind", "tool_name", "arguments", "response", "mode"),
    [
        (
            "plan",
            "propose_plan",
            _selective_plan(),
            _selective_plan_approval(),
            "plan",
        ),
        (
            "directory",
            "request_directory",
            {
                "reason": "Read shared schemas",
                "writable": False,
            },
            None,
            "interactive",
        ),
    ],
)
def test_restart_restores_other_interactions_and_resumes_once(
    tmp_path,
    kind,
    tool_name,
    arguments,
    response,
    mode,
):
    class RecoveryProvider(ProviderClient):
        def __init__(self):
            self.calls = 0

        def complete(self, **_kwargs):
            self.calls += 1
            return AssistantTurn(text=f"{kind} response applied")

        def capabilities(self, _model):
            return ModelCapabilities()

    workspace = tmp_path / "workspace"
    shared = tmp_path / "shared"
    workspace.mkdir()
    shared.mkdir()
    if response is None:
        response = {
            "granted": True,
            "path": str(shared),
            "writable": False,
        }
    session_id = f"session-{kind}-recovery"
    tool_call_id = f"provider/{kind}-recovery"
    data_dir = tmp_path / "data"
    store = ConversationStore(data_dir)
    store.save(
        SessionRecord(
            session_id=session_id,
            workspace=str(workspace),
            source_workspace=str(workspace),
            model="openai:gpt-test",
            mode=mode,
            messages=[
                {"role": "user", "content": f"request {kind}"},
                {
                    "role": "assistant",
                    "content": None,
                    "tool_calls": [
                        {
                            "id": tool_call_id,
                            "type": "function",
                            "function": {
                                "name": tool_name,
                                "arguments": json.dumps(arguments),
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
                f"/v1/sessions/{session_id}/interactions",
                headers=AUTH,
            ).json()
            if pending:
                break
            time.sleep(0.01)
        assert len(pending) == 1
        assert pending[0]["kind"] == kind
        resolved = client.post(
            (
                f"/v1/sessions/{session_id}/interactions/"
                f"{pending[0]['interaction_id']}"
            ),
            headers=AUTH,
            json=response,
        )
        assert resolved.status_code == 200
        for _ in range(100):
            if not services.turns.is_active(session_id):
                break
            time.sleep(0.01)

    assert provider.calls == 1
    recovered = ConversationStore(data_dir).load(session_id)
    assert recovered is not None
    assert recovered.turn_checkpoint == TurnCheckpoint()
    assert [
        message.get("tool_call_id")
        for message in recovered.messages
        if message.get("role") == "tool"
    ] == [tool_call_id]
    if kind == "plan":
        assert recovered.mode == "interactive"
    else:
        assert recovered.extra_roots == [
            {
                "path": str(shared.resolve()),
                "writable": False,
                "label": "shared",
                "_device": shared.stat().st_dev,
                "_inode": shared.stat().st_ino,
            }
        ]


def test_directory_replay_rejects_replaced_approved_filesystem_object(
    tmp_path,
):
    class RecoveryProvider(ProviderClient):
        def complete(self, **_kwargs):
            return AssistantTurn(text="directory response handled")

        def capabilities(self, _model):
            return ModelCapabilities()

    workspace = tmp_path / "workspace"
    approved = tmp_path / "approved"
    outside = tmp_path / "outside"
    workspace.mkdir()
    approved.mkdir()
    outside.mkdir()
    arguments = {
        "reason": "Read shared schemas",
        "writable": False,
    }
    fingerprint = hashlib.sha256(
        json.dumps(
            {
                "arguments": arguments,
                "kind": "directory",
            },
            allow_nan=False,
            separators=(",", ":"),
            sort_keys=True,
        ).encode("utf-8")
    ).hexdigest()
    metadata = approved.stat()
    data_dir = tmp_path / "data"
    store = ConversationStore(data_dir)
    store.save(
        SessionRecord(
            session_id="session-directory-swap",
            workspace=str(workspace),
            source_workspace=str(workspace),
            model="openai:gpt-test",
            mode="interactive",
            messages=[
                {"role": "user", "content": "add shared schemas"},
                {
                    "role": "assistant",
                    "content": None,
                    "tool_calls": [
                        {
                            "id": "provider/directory-swap",
                            "type": "function",
                            "function": {
                                "name": "request_directory",
                                "arguments": json.dumps(arguments),
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
    store.save_interaction_decision(
        "session-directory-swap",
        "provider/directory-swap",
        "directory",
        fingerprint,
        {
            "granted": True,
            "path": str(approved.resolve()),
            "writable": False,
            "_device": metadata.st_dev,
            "_inode": metadata.st_ino,
        },
    )
    store.close()
    moved = tmp_path / "approved-original"
    approved.rename(moved)
    approved.symlink_to(outside, target_is_directory=True)
    services = build_services(
        ServerConfig(
            token=TOKEN,
            port=43123,
            data_dir=data_dir,
            default_model="openai:gpt-test",
        ),
        provider=RecoveryProvider(),
    )

    with TestClient(
        create_control_plane_app(token=TOKEN, services=services)
    ):
        for _ in range(100):
            if not services.turns.is_active(
                "session-directory-swap"
            ):
                break
            time.sleep(0.01)

    recovered = ConversationStore(data_dir).load(
        "session-directory-swap"
    )
    assert recovered is not None
    assert recovered.extra_roots == []
    tool_result = next(
        message
        for message in recovered.messages
        if message.get("role") == "tool"
    )
    assert "approved resource changed" in tool_result["content"]


@pytest.mark.parametrize(
    ("kind", "tool_name", "arguments", "response", "mode"),
    [
        (
            "question",
            "ask_user",
            {"question": "Which database?"},
            {"answer": "PostgreSQL"},
            "interactive",
        ),
        (
            "plan",
            "propose_plan",
            _selective_plan(),
            _selective_plan_approval(),
            "plan",
        ),
        (
            "directory",
            "request_directory",
            {
                "reason": "Read shared schemas",
                "writable": False,
            },
            None,
            "interactive",
        ),
    ],
)
def test_graceful_restart_preserves_live_waiting_interaction(
    tmp_path,
    kind,
    tool_name,
    arguments,
    response,
    mode,
):
    class PromptProvider(ProviderClient):
        def complete(self, **_kwargs):
            return AssistantTurn(
                tool_calls=[
                    ToolCall(
                        f"provider/{kind}-graceful",
                        tool_name,
                        arguments,
                    )
                ]
            )

        def capabilities(self, _model):
            return ModelCapabilities()

    class RecoveryProvider(ProviderClient):
        def __init__(self):
            self.calls = 0
            self.messages = []

        def complete(self, **kwargs):
            self.calls += 1
            self.messages = list(kwargs["messages"])
            return AssistantTurn(text=f"{kind} resumed")

        def capabilities(self, _model):
            return ModelCapabilities()

    workspace = tmp_path / "workspace"
    shared = tmp_path / "shared"
    workspace.mkdir()
    shared.mkdir()
    if response is None:
        response = {
            "granted": True,
            "path": str(shared),
            "writable": False,
        }
    session_id = f"session-{kind}-graceful"
    config = ServerConfig(
        token=TOKEN,
        port=43123,
        data_dir=tmp_path / "data",
        default_model="openai:gpt-test",
    )
    first = build_services(config, provider=PromptProvider())

    with TestClient(
        create_control_plane_app(token=TOKEN, services=first)
    ) as client:
        with client.websocket_connect(
            f"/ws/session/{session_id}",
            subprotocols=[
                "codinal.v1",
                websocket_auth_protocol(TOKEN),
            ],
        ) as socket:
            accepted = client.post(
                f"/v1/sessions/{session_id}/turns",
                headers=AUTH,
                json={
                    "input": f"request {kind}",
                    "workspace": str(workspace),
                    "agent": "plan" if kind == "plan" else "code",
                    "mode": mode,
                },
            )
            assert accepted.status_code == 202
            expected_event = {
                "directory": "directory_requested",
                "plan": "plan_proposed",
                "question": "question_requested",
            }[kind]
            while socket.receive_json()["type"] != expected_event:
                pass

    waiting = ConversationStore(config.data_dir).load(session_id)
    assert waiting is not None
    assert waiting.turn_checkpoint == TurnCheckpoint(
        TurnStatus.AWAITING_APPROVAL
    )
    assert not any(
        message.get("role") == "tool"
        for message in waiting.messages
    )
    recovery_provider = RecoveryProvider()
    second = build_services(config, provider=recovery_provider)

    with TestClient(
        create_control_plane_app(token=TOKEN, services=second)
    ) as client:
        pending = []
        for _ in range(100):
            pending = client.get(
                f"/v1/sessions/{session_id}/interactions",
                headers=AUTH,
            ).json()
            if pending:
                break
            time.sleep(0.01)
        assert len(pending) == 1
        resolved = client.post(
            (
                f"/v1/sessions/{session_id}/interactions/"
                f"{pending[0]['interaction_id']}"
            ),
            headers=AUTH,
            json=response,
        )
        assert resolved.status_code == 200
        for _ in range(100):
            if not second.turns.is_active(session_id):
                break
            time.sleep(0.01)

    assert recovery_provider.calls == 1
    recovered = ConversationStore(config.data_dir).load(session_id)
    assert recovered is not None
    assert recovered.turn_checkpoint == TurnCheckpoint()
    assert len(
        [
            message
            for message in recovered.messages
            if message.get("role") == "tool"
        ]
    ) == 1
    if kind == "plan":
        reopened = ConversationStore(config.data_dir)
        plans = reopened.list_plan_artifacts(session_id)
        reopened.close()
        assert plans[0]["status"] == "approved"
        assert plans[0]["revision"] == 2
        assert plans[0]["plan"] == "Implement only"
        assert plans[0]["selected_task_ids"] == ["implement"]
        tool_result = next(
            message
            for message in recovery_provider.messages
            if message.get("role") == "tool"
        )
        result = json.loads(_unfence(tool_result["content"]))
        assert result["selected_task_ids"] == ["implement"]
        assert result["selected_tasks"][0]["verification"] == (
            "Restart E2E passes"
        )
        assert sum(
            message.get("role") == "user"
            and message.get("content") == "request plan"
            for message in recovery_provider.messages
        ) == 1


def test_v6_legacy_plan_wait_recovers_with_required_verification(
    tmp_path,
):
    class RecoveryProvider(ProviderClient):
        def __init__(self):
            self.calls = 0
            self.messages = []

        def complete(self, **kwargs):
            self.calls += 1
            self.messages = list(kwargs["messages"])
            return AssistantTurn(text="legacy plan resumed")

        def capabilities(self, _model):
            return ModelCapabilities()

    workspace = tmp_path / "workspace"
    workspace.mkdir()
    data_dir = tmp_path / "data"
    store = ConversationStore(data_dir)
    store.save(
        SessionRecord(
            session_id="session-v6-plan",
            workspace=str(workspace),
            source_workspace=str(workspace),
            model="openai:gpt-test",
            mode="plan",
            messages=[
                {"role": "user", "content": "legacy request"},
                {
                    "role": "assistant",
                    "content": None,
                    "tool_calls": [
                        {
                            "id": "provider/v6-plan",
                            "type": "function",
                            "function": {
                                "name": "propose_plan",
                                "arguments": json.dumps(
                                    {"plan": "Legacy implementation"}
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
    database = data_dir / "codinal.db"
    with sqlite3.connect(database) as connection:
        connection.execute("DROP TABLE plan_artifacts")
        connection.execute("PRAGMA user_version = 6")
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
                "/v1/sessions/session-v6-plan/interactions",
                headers=AUTH,
            ).json()
            if pending:
                break
            time.sleep(0.01)
        assert len(pending) == 1
        task = pending[0]["arguments"]["tasks"][0]
        assert task["id"] == "legacy-plan"
        rejected = client.post(
            (
                "/v1/sessions/session-v6-plan/interactions/"
                f"{pending[0]['interaction_id']}"
            ),
            headers=AUTH,
            json={
                "approved": True,
                "mode": "interactive",
                "selected_task_ids": ["legacy-plan"],
            },
        )
        assert rejected.status_code == 400
        resolved = client.post(
            (
                "/v1/sessions/session-v6-plan/interactions/"
                f"{pending[0]['interaction_id']}"
            ),
            headers=AUTH,
            json={
                "approved": True,
                "mode": "interactive",
                "plan": "Legacy implementation",
                "tasks": [
                    {
                        "id": "legacy-plan",
                        "title": "Legacy implementation",
                        "verification": "Migration E2E passes",
                    }
                ],
                "selected_task_ids": ["legacy-plan"],
            },
        )
        assert resolved.status_code == 200
        for _ in range(100):
            if not services.turns.is_active("session-v6-plan"):
                break
            time.sleep(0.01)

    assert provider.calls == 1
    assert sum(
        message.get("role") == "user"
        and message.get("content") == "legacy request"
        for message in provider.messages
    ) == 1
    assert sum(
        message.get("role") == "tool"
        and message.get("tool_call_id") == "provider/v6-plan"
        for message in provider.messages
    ) == 1
    reopened = ConversationStore(data_dir)
    plans = reopened.list_plan_artifacts("session-v6-plan")
    reopened.close()
    assert plans[0]["status"] == "approved"
    assert plans[0]["selected_task_ids"] == ["legacy-plan"]
    assert plans[0]["tasks"][0]["verification"] == "Migration E2E passes"
    with sqlite3.connect(database) as connection:
        assert connection.execute("PRAGMA user_version").fetchone()[0] == 8


def test_production_question_and_directory_cards_apply_selected_root(
    tmp_path,
):
    class InteractionProvider(ProviderClient):
        def __init__(self):
            self.calls = 0

        def complete(self, **_kwargs):
            self.calls += 1
            if self.calls == 1:
                return AssistantTurn(
                    tool_calls=[
                        ToolCall(
                            "provider/question-1",
                            "ask_user",
                            {
                                "question": "Which database?",
                                "options": ["PostgreSQL", "SQLite"],
                            },
                        )
                    ]
                )
            if self.calls == 2:
                return AssistantTurn(
                    tool_calls=[
                        ToolCall(
                            "provider/directory-1",
                            "request_directory",
                            {
                                "reason": "Read shared schemas",
                                "writable": False,
                            },
                        )
                    ]
                )
            return AssistantTurn(text="inputs applied")

        def capabilities(self, _model):
            return ModelCapabilities()

    workspace = tmp_path / "workspace"
    shared = tmp_path / "shared"
    workspace.mkdir()
    shared.mkdir()
    config = ServerConfig(
        token=TOKEN,
        port=43123,
        data_dir=tmp_path / "data",
        default_model="openai:gpt-test",
    )
    services = build_services(
        config,
        provider=InteractionProvider(),
    )
    events = []

    with TestClient(
        create_control_plane_app(token=TOKEN, services=services)
    ) as client:
        with client.websocket_connect(
            "/ws/session/session-interactions",
            subprotocols=[
                "codinal.v1",
                websocket_auth_protocol(TOKEN),
            ],
        ) as socket:
            accepted = client.post(
                "/v1/sessions/session-interactions/turns",
                headers=AUTH,
                json={
                    "input": "configure the project",
                    "workspace": str(workspace),
                },
            )
            while not events or events[-1]["type"] != "turn_end":
                event = socket.receive_json()
                events.append(event)
                if event["type"] == "question_requested":
                    response = client.post(
                        (
                            "/v1/sessions/session-interactions/"
                            f"interactions/{event['interaction_id']}"
                        ),
                        headers=AUTH,
                        json={"answer": "PostgreSQL"},
                    )
                    assert response.status_code == 200
                elif event["type"] == "directory_requested":
                    response = client.post(
                        (
                            "/v1/sessions/session-interactions/"
                            f"interactions/{event['interaction_id']}"
                        ),
                        headers=AUTH,
                        json={
                            "granted": True,
                            "path": str(shared),
                            "writable": False,
                        },
                    )
                    assert response.status_code == 200

    assert accepted.status_code == 202
    assert [
        event["type"]
        for event in events
        if event["type"].endswith("_requested")
    ] == ["question_requested", "directory_requested"]
    assert services.sessions.roots("session-interactions")[1] == {
        "path": str(shared.resolve()),
        "writable": False,
        "label": "shared",
        "primary": False,
        "exists": True,
    }
    stored = ConversationStore(config.data_dir).load(
        "session-interactions"
    )
    assert stored is not None
    assert stored.extra_roots == [
        {
            "path": str(shared.resolve()),
            "writable": False,
            "label": "shared",
            "_device": shared.stat().st_dev,
            "_inode": shared.stat().st_ino,
        }
    ]


def test_production_plan_card_approves_into_interactive_mode(tmp_path):
    class PlanProvider(ProviderClient):
        def __init__(self):
            self.calls = 0

        def complete(self, **_kwargs):
            self.calls += 1
            if self.calls == 1:
                return AssistantTurn(
                    tool_calls=[
                        ToolCall(
                            "provider/plan-1",
                            "propose_plan",
                            _plan("1. Test\n2. Build"),
                        )
                    ]
                )
            return AssistantTurn(text="building approved plan")

        def capabilities(self, _model):
            return ModelCapabilities()

    workspace = tmp_path / "workspace"
    workspace.mkdir()
    data_dir = tmp_path / "data"
    services = build_services(
        ServerConfig(
            token=TOKEN,
            port=43123,
            data_dir=data_dir,
            default_model="openai:gpt-test",
        ),
        provider=PlanProvider(),
    )

    with TestClient(
        create_control_plane_app(token=TOKEN, services=services)
    ) as client:
        with client.websocket_connect(
            "/ws/session/session-plan",
            subprotocols=[
                "codinal.v1",
                websocket_auth_protocol(TOKEN),
            ],
        ) as socket:
            accepted = client.post(
                "/v1/sessions/session-plan/turns",
                headers=AUTH,
                json={
                    "input": "plan the change",
                    "workspace": str(workspace),
                    "agent": "plan",
                    "mode": "plan",
                },
            )
            while True:
                event = socket.receive_json()
                if event["type"] == "plan_proposed":
                    resolved = client.post(
                        (
                            "/v1/sessions/session-plan/"
                            f"interactions/{event['interaction_id']}"
                        ),
                        headers=AUTH,
                        json={
                            "approved": True,
                            "mode": "interactive",
                        },
                    )
                    assert resolved.status_code == 200
                if event["type"] == "turn_end":
                    break

    assert accepted.status_code == 202
    stored = ConversationStore(data_dir).load("session-plan")
    assert stored is not None
    assert stored.mode == "interactive"
    assert any(
        message.get("role") == "tool"
        and "approved" in message.get("content", "")
        for message in stored.messages
    )


def test_production_plan_edits_and_selected_tasks_reach_same_turn(
    tmp_path,
):
    class PlanProvider(ProviderClient):
        def __init__(self):
            self.calls = 0
            self.follow_up_messages = []

        def complete(self, **kwargs):
            self.calls += 1
            if self.calls == 1:
                return AssistantTurn(
                    tool_calls=[
                        ToolCall(
                            "provider/structured-plan",
                            "propose_plan",
                            {
                                "plan": "Original plan",
                                "tasks": [
                                    {
                                        "id": "tests",
                                        "title": "Add tests",
                                        "verification": "Focused tests pass",
                                    },
                                    {
                                        "id": "build",
                                        "title": "Build feature",
                                        "verification": "Full suite passes",
                                    },
                                ],
                            },
                        )
                    ]
                )
            self.follow_up_messages = list(kwargs["messages"])
            return AssistantTurn(text="executing selected task")

        def capabilities(self, _model):
            return ModelCapabilities()

    workspace = tmp_path / "workspace"
    workspace.mkdir()
    data_dir = tmp_path / "data"
    provider = PlanProvider()
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
        with client.websocket_connect(
            "/ws/session/session-structured-plan",
            subprotocols=[
                "codinal.v1",
                websocket_auth_protocol(TOKEN),
            ],
        ) as socket:
            accepted = client.post(
                "/v1/sessions/session-structured-plan/turns",
                headers=AUTH,
                json={
                    "input": "plan the change",
                    "workspace": str(workspace),
                    "agent": "plan",
                    "mode": "plan",
                },
            )
            while True:
                event = socket.receive_json()
                if event["type"] == "plan_proposed":
                    pending = client.get(
                        "/v1/sessions/session-structured-plan/interactions",
                        headers=AUTH,
                    ).json()[0]
                    assert pending["arguments"]["tasks"][0][
                        "verification"
                    ] == "Focused tests pass"
                    resolved = client.post(
                        (
                            "/v1/sessions/session-structured-plan/"
                            f"interactions/{event['interaction_id']}"
                        ),
                        headers=AUTH,
                        json={
                            "approved": True,
                            "mode": "interactive",
                            "plan": "Edited plan",
                            "tasks": [
                                {
                                    "id": "tests",
                                    "title": "Add regression tests",
                                    "verification": (
                                        "Regression suite passes"
                                    ),
                                },
                                {
                                    "id": "build",
                                    "title": "Build feature",
                                    "verification": "Full suite passes",
                                },
                            ],
                            "selected_task_ids": ["tests"],
                        },
                    )
                    assert resolved.status_code == 200
                if event["type"] == "turn_end":
                    break
        plans = client.get(
            "/v1/sessions/session-structured-plan/plans",
            headers=AUTH,
        )

    assert accepted.status_code == 202
    assert plans.status_code == 200
    artifact = plans.json()[0]
    assert artifact["status"] == "approved"
    assert artifact["plan"] == "Edited plan"
    assert artifact["selected_task_ids"] == ["tests"]
    tool_result = next(
        message
        for message in provider.follow_up_messages
        if message.get("role") == "tool"
    )
    result = json.loads(_unfence(tool_result["content"]))
    assert result["selected_task_ids"] == ["tests"]
    assert result["selected_tasks"][0]["title"] == "Add regression tests"
    assert any(
        message.get("role") == "user"
        and message.get("content") == "plan the change"
        for message in provider.follow_up_messages
    )


def test_existing_task_can_switch_from_code_to_plan_mode(tmp_path):
    class PlanProvider(ProviderClient):
        def __init__(self):
            self.calls = 0

        def complete(self, **_kwargs):
            self.calls += 1
            if self.calls == 1:
                return AssistantTurn(text="code task ready")
            if self.calls == 2:
                return AssistantTurn(
                    tool_calls=[
                        ToolCall(
                            "provider/existing-plan",
                            "propose_plan",
                            _plan("1. Inspect\n2. Implement"),
                        )
                    ]
                )
            return AssistantTurn(text="existing plan approved")

        def capabilities(self, _model):
            return ModelCapabilities()

    workspace = tmp_path / "workspace"
    workspace.mkdir()
    data_dir = tmp_path / "data"
    services = build_services(
        ServerConfig(
            token=TOKEN,
            port=43123,
            data_dir=data_dir,
            default_model="openai:gpt-test",
        ),
        provider=PlanProvider(),
    )

    with TestClient(
        create_control_plane_app(token=TOKEN, services=services)
    ) as client:
        with client.websocket_connect(
            "/ws/session/session-existing-plan",
            subprotocols=[
                "codinal.v1",
                websocket_auth_protocol(TOKEN),
            ],
        ) as socket:
            first = client.post(
                "/v1/sessions/session-existing-plan/turns",
                headers=AUTH,
                json={
                    "input": "start coding",
                    "workspace": str(workspace),
                    "agent": "code",
                    "mode": "interactive",
                },
            )
            while socket.receive_json()["type"] != "turn_end":
                pass
            second = client.post(
                "/v1/sessions/session-existing-plan/turns",
                headers=AUTH,
                json={
                    "input": "plan the next change",
                    "agent": "plan",
                    "mode": "plan",
                },
            )
            saw_plan = False
            while True:
                event = socket.receive_json()
                if event["type"] == "plan_proposed":
                    saw_plan = True
                    resolved = client.post(
                        (
                            "/v1/sessions/session-existing-plan/"
                            f"interactions/{event['interaction_id']}"
                        ),
                        headers=AUTH,
                        json={
                            "approved": True,
                            "mode": "interactive",
                        },
                    )
                    assert resolved.status_code == 200
                if event["type"] == "turn_end":
                    break

    assert first.status_code == 202
    assert second.status_code == 202
    assert saw_plan
    stored = ConversationStore(data_dir).load(
        "session-existing-plan"
    )
    assert stored is not None
    assert stored.mode == "interactive"


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
    reason="production worktree creation uses macOS Seatbelt",
)
def test_checkpoint_restore_aborts_same_path_manual_edit_e2e(tmp_path):
    """A manual edit to a path the Agent touched aborts restore over HTTP
    and leaves the workspace exactly as the user left it.

    Roadmap L54 "same-path conflict-abort" E2E. The invariant was previously
    proven only at the service/shell layer
    (tests/git_runtime/test_plain_checkpoints.py:167,
    tests/git_runtime/test_worktree_lifecycle.py:878); this drives it through
    the live control-plane restore route, which reaches the workspace via
    CheckpointRestoreCoordinator -> resume_restore_code -> _apply_restore_patch
    (service.py:3075), not the direct restore_checkpoint_code path.
    """

    class WriteTargetProvider(ProviderClient):
        def __init__(self):
            self.calls = 0

        def complete(self, **_kwargs):
            self.calls += 1
            if self.calls == 1:
                return AssistantTurn(
                    tool_calls=[
                        ToolCall(
                            "agent-write",
                            "write_file",
                            {
                                "path": "target.txt",
                                "content": "agent change\n",
                            },
                        )
                    ]
                )
            return AssistantTurn(text="written")

        def capabilities(self, _model):
            return ModelCapabilities()

    async def approve_once(_request):
        return ApprovalOutcome.ONCE

    source = tmp_path / "conflict-source"
    source.mkdir()
    subprocess.run(
        ["git", "init", "-b", "feature", str(source)],
        check=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    subprocess.run(
        ["git", "-C", str(source), "config", "user.name", "Codinal Test"],
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
    (source / "target.txt").write_text("base\n", encoding="utf-8")
    subprocess.run(
        ["git", "-C", str(source), "add", "target.txt"],
        check=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
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
        data_dir=tmp_path / "conflict-data",
        default_model="openai:gpt-test",
    )
    services = build_services(
        config,
        provider=WriteTargetProvider(),
        approver=approve_once,
    )

    with TestClient(
        create_control_plane_app(token=TOKEN, services=services)
    ) as client:
        with client.websocket_connect(
            "/ws/session/conflict-e2e",
            subprotocols=[
                "codinal.v1",
                websocket_auth_protocol(TOKEN),
            ],
        ) as socket:
            accepted = client.post(
                "/v1/sessions/conflict-e2e/turns",
                headers=AUTH,
                json={
                    "input": "write target.txt",
                    "workspace": str(source),
                },
            )
            event = socket.receive_json()
            while event["type"] != "turn_end":
                event = socket.receive_json()
        checkpoints = client.get(
            "/v1/sessions/conflict-e2e/checkpoints",
            headers=AUTH,
        )
        checkpoint_id = checkpoints.json()[0]["checkpoint_id"]
        git_record = services.git.load("conflict-e2e")

        # Manual edit to the SAME path the Agent touched.
        (git_record.worktree_path / "target.txt").write_text(
            "manual override\n",
            encoding="utf-8",
        )

        restore = client.post(
            f"/v1/sessions/conflict-e2e/checkpoints/{checkpoint_id}/restore",
            headers=AUTH,
            json={"scope": "code"},
        )

    assert accepted.status_code == 202
    assert checkpoints.status_code == 200
    # The coordinator's _apply_restore_patch runs `git apply --check` first
    # and raises "checkpoint conflicts with current edits" -> HTTP 409.
    assert restore.status_code == 409
    assert (
        restore.json()["detail"]
        == "checkpoint conflicts with current edits"
    )
    # The workspace is left exactly as the user left it.
    assert (
        git_record.worktree_path / "target.txt"
    ).read_text(encoding="utf-8") == "manual override\n"


@pytest.mark.skipif(
    platform.system() != "Darwin",
    reason="transactional shell requires macOS Seatbelt",
)
def test_checkpoint_never_captures_uncaptured_secret_e2e(tmp_path):
    """A file the Agent never touched never enters the checkpoint object
    store, end-to-end through the live turn + mutation tools stack.

    Roadmap L54 "uncaptured-secret exclusion" E2E. The invariant was
    previously proven only at the service layer
    (tests/git_runtime/test_plain_checkpoints.py:73); this drives a real
    turn through the control plane and asserts the secret's blob is absent
    from the content-addressed checkpoint store.
    """

    class WriteAgentFileProvider(ProviderClient):
        def __init__(self):
            self.calls = 0

        def complete(self, **_kwargs):
            self.calls += 1
            if self.calls == 1:
                return AssistantTurn(
                    tool_calls=[
                        ToolCall(
                            "agent-write",
                            "write_file",
                            {
                                "path": "agent.txt",
                                "content": "agent only\n",
                            },
                        )
                    ]
                )
            return AssistantTurn(text="done")

        def capabilities(self, _model):
            return ModelCapabilities()

    async def approve_once(_request):
        return ApprovalOutcome.ONCE

    workspace = tmp_path / "secret-workspace"
    workspace.mkdir()
    # A secret the Agent will never touch.
    secret = workspace / "manual-secret.txt"
    secret.write_text("never captured\n", encoding="utf-8")
    config = ServerConfig(
        token=TOKEN,
        port=43123,
        data_dir=tmp_path / "secret-data",
        default_model="openai:gpt-test",
    )
    services = build_services(
        config,
        provider=WriteAgentFileProvider(),
        approver=approve_once,
    )

    with TestClient(
        create_control_plane_app(token=TOKEN, services=services)
    ) as client:
        with client.websocket_connect(
            "/ws/session/secret-e2e",
            subprotocols=[
                "codinal.v1",
                websocket_auth_protocol(TOKEN),
            ],
        ) as socket:
            accepted = client.post(
                "/v1/sessions/secret-e2e/turns",
                headers=AUTH,
                json={
                    "input": "write agent.txt only",
                    "workspace": str(workspace),
                },
            )
            event = socket.receive_json()
            while event["type"] != "turn_end":
                event = socket.receive_json()
        checkpoints = client.get(
            "/v1/sessions/secret-e2e/checkpoints",
            headers=AUTH,
        )
        checkpoint_id = checkpoints.json()[0]["checkpoint_id"]
        attributed_paths = {
            item.path
            for item in services.git.store.list_checkpoint_files(
                checkpoint_id
            )
        }

    # The secret must not be retrievable from the content-addressed
    # checkpoint object store for this session.
    secret_blob = subprocess.run(
        [
            services.git.git_executable,
            "hash-object",
            str(secret),
        ],
        check=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    ).stdout.strip()
    store_repo = (
        services.git.checkpoint_base
        / hashlib.sha256(b"secret-e2e").hexdigest()
    )
    stored_objects = subprocess.run(
        [
            services.git.git_executable,
            f"--git-dir={store_repo}",
            "cat-file",
            "--batch-all-objects",
            "--batch-check=%(objectname)",
        ],
        check=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    ).stdout.splitlines()

    assert accepted.status_code == 202
    assert checkpoints.status_code == 200
    assert attributed_paths == {"agent.txt"}
    assert secret_blob not in stored_objects
    # And the secret itself is untouched on disk.
    assert secret.read_text(encoding="utf-8") == "never captured\n"


@pytest.mark.skipif(
    platform.system() != "Darwin",
    reason="transactional shell requires macOS Seatbelt",
)
def test_manual_edit_during_active_turn_survives_restore_e2e(tmp_path):
    """A manual edit made while a turn is active is preserved when the
    turn's checkpoint is later restored, and restore is refused while the
    turn is still active.

    Roadmap L54 "active-turn manual-edit preservation" E2E — the subtlest
    case, previously untested at any level. The active-turn restore guard
    (turns/service.py:263) was only unit-tested for refusal; this proves
    both halves: (a) restore returns 409 while active, and (b) a manual
    edit to a different path, injected mid-turn, survives the post-turn
    restore because the attributed checkpoint only contains Agent-touched
    paths.
    """

    class WriteThenBlockingShellProvider(ProviderClient):
        """Turn 1: write a file (creates a checkpoint we can later restore).
        Turn 2: a run_shell that blocks until the test releases it, keeping
        the turn active while the manual edit is injected."""

        def __init__(self, release_path):
            self.calls = 0
            self.release_path = release_path

        def complete(self, **_kwargs):
            self.calls += 1
            if self.calls == 1:
                return AssistantTurn(
                    tool_calls=[
                        ToolCall(
                            "seed-write",
                            "write_file",
                            {
                                "path": "agent.txt",
                                "content": "agent seed\n",
                            },
                        )
                    ]
                )
            if self.calls == 2:
                # Bounded poll (10s) so a test failure can't hang forever.
                return AssistantTurn(
                    tool_calls=[
                        ToolCall(
                            "blocking-shell",
                            "run_shell",
                            {
                                "command": (
                                    "/usr/bin/perl -e "
                                    "\"my $deadline=time+10; "
                                    "while(!-f $ARGV[0]){ "
                                    "exit 1 if time>$deadline; "
                                    "select(undef,undef,undef,0.05)} "
                                    "exit 0\" "
                                    f"\"{self.release_path}\""
                                ),
                                "timeout_seconds": 12,
                            },
                        )
                    ]
                )
            return AssistantTurn(text="released")

        def capabilities(self, _model):
            return ModelCapabilities()

    async def approve_once(_request):
        return ApprovalOutcome.ONCE

    workspace = tmp_path / "active-workspace"
    workspace.mkdir()
    release = tmp_path / "release.txt"
    config = ServerConfig(
        token=TOKEN,
        port=43123,
        data_dir=tmp_path / "active-data",
        default_model="openai:gpt-test",
    )
    services = build_services(
        config,
        provider=WriteThenBlockingShellProvider(release),
        approver=approve_once,
    )

    with TestClient(
        create_control_plane_app(token=TOKEN, services=services)
    ) as client:
        with client.websocket_connect(
            "/ws/session/active-e2e",
            subprotocols=[
                "codinal.v1",
                websocket_auth_protocol(TOKEN),
            ],
        ) as socket:
            # Turn 1: seed a checkpoint (completes immediately).
            client.post(
                "/v1/sessions/active-e2e/turns",
                headers=AUTH,
                json={
                    "input": "seed a file",
                    "workspace": str(workspace),
                },
            )
            event = socket.receive_json()
            while event["type"] != "turn_end":
                event = socket.receive_json()
            checkpoints = client.get(
                "/v1/sessions/active-e2e/checkpoints",
                headers=AUTH,
            )
            checkpoint_id = checkpoints.json()[0]["checkpoint_id"]

            # Turn 2: the blocking shell — stays active until released.
            accepted = client.post(
                "/v1/sessions/active-e2e/turns",
                headers=AUTH,
                json={
                    "input": "run the blocking shell",
                    "workspace": str(workspace),
                },
            )
            # Wait until the turn is actually active.
            for _ in range(500):
                if services.turns.is_active("active-e2e"):
                    break
                time.sleep(0.01)
            assert services.turns.is_active("active-e2e")

            # (a) Restore of the prior checkpoint is refused while turn 2
            # is active (the active-turn restore guard).
            restore_while_active = client.post(
                f"/v1/sessions/active-e2e/checkpoints/{checkpoint_id}/restore",
                headers=AUTH,
                json={"scope": "code"},
            )

            # Inject the manual edit to a DIFFERENT path WHILE the turn is
            # active.
            manual = workspace / "manual.txt"
            manual.write_text("mid-turn manual\n", encoding="utf-8")

            # Release the blocking shell and drain turn 2 to completion.
            release.write_text("go\n", encoding="utf-8")
            event = socket.receive_json()
            while event["type"] != "turn_end":
                event = socket.receive_json()

            # (b) Now idle — restore the prior checkpoint; the mid-turn
            # manual edit to a different path survives (attribution).
            restore_after = client.post(
                f"/v1/sessions/active-e2e/checkpoints/{checkpoint_id}/restore",
                headers=AUTH,
                json={"scope": "code"},
            )

    assert accepted.status_code == 202
    # (a) Restore is refused while the turn is active.
    assert restore_while_active.status_code == 409
    assert (
        restore_while_active.json()["detail"]
        == "session already has an active turn"
    )
    # (b) The mid-turn manual edit to a different path survives the
    # post-turn restore (attribution: only Agent-touched paths are in the
    # patch).
    assert restore_after.status_code == 200
    assert (
        workspace / "manual.txt"
    ).read_text(encoding="utf-8") == "mid-turn manual\n"


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


def test_mcp_server_lifecycle_routes_expose_list_and_disconnect(
    tmp_path,
):
    class FakeMCPManager:
        def __init__(self):
            self.connected = []
            self.disconnected = []
            self.listed: list[list[str]] = []
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

        async def call(self, _server, _tool, _arguments):
            self.called.append((_server, _tool, _arguments))
            return {"matches": ["policy.md"]}

        async def disconnect(self, server_name):
            self.disconnected.append(server_name)
            return True

        async def list(self):
            self.listed.append(list(self.connected))
            return sorted({name for name, approved in self.connected})

        async def aclose(self):
            self.closed = True

    workspace = tmp_path / "workspace"
    workspace.mkdir()
    from runtime.sessions import SessionRecord, TurnCheckpoint

    config = ServerConfig(
        token=TOKEN,
        port=43123,
        data_dir=tmp_path / "data",
        default_model="openai:gpt-test",
    )
    services = build_services(config, mcp_manager=FakeMCPManager())
    services.sessions._store.save(
        SessionRecord(
            session_id="session-lifecycle",
            workspace=str(workspace),
            model="openai:gpt-test",
            mode="interactive",
            turn_checkpoint=TurnCheckpoint(),
        )
    )

    with TestClient(
        create_control_plane_app(token=TOKEN, services=services)
    ) as client:
        list_initial = client.get(
            "/v1/sessions/session-lifecycle/mcp/servers",
            headers=AUTH,
        )
        assert list_initial.status_code == 200
        assert list_initial.json() == []

        connected = client.post(
            "/v1/sessions/session-lifecycle/mcp/connect",
            headers=AUTH,
            json={
                "server": {
                    "name": "docs",
                    "transport": "http",
                    "url": "https://mcp.example.com/v1",
                }
            },
        )
        assert connected.status_code == 200

        listed = client.get(
            "/v1/sessions/session-lifecycle/mcp/servers",
            headers=AUTH,
        )
        rows = listed.json()
        assert listed.status_code == 200
        assert rows == [
            {
                "name": "docs",
                "transport": "http",
                "url": "https://mcp.example.com/v1",
                "command": None,
                "cwd": None,
                "tools": [connected.json()["tools"][0]],
                "include_tools": None,
                "exclude_tools": [],
                "enabled": True,
            }
        ]

        removed = client.delete(
            "/v1/sessions/session-lifecycle/mcp/servers/docs",
            headers=AUTH,
        )
        assert removed.status_code == 200
        assert removed.json()["server"] == "docs"
        assert removed.json()["tools"] == [connected.json()["tools"][0]]
        assert services.mcp is not None
        assert services.mcp._manager.disconnected == ["docs"]

        final = client.get(
            "/v1/sessions/session-lifecycle/mcp/servers",
            headers=AUTH,
        )
        assert final.json() == []

        missing = client.delete(
            "/v1/sessions/session-lifecycle/mcp/servers/docs",
            headers=AUTH,
        )
        assert missing.status_code == 404


def test_mcp_connections_survive_restart_and_reconnect(tmp_path):
    class FakeMCPManager:
        def __init__(self):
            self.connect_calls: list[str] = []
            self.live: set[str] = set()

        async def connect(self, server, *, approved):
            self.connect_calls.append(server.name)
            self.live.add(server.name)
            return [
                SimpleNamespace(
                    name="search",
                    description="Search remote docs",
                    inputSchema={
                        "type": "object",
                        "properties": {"query": {"type": "string"}},
                        "required": ["query"],
                    },
                )
            ]

        async def call(self, _server, _tool, _arguments):
            return {"matches": ["policy.md"]}

        async def disconnect(self, server_name):
            self.live.discard(server_name)
            return True

        async def list(self):
            return sorted(self.live)

        async def aclose(self):
            self.live.clear()

    workspace = tmp_path / "workspace"
    workspace.mkdir()
    from runtime.sessions import SessionRecord, TurnCheckpoint

    data_dir = tmp_path / "data"
    config = ServerConfig(
        token=TOKEN,
        port=43123,
        data_dir=data_dir,
        default_model="openai:gpt-test",
    )

    # First lifecycle: connect docs (stays enabled) + cache (gets disabled).
    first_manager = FakeMCPManager()
    services = build_services(config, mcp_manager=first_manager)
    services.sessions._store.save(
        SessionRecord(
            session_id="session-restart",
            workspace=str(workspace),
            model="openai:gpt-test",
            mode="interactive",
            turn_checkpoint=TurnCheckpoint(),
        )
    )
    with TestClient(
        create_control_plane_app(token=TOKEN, services=services)
    ) as client:
        connect_docs = client.post(
            "/v1/sessions/session-restart/mcp/connect",
            headers=AUTH,
            json={
                "server": {
                    "name": "docs",
                    "transport": "http",
                    "url": "https://mcp.example.com/v1",
                }
            },
        )
        connect_cache = client.post(
            "/v1/sessions/session-restart/mcp/connect",
            headers=AUTH,
            json={
                "server": {
                    "name": "cache",
                    "transport": "http",
                    "url": "https://mcp.example.com/cache",
                }
            },
        )
        disable_cache = client.patch(
            "/v1/sessions/session-restart/mcp/servers/cache",
            headers=AUTH,
            json={"enabled": False},
        )
    assert connect_docs.status_code == 200
    assert connect_cache.status_code == 200
    assert disable_cache.status_code == 200

    # Second lifecycle: rebuild services from the same data_dir. lifespan must
    # reconnect docs (enabled) and leave cache (disabled) dormant.
    second_manager = FakeMCPManager()
    restarted = build_services(config, mcp_manager=second_manager)
    with TestClient(
        create_control_plane_app(token=TOKEN, services=restarted)
    ) as client:
        listed = client.get(
            "/v1/sessions/session-restart/mcp/servers",
            headers=AUTH,
        )
    rows = {row["name"]: row for row in listed.json()}
    assert rows["docs"]["enabled"] is True
    assert rows["docs"]["tools"] == ["mcp__docs__search"]
    assert rows["cache"]["enabled"] is False
    assert rows["cache"]["tools"] == []
    assert second_manager.connect_calls == ["docs"]

    # Audit chain survived restart and recorded every lifecycle event.
    events = restarted.audit.list(domain="mcp")
    actions = [event["action"] for event in events]
    # Restart lifecycle: connect docs, connect cache, disable cache,
    # then recover docs. Newest first.
    assert "connect" in actions
    assert "disable" in actions
    assert "recover" in actions
    assert restarted.audit.verify_chain() is True


def test_git_ship_loop_stage_commit_log_graph_push(tmp_path):
    import subprocess

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
    # Bare remote for push.
    bare = tmp_path / "remote.git"
    subprocess.run(
        ["git", "init", "--bare", str(bare)],
        check=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    subprocess.run(
        ["git", "-C", str(source), "remote", "add", "origin", str(bare)],
        check=True,
    )

    config = ServerConfig(
        token=TOKEN,
        port=43123,
        data_dir=tmp_path / "data",
        default_model="openai:gpt-test",
    )
    services = build_services(config)
    record = services.git.prepare("session-ship", source)

    with TestClient(
        create_control_plane_app(token=TOKEN, services=services)
    ) as client:
        # Make a change, stage, commit — all through the new routes.
        (Path(record.worktree_path) / "tracked.txt").write_text(
            "session edit\n", encoding="utf-8"
        )
        staged = client.post(
            "/v1/sessions/session-ship/git/stage",
            headers=AUTH,
            json={"path": "tracked.txt"},
        )
        committed = client.post(
            "/v1/sessions/session-ship/git/commit",
            headers=AUTH,
            json={"message": "Ship session change"},
        )
        log = client.get(
            "/v1/sessions/session-ship/git/log",
            headers=AUTH,
        )
        graph = client.get(
            "/v1/sessions/session-ship/git/graph",
            headers=AUTH,
        )
        per_commit = client.get(
            "/v1/sessions/session-ship/git/diff",
            headers=AUTH,
            params={"commit": committed.json()["commit"]},
        )
        pushed = client.post(
            "/v1/sessions/session-ship/git/push",
            headers=AUTH,
            json={"remote": "origin", "set_upstream": False},
        )

    assert staged.status_code == 200
    assert committed.status_code == 200
    assert committed.json()["ok"] is True
    log_body = log.json()
    assert log_body["ok"] is True
    assert [entry["subject"] for entry in log_body["commits"]] == [
        "Ship session change"
    ]
    assert graph.json()["ok"] is True
    assert "Ship session change" in graph.json()["graph"]
    assert per_commit.status_code == 200
    assert "+session edit" in per_commit.json()["diff"]

    assert pushed.status_code == 200
    assert pushed.json()["ok"] is True
    # Remote ref advances to the session HEAD.
    remote_ref = subprocess.run(
        [
            "git",
            "-C",
            str(bare),
            "rev-parse",
            "refs/heads/" + record.session_branch,
        ],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    assert remote_ref.returncode == 0
    session_head = subprocess.run(
        [
            "git",
            "-C",
            str(record.worktree_path),
            "rev-parse",
            "HEAD",
        ],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    assert remote_ref.stdout.strip() == session_head.stdout.strip()

    # Audit ledger recorded the push.
    events = services.audit.list(domain="git")
    assert [event["action"] for event in events] == ["push"]
    assert events[0]["subject"] == record.session_branch
    assert services.audit.verify_chain() is True


@pytest.mark.skipif(
    platform.system() == "Windows",
    reason="requires SIGSTOP/SIGKILL process semantics",
)
def test_sigkill_during_plan_wait_resurfaces_without_replay(tmp_path):
    """A plan awaiting decision survives a real SIGKILL and re-surfaces."""

    class PlanRecoveryProvider(ProviderClient):
        def __init__(self):
            self.calls = 0

        def complete(self, **_kwargs):
            self.calls += 1
            if self.calls == 1:
                return AssistantTurn(
                    tool_calls=[
                        ToolCall(
                            "provider/plan-crash-window",
                            "propose_plan",
                            {"plan": "1. Inspect\n2. Implement"},
                        )
                    ]
                )
            return AssistantTurn(text="plan recovery complete")

        def capabilities(self, _model):
            return ModelCapabilities()

    workspace = tmp_path / "workspace"
    workspace.mkdir()
    data_dir = tmp_path / "data"
    ready = tmp_path / "plan-checkpoint.txt"
    _kill_crash_worker_at_durable_window(
        mode="plan",
        data_dir=data_dir,
        workspace=workspace,
        ready=ready,
    )

    provider = PlanRecoveryProvider()
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
            "/v1/sessions/session-kill/interactions",
            headers=AUTH,
        )

    plan_pending = [
        item for item in pending.json() if item.get("kind") == "plan"
    ]
    # The plan re-surfaced after restart. The resume re-emits the pending
    # propose_plan (parks again in AWAITING) without calling the provider
    # again — no completed tool call is replayed.
    assert plan_pending
    assert provider.calls == 0


@pytest.mark.skipif(
    platform.system() == "Windows",
    reason="requires SIGSTOP/SIGKILL process semantics",
)
def test_sigkill_during_shell_execution_abandons_call_without_replay(
    tmp_path,
):
    """An in-flight run_shell is abandoned on resume; never replayed."""

    class ShellRecoveryProvider(ProviderClient):
        def __init__(self):
            self.calls = 0

        def complete(self, **_kwargs):
            self.calls += 1
            return AssistantTurn(text="shell recovery complete")

        def capabilities(self, _model):
            return ModelCapabilities()

    workspace = tmp_path / "workspace"
    workspace.mkdir()
    data_dir = tmp_path / "data"
    ready = tmp_path / "shell-checkpoint.txt"
    _kill_crash_worker_at_durable_window(
        mode="shell",
        data_dir=data_dir,
        workspace=workspace,
        ready=ready,
    )

    provider = ShellRecoveryProvider()
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

    # The shell call was abandoned (never replayed); the turn recovered and
    # completed with the recovery provider answering once.
    assert provider.calls == 1
    recovered = ConversationStore(data_dir).load("session-kill")
    assert recovered is not None
    assert recovered.turn_checkpoint == TurnCheckpoint()
    tool_messages = [
        m for m in recovered.messages if m.get("role") == "tool"
    ]
    assert tool_messages
    # The abandoned call's result records the unknown outcome.
    assert any(
        "unknown" in str(m.get("content", "")).lower()
        or "interrupted" in str(m.get("content", "")).lower()
        for m in tool_messages
    )


def test_apply_back_crash_reconciles_stale_merge_on_restart(tmp_path):
    """A crashed apply_back leaves a stale MERGE_HEAD; boot reconcile cleans it."""
    import subprocess

    from runtime.git import GitWorktreeService, WorktreeState

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
    subprocess.run(["git", "-C", str(source), "add", "tracked.txt"], check=True)
    subprocess.run(
        ["git", "-C", str(source), "commit", "-m", "base"],
        check=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    data_dir = tmp_path / "data"
    service = GitWorktreeService(data_dir)
    record = service.prepare("crashed-apply", source)
    # Simulate a commit on the session branch.
    (record.worktree_path / "tracked.txt").write_text(
        "session edit\n", encoding="utf-8"
    )
    service.stage("crashed-apply", "tracked.txt")
    service.commit("crashed-apply", "session change")
    session_tip = subprocess.run(
        ["git", "-C", str(record.worktree_path), "rev-parse", "HEAD"],
        stdout=subprocess.PIPE,
        text=True,
        check=True,
    ).stdout.strip()
    # Simulate a crash mid-merge by leaving a stale MERGE_HEAD in source.
    (source / ".git" / "MERGE_HEAD").write_text(
        f"{session_tip}\n", encoding="utf-8"
    )

    # Boot reconcile (run via lifespan in production; called directly here).
    recovered = service.reconcile_crashed_applies()

    assert recovered == 1
    assert not (source / ".git" / "MERGE_HEAD").exists()
    final = service.load("crashed-apply")
    assert final.state is WorktreeState.CONFLICT


def test_selective_apply_e2e_applies_only_chosen_files(tmp_path):
    import subprocess

    from runtime.git import WorktreeState

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
    (source / "base.txt").write_text("base\n", encoding="utf-8")
    subprocess.run(["git", "-C", str(source), "add", "base.txt"], check=True)
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
    services = build_services(config)
    record = services.git.prepare("session-selective", source)
    # Three file changes on the session branch.
    (Path(record.worktree_path) / "base.txt").write_text(
        "edited\n", encoding="utf-8"
    )
    (Path(record.worktree_path) / "alpha.txt").write_text("a\n", encoding="utf-8")
    (Path(record.worktree_path) / "beta.txt").write_text("b\n", encoding="utf-8")
    services.git.stage("session-selective", ".")
    services.git.commit("session-selective", "three files")
    source_head_before = subprocess.run(
        ["git", "-C", str(source), "rev-parse", "HEAD"],
        stdout=subprocess.PIPE,
        text=True,
        check=True,
    ).stdout.strip()

    with TestClient(
        create_control_plane_app(token=TOKEN, services=services)
    ) as client:
        listed = client.get(
            "/v1/sessions/session-selective/git/files",
            headers=AUTH,
        )
        applied = client.post(
            "/v1/sessions/session-selective/git/apply",
            headers=AUTH,
            json={"paths": ["alpha.txt", "beta.txt"]},
        )
        final_record = services.git.load("session-selective")

    assert listed.status_code == 200
    assert {f["path"] for f in listed.json()["files"]} == {
        "base.txt",
        "alpha.txt",
        "beta.txt",
    }
    assert applied.status_code == 200
    body = applied.json()
    assert body["strategy"] == "selective"
    assert set(body["files"]) == {"alpha.txt", "beta.txt"}
    # Selected files landed on source.
    assert (source / "alpha.txt").read_text(encoding="utf-8") == "a\n"
    assert (source / "beta.txt").read_text(encoding="utf-8") == "b\n"
    # Non-selected file unchanged on source.
    assert (source / "base.txt").read_text(encoding="utf-8") == "base\n"
    # Source advanced by exactly one commit.
    source_head_after = subprocess.run(
        ["git", "-C", str(source), "rev-parse", "HEAD"],
        stdout=subprocess.PIPE,
        text=True,
        check=True,
    ).stdout.strip()
    assert source_head_after != source_head_before
    assert final_record.state is WorktreeState.APPLIED
