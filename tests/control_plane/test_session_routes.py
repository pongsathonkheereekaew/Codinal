import asyncio
import hashlib
import threading
from typing import Any
from types import SimpleNamespace

import httpx
from fastapi.testclient import TestClient

from runtime.control_plane import create_control_plane_app
from runtime.events import EventHub
from runtime.oauth import OAuthCoordinator
from runtime.secrets import ProviderSecretService
from runtime.policy import (
    ApprovalOutcome,
    ApprovalPersistenceError,
    Decision,
)
from runtime.storage import ExportTooLargeError
from runtime.turns import ExportBusyError, SessionBusyError
from runtime.sandbox import InvalidCommandError, SandboxUnavailableError


TOKEN = "test-session-token-with-at-least-32-characters"
AUTH = {"Authorization": f"Bearer {TOKEN}"}


class FakeSettings:
    def __init__(self):
        self.routing_profile = "manual"
        self.stirling_url = None

    def view(self):
        return {
            "model": "openai:gpt-test",
            "routing_profile": self.routing_profile,
            "stirling_url": self.stirling_url,
        }

    def set_routing_profile(self, profile):
        if profile not in {"manual", "quality", "balanced", "economy"}:
            return {"ok": False, "error": "invalid routing profile"}
        self.routing_profile = profile
        return {"ok": True, "routing_profile": profile}

    def set_stirling_url(self, url):
        if url != "http://localhost:8080":
            return {"ok": False, "error": "invalid Stirling URL"}
        self.stirling_url = url
        return {"ok": True, "stirling_url": url}

    def add_models(self, models):
        return {"ok": True, "models": list(models)}


class FakeRouting:
    def __init__(self):
        self.resolved = []

    def view(self, profile):
        return {
            "profile": profile,
            "profiles": [{"id": "manual"}, {"id": "balanced"}],
            "models": [],
        }

    def resolve(
        self,
        profile,
        *,
        preferred_model,
        user_input,
        required_capabilities=(),
    ):
        self.resolved.append(
            (
                profile,
                preferred_model,
                user_input,
                list(required_capabilities),
            )
        )
        return {
            "profile": profile,
            "selected_model": "gemini:gemini-2.5-flash",
            "provider": "gemini",
            "cost_class": "economy",
            "configured": True,
            "required_capabilities": ["tools"],
            "degradations": [],
            "reason": "balanced selected configured gemini",
        }


class FakeGit:
    def __init__(self):
        self.context_roots = []

    def close(self):
        return None

    def load(self, session_id):
        return {"session_id": session_id}

    def status(self, _session_id):
        return {
            "ok": True,
            "branch": "codinal/session-1",
            "base_commit": "abc123",
            "clean": False,
            "porcelain": " M src/main.py\n",
            "output_truncated": False,
        }

    def diff(self, _session_id, **_options):
        return {
            "ok": True,
            "diff": "diff --git a/src/main.py b/src/main.py\n+change\n",
            "output_truncated": False,
        }

    def apply_selected(self, _session_id, paths):
        return {
            "ok": True,
            "strategy": "selective",
            "files": list(paths),
            "commit": "deadbeef",
        }

    def changed_files(self, _session_id):
        return {
            "ok": True,
            "files": [
                {"path": "src/main.py", "status": "modified"},
                {"path": "src/new.py", "status": "added"},
            ],
        }

    def stage(self, _session_id, path="."):
        return {"ok": True, "path": path}

    def apply_back(self, _session_id):
        return {"ok": True, "strategy": "fast-forward", "commit": "deadbeef"}

    def commit(self, _session_id, message):
        return {
            "ok": True,
            "commit": "deadbeef" * 5,
            "branch": "codinal/session-1",
        }

    def log(self, _session_id, *, limit=50):
        return {
            "ok": True,
            "branch": "codinal/session-1",
            "base_commit": "abc123",
            "head_commit": "deadbeef" * 5,
            "commits": [
                {
                    "sha": "deadbeef" * 5,
                    "parents": ["abc123"],
                    "author": "Codinal Test",
                    "email": "codinal@example.invalid",
                    "date": "2026-07-27T00:00:00+00:00",
                    "subject": "Apply change",
                }
            ],
            "output_truncated": False,
        }

    def graph(self, _session_id, *, limit=50):
        return {
            "ok": True,
            "branch": "codinal/session-1",
            "base_commit": "abc123",
            "graph": "* deadbeef (HEAD) Apply change\n",
            "commits": [
                {
                    "sha": "deadbeef" * 5,
                    "parents": [],
                    "author": "Codinal Test",
                    "email": "codinal@example.invalid",
                    "date": "2026-07-27T00:00:00+00:00",
                    "subject": "Apply change",
                }
            ],
            "output_truncated": False,
        }

    def push(self, _session_id, *, remote="origin", set_upstream=False):
        return {
            "ok": True,
            "remote": remote,
            "branch": "codinal/session-1",
            "summary": "To refs/heads/codinal/session-1\n",
        }

    def context_snapshot(self, _session_id, *, root, expected_identity):
        self.context_roots.append(root)
        return {
            "ok": True,
            "content": (
                "branch: codinal/session-1\n"
                "base_commit: abc123\n\n"
                "status:\n M src/main.py\n\n"
                "unstaged diff:\n"
                "diff --git a/src/main.py b/src/main.py\n+change\n"
            ),
            "truncated": False,
            "root": root,
            "expected_identity": expected_identity,
        }


class FakeTurns:
    def __init__(self):
        self.active = set()
        self.restore_pending = set()
        self.started = []

    async def recover(self):
        return 0

    async def shutdown(self):
        return None

    def interrupt(self, _session_id):
        return False

    def is_active(self, session_id):
        return session_id in self.active

    async def start(self, session_id, **options):
        resolver = options.pop("user_input_resolver", None)
        if resolver is not None:
            options["user_input"] = await resolver()
        self.started.append((session_id, options))
        return {"ok": True, "session_id": session_id}

    async def export_when_idle(self, exporter):
        if self.active:
            raise ExportBusyError("active turn")
        return exporter()

    async def mutate_when_idle(self, session_id, mutation):
        if session_id in self.active:
            raise SessionBusyError("session already has an active turn")
        if session_id in self.restore_pending:
            raise SessionBusyError(
                "session has a pending checkpoint restore"
            )
        return mutation()


class FakeShellResult(dict):
    def __init__(self, values: dict[str, object]):
        self._values = values

    def as_dict(self) -> dict[str, object]:
        return dict(self._values)


class FakeShell:
    def __init__(
        self,
        result: object | None = None,
        error: Exception | None = None,
        interrupted: bool = True,
    ):
        self.calls: list[tuple[str, float | None]] = []
        self.interrupted = interrupted
        self.interrupt_calls: list[str] = []
        self.result = (
            result
            if result is not None
            else FakeShellResult({"exit_code": 0, "stdout": "ok"})
        )
        self.error = error

    def run(self, command: str, *, timeout_seconds: float | None = None):
        self.calls.append((command, timeout_seconds))
        if self.error is not None:
            raise self.error
        return self.result

    def interrupt(self):
        self.interrupt_calls.append("called")
        return self.interrupted


class FakeLegacyShell:
    def __init__(self, result: object | None = None, error: Exception | None = None):
        self.calls: list[tuple[str, float | None]] = []
        self.result = (
            result
            if result is not None
            else FakeShellResult({"exit_code": 0, "stdout": "ok"})
        )
        self.error = error

    def run(self, command: str, *, timeout_seconds: float | None = None):
        self.calls.append((command, timeout_seconds))
        if self.error is not None:
            raise self.error
        return self.result


class FakePermissions:
    def __init__(self, decision: Decision):
        self.decision = decision
        self.allowed = []

    def evaluate(self, tool_name: str, arguments: dict[str, object]):
        self.last_tool = (tool_name, arguments)
        return self.decision

    def allow_command_for_session(self, command: str) -> None:
        self.allowed.append(command)


class FakeEngine:
    def __init__(self, shell: object, permissions: FakePermissions):
        self._terminal_shell = shell
        self.permissions = permissions


class FakeTerminalSessions:
    def __init__(self):
        self._engine: FakeEngine | None = None
        self.get_engine_calls: list[str] = []

    def set_engine(self, engine: FakeEngine | None) -> None:
        self._engine = engine

    def get_engine(
        self,
        session_id: str,
        *,
        workspace: str | None = None,
        agent: str = "code",
        mode: str | None = None,
        model: str | None = None,
    ):
        self.get_engine_calls.append(session_id)
        return self._engine


