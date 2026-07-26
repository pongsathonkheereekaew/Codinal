from types import SimpleNamespace

from fastapi.testclient import TestClient

from runtime.control_plane import create_control_plane_app
from runtime.events import EventHub

TOKEN = "test-session-token-with-at-least-32-characters"
AUTH = {"Authorization": f"Bearer {TOKEN}"}


class FakeTurns:
    async def recover(self):
        return 0

    async def shutdown(self):
        return True


class FakeGoals:
    def __init__(self):
        self.actions = []
        self.record = {
            "goal_id": "goal-test",
            "session_id": "session-parent",
            "objective": "Ship safely",
            "requirements": [],
            "state": "active",
            "tokens_used": 0,
            "continuation_count": 0,
            "continuation_running": False,
            "evidence": [],
        }

    async def create(self, session_id, **options):
        self.actions.append(("create", session_id, options))
        return self.record

    def list(self, session_id):
        self.actions.append(("list", session_id))
        return [self.record]

    async def continue_goal(self, goal_id):
        self.actions.append(("continue", goal_id))
        return {**self.record, "continuation_running": True}

    async def add_evidence(self, goal_id, **options):
        self.actions.append(("evidence", goal_id, options))
        return {"evidence_id": "evidence-test", **options}

    async def audit(self, goal_id, **options):
        self.actions.append(("audit", goal_id, options))
        return {**self.record, "state": "completed"}

    async def recover(self):
        return 0

    async def shutdown(self):
        pass


def make_client():
    goals = FakeGoals()
    services = SimpleNamespace(
        events=EventHub(),
        turns=FakeTurns(),
        goals=goals,
    )
    return (
        TestClient(
            create_control_plane_app(token=TOKEN, services=services)
        ),
        goals,
    )


def test_authenticated_goal_lifecycle_routes():
    client, goals = make_client()
    created = client.post(
        "/v1/sessions/session-parent/goals",
        headers=AUTH,
        json={
            "objective": "Ship safely",
            "requirements": [
                {"requirement_id": "tests", "text": "Tests pass"}
            ],
            "continuation_prompt": "Continue and verify.",
            "token_budget": 1000,
            "time_budget_seconds": 3600,
        },
    )
    listed = client.get(
        "/v1/sessions/session-parent/goals",
        headers=AUTH,
    )
    continued = client.post(
        "/v1/goals/goal-test/continue",
        headers=AUTH,
    )
    evidence = client.post(
        "/v1/goals/goal-test/evidence",
        headers=AUTH,
        json={
            "requirement_id": "tests",
            "kind": "verification",
            "summary": "Focused suite",
            "result": "12 passed",
            "passed": True,
        },
    )
    audited = client.post(
        "/v1/goals/goal-test/audit",
        headers=AUTH,
        json={
            "status": "complete",
            "summary": "Verified",
            "requirement_evidence": {
                "tests": ["evidence-test"],
            },
        },
    )

    assert created.status_code == 201
    assert listed.status_code == 200
    assert continued.status_code == 202
    assert evidence.status_code == 201
    assert audited.status_code == 200
    assert [action[0] for action in goals.actions] == [
        "create",
        "list",
        "continue",
        "evidence",
        "audit",
    ]


def test_goal_routes_reject_malformed_and_oversized_payloads():
    client, goals = make_client()
    invalid = client.post(
        "/v1/sessions/session-parent/goals",
        headers=AUTH,
        json={
            "objective": "Ship",
            "requirements": [
                {"requirement_id": "../bad", "text": "Invalid"}
            ],
            "continuation_prompt": "Continue",
        },
    )
    oversized = client.post(
        "/v1/goals/goal-test/evidence",
        headers=AUTH,
        json={
            "requirement_id": "tests",
            "kind": "verification",
            "summary": "x" * (9 * 1024),
            "result": "pass",
            "passed": True,
        },
    )
    contradictory = client.post(
        "/v1/goals/goal-test/evidence",
        headers=AUTH,
        json={
            "requirement_id": "tests",
            "kind": "blocker",
            "summary": "Unavailable",
            "result": "503",
            "passed": True,
        },
    )

    assert invalid.status_code == 400
    assert oversized.status_code == 400
    assert contradictory.status_code == 400
    assert goals.actions == []
