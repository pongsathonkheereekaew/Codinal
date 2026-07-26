import hashlib
from types import SimpleNamespace

from fastapi.testclient import TestClient

from runtime.control_plane import create_control_plane_app
from runtime.events import EventHub
from runtime.oauth import OAuthCoordinator
from runtime.secrets import ProviderSecretService
from runtime.storage import ExportTooLargeError
from runtime.turns import ExportBusyError, SessionBusyError


TOKEN = "test-session-token-with-at-least-32-characters"
AUTH = {"Authorization": f"Bearer {TOKEN}"}


class FakeSettings:
    def view(self):
        return {"model": "openai:gpt-test"}


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


class FakeSessions:
    def __init__(self):
        self.renamed = []
        self.flags = []
        self.models = []
        self.deleted = []
        self.forked = []
        self.side_conversations = []
        self.added_roots = []
        self.removed_roots = []
        self.opened_project_paths = []
        self.cancelled_project_searches = []
        self.rebuilt_project_indexes = []
        self.cleared_project_indexes = []
        self.export_too_large = False

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


def make_client(*, git=None):
    turns = FakeTurns()
    sessions = FakeSessions()
    services = SimpleNamespace(
        events=EventHub(),
        settings=FakeSettings(),
        secrets=ProviderSecretService(),
        oauth=OAuthCoordinator(),
        turns=turns,
        sessions=sessions,
        approvals=None,
        mcp=None,
        git=git,
    )
    return (
        TestClient(create_control_plane_app(token=TOKEN, services=services)),
        sessions,
        turns,
    )


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