class FakeApprovalBroker:
    def __init__(self, outcome: ApprovalOutcome | Exception):
        self.outcome = outcome
        self.calls = []

    def approver(self, session_id: str):
        async def _approve(request):
            self.calls.append((session_id, request))
            if isinstance(self.outcome, Exception):
                raise self.outcome
            return self.outcome

        return _approve


class FakeSessions:
    def __init__(self):
        self.renamed = []
        self.flags = []
        self.models = []
        self.deleted = []
        self.forked = []
        self.artifacts_listed = []
        self.artifact_reads = []
        self.artifact_reveals = []
        self.side_conversations = []
        self.added_roots = []
        self.removed_roots = []
        self.opened_project_paths = []
        self.cancelled_project_searches = []
        self.workspace_file_indexes = []
        self.rebuilt_project_indexes = []
        self.cleared_project_indexes = []
        self.export_too_large = False
        self.routing_context_calls = []

    def list_sessions(self, *, workspace=None):
        return [
            {
                "session_id": "session-1",
                "title": "Inspect runtime",
                "workspace": workspace or "/tmp/project",
            }
        ]

    def messages(self, session_id):
        return [{"role": "user", "content": session_id}]

    def selected_model(self, _session_id):
        return "openai:gpt-session"

    def routing_requirements(self, _session_id):
        return ["tools"]

    def routing_context(self, session_id):
        self.routing_context_calls.append(session_id)
        return {
            "model": self.selected_model(session_id),
            "required_capabilities": self.routing_requirements(session_id),
        }

    def search_sessions(self, query, *, limit):
        return [
            {
                "session_id": "session-1",
                "title": "Inspect runtime",
                "workspace": "/tmp/project",
                "match_excerpt": f"{query}:{limit}",
                "match_message_index": 0,
            }
        ]

    def roots(self, _session_id):
        return [{"path": "/tmp/project", "writable": True, "primary": True}]

    def tree(self, session_id, *, root, path, limit):
        return {
            "ok": True,
            "root": root,
            "path": path,
            "entries": [
                {"name": session_id, "path": session_id, "kind": "file"}
            ][:limit],
            "truncated": False,
        }

    def project_search(self, session_id, *, query, mode, limit):
        return {
            "ok": True,
            "query": query,
            "mode": mode,
            "count": 1,
            "matches": [
                {
                    "root": "/tmp/project",
                    "root_label": "project",
                    "path": "src/main.py",
                    "line": 7,
                    "column": 5,
                    "text": f"{session_id}:{query}",
                }
            ][:limit],
            "files_scanned": 1,
            "duration_ms": 1,
            "truncated": False,
        }

    def workspace_files(self, session_id, *, limit):
        self.workspace_file_indexes.append((session_id, limit))
        return {
            "ok": True,
            "root": "/tmp/project",
            "paths": ["README.md", "src/main.py"][:limit],
            "truncated": False,
        }

    def cancel_project_search(self, session_id):
        self.cancelled_project_searches.append(session_id)
        return True

    def project_index_status(self, _session_id):
        return {
            "ok": True,
            "schema_version": 1,
            "state": "ready",
            "roots": [
                {
                    "root": "/tmp/project",
                    "state": "ready",
                    "files": 7,
                    "chunks": 12,
                    "truncated": False,
                }
            ],
        }

    def rebuild_project_index(self, session_id):
        self.rebuilt_project_indexes.append(session_id)
        return {
            "ok": True,
            "indexed_roots": 1,
            "indexed_files": 7,
            "indexed_chunks": 12,
            "truncated": False,
        }

    def clear_project_index(self, session_id):
        self.cleared_project_indexes.append(session_id)
        return {
            "ok": True,
            "deleted_roots": 1,
            "deleted_chunks": 12,
        }

    def add_root(self, session_id, path, *, writable=False):
        self.added_roots.append((session_id, path, writable))
        return {"ok": True, "roots": self.roots(session_id)}

    def remove_root(self, session_id, path):
        self.removed_roots.append((session_id, path))
        return {"ok": True, "roots": self.roots(session_id)}

    def project_context(self, session_id, *, root, path, kind):
        text = f"context:{kind}:{root}:{path}"
        return {
            "ok": True,
            "item": {
                "kind": kind,
                "root": root,
                "path": path,
                "label": f"{session_id}/{path}",
                "truncated": False,
                "fingerprint": hashlib.sha256(
                    text.encode("utf-8")
                ).hexdigest(),
                "content_part": {"type": "text", "text": text},
            },
        }

    def open_project_path(self, session_id, *, root, path, mode):
        self.opened_project_paths.append(
            (session_id, root, path, mode)
        )
        return {"ok": True}

    def project_root_identity(self, _session_id, _root):
        return (17, 23)

    def list_artifacts(self, session_id: str) -> list[dict[str, Any]]:
        self.artifacts_listed.append(session_id)
        return [
            {
                "path": "notes.md",
                "abs_path": "/tmp/project/notes.md",
                "name": "notes.md",
                "kind": "markdown",
                "size": 24,
                "modified_at": 1_700_000_000.0,
            }
        ]

    def read_artifact(self, session_id: str, path: str) -> dict[str, Any]:
        self.artifact_reads.append((session_id, path))
        if path == "notes.md":
            return {
                "ok": True,
                "path": path,
                "kind": "markdown",
                "content": "# Notes\n\nalpha\n",
                "truncated": False,
            }
        return {"ok": False, "error": "not found"}

    def reveal_artifact(
        self,
        session_id: str,
        path: str,
        *,
        mode: str = "reveal",
    ) -> dict[str, Any]:
        self.artifact_reveals.append((session_id, path, mode))
        if path == "notes.md":
            return {"ok": True}
        return {"ok": False, "error": "not found"}

    def rename(self, session_id, title):
        self.renamed.append((session_id, title))
        return {"ok": True, "session_id": session_id, "title": title}

    def set_flags(self, session_id, *, pinned=None, archived=None):
        self.flags.append((session_id, pinned, archived))
        return {"ok": True, "session_id": session_id}

    def set_model(self, session_id, model):
        self.models.append((session_id, model))
        return {"ok": True, "session_id": session_id, "model": model}

    def delete(self, session_id):
        self.deleted.append(session_id)
        return {"ok": True, "session_id": session_id}

    def fork(self, session_id, *, message_index):
        self.forked.append((session_id, message_index))
        return {
            "ok": True,
            "session_id": "session-fork",
            "source_session_id": session_id,
            "message_count": message_index + 1,
        }

    def side_conversation(self, session_id, *, message_index):
        self.side_conversations.append((session_id, message_index))
        return {
            "ok": True,
            "session_id": "session-side",
            "source_session_id": session_id,
            "message_count": message_index + 1,
            "session": {
                "session_id": "session-side",
                "origin": "side_conversation",
                "origin_session_id": session_id,
            },
        }

    def export_markdown(self, session_id):
        return {
            "ok": True,
            "filename": "inspect-runtime.md",
            "content": f"# Inspect runtime\n\n{session_id}\n",
        }

    def export(self):
        if self.export_too_large:
            raise ExportTooLargeError("too large")
        return {
            "export_version": 1,
            "sessions": [
                {
                    "session_id": "session-1",
                    "messages": [
                        {"role": "user", "content": "preserved"}
                    ],
                }
            ],
        }


def make_client(
    *,
    git=None,
    routing=None,
    turns: FakeTurns | None = None,
    sessions: FakeSessions | FakeTerminalSessions | None = None,
    approvals=None,
):
    if turns is None:
        turns = FakeTurns()
    if sessions is None:
        sessions = FakeSessions()
    services = SimpleNamespace(
        events=EventHub(),
        settings=FakeSettings(),
        routing=routing,
        secrets=ProviderSecretService(),
        oauth=OAuthCoordinator(),
        turns=turns,
        sessions=sessions,
        approvals=approvals,
        mcp=None,
        git=git,
        audit=None,
    )
    return (
        TestClient(create_control_plane_app(token=TOKEN, services=services)),
        sessions,
        turns,
    )


