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


class FakeTurns:
    async def recover(self):
        return 0

    async def shutdown(self):
        return None

    def interrupt(self, _session_id):
        return False


def make_client(broker):
    services = SimpleNamespace(
        events=EventHub(),
        settings=SimpleNamespace(
            view=lambda: {"model": "openai:gpt-test"}
        ),
        secrets=ProviderSecretService(),
        oauth=OAuthCoordinator(),
        turns=FakeTurns(),
        interactions=broker,
        approvals=None,
        mcp=None,
        git=None,
    )
    return TestClient(
        create_control_plane_app(token=TOKEN, services=services)
    )


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
        )({"plan": "1. Test"}, "call-1")
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
                content=b"x" * (32 * 1024 + 1),
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
