import asyncio
from types import SimpleNamespace

from fastapi.testclient import TestClient

from runtime.control_plane import create_control_plane_app
from runtime.events import EventHub
from runtime.oauth import OAuthCoordinator
from runtime.policy import (
    ApprovalBroker,
    ApprovalOutcome,
    PermissionRequest,
)
from runtime.secrets import ProviderSecretService


TOKEN = "test-session-token-with-at-least-32-characters"
AUTH = {"Authorization": f"Bearer {TOKEN}"}


class FakeSettings:
    def view(self):
        return {"model": "openai:gpt-test"}


class FakeTurns:
    async def recover(self):
        return 0

    async def shutdown(self):
        return None

    def interrupt(self, _session_id):
        return False

    def is_active(self, _session_id):
        return False


def make_client(broker):
    services = SimpleNamespace(
        events=EventHub(),
        settings=FakeSettings(),
        secrets=ProviderSecretService(),
        oauth=OAuthCoordinator(),
        turns=FakeTurns(),
        approvals=broker,
        mcp=None,
        git=None,
    )
    return TestClient(
        create_control_plane_app(token=TOKEN, services=services)
    )


def test_approval_routes_list_and_resolve_session_request():
    async def scenario():
        broker = ApprovalBroker()
        request = PermissionRequest(
            tool_name="write_file",
            arguments={"path": "notes.txt", "content": "safe"},
            reason="write requires approval",
            risk="write_local",
            tool_call_id="call/1",
        )
        task = asyncio.create_task(
            broker.approver("session-1")(request)
        )
        while not broker.pending("session-1"):
            await asyncio.sleep(0)
        approval_id = broker.approval_id("session-1", "call/1")
        with make_client(broker) as client:
            listed = client.get(
                "/v1/sessions/session-1/approvals",
                headers=AUTH,
            )
            wrong = client.post(
                f"/v1/sessions/session-2/approvals/{approval_id}",
                headers=AUTH,
                json={"outcome": "once"},
            )
            resolved = client.post(
                f"/v1/sessions/session-1/approvals/{approval_id}",
                headers=AUTH,
                json={"outcome": "once"},
            )
        return listed, wrong, resolved, await task

    listed, wrong, resolved, outcome = asyncio.run(scenario())

    assert listed.status_code == 200
    assert listed.json()[0]["tool_name"] == "write_file"
    assert listed.json()[0]["approval_id"]
    assert wrong.status_code == 409
    assert resolved.status_code == 200
    assert resolved.json() == {"ok": True}
    assert outcome is ApprovalOutcome.ONCE


def test_approval_route_rejects_invalid_payload_and_persistence_scope():
    async def scenario():
        broker = ApprovalBroker()
        request = PermissionRequest(
            tool_name="mcp__docs__search",
            arguments={"query": "policy"},
            reason="external call requires approval",
            risk="external",
            tool_call_id="call-1",
        )
        task = asyncio.create_task(
            broker.approver("session-1")(request)
        )
        while not broker.pending("session-1"):
            await asyncio.sleep(0)
        approval_id = broker.approval_id("session-1", "call-1")
        with make_client(broker) as client:
            invalid = client.post(
                f"/v1/sessions/session-1/approvals/{approval_id}",
                headers=AUTH,
                json={"outcome": "forever"},
            )
            persistent = client.post(
                f"/v1/sessions/session-1/approvals/{approval_id}",
                headers=AUTH,
                json={"outcome": "always_tool"},
            )
            denied = client.post(
                f"/v1/sessions/session-1/approvals/{approval_id}",
                headers=AUTH,
                json={"outcome": "deny"},
            )
        return invalid, persistent, denied, await task

    invalid, persistent, denied, outcome = asyncio.run(scenario())

    assert invalid.status_code == 400
    assert persistent.status_code == 409
    assert denied.status_code == 200
    assert outcome is ApprovalOutcome.DENY


def test_approval_route_returns_503_when_decision_cannot_be_saved():
    class FailingDecisions:
        def load_approval_decision(self, *_args):
            return None

        def save_approval_decision(self, *_args):
            raise OSError("private disk detail")

        def delete_approval_decision(self, *_args):
            return None

    async def scenario():
        broker = ApprovalBroker(decisions=FailingDecisions())
        request = PermissionRequest(
            tool_name="write_file",
            arguments={"path": "notes.txt"},
            reason="write requires approval",
            risk="write_local",
            tool_call_id="call-1",
        )
        task = asyncio.create_task(
            broker.approver("session-1")(request)
        )
        while not broker.pending("session-1"):
            await asyncio.sleep(0)
        approval_id = broker.approval_id("session-1", "call-1")
        with make_client(broker) as client:
            response = client.post(
                f"/v1/sessions/session-1/approvals/{approval_id}",
                headers=AUTH,
                json={"outcome": "once"},
            )
        return response, await task

    response, outcome = asyncio.run(scenario())

    assert response.status_code == 503
    assert response.json() == {
        "detail": "approval decision could not be saved"
    }
    assert outcome is ApprovalOutcome.DENY