def test_settings_expose_and_persist_transparent_routing_profile():
    routing = FakeRouting()
    client, _sessions, _turns = make_client(routing=routing)

    with client:
        initial = client.get("/v1/settings", headers=AUTH)
        updated = client.patch(
            "/v1/settings/routing",
            headers=AUTH,
            json={"profile": "balanced"},
        )
        invalid = client.patch(
            "/v1/settings/routing",
            headers=AUTH,
            json={"profile": "hidden"},
        )

    assert initial.json()["routing"]["profile"] == "manual"
    assert updated.json()["routing"]["profile"] == "balanced"
    assert invalid.status_code == 400


def test_settings_refreshes_discovered_loopback_ollama_models(monkeypatch):
    client, _sessions, _turns = make_client()
    monkeypatch.setattr(
        "runtime.control_plane.app.discover_ollama_models",
        lambda: {
            "available": True,
            "models": ["ollama:qwen3:8b", "ollama:llama3.2"],
        },
    )

    with client:
        response = client.post("/v1/settings/ollama/refresh", headers=AUTH)

    assert response.status_code == 200
    assert response.json() == {
        "available": True,
        "models": ["ollama:qwen3:8b", "ollama:llama3.2"],
    }


def test_settings_accept_stirling_url_only_through_validated_route():
    client, _sessions, _turns = make_client()

    with client:
        configured = client.patch(
            "/v1/settings/stirling",
            headers=AUTH,
            json={"url": "http://localhost:8080"},
        )
        invalid = client.patch(
            "/v1/settings/stirling",
            headers=AUTH,
            json={"url": "https://example.com"},
        )
        malformed = client.patch(
            "/v1/settings/stirling",
            headers=AUTH,
            json={"url": "http://localhost:8080", "extra": True},
        )

    assert configured.json() == {
        "ok": True,
        "stirling_url": "http://localhost:8080",
    }
    assert invalid.status_code == 400
    assert malformed.status_code == 400


def test_stirling_health_uses_the_saved_local_endpoint(monkeypatch):
    monkeypatch.setattr(
        "runtime.control_plane.app.check_stirling_health",
        lambda url: {"ok": True, "version": "1.2.3"}
        if url == "http://localhost:8080"
        else {"ok": False, "version": None},
    )
    client, _sessions, _turns = make_client()

    with client:
        unconfigured = client.post("/v1/settings/stirling/health", headers=AUTH)
        client.patch(
            "/v1/settings/stirling",
            headers=AUTH,
            json={"url": "http://localhost:8080"},
        )
        healthy = client.post("/v1/settings/stirling/health", headers=AUTH)

    assert unconfigured.status_code == 400
    assert healthy.json() == {"ok": True, "version": "1.2.3"}


def test_turn_routing_returns_exact_resolution_and_uses_selected_model():
    routing = FakeRouting()
    client, _sessions, turns = make_client(routing=routing)

    with client:
        response = client.post(
            "/v1/sessions/session-1/turns",
            headers=AUTH,
            json={
                "input": "Build it",
                "model": "openai:gpt-test",
                "routing_profile": "balanced",
            },
        )

    assert response.status_code == 202
    assert response.json()["routing"]["provider"] == "gemini"
    assert turns.started[0][1]["model"] == "gemini:gemini-2.5-flash"
    assert routing.resolved == [
        ("balanced", "openai:gpt-test", "Build it", ["tools"])
    ]
    assert turns.started[0][1]["source"]["routing"]["provider"] == "gemini"


def test_persisted_auto_profile_routes_turn_without_request_overrides():
    routing = FakeRouting()
    client, _sessions, turns = make_client(routing=routing)

    with client:
        configured = client.patch(
            "/v1/settings/routing",
            headers=AUTH,
            json={"profile": "economy"},
        )
        response = client.post(
            "/v1/sessions/session-1/turns",
            headers=AUTH,
            json={"input": "Continue"},
        )

    assert configured.status_code == 200
    assert response.status_code == 202
    assert response.json()["routing"]["profile"] == "economy"
    assert routing.resolved == [
        ("economy", "openai:gpt-session", "Continue", ["tools"])
    ]
    assert turns.started[0][1]["model"] == "gemini:gemini-2.5-flash"


def test_cold_routing_context_does_not_block_control_plane_health():
    started = threading.Event()
    release = threading.Event()

    class SlowSessions(FakeSessions):
        def routing_context(self, session_id):
            started.set()
            release.wait(timeout=2)
            return super().routing_context(session_id)

    turns = FakeTurns()
    sessions = SlowSessions()
    services = SimpleNamespace(
        events=EventHub(),
        settings=FakeSettings(),
        routing=FakeRouting(),
        secrets=ProviderSecretService(),
        oauth=OAuthCoordinator(),
        turns=turns,
        sessions=sessions,
        approvals=None,
        mcp=None,
        git=None,
    )
    app = create_control_plane_app(token=TOKEN, services=services)

    async def scenario():
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(
            transport=transport,
            base_url="http://test",
        ) as client:
            turn = asyncio.create_task(
                client.post(
                    "/v1/sessions/session-1/turns",
                    headers=AUTH,
                    json={"input": "Continue"},
                )
            )
            assert await asyncio.to_thread(started.wait, 1)
            health = await asyncio.wait_for(
                client.get("/v1/health", headers=AUTH),
                timeout=0.5,
            )
            release.set()
            return health, await turn

    try:
        health, turn = asyncio.run(scenario())
    finally:
        release.set()

    assert health.status_code == 200
    assert turn.status_code == 202
    assert sessions.routing_context_calls == ["session-1"]


def test_default_manual_turn_overwrites_untrusted_routing_source():
    routing = FakeRouting()
    client, _sessions, turns = make_client(routing=routing)

    with client:
        response = client.post(
            "/v1/sessions/session-1/turns",
            headers=AUTH,
            json={
                "input": "Inspect",
                "source": {
                    "routing": {
                        "selected_model": "attacker:spoofed",
                    }
                },
            },
        )

    assert response.status_code == 202
    assert routing.resolved == [
        ("manual", "openai:gpt-session", "Inspect", ["tools"])
    ]
    assert turns.started[0][1]["source"]["routing"] == (
        response.json()["routing"]
    )


def test_client_routing_source_is_reserved_without_routing_service():
    client, _sessions, turns = make_client(routing=None)

    with client:
        response = client.post(
            "/v1/sessions/session-1/turns",
            headers=AUTH,
            json={
                "input": "Inspect",
                "source": {
                    "routing": {
                        "selected_model": "attacker:spoofed",
                    }
                },
            },
        )

    assert response.status_code == 202
    assert turns.started[0][1]["source"] is None


def test_versioned_export_is_authenticated_and_consistent():
    client, sessions, turns = make_client()

    unauthorized = client.get("/v1/data/export")
    response = client.get("/v1/data/export", headers=AUTH)

    assert unauthorized.status_code == 401
    assert response.status_code == 200
    assert response.headers["content-type"] == "application/json"
    assert response.headers["content-disposition"] == (
        'attachment; filename="codinal-export-v1.json"'
    )
    assert response.headers["cache-control"] == "no-store"
    assert response.json() == sessions.export()

    turns.active.add("session-1")
    busy = client.get("/v1/data/export", headers=AUTH)
    assert busy.status_code == 409
    assert busy.json() == {
        "detail": "cannot export while a turn is active"
    }

    turns.active.clear()
    sessions.export_too_large = True
    too_large = client.get("/v1/data/export", headers=AUTH)
    assert too_large.status_code == 413
    assert too_large.json() == {
        "detail": "conversation export exceeds the 32 MiB safety limit"
    }


def test_session_routes_list_messages_and_roots():
    with make_client()[0] as client:
        listed = client.get(
            "/v1/sessions",
            headers=AUTH,
            params={"workspace": "/tmp/project"},
        )
        messages = client.get(
            "/v1/sessions/session-1/messages",
            headers=AUTH,
        )
        roots = client.get(
            "/v1/sessions/session-1/roots",
            headers=AUTH,
        )

    assert listed.status_code == 200
    assert listed.json()[0]["session_id"] == "session-1"
    assert messages.json() == [
        {"role": "user", "content": "session-1"}
    ]
    assert roots.json()[0]["primary"] is True


