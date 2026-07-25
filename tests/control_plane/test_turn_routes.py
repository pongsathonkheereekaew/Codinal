import asyncio
from types import SimpleNamespace

import pytest
from fastapi import HTTPException, Request
from fastapi.testclient import TestClient

from runtime.control_plane import create_control_plane_app
from runtime.control_plane.app import _read_turn
from runtime.events import EventHub
from runtime.oauth import OAuthCoordinator
from runtime.secrets import ProviderSecretService
from runtime.turns import SessionBusyError, SessionNotFoundError


TOKEN = "test-session-token-with-at-least-32-characters"
AUTH = {"Authorization": f"Bearer {TOKEN}"}


class FakeSettings:
    def view(self):
        return {"model": "openai:gpt-test"}


class FakeTurns:
    def __init__(self):
        self.started = []
        self.interrupted = []

    async def start(
        self,
        session_id,
        *,
        user_input,
        workspace=None,
        agent="code",
        model=None,
        source=None,
    ):
        self.started.append(
            (session_id, user_input, workspace, agent, model, source)
        )
        return {"ok": True, "session_id": session_id}

    def interrupt(self, session_id):
        self.interrupted.append(session_id)
        return True


def make_client(turns=None):
    turns = turns or FakeTurns()
    services = SimpleNamespace(
        events=EventHub(),
        settings=FakeSettings(),
        secrets=ProviderSecretService(),
        oauth=OAuthCoordinator(),
        turns=turns,
    )
    client = TestClient(
        create_control_plane_app(token=TOKEN, services=services)
    )
    return client, turns


def test_turn_route_requires_auth_and_starts_bounded_request(tmp_path):
    client, turns = make_client()
    body = {
        "input": "inspect the project",
        "workspace": str(tmp_path),
        "agent": "code",
    }

    unauthorized = client.post("/v1/sessions/session-1/turns", json=body)
    accepted = client.post(
        "/v1/sessions/session-1/turns",
        headers=AUTH,
        json=body,
    )

    assert unauthorized.status_code == 401
    assert accepted.status_code == 202
    assert accepted.json() == {"ok": True, "session_id": "session-1"}
    assert turns.started == [
        (
            "session-1",
            "inspect the project",
            str(tmp_path),
            "code",
            None,
            None,
        )
    ]


def test_turn_route_rejects_unknown_fields_and_internal_session():
    client, turns = make_client()

    unknown = client.post(
        "/v1/sessions/session-1/turns",
        headers=AUTH,
        json={"input": "hello", "command": "rm -rf /"},
    )
    internal = client.post(
        "/v1/sessions/__system/turns",
        headers=AUTH,
        json={"input": "hello"},
    )
    relative_workspace = client.post(
        "/v1/sessions/session-1/turns",
        headers=AUTH,
        json={"input": "hello", "workspace": "../other"},
    )

    assert unknown.status_code == 400
    assert unknown.json() == {"detail": "invalid turn payload"}
    assert internal.status_code == 400
    assert relative_workspace.status_code == 400
    assert turns.started == []


def test_turn_route_accepts_bounded_image_and_pdf_attachments(tmp_path):
    client, turns = make_client()
    content = [
        {"type": "text", "text": "Explain these files"},
        {
            "type": "image_url",
            "image_url": {
                "url": "data:image/png;base64,iVBORw0KGgo=",
            },
        },
        {
            "type": "file",
            "file": {
                "filename": "architecture.pdf",
                "file_data": "data:application/pdf;base64,JVBERi0xLjQ=",
            },
        },
    ]

    response = client.post(
        "/v1/sessions/session-1/turns",
        headers=AUTH,
        json={"input": content, "workspace": str(tmp_path)},
    )

    assert response.status_code == 202
    assert turns.started[0][1] == content


def test_turn_route_rejects_remote_invalid_and_unbounded_attachments():
    client, turns = make_client()
    invalid_inputs = [
        [
            {
                "type": "image_url",
                "image_url": {"url": "https://example.test/private.png"},
            }
        ],
        [
            {
                "type": "file",
                "file": {
                    "filename": "../secret.pdf",
                    "file_data": "data:application/pdf;base64,JVBERg==",
                },
            }
        ],
        [
            {
                "type": "image_url",
                "image_url": {"url": "data:image/png;base64,not-base64!"},
            }
        ],
        [
            {
                "type": "image_url",
                "image_url": {"url": "data:image/png;base64,JVBERi0xLjQ="},
            }
        ],
        [
            {
                "type": "image_url",
                "image_url": {
                    "url": "data:image/png;base64,"
                    + ("A" * (14 * 1024 * 1024)),
                },
            }
        ],
    ]

    for content in invalid_inputs:
        response = client.post(
            "/v1/sessions/session-1/turns",
            headers=AUTH,
            json={"input": content},
        )
        assert response.status_code == 400
        assert response.json() == {"detail": "invalid turn payload"}

    assert turns.started == []


def test_turn_reader_stops_stream_when_body_limit_is_exceeded():
    chunks_read = 0

    async def receive():
        nonlocal chunks_read
        chunks_read += 1
        return {
            "type": "http.request",
            "body": b"x" * (1024 * 1024),
            "more_body": chunks_read < 20,
        }

    request = Request(
        {
            "type": "http",
            "method": "POST",
            "path": "/v1/sessions/session-1/turns",
            "headers": [],
        },
        receive,
    )

    with pytest.raises(HTTPException) as error:
        asyncio.run(_read_turn(request))

    assert error.value.status_code == 400
    assert chunks_read == 16


def test_interrupt_route_delegates_without_direct_tool_execution():
    client, turns = make_client()

    response = client.post(
        "/v1/sessions/session-1/interrupt",
        headers=AUTH,
    )

    assert response.status_code == 200
    assert response.json() == {
        "ok": True,
        "session_id": "session-1",
    }
    assert turns.interrupted == ["session-1"]


def test_turn_route_maps_missing_and_busy_without_exception_details():
    class FailingTurns(FakeTurns):
        def __init__(self, error):
            super().__init__()
            self.error = error

        async def start(self, *_args, **_kwargs):
            raise self.error

    missing_client, _ = make_client(
        FailingTurns(SessionNotFoundError("secret-path"))
    )
    busy_client, _ = make_client(
        FailingTurns(SessionBusyError("secret-state"))
    )

    missing = missing_client.post(
        "/v1/sessions/session-1/turns",
        headers=AUTH,
        json={"input": "hello"},
    )
    busy = busy_client.post(
        "/v1/sessions/session-1/turns",
        headers=AUTH,
        json={"input": "hello"},
    )

    assert missing.status_code == 404
    assert missing.json() == {"detail": "session not found"}
    assert "secret-path" not in missing.text
    assert busy.status_code == 409
    assert busy.json() == {
        "detail": "session already has an active turn"
    }
    assert "secret-state" not in busy.text
