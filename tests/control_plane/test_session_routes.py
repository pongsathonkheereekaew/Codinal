from types import SimpleNamespace

from fastapi.testclient import TestClient

from runtime.control_plane import create_control_plane_app
from runtime.events import EventHub
from runtime.oauth import OAuthCoordinator
from runtime.secrets import ProviderSecretService


TOKEN = "test-session-token-with-at-least-32-characters"
AUTH = {"Authorization": f"Bearer {TOKEN}"}


class FakeSettings:
    def view(self):
        return {"model": "openai:gpt-test"}


class FakeTurns:
    def __init__(self):
        self.active = set()

    def interrupt(self, _session_id):
        return False

    def is_active(self, session_id):
        return session_id in self.active


class FakeSessions:
    def __init__(self):
        self.renamed = []
        self.flags = []
        self.models = []
        self.deleted = []

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
