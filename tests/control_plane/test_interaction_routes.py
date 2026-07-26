import asyncio
from types import SimpleNamespace

from fastapi.testclient import TestClient

from runtime.control_plane import create_control_plane_app
from runtime.events import EventHub
from runtime.interactions import InteractionBroker
from runtime.oauth import OAuthCoordinator
from runtime.secrets import ProviderSecretService

TOKEN = "test-session-token-with-at-least-32-characters"
AUTH = {"Authorization": f"Bearer {TOKEN}"}


class Decisions:
    def __init__(self):
        self.values = {}

    def load_interaction_decision(self, *key):
        return self.values.get(key)

    def save_interaction_decision(self, *values):
        *key, response = values
        self.values[tuple(key)] = response

    def ensure_plan_artifact(
        self,
        session_id,
        plan_id,
        tool_call_id,
        arguments,
    ):
        return {
            "plan_id": plan_id,
            "session_id": session_id,
            "tool_call_id": tool_call_id,
            "plan": arguments["plan"],
            "tasks": arguments["tasks"],
            "revision": 1,
        }

    def save_plan_interaction_decision(
        self,
        session_id,
        tool_call_id,
        fingerprint,
        response,
        _plan_id,
    ):
        self.save_interaction_decision(
            session_id,
            tool_call_id,
            "plan",
            fingerprint,
            response,
        )


class FakeTurns:
    async def recover(self):
        return 0

    async def shutdown(self):
        return None

    def interrupt(self, _session_id):
        return False


def make_client(broker, plans=None):
    services = SimpleNamespace(
        events=EventHub(),
        settings=SimpleNamespace(
            view=lambda: {"model": "openai:gpt-test"}
        ),
        secrets=ProviderSecretService(),
        oauth=OAuthCoordinator(),
        turns=FakeTurns(),
        interactions=broker,
        plans=plans,
        approvals=None,
        mcp=None,
        git=None,
    )
    return TestClient(
        create_control_plane_app(token=TOKEN, services=services)
    )


def test_plan_route_lists_durable_session_artifacts():
    artifact = {
        "plan_id": "a" * 32,
        "session_id": "session-1",
        "tool_call_id": "call-1",
        "plan": "Ship it",
        "tasks": [
            {
                "id": "ship",
                "title": "Ship it",
                "verification": "Release smoke passes",
            }
        ],
        "selected_task_ids": [],
        "status": "draft",
        "revision": 1,
        "updated_at": "2026-07-26T00:00:00Z",
    }
    plans = SimpleNamespace(
        list_plan_artifacts=lambda session_id: (
            [artifact] if session_id == "session-1" else []
        )
    )

    with make_client(InteractionBroker(Decisions()), plans) as client:
        response = client.get(
            "/v1/sessions/session-1/plans",
            headers=AUTH,
        )

    assert response.status_code == 200
    assert response.json() == [artifact]


def test_interaction_routes_list_and_resolve_question():
    async def scenario():
        broker = InteractionBroker(Decisions())
        awaitable = broker.requester(
            "session-1",
            "question",
        )(
            {
                "question": "Choose a database",
                "options": ["PostgreSQL", "SQLite"],
            },
            "call-1",
        )
        interaction_id = broker.interaction_id(
            "session-1",
            "call-1",
            "question",
        )
        with make_client(broker) as client:
            listed = client.get(
                "/v1/sessions/session-1/interactions",
                headers=AUTH,
            )
            wrong_session = client.post(
                f"/v1/sessions/session-2/interactions/{interaction_id}",
                headers=AUTH,
                json={"answer": "PostgreSQL"},
            )
            resolved = client.post(
                f"/v1/sessions/session-1/interactions/{interaction_id}",
                headers=AUTH,
                json={"answer": "PostgreSQL"},
            )
        return listed, wrong_session, resolved, await awaitable

    listed, wrong_session, resolved, answer = asyncio.run(scenario())

    assert listed.status_code == 200
    assert listed.json()[0]["kind"] == "question"
    assert listed.json()[0]["arguments"]["question"] == (
        "Choose a database"
    )
    assert wrong_session.status_code == 409
    assert resolved.status_code == 200
    assert answer == {"answer": "PostgreSQL"}


def test_interaction_route_rejects_invalid_response_and_body_limit():
    async def scenario():
        broker = InteractionBroker(Decisions())
        awaitable = broker.requester(
            "session-1",
            "plan",
        )(
            {
                "plan": "Test",
                "tasks": [
                    {
                        "id": "test",
                        "title": "Test",
                        "verification": "Focused test passes",
                    }
                ],
            },
            "call-1",
        )
        interaction_id = broker.interaction_id(
            "session-1",
            "call-1",
            "plan",
        )
        with make_client(broker) as client:
            invalid = client.post(
                f"/v1/sessions/session-1/interactions/{interaction_id}",
                headers=AUTH,
                json={"approved": True, "mode": "unsafe"},
            )
            oversized = client.post(
                f"/v1/sessions/session-1/interactions/{interaction_id}",
                headers=AUTH,
                content=b"x" * (128 * 1024 + 1),
            )
            resolved = client.post(
                f"/v1/sessions/session-1/interactions/{interaction_id}",
                headers=AUTH,
                json={"approved": False, "feedback": "Revise step 1"},
            )
        return invalid, oversized, resolved, await awaitable

    invalid, oversized, resolved, response = asyncio.run(scenario())

    assert invalid.status_code == 400
    assert oversized.status_code == 400
    assert resolved.status_code == 200
    assert response == {
        "approved": False,
        "feedback": "Revise step 1",
    }


def test_plan_interaction_approves_only_selected_edited_tasks():
    async def scenario():
        broker = InteractionBroker(Decisions())
        awaitable = broker.requester(
            "session-1",
            "plan",
        )(
            {
                "plan": "Original plan",
                "tasks": [
                    {
                        "id": "tests",
                        "title": "Add tests",
                        "verification": "Focused test passes",
                    },
                    {
                        "id": "build",
                        "title": "Build feature",
                        "verification": "Full suite passes",
                    },
                ],
            },
            "call-1",
        )
        interaction_id = broker.interaction_id(
            "session-1",
            "call-1",
            "plan",
        )
        with make_client(broker) as client:
            unknown = client.post(
                f"/v1/sessions/session-1/interactions/{interaction_id}",
                headers=AUTH,
                json={
                    "approved": True,
                    "mode": "interactive",
                    "plan": "Edited plan",
                    "selected_task_ids": ["missing"],
                },
            )
            resolved = client.post(
                f"/v1/sessions/session-1/interactions/{interaction_id}",
                headers=AUTH,
                json={
                    "approved": True,
                    "mode": "interactive",
                    "plan": "Edited plan",
                    "tasks": [
                        {
                            "id": "tests",
                            "title": "Add regression tests",
                            "verification": "Regression test passes",
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
        return unknown, resolved, await awaitable

    unknown, resolved, response = asyncio.run(scenario())

    assert unknown.status_code == 400
    assert resolved.status_code == 200
    assert response == {
        "approved": True,
        "mode": "interactive",
        "plan": "Edited plan",
        "tasks": [
            {
                "id": "tests",
                "title": "Add regression tests",
                "verification": "Regression test passes",
            },
            {
                "id": "build",
                "title": "Build feature",
                "verification": "Full suite passes",
            },
        ],
        "selected_task_ids": ["tests"],
        "selected_tasks": [
            {
                "id": "tests",
                "title": "Add regression tests",
                "verification": "Regression test passes",
            }
        ],
    }
