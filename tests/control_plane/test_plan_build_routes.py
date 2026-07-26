from types import SimpleNamespace

from fastapi.testclient import TestClient

from runtime.control_plane import create_control_plane_app
from runtime.events import EventHub

TOKEN = "test-session-token-with-at-least-32-characters"
AUTH = {"Authorization": f"Bearer {TOKEN}"}
PLAN_ID = "a" * 32


class FakeTurns:
    async def recover(self):
        return 0

    async def shutdown(self):
        return True


class FakeBuilds:
    def __init__(self):
        self.actions = []
        self.record = {
            "build_id": "build-test",
            "parent_session_id": "session-parent",
            "plan_id": PLAN_ID,
            "state": "running",
            "tasks": [],
            "created_at": "2026-07-26T00:00:00Z",
            "updated_at": "2026-07-26T00:00:00Z",
        }

    async def create(self, parent_session_id, **options):
        self.actions.append(("create", parent_session_id, options))
        return self.record

    def list(self, parent_session_id):
        self.actions.append(("list", parent_session_id))
        return [self.record]

    async def select(self, build_id, worker_id):
        self.actions.append(("select", build_id, worker_id))
        return {**self.record, "state": "selected"}

    def candidate_diff(self, build_id, worker_id):
        self.actions.append(("diff", build_id, worker_id))
        return {
            "worker_id": worker_id,
            "verification": "Focused suite passes",
            "summary": "Focused suite passed",
            "diff": "+implemented",
            "output_truncated": False,
        }

    async def adopt(self, build_id):
        self.actions.append(("adopt", build_id))
        return {"ok": True, "strategy": "cherry-pick"}

    async def recover(self):
        return 0

    async def shutdown(self):
        pass


def make_client():
    builds = FakeBuilds()
    services = SimpleNamespace(
        events=EventHub(),
        turns=FakeTurns(),
        builds=builds,
    )
    return (
        TestClient(
            create_control_plane_app(token=TOKEN, services=services)
        ),
        builds,
    )


def test_authenticated_plan_build_comparison_selection_and_adoption():
    client, builds = make_client()
    created = client.post(
        "/v1/sessions/session-parent/plan-builds",
        headers=AUTH,
        json={
            "plan_id": PLAN_ID,
            "tasks": [
                {
                    "task_id": "parser",
                    "ownership": ["runtime/parser"],
                    "candidates": [
                        {"model": "openai:a"},
                        {"model": "anthropic:b"},
                    ],
                }
            ],
        },
    )
    listed = client.get(
        "/v1/sessions/session-parent/plan-builds",
        headers=AUTH,
    )
    reviewed = client.get(
        "/v1/plan-builds/build-test/candidates/worker-best/diff",
        headers=AUTH,
    )
    selected = client.post(
        "/v1/plan-builds/build-test/select",
        headers=AUTH,
        json={"worker_id": "worker-best"},
    )
    adopted = client.post(
        "/v1/plan-builds/build-test/adopt",
        headers=AUTH,
    )

    assert created.status_code == 202
    assert created.json()["build_id"] == "build-test"
    assert listed.status_code == 200
    assert listed.json()[0]["state"] == "running"
    assert reviewed.status_code == 200
    assert reviewed.json()["diff"] == "+implemented"
    assert selected.status_code == 200
    assert selected.json()["state"] == "selected"
    assert adopted.status_code == 200
    assert adopted.json()["strategy"] == "cherry-pick"
    assert [action[0] for action in builds.actions] == [
        "create",
        "list",
        "diff",
        "select",
        "adopt",
    ]


def test_plan_build_routes_require_auth_and_validate_bounded_payloads():
    client, builds = make_client()
    unauthorized = client.get(
        "/v1/sessions/session-parent/plan-builds",
    )
    invalid = client.post(
        "/v1/sessions/session-parent/plan-builds",
        headers=AUTH,
        json={
            "plan_id": PLAN_ID,
            "tasks": [
                {
                    "task_id": "parser",
                    "ownership": ["../outside"],
                    "candidates": [{"model": "openai:a"}],
                }
            ],
        },
    )

    assert unauthorized.status_code == 401
    assert invalid.status_code == 400
    assert builds.actions == []


def test_plan_build_rejects_unhashable_ownership_as_client_error():
    client, builds = make_client()

    response = client.post(
        "/v1/sessions/session-parent/plan-builds",
        headers=AUTH,
        json={
            "plan_id": PLAN_ID,
            "tasks": [
                {
                    "task_id": "parser",
                    "ownership": [["runtime/parser"]],
                    "candidates": [
                        {"model": "openai:a"},
                        {"model": "anthropic:b"},
                    ],
                }
            ],
        },
    )

    assert response.status_code == 400
    assert builds.actions == []


def test_plan_build_rejects_more_candidates_than_scheduler_capacity():
    client, builds = make_client()

    response = client.post(
        "/v1/sessions/session-parent/plan-builds",
        headers=AUTH,
        json={
            "plan_id": PLAN_ID,
            "tasks": [
                {
                    "task_id": f"task-{index}",
                    "ownership": [f"runtime/task-{index}"],
                    "candidates": [
                        {"model": "openai:a"},
                        {"model": "anthropic:b"},
                    ],
                }
                for index in range(5)
            ],
        },
    )

    assert response.status_code == 400
    assert builds.actions == []