def test_session_artifact_routes_are_authenticated_and_bounded():
    client, sessions, _turns = make_client()
    with client:
        unauthorized = client.get("/v1/sessions/session-1/artifacts")
        artifacts = client.get(
            "/v1/sessions/session-1/artifacts",
            headers=AUTH,
        )
        read = client.get(
            "/v1/sessions/session-1/artifacts/read",
            headers=AUTH,
            params={"path": "notes.md"},
        )
        read_unknown = client.get(
            "/v1/sessions/session-1/artifacts/read",
            headers=AUTH,
            params={"path": "does-not-exist.md"},
        )
        read_escape = client.get(
            "/v1/sessions/session-1/artifacts/read",
            headers=AUTH,
            params={"path": "../secret.md"},
        )
        reveal = client.post(
            "/v1/sessions/session-1/artifacts/reveal",
            headers=AUTH,
            json={"path": "notes.md", "mode": "open"},
        )
        reveal_bad = client.post(
            "/v1/sessions/session-1/artifacts/reveal",
            headers=AUTH,
            json={"path": "../secret.md", "mode": "open"},
        )

    assert unauthorized.status_code == 401
    assert artifacts.status_code == 200
    assert artifacts.json()[0]["path"] == "notes.md"
    assert sessions.artifacts_listed == ["session-1"]
    assert read.status_code == 200
    assert read.json()["kind"] == "markdown"
    assert read_unknown.status_code == 404
    assert read_escape.status_code == 400
    assert reveal.status_code == 200
    assert reveal.json() == {"ok": True}
    assert sessions.artifact_reveals == [("session-1", "notes.md", "open")]
    assert reveal_bad.status_code == 400


def test_session_tree_and_root_mutations_are_bounded_and_idle_gated():
    client, sessions, turns = make_client()
    with client:
        tree = client.get(
            "/v1/sessions/session-1/tree",
            headers=AUTH,
            params={
                "root": "/tmp/project",
                "path": "src",
                "limit": 100,
            },
        )
        invalid_tree = client.get(
            "/v1/sessions/session-1/tree",
            headers=AUTH,
            params={"root": "/tmp/project", "path": "../escape"},
        )
        turns.active.add("session-1")
        busy = client.post(
            "/v1/sessions/session-1/roots",
            headers=AUTH,
            json={"path": "/tmp/shared", "writable": False},
        )
        turns.active.clear()
        added = client.post(
            "/v1/sessions/session-1/roots",
            headers=AUTH,
            json={"path": "/tmp/shared", "writable": True},
        )
        removed = client.request(
            "DELETE",
            "/v1/sessions/session-1/roots",
            headers=AUTH,
            json={"path": "/tmp/shared"},
        )

    assert tree.status_code == 200
    assert tree.json()["entries"][0]["name"] == "session-1"
    assert invalid_tree.status_code == 400
    assert busy.status_code == 409
    assert added.status_code == 200
    assert sessions.added_roots == [
        ("session-1", "/tmp/shared", True)
    ]
    assert removed.status_code == 200
    assert sessions.removed_roots == [
        ("session-1", "/tmp/shared")
    ]


def test_project_search_route_is_bounded():
    with make_client()[0] as client:
        searched = client.get(
            "/v1/sessions/session-1/project/search",
            headers=AUTH,
            params={"q": "GoalCoordinator", "mode": "symbol", "limit": 20},
        )
        semantic = client.get(
            "/v1/sessions/session-1/project/search",
            headers=AUTH,
            params={"q": "repair auth", "mode": "semantic", "limit": 20},
        )
        invalid = client.get(
            "/v1/sessions/session-1/project/search",
            headers=AUTH,
            params={"q": "", "mode": "regex", "limit": 101},
        )
        cancelled = client.delete(
            "/v1/sessions/session-1/project/search",
            headers=AUTH,
        )

    assert searched.status_code == 200
    assert semantic.status_code == 200
    assert searched.json()["matches"][0]["line"] == 7
    assert invalid.status_code == 400
    assert cancelled.json() == {"ok": True}


def test_workspace_file_index_is_authenticated_and_bounded():
    client, sessions, _turns = make_client()
    with client:
        unauthorized = client.get("/v1/sessions/session-1/workspace/files")
        indexed = client.get(
            "/v1/sessions/session-1/workspace/files",
            headers=AUTH,
            params={"limit": 20},
        )
        invalid = client.get(
            "/v1/sessions/session-1/workspace/files",
            headers=AUTH,
            params={"limit": 2001},
        )

    assert unauthorized.status_code == 401
    assert indexed.json()["paths"] == ["README.md", "src/main.py"]
    assert invalid.status_code == 400
    assert sessions.workspace_file_indexes == [("session-1", 20)]


def test_semantic_index_lifecycle_routes_are_authenticated():
    client, sessions, _turns = make_client()
    with client:
        unauthorized = client.get(
            "/v1/sessions/session-1/project/index",
        )
        status = client.get(
            "/v1/sessions/session-1/project/index",
            headers=AUTH,
        )
        rebuilt = client.post(
            "/v1/sessions/session-1/project/index",
            headers=AUTH,
        )
        cleared = client.delete(
            "/v1/sessions/session-1/project/index",
            headers=AUTH,
        )

    assert unauthorized.status_code == 401
    assert status.json()["state"] == "ready"
    assert rebuilt.json()["indexed_chunks"] == 12
    assert cleared.json()["deleted_chunks"] == 12
    assert sessions.rebuilt_project_indexes == ["session-1"]
    assert sessions.cleared_project_indexes == ["session-1"]


def test_project_context_is_authenticated_and_open_actions_are_idle_gated():
    client, sessions, turns = make_client()
    descriptor = {
        "kind": "file",
        "root": "/tmp/project",
        "path": "src/main.py",
    }
    with client:
        unauthorized = client.post(
            "/v1/sessions/session-1/context",
            json=descriptor,
        )
        context = client.post(
            "/v1/sessions/session-1/context",
            headers=AUTH,
            json=descriptor,
        )
        turns.active.add("session-1")
        busy = client.post(
            "/v1/sessions/session-1/project/open",
            headers=AUTH,
            json={**descriptor, "mode": "reveal"},
        )
        turns.active.clear()
        opened = client.post(
            "/v1/sessions/session-1/project/open",
            headers=AUTH,
            json={**descriptor, "mode": "open"},
        )

    assert unauthorized.status_code == 401
    assert context.status_code == 200
    assert context.json()["item"]["label"] == "session-1/src/main.py"
    assert busy.status_code == 409
    assert opened.status_code == 200
    assert sessions.opened_project_paths == [
        ("session-1", "/tmp/project", "src/main.py", "open")
    ]


def test_turn_revalidates_context_fingerprint_and_sends_exact_resolved_part():
    client, _sessions, turns = make_client()
    descriptor = {
        "kind": "file",
        "root": "/tmp/project",
        "path": "src/main.py",
    }
    with client:
        selected = client.post(
            "/v1/sessions/session-1/context",
            headers=AUTH,
            json=descriptor,
        )
        item = selected.json()["item"]
        started = client.post(
            "/v1/sessions/session-1/turns",
            headers=AUTH,
            json={
                "input": "Fix it",
                "workspace": "/tmp/project",
                "context": [
                    {
                        **descriptor,
                        "fingerprint": item["fingerprint"],
                    }
                ],
            },
        )
        stale = client.post(
            "/v1/sessions/session-1/turns",
            headers=AUTH,
            json={
                "input": "Do not send",
                "context": [{**descriptor, "fingerprint": "0" * 64}],
            },
        )

    assert started.status_code == 202
    assert turns.started[0][1]["user_input"] == [
        item["content_part"],
        {"type": "text", "text": "Fix it"},
    ]
    assert stale.status_code == 409
    assert stale.json() == {
        "detail": "project context changed; refresh it before sending"
    }
    assert len(turns.started) == 1


def test_git_context_snapshot_is_exactly_the_part_sent_to_provider():
    client, _sessions, turns = make_client(git=FakeGit())
    descriptor = {
        "kind": "git",
        "root": "/tmp/project",
        "path": "",
    }
    with client:
        selected = client.post(
            "/v1/sessions/session-1/context",
            headers=AUTH,
            json=descriptor,
        )
        item = selected.json()["item"]
        started = client.post(
            "/v1/sessions/session-1/turns",
            headers=AUTH,
            json={
                "input": "Review these changes",
                "context": [
                    {
                        **descriptor,
                        "fingerprint": item["fingerprint"],
                    }
                ],
            },
        )

    assert selected.status_code == 200
    assert item["kind"] == "git"
    assert " M src/main.py" in item["content_part"]["text"]
    assert "diff --git a/src/main.py" in item["content_part"]["text"]
    assert started.status_code == 202
    assert turns.started[0][1]["user_input"][0] == item["content_part"]


