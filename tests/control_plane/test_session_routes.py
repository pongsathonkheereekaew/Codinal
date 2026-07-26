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


class FakeTurns:
    def __init__(self):
        self.active = set()
        self.restore_pending = set()

    async def recover(self):
        return 0

    async def shutdown(self):
        return None

    def interrupt(self, _session_id):
        return False

    def is_active(self, session_id):
        return session_id in self.active

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


def make_client():
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
        git=None,
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
