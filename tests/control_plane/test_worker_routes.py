from types import SimpleNamespace

from fastapi.testclient import TestClient

from runtime.control_plane import create_control_plane_app
from runtime.events import EventHub
from runtime.workers import (
    PROTOCOL_VERSION,
    REQUIRED_CAPABILITIES,
    WorkerRecord,
    WorkerState,
)

TOKEN = "test-session-token-with-at-least-32-characters"
AUTH = {"Authorization": f"Bearer {TOKEN}"}


class FakeTurns:
    async def recover(self):
        return 0

    async def shutdown(self):
        return True


class FakeStore:
    def close(self):
        pass


class FakeWorkers:
    def __init__(self):
        self.store = FakeStore()
        self.records = {}
        self.actions = []

    async def recover(self):
        return 0

    async def shutdown(self):
        pass

    async def create(self, parent_session_id, **options):
        record = WorkerRecord(
            worker_id="worker-test",
            parent_session_id=parent_session_id,
            child_session_id="session-worker-test",
            task=options["task"],
            ownership=options["ownership"],
            dependencies=options["dependencies"],
            model=options["model"],
            state=WorkerState.RUNNING,
        )
        self.records[record.worker_id] = record
        self.actions.append(("create", options))
        return record

    def list(self, parent_session_id):
        return [
            record
            for record in self.records.values()
            if record.parent_session_id == parent_session_id
        ]

    def steer(self, worker_id, text):
        self.actions.append(("steer", worker_id, text))
        return True

    async def cancel(self, worker_id):
        self.actions.append(("cancel", worker_id))
        return True

    async def adopt(self, worker_id):
        self.actions.append(("adopt", worker_id))
        return {"ok": True, "strategy": "cherry-pick"}


def make_client():
    workers = FakeWorkers()
    services = SimpleNamespace(
        events=EventHub(),
        turns=FakeTurns(),
        workers=workers,
    )
    return (
        TestClient(
            create_control_plane_app(token=TOKEN, services=services)
        ),
        workers,
    )


def test_authenticated_worker_lifecycle_routes():
    client, workers = make_client()
    created = client.post(
        "/v1/sessions/session-parent/workers",
        headers=AUTH,
        json={
            "task": "Implement parser",
            "ownership": ["runtime/parser"],
            "dependencies": [],
            "model": "openai:test",
        },
    )
    worker_id = created.json()["worker_id"]

    listed = client.get(
        "/v1/sessions/session-parent/workers",
        headers=AUTH,
    )
    steered = client.post(
        f"/v1/workers/{worker_id}/steer",
        headers=AUTH,
        json={"text": "Cover empty input"},
    )
    cancelled = client.post(
        f"/v1/workers/{worker_id}/cancel",
        headers=AUTH,
    )
    adopted = client.post(
        f"/v1/workers/{worker_id}/adopt",
        headers=AUTH,
    )

    assert created.status_code == 202
    assert created.json()["state"] == "running"
    assert listed.status_code == 200
    assert len(listed.json()) == 1
    assert steered.json()["ok"] is True
    assert cancelled.json()["ok"] is True
    assert adopted.json()["strategy"] == "cherry-pick"
    assert [action[0] for action in workers.actions] == [
        "create",
        "steer",
        "cancel",
        "adopt",
    ]


def test_local_handshake_negotiates_and_remote_transport_fails_closed():
    client, _ = make_client()

    body = {
        "version": PROTOCOL_VERSION,
        "worker_kind": "local",
        "capabilities": sorted(REQUIRED_CAPABILITIES),
    }
    local = client.post(
        "/v1/workers/negotiate",
        headers=AUTH,
        json=body,
    )
    remote = client.post(
        "/v1/workers/negotiate",
        headers=AUTH,
        json={**body, "worker_kind": "remote"},
    )

    assert local.status_code == 200
    assert local.json()["worker_kind"] == "local"
    assert remote.status_code == 501
    assert remote.json()["detail"] == (
        "remote worker transport is unavailable"
    )


def test_worker_routes_require_auth_and_reject_unbounded_authority():
    client, workers = make_client()

    unauthorized = client.get(
        "/v1/sessions/session-parent/workers",
    )
    invalid = client.post(
        "/v1/sessions/session-parent/workers",
        headers=AUTH,
        json={
            "task": "Escape",
            "ownership": ["../outside"],
            "model": "openai:test",
            "extra_roots": ["/"],
        },
    )

    assert unauthorized.status_code == 401
    assert invalid.status_code == 400
    assert workers.actions == []