def test_git_context_accepts_an_available_additional_root():
    git = FakeGit()
    client, sessions, _turns = make_client(git=git)
    sessions.roots = lambda _session_id: [
        {
            "path": "/tmp/project",
            "writable": True,
            "primary": True,
        },
        {
            "path": "/tmp/shared-repo",
            "label": "shared-repo",
            "writable": False,
            "primary": False,
            "available": True,
        },
    ]
    descriptor = {
        "kind": "git",
        "root": "/tmp/shared-repo",
        "path": "",
    }

    with client:
        selected = client.post(
            "/v1/sessions/session-1/context",
            headers=AUTH,
            json=descriptor,
        )

    assert selected.status_code == 200
    assert selected.json()["item"]["label"] == "shared-repo · Git changes"
    assert git.context_roots == ["/tmp/shared-repo"]


def test_session_search_is_authenticated_and_bounded():
    client, sessions, _ = make_client()
    with client:
        unauthorized = client.get(
            "/v1/sessions/search",
            params={"q": "runtime"},
        )
        found = client.get(
            "/v1/sessions/search",
            headers=AUTH,
            params={"q": "runtime", "limit": 25},
        )
        empty = client.get(
            "/v1/sessions/search",
            headers=AUTH,
            params={"q": ""},
        )
        too_long = client.get(
            "/v1/sessions/search",
            headers=AUTH,
            params={"q": "x" * 257},
        )
        too_many = client.get(
            "/v1/sessions/search",
            headers=AUTH,
            params={"q": "runtime", "limit": 101},
        )

    assert unauthorized.status_code == 401
    assert found.status_code == 200
    assert found.json()[0]["match_excerpt"] == "runtime:25"
    assert empty.status_code == 400
    assert too_long.status_code == 400
    assert too_many.status_code == 400


def test_session_search_offloads_synchronous_storage(monkeypatch):
    client, _sessions, _ = make_client()
    calls = []

    async def offload(function, *args, **kwargs):
        calls.append((function.__name__, args, kwargs))
        return function(*args, **kwargs)

    monkeypatch.setattr("runtime.control_plane.app.asyncio.to_thread", offload)
    with client:
        response = client.get(
            "/v1/sessions/search",
            headers=AUTH,
            params={"q": "runtime", "limit": 12},
        )

    assert response.status_code == 200
    assert calls == [
        ("search_sessions", ("runtime",), {"limit": 12})
    ]


def test_session_fork_refuses_active_turn_then_forks_selected_history():
    client, sessions, turns = make_client()
    turns.active.add("session-1")
    with client:
        busy = client.post(
            "/v1/sessions/session-1/fork",
            headers=AUTH,
            json={"message_index": 3},
        )
        turns.active.clear()
        forked = client.post(
            "/v1/sessions/session-1/fork",
            headers=AUTH,
            json={"message_index": 3},
        )
        invalid = client.post(
            "/v1/sessions/session-1/fork",
            headers=AUTH,
            json={"message_index": True},
        )
        oversized = client.post(
            "/v1/sessions/session-1/fork",
            headers=AUTH,
            content=b"{" + (b"x" * 1024) + b"}",
        )

    assert busy.status_code == 409
    assert forked.status_code == 200
    assert forked.json()["session_id"] == "session-fork"
    assert sessions.forked == [("session-1", 3)]
    assert invalid.status_code == 400
    assert oversized.status_code == 400


def test_session_markdown_export_is_authenticated_and_not_cached():
    with make_client()[0] as client:
        unauthorized = client.get("/v1/sessions/session-1/export.md")
        exported = client.get(
            "/v1/sessions/session-1/export.md",
            headers=AUTH,
        )

    assert unauthorized.status_code == 401
    assert exported.status_code == 200
    assert exported.headers["content-type"].startswith("text/markdown")
    assert exported.headers["cache-control"] == "no-store"
    assert exported.headers["content-disposition"] == (
        'attachment; filename="inspect-runtime.md"'
    )
    assert exported.text == "# Inspect runtime\n\nsession-1\n"


def test_side_conversation_refuses_active_turn_then_branches_history():
    client, sessions, turns = make_client()
    turns.active.add("session-1")
    with client:
        busy = client.post(
            "/v1/sessions/session-1/side-conversations",
            headers=AUTH,
            json={"message_index": 1},
        )
        turns.active.clear()
        created = client.post(
            "/v1/sessions/session-1/side-conversations",
            headers=AUTH,
            json={"message_index": 1},
        )

    assert busy.status_code == 409
    assert created.status_code == 200
    assert created.json()["session"]["origin"] == "side_conversation"
    assert created.json()["session"]["origin_session_id"] == "session-1"
    assert sessions.side_conversations == [("session-1", 1)]


def test_session_patch_is_strict_and_delegates_metadata_changes():
    client, sessions, _ = make_client()
    with client:
        renamed = client.patch(
            "/v1/sessions/session-1",
            headers=AUTH,
            json={"title": "  New title  "},
        )
        flagged = client.patch(
            "/v1/sessions/session-1",
            headers=AUTH,
            json={"pinned": True, "archived": False},
        )
        modeled = client.patch(
            "/v1/sessions/session-1",
            headers=AUTH,
            json={"model": "anthropic:claude-test"},
        )
        invalid = client.patch(
            "/v1/sessions/session-1",
            headers=AUTH,
            json={"mode": "auto"},
        )

    assert renamed.status_code == 200
    assert sessions.renamed == [("session-1", "  New title  ")]
    assert flagged.status_code == 200
    assert sessions.flags == [("session-1", True, False)]
    assert modeled.status_code == 200
    assert sessions.models == [
        ("session-1", "anthropic:claude-test")
    ]
    assert invalid.status_code == 400


def test_session_model_change_refuses_active_turn():
    client, sessions, turns = make_client()
    turns.active.add("session-1")

    with client:
        response = client.patch(
            "/v1/sessions/session-1",
            headers=AUTH,
            json={
                "title": "Must not partially apply",
                "model": "gemini:gemini-test",
            },
        )

    assert response.status_code == 409
    assert sessions.models == []
    assert sessions.renamed == []


def test_session_delete_refuses_active_turn_then_deletes():
    client, sessions, turns = make_client()
    turns.active.add("session-1")
    with client:
        busy = client.delete(
            "/v1/sessions/session-1",
            headers=AUTH,
        )
        turns.active.clear()
        deleted = client.delete(
            "/v1/sessions/session-1",
            headers=AUTH,
        )

    assert busy.status_code == 409
    assert deleted.status_code == 200
    assert sessions.deleted == ["session-1"]


def test_session_delete_refuses_pending_checkpoint_restore():
    client, sessions, turns = make_client()
    turns.restore_pending.add("session-1")

    with client:
        response = client.delete(
            "/v1/sessions/session-1",
            headers=AUTH,
        )

    assert response.status_code == 409
    assert response.json()["detail"] == (
        "session has a pending checkpoint restore"
    )
    assert sessions.deleted == []


def test_terminal_route_executes_auto_allowed_command():
    sessions = FakeTerminalSessions()
    sessions.set_engine(
        FakeEngine(
            shell=FakeShell(result=FakeShellResult(
                {
                    "exit_code": 0,
                    "stdout": "ok",
                    "stderr": "",
                    "timed_out": False,
                }
            )),
            permissions=FakePermissions(
                Decision(True, reason="auto allow")
            ),
        )
    )
    client, _sessions, turns = make_client(
        sessions=sessions,
        turns=FakeTurns(),
    )
    with client:
        response = client.post(
            "/v1/sessions/session-1/terminal/run",
            headers=AUTH,
            json={"command": "git status", "timeout_seconds": 12.5},
        )

    assert response.status_code == 200
    assert response.json()["exit_code"] == 0
    assert sessions.get_engine_calls == ["session-1"]


def test_terminal_route_accepts_once_then_denies_new_command():
    decision = Decision(False, reason="requires approval", needs_user=True)
    permissions = FakePermissions(decision)
    shell = FakeShell()
    sessions = FakeTerminalSessions()
    sessions.set_engine(
        FakeEngine(
            shell=shell,
            permissions=permissions,
        )
    )
    approvals = FakeApprovalBroker(ApprovalOutcome.DENY)
    client, _sessions, _turns = make_client(
        sessions=sessions,
        approvals=approvals,
    )

    with client:
        denied = client.post(
            "/v1/sessions/session-1/terminal/run",
            headers=AUTH,
            json={"command": "pytest -q"},
        )

    assert denied.status_code == 409
    assert denied.json() == {"detail": "command denied by user"}
    assert shell.calls == []


def test_terminal_route_respects_approval_outcome_always_command():
    decision = Decision(False, reason="requires approval", needs_user=True)
    permissions = FakePermissions(decision)
    shell = FakeShell(result=FakeShellResult({"exit_code": 0, "stdout": "ok"}))
    sessions = FakeTerminalSessions()
    sessions.set_engine(
        FakeEngine(
            shell=shell,
            permissions=permissions,
        )
    )
    approvals = FakeApprovalBroker(ApprovalOutcome.ALWAYS_COMMAND)
    client, _sessions, _turns = make_client(
        sessions=sessions,
        approvals=approvals,
    )

    with client:
        allowed = client.post(
            "/v1/sessions/session-1/terminal/run",
            headers=AUTH,
            json={"command": "pytest -q"},
        )

    assert allowed.status_code == 200
    assert permissions.allowed == ["pytest -q"]
    assert shell.calls == [("pytest -q", None)]


def test_terminal_route_rejects_busy_session_or_invalid_request():
    turns = FakeTurns()
    turns.active.add("session-1")
    sessions = FakeTerminalSessions()
    sessions.set_engine(
        FakeEngine(
            shell=FakeShell(),
            permissions=FakePermissions(Decision(True)),
        )
    )
    client, _sessions, _ = make_client(
        sessions=sessions,
        turns=turns,
    )
    with client:
        blocked = client.post(
            "/v1/sessions/session-1/terminal/run",
            headers=AUTH,
            json={"command": "echo hi"},
        )

    assert blocked.status_code == 409
    assert blocked.json() == {
        "detail": "session already has an active turn"
    }

    turns.active.clear()
    with client:
        malformed = client.post(
            "/v1/sessions/session-1/terminal/run",
            headers=AUTH,
            json={"timeout_seconds": 1},
        )

    assert malformed.status_code == 400
    assert malformed.json() == {"detail": "invalid terminal payload"}


def test_terminal_route_maps_shell_and_approval_errors():
    sessions = FakeTerminalSessions()
    sessions.set_engine(
        FakeEngine(
            shell=FakeShell(error=InvalidCommandError("bad")),
            permissions=FakePermissions(Decision(True)),
        )
    )
    client, _sessions, _turns = make_client(sessions=sessions)
    with client:
        invalid = client.post(
            "/v1/sessions/session-1/terminal/run",
            headers=AUTH,
            json={"command": "bad syntax"},
        )
    assert invalid.status_code == 400

    sessions.set_engine(
        FakeEngine(
            shell=FakeShell(error=SandboxUnavailableError("missing")),
            permissions=FakePermissions(Decision(True)),
        )
    )
    with client:
        unavailable = client.post(
            "/v1/sessions/session-1/terminal/run",
            headers=AUTH,
            json={"command": "echo ready"},
        )
    assert unavailable.status_code == 503

    sessions.set_engine(
        FakeEngine(
            shell=FakeShell(),
            permissions=FakePermissions(
                Decision(False, reason="x", needs_user=True)
            ),
        )
    )
    approvals = FakeApprovalBroker(
        ApprovalPersistenceError("approval write failed"),
    )
    client, _sessions, _turns = make_client(
        sessions=sessions,
        approvals=approvals,
    )
    with client:
        persistence = client.post(
            "/v1/sessions/session-1/terminal/run",
            headers=AUTH,
            json={"command": "echo ready"},
        )

    assert persistence.status_code == 503
    assert persistence.json() == {
        "detail": "approval decision could not be saved"
    }


def test_terminal_interrupt_route_stops_active_terminal_command():
    shell = FakeShell(interrupted=True)
    sessions = FakeTerminalSessions()
    sessions.set_engine(
        FakeEngine(
            shell=shell,
            permissions=FakePermissions(Decision(True)),
        )
    )
    client, _sessions, _turns = make_client(sessions=sessions)

    with client:
        response = client.post(
            "/v1/sessions/session-1/terminal/interrupt",
            headers=AUTH,
        )

    assert response.status_code == 200
    assert response.json() == {
        "ok": True,
        "session_id": "session-1",
    }
    assert shell.interrupt_calls == ["called"]


def test_terminal_interrupt_route_reports_no_running_command():
    shell = FakeShell(interrupted=False)
    sessions = FakeTerminalSessions()
    sessions.set_engine(
        FakeEngine(
            shell=shell,
            permissions=FakePermissions(Decision(True)),
        )
    )
    client, _sessions, _turns = make_client(sessions=sessions)

    with client:
        response = client.post(
            "/v1/sessions/session-1/terminal/interrupt",
            headers=AUTH,
        )

    assert response.status_code == 200
    assert response.json() == {
        "ok": False,
        "session_id": "session-1",
    }


def test_terminal_interrupt_route_reports_unavailable_when_no_interrupt_hook():
    sessions = FakeTerminalSessions()
    sessions.set_engine(
        FakeEngine(
            shell=FakeLegacyShell(),
            permissions=FakePermissions(Decision(True)),
        )
    )
    client, _sessions, _turns = make_client(sessions=sessions)

    with client:
        response = client.post(
            "/v1/sessions/session-1/terminal/interrupt",
            headers=AUTH,
        )

    assert response.status_code == 503
    assert response.json()["detail"] == "terminal interrupt unavailable"


def test_terminal_interrupt_route_404s_when_session_engine_is_missing():
    sessions = FakeTerminalSessions()
    sessions.set_engine(None)
    client, _sessions, _turns = make_client(sessions=sessions)

    with client:
        response = client.post(
            "/v1/sessions/missing-session/terminal/interrupt",
            headers=AUTH,
        )

    assert response.status_code == 404
    assert response.json()["detail"] == "session not found"


def test_terminal_route_404s_when_session_engine_is_missing():
    sessions = FakeTerminalSessions()
    sessions.set_engine(None)
    client, _sessions, _turns = make_client(sessions=sessions)

    with client:
        response = client.post(
            "/v1/sessions/missing-session/terminal/run",
            headers=AUTH,
            json={"command": "echo hi"},
        )

    assert response.status_code == 404
    assert response.json()["detail"] == "session not found"


class FakeMcpService:
    def __init__(self, *, raises_value_error=False):
        self.enabled_calls: list[tuple[str, str, bool]] = []
        self.raises_value_error = raises_value_error
        self._servers = [
            {
                "name": "docs",
                "transport": "http",
                "url": "https://mcp.example.com/v1",
                "command": None,
                "cwd": None,
                "tools": ["mcp__docs__search"],
                "include_tools": None,
                "exclude_tools": [],
                "enabled": True,
            }
        ]

    async def connect(self, *_args, **_kwargs):
        return {"ok": True, "server": "docs", "tools": ["mcp__docs__search"]}

    def list_connected(self, _session_id):
        return list(self._servers)

    async def disconnect(self, *_args, **_kwargs):
        return {"ok": True, "server": "docs", "tools": []}

    async def set_enabled(self, session_id, name, *, enabled):
        if self.raises_value_error:
            raise ValueError("MCP server not connected")
        self.enabled_calls.append((session_id, name, enabled))
        for server in self._servers:
            if server["name"] == name:
                server["enabled"] = enabled
        return {"ok": True, "server": name, "enabled": enabled, "tools": []}

    async def recover(self):
        return 0

    async def aclose(self):
        return None


def _make_mcp_client(mcp):
    services = SimpleNamespace(
        events=EventHub(),
        settings=FakeSettings(),
        routing=None,
        secrets=ProviderSecretService(),
        oauth=OAuthCoordinator(),
        turns=FakeTurns(),
        sessions=FakeSessions(),
        approvals=None,
        mcp=mcp,
        git=None,
    )
    return TestClient(create_control_plane_app(token=TOKEN, services=services))


def test_mcp_list_includes_enabled_field():
    client = _make_mcp_client(FakeMcpService())

    with client:
        response = client.get(
            "/v1/sessions/session-1/mcp/servers",
            headers=AUTH,
        )

    assert response.status_code == 200
    rows = response.json()
    assert rows[0]["enabled"] is True


def test_mcp_patch_route_toggles_enabled_state():
    mcp = FakeMcpService()
    client = _make_mcp_client(mcp)

    with client:
        disabled = client.patch(
            "/v1/sessions/session-1/mcp/servers/docs",
            headers=AUTH,
            json={"enabled": False},
        )
        listed = client.get(
            "/v1/sessions/session-1/mcp/servers",
            headers=AUTH,
        )
        re_enabled = client.patch(
            "/v1/sessions/session-1/mcp/servers/docs",
            headers=AUTH,
            json={"enabled": True},
        )

    assert disabled.json() == {
        "ok": True,
        "server": "docs",
        "enabled": False,
        "tools": [],
    }
    assert listed.json()[0]["enabled"] is False
    assert re_enabled.json()["enabled"] is True
    assert mcp.enabled_calls == [
        ("session-1", "docs", False),
        ("session-1", "docs", True),
    ]


def test_mcp_patch_route_returns_404_when_server_unknown():
    client = _make_mcp_client(FakeMcpService(raises_value_error=True))

    with client:
        response = client.patch(
            "/v1/sessions/session-1/mcp/servers/unknown",
            headers=AUTH,
            json={"enabled": False},
        )

    assert response.status_code == 404
    assert response.json()["detail"] == "MCP server not connected"


def test_mcp_patch_route_rejects_malformed_body():
    client = _make_mcp_client(FakeMcpService())

    with client:
        bad_enabled_type = client.patch(
            "/v1/sessions/session-1/mcp/servers/docs",
            headers=AUTH,
            json={"enabled": "yes"},
        )
        extra_field = client.patch(
            "/v1/sessions/session-1/mcp/servers/docs",
            headers=AUTH,
            json={"enabled": True, "other": "extra"},
        )
        invalid_name = client.patch(
            "/v1/sessions/session-1/mcp/servers/bad name",
            headers=AUTH,
            json={"enabled": True},
        )

    assert bad_enabled_type.status_code == 400
    assert extra_field.status_code == 400
    assert invalid_name.status_code == 400


def test_mcp_patch_route_returns_503_when_mcp_unavailable():
    services = SimpleNamespace(
        events=EventHub(),
        settings=FakeSettings(),
        routing=None,
        secrets=ProviderSecretService(),
        oauth=OAuthCoordinator(),
        turns=FakeTurns(),
        sessions=FakeSessions(),
        approvals=None,
        mcp=None,
        git=None,
    )
    client = TestClient(create_control_plane_app(token=TOKEN, services=services))

    with client:
        response = client.patch(
            "/v1/sessions/session-1/mcp/servers/docs",
            headers=AUTH,
            json={"enabled": False},
        )

    assert response.status_code == 503
    assert response.json()["detail"] == "MCP unavailable"


def test_git_stage_route_stages_path():
    client, _sessions, _turns = make_client(git=FakeGit())

    with client:
        response = client.post(
            "/v1/sessions/session-1/git/stage",
            headers=AUTH,
            json={"path": "src/main.py"},
        )

    assert response.status_code == 200
    assert response.json() == {"ok": True, "path": "src/main.py"}


def test_git_commit_route_commits_message():
    client, _sessions, _turns = make_client(git=FakeGit())

    with client:
        response = client.post(
            "/v1/sessions/session-1/git/commit",
            headers=AUTH,
            json={"message": "Apply change"},
        )

    assert response.status_code == 200
    body = response.json()
    assert body["ok"] is True
    assert body["branch"] == "codinal/session-1"


def test_git_commit_route_rejects_empty_message():
    client, _sessions, _turns = make_client(git=FakeGit())

    with client:
        response = client.post(
            "/v1/sessions/session-1/git/commit",
            headers=AUTH,
            json={"message": "   "},
        )

    assert response.status_code == 400


def test_git_log_and_graph_routes_return_history():
    client, _sessions, _turns = make_client(git=FakeGit())

    with client:
        log = client.get(
            "/v1/sessions/session-1/git/log",
            headers=AUTH,
        )
        graph = client.get(
            "/v1/sessions/session-1/git/graph",
            headers=AUTH,
        )

    assert log.status_code == 200
    assert log.json()["commits"][0]["subject"] == "Apply change"
    assert graph.status_code == 200
    assert "* " in graph.json()["graph"]


def test_git_diff_route_accepts_commit_param():
    client, _sessions, _turns = make_client(git=FakeGit())

    with client:
        response = client.get(
            "/v1/sessions/session-1/git/diff?commit=abc1234",
            headers=AUTH,
        )

    assert response.status_code == 200


def test_git_push_route_pushes_and_audits(tmp_path):
    from runtime.audit import AuditLedger

    git = FakeGit()
    services = SimpleNamespace(
        events=EventHub(),
        settings=FakeSettings(),
        routing=None,
        secrets=ProviderSecretService(),
        oauth=OAuthCoordinator(),
        turns=FakeTurns(),
        sessions=FakeSessions(),
        approvals=None,
        mcp=None,
        git=git,
        audit=AuditLedger(tmp_path),
    )
    client = TestClient(create_control_plane_app(token=TOKEN, services=services))

    with client:
        response = client.post(
            "/v1/sessions/session-1/git/push",
            headers=AUTH,
            json={"remote": "origin", "set_upstream": False},
        )

    assert response.status_code == 200
    body = response.json()
    assert body["ok"] is True
    assert body["remote"] == "origin"
    events = services.audit.list(domain="git")
    assert [event["action"] for event in events] == ["push"]
    assert events[0]["payload"]["remote"] == "origin"


def test_git_push_route_rejects_invalid_remote():
    client, _sessions, _turns = make_client(git=FakeGit())

    with client:
        response = client.post(
            "/v1/sessions/session-1/git/push",
            headers=AUTH,
            json={"remote": "bad remote!", "set_upstream": False},
        )

    assert response.status_code == 400


def test_git_routes_404_when_session_not_a_git_session():
    class NoGit:
        def load(self, _session_id):
            return None

        def close(self):
            return None

    client, _sessions, _turns = make_client(git=NoGit())

    with client:
        for path in [
            "/v1/sessions/session-1/git/log",
            "/v1/sessions/session-1/git/graph",
        ]:
            response = client.get(path, headers=AUTH)
            assert response.status_code == 404
        for path, body in [
            ("/v1/sessions/session-1/git/stage", {"path": "."}),
            ("/v1/sessions/session-1/git/commit", {"message": "x"}),
            ("/v1/sessions/session-1/git/push", {"remote": "origin", "set_upstream": False}),
        ]:
            response = client.post(path, headers=AUTH, json=body)
            assert response.status_code == 404


def test_git_files_route_lists_changed_files():
    client, _sessions, _turns = make_client(git=FakeGit())

    with client:
        response = client.get(
            "/v1/sessions/session-1/git/files",
            headers=AUTH,
        )

    assert response.status_code == 200
    body = response.json()
    assert body["ok"] is True
    assert {entry["path"] for entry in body["files"]} == {
        "src/main.py",
        "src/new.py",
    }


def test_git_apply_with_paths_routes_to_selective():
    client, _sessions, _turns = make_client(git=FakeGit())

    with client:
        response = client.post(
            "/v1/sessions/session-1/git/apply",
            headers=AUTH,
            json={"paths": ["src/main.py"]},
        )

    assert response.status_code == 200
    body = response.json()
    assert body["strategy"] == "selective"
    assert body["files"] == ["src/main.py"]


def test_git_apply_without_paths_still_applies_all():
    client, _sessions, _turns = make_client(git=FakeGit())

    with client:
        response = client.post(
            "/v1/sessions/session-1/git/apply",
            headers=AUTH,
            json={},
        )

    # Empty body {} → apply all (legacy). FakeGit.apply_back returns its status.
    assert response.status_code == 200


def test_git_apply_rejects_malformed_paths():
    client, _sessions, _turns = make_client(git=FakeGit())

    with client:
        not_a_list = client.post(
            "/v1/sessions/session-1/git/apply",
            headers=AUTH,
            json={"paths": "src/main.py"},
        )
        extra_field = client.post(
            "/v1/sessions/session-1/git/apply",
            headers=AUTH,
            json={"paths": ["x"], "other": 1},
        )

    assert not_a_list.status_code == 400
    assert extra_field.status_code == 400


class _FakeGitWithRecord:
    def __init__(self, source_root=None):
        self._source_root = source_root

    def load(self, session_id):
        if self._source_root is None:
            return None
        return SimpleNamespace(
            source_root=self._source_root, session_branch="feature"
        )

    def status(self, _session_id):
        return {"head_commit": "abc123"}

    def close(self):
        return None


class _FakeGitHub:
    def __init__(self):
        self.created = None
        self.merged = None
        self.commented = None
        self.cleaned_up = None

    def create_pr(self, source_root, branch, *, title, body="", base=""):
        self.created = (title, body, base)
        return {"open": True, "number": 1, "title": title, "url": "https://github.com/o/r/pull/1"}

    def find_pr(self, source_root, branch):
        return {"open": False}

    def list_checks(self, source_root, ref):
        return {"total": 0, "runs": []}

    def merge_pr(self, source_root, branch, *, method="squash"):
        self.merged = (branch, method)
        return {"ok": True, "sha": "abc123", "message": "merged"}

    def add_review_comment(self, source_root, branch, *, body):
        self.commented = body
        return {"ok": True}

    def post_merge_cleanup(self, source_root, branch):
        self.cleaned_up = branch
        return {"ok": True, "branch": branch}


def _github_client(git, github):
    services = SimpleNamespace(
        events=EventHub(),
        settings=FakeSettings(),
        routing=None,
        secrets=ProviderSecretService(),
        oauth=OAuthCoordinator(),
        turns=FakeTurns(),
        sessions=FakeSessions(),
        approvals=None,
        mcp=None,
        git=git,
        github=github,
        audit=None,
    )
    return TestClient(create_control_plane_app(token=TOKEN, services=services))


def test_github_create_pr_route_creates_pr():
    github = _FakeGitHub()
    git = _FakeGitWithRecord(source_root="/repo")
    client = _github_client(git, github)

    with client:
        response = client.post(
            "/v1/sessions/session-1/github/pr",
            headers=AUTH,
            json={"title": "Add feature", "body": "details", "base": "main"},
        )

    assert response.status_code == 200
    body = response.json()
    assert body["open"] is True
    assert body["number"] == 1
    assert github.created == ("Add feature", "details", "main")


def test_github_get_pr_route_returns_pr_info():
    github = _FakeGitHub()
    git = _FakeGitWithRecord(source_root="/repo")
    client = _github_client(git, github)

    with client:
        response = client.get(
            "/v1/sessions/session-1/github/pr",
            headers=AUTH,
        )

    assert response.status_code == 200
    assert response.json() == {"open": False}


def test_github_checks_route_returns_check_runs():
    github = _FakeGitHub()
    git = _FakeGitWithRecord(source_root="/repo")
    client = _github_client(git, github)

    with client:
        response = client.get(
            "/v1/sessions/session-1/github/checks",
            headers=AUTH,
        )

    assert response.status_code == 200
    body = response.json()
    assert body["total"] == 0


def test_github_routes_503_when_github_unavailable():
    git = _FakeGitWithRecord(source_root="/repo")
    client = _github_client(git, github=None)

    with client:
        for method, path in [
            ("POST", "/v1/sessions/session-1/github/pr"),
            ("GET", "/v1/sessions/session-1/github/pr"),
            ("GET", "/v1/sessions/session-1/github/checks"),
        ]:
            kwargs = {"json": {"title": "x"}} if method == "POST" else {}
            response = client.request(method, path, headers=AUTH, **kwargs)
            assert response.status_code == 503


def test_github_create_pr_rejects_missing_title():
    github = _FakeGitHub()
    git = _FakeGitWithRecord(source_root="/repo")
    client = _github_client(git, github)

    with client:
        response = client.post(
            "/v1/sessions/session-1/github/pr",
            headers=AUTH,
            json={"body": "no title"},
        )

    assert response.status_code == 400


class _FakePreview:
    def __init__(self):
        self.store = {}

    def add_evidence(self, session_id, kind, content):
        entry = {"id": len(self.store) + 1, "session_id": session_id, "kind": kind, "content": content}
        self.store.setdefault(session_id, []).append(entry)
        return entry

    def list_evidence(self, session_id):
        return self.store.get(session_id, [])

    def clear_evidence(self, session_id):
        count = len(self.store.get(session_id, []))
        self.store.pop(session_id, None)
        return count


def _preview_client(preview):
    services = SimpleNamespace(
        events=EventHub(),
        settings=FakeSettings(),
        routing=None,
        secrets=ProviderSecretService(),
        oauth=OAuthCoordinator(),
        turns=FakeTurns(),
        sessions=FakeSessions(),
        approvals=None,
        mcp=None,
        git=None,
        github=None,
        preview=preview,
        audit=None,
    )
    return TestClient(create_control_plane_app(token=TOKEN, services=services))


def test_preview_evidence_add_list_clear_round_trip():
    preview = _FakePreview()
    client = _preview_client(preview)

    with client:
        added = client.post(
            "/v1/sessions/session-1/preview/evidence",
            headers=AUTH,
            json={"kind": "console", "content": "TypeError at line 5"},
        )
        listed = client.get(
            "/v1/sessions/session-1/preview/evidence",
            headers=AUTH,
        )
        cleared = client.delete(
            "/v1/sessions/session-1/preview/evidence",
            headers=AUTH,
        )
        after = client.get(
            "/v1/sessions/session-1/preview/evidence",
            headers=AUTH,
        )

    assert added.status_code == 200
    assert added.json()["kind"] == "console"
    assert listed.status_code == 200
    assert len(listed.json()) == 1
    assert cleared.status_code == 200
    assert cleared.json()["cleared"] == 1
    assert after.json() == []


def test_preview_evidence_rejects_invalid_kind():
    preview = _FakePreview()
    client = _preview_client(preview)

    with client:
        response = client.post(
            "/v1/sessions/session-1/preview/evidence",
            headers=AUTH,
            json={"kind": "bogus", "content": "x"},
        )

    assert response.status_code == 400


def test_preview_origin_requires_loopback_ip_literal():
    client = _preview_client(_FakePreview())

    with client:
        blocked = client.post(
            "/v1/sessions/session-1/preview/verify-origin",
            headers=AUTH,
            json={"url": "https://example.com"},
        )
        accepted = client.post(
            "/v1/sessions/session-1/preview/verify-origin",
            headers=AUTH,
            json={"url": "http://127.0.0.1:3000/app"},
        )

    assert blocked.status_code == 400
    assert accepted.json() == {"url": "http://127.0.0.1:3000/app"}


def test_preview_evidence_503_when_unavailable():
    client = _preview_client(None)

    with client:
        for method, path in [
            ("POST", "/v1/sessions/session-1/preview/evidence"),
            ("GET", "/v1/sessions/session-1/preview/evidence"),
            ("DELETE", "/v1/sessions/session-1/preview/evidence"),
        ]:
            kwargs = {"json": {"kind": "console", "content": "x"}} if method == "POST" else {}
            response = client.request(method, path, headers=AUTH, **kwargs)
            assert response.status_code == 503


def test_github_merge_route_merges_pr():
    github = _FakeGitHub()
    git = _FakeGitWithRecord(source_root="/repo")
    client = _github_client(git, github)

    with client:
        response = client.post(
            "/v1/sessions/session-1/github/merge",
            headers=AUTH,
            json={"method": "squash"},
        )

    assert response.status_code == 200
    assert response.json()["ok"] is True
    assert github.merged == ("feature", "squash")


def test_github_comment_route_adds_review_comment():
    github = _FakeGitHub()
    git = _FakeGitWithRecord(source_root="/repo")
    client = _github_client(git, github)

    with client:
        response = client.post(
            "/v1/sessions/session-1/github/comment",
            headers=AUTH,
            json={"body": "Looks good!"},
        )

    assert response.status_code == 200
    assert github.commented == "Looks good!"


def test_github_cleanup_route_deletes_branch():
    github = _FakeGitHub()
    git = _FakeGitWithRecord(source_root="/repo")
    client = _github_client(git, github)

    with client:
        response = client.post(
            "/v1/sessions/session-1/github/cleanup",
            headers=AUTH,
        )

    assert response.status_code == 200
    assert github.cleaned_up == "feature"


def test_github_merge_rejects_invalid_method():
    github = _FakeGitHub()
    git = _FakeGitWithRecord(source_root="/repo")
    client = _github_client(git, github)

    with client:
        response = client.post(
            "/v1/sessions/session-1/github/merge",
            headers=AUTH,
            json={"method": "bomb"},
        )

    assert response.status_code == 400
