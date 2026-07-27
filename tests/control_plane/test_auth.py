from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient
from starlette.websockets import WebSocketDisconnect

from runtime.control_plane import (
    DEFAULT_ALLOWED_ORIGINS,
    create_control_plane_app,
    websocket_auth_protocol,
)
from runtime.events import EventHub
from runtime.oauth import OAuthCoordinator, OAuthStateService
from runtime.secrets import ProviderSecretService


TOKEN = "test-session-token-with-at-least-32-characters"
SECRET_SYNC_TOKEN = "test-secret-sync-token-with-at-least-32-chars"
ALLOWED_ORIGIN = DEFAULT_ALLOWED_ORIGINS[0]
EMPTY_SECRET_STATUS = [
    {"provider": "anthropic", "configured": False},
    {"provider": "gemini", "configured": False},
    {"provider": "openai", "configured": False},
    {"provider": "zai", "configured": False},
    {"provider": "deepseek", "configured": False},
    {"provider": "omniroute", "configured": False},
    {"provider": "github", "configured": False},
]


class FakeSettings:
    def view(self) -> dict[str, object]:
        return {"model": "test/model", "models": ["test/model"]}


@pytest.fixture
def client() -> TestClient:
    services = SimpleNamespace(
        events=EventHub(),
        settings=FakeSettings(),
        secrets=ProviderSecretService(sync_token=SECRET_SYNC_TOKEN),
        oauth=OAuthCoordinator(),
    )
    return TestClient(create_control_plane_app(token=TOKEN, services=services))


@pytest.mark.parametrize(
    "path",
    [
        "/v1/health",
        "/v1/health?token=" + TOKEN,
        "/v1/settings",
        "/docs",
        "/openapi.json",
        "/missing",
    ],
)
def test_every_http_route_requires_bearer_token(
    client: TestClient, path: str
) -> None:
    response = client.get(path)

    assert response.status_code == 401
    assert response.headers["www-authenticate"] == "Bearer"
    assert response.json() == {"detail": "unauthorized"}


@pytest.mark.parametrize(
    "authorization",
    [
        "Basic abc123",
        "Bearer wrong-token",
        f"bearer {TOKEN}",
        f"Bearer  {TOKEN}",
    ],
)
def test_http_rejects_invalid_authorization(
    client: TestClient, authorization: str
) -> None:
    response = client.get(
        "/v1/health", headers={"Authorization": authorization}
    )

    assert response.status_code == 401


def test_http_accepts_valid_bearer_token(client: TestClient) -> None:
    headers = {"Authorization": f"Bearer {TOKEN}"}

    assert client.get("/v1/health", headers=headers).json() == {
        "status": "ok"
    }
    assert client.get("/v1/settings", headers=headers).json() == {
        "model": "test/model",
        "models": ["test/model"],
    }
    assert client.get("/missing", headers=headers).status_code == 404


def test_provider_secret_route_updates_memory_without_echoing_value(
    client: TestClient,
) -> None:
    headers = {
        "Authorization": f"Bearer {TOKEN}",
        "X-Codinal-Secret-Sync": SECRET_SYNC_TOKEN,
    }

    response = client.put(
        "/v1/secrets/providers/openai",
        headers=headers,
        json={"api_key": "sk-test-do-not-echo"},
    )

    assert response.status_code == 200
    assert response.json() == {"provider": "openai", "configured": True}
    assert "sk-test-do-not-echo" not in response.text
    assert client.get(
        "/v1/secrets/providers", headers=headers
    ).json() == [
        {"provider": "anthropic", "configured": False},
        {"provider": "gemini", "configured": False},
        {"provider": "openai", "configured": True},
        {"provider": "zai", "configured": False},
        {"provider": "deepseek", "configured": False},
        {"provider": "omniroute", "configured": False},
        {"provider": "github", "configured": False},
    ]

    deleted = client.delete(
        "/v1/secrets/providers/openai", headers=headers
    )
    assert deleted.json() == {"provider": "openai", "configured": False}


def test_provider_secret_route_is_authenticated_before_mutation(
    client: TestClient,
) -> None:
    response = client.put(
        "/v1/secrets/providers/openai",
        headers={"X-Codinal-Secret-Sync": SECRET_SYNC_TOKEN},
        json={"api_key": "sk-test-must-not-be-stored"},
    )

    assert response.status_code == 401
    authorized = {"Authorization": f"Bearer {TOKEN}"}
    assert client.get(
        "/v1/secrets/providers", headers=authorized
    ).json() == EMPTY_SECRET_STATUS


def test_provider_secret_route_requires_native_sync_token(
    client: TestClient,
) -> None:
    headers = {"Authorization": f"Bearer {TOKEN}"}

    response = client.put(
        "/v1/secrets/providers/openai",
        headers=headers,
        json={"api_key": "sk-test-must-not-be-stored"},
    )

    assert response.status_code == 403
    assert response.json() == {"detail": "secret sync forbidden"}
    assert client.get(
        "/v1/secrets/providers", headers=headers
    ).json() == EMPTY_SECRET_STATUS


def test_provider_secret_route_rejects_unknown_provider(
    client: TestClient,
) -> None:
    response = client.put(
        "/v1/secrets/providers/unknown",
        headers={
            "Authorization": f"Bearer {TOKEN}",
            "X-Codinal-Secret-Sync": SECRET_SYNC_TOKEN,
        },
        json={"api_key": "secret-value"},
    )

    assert response.status_code == 400
    assert response.json() == {"detail": "unsupported provider"}


def test_provider_secret_validation_error_never_echoes_value(
    client: TestClient,
) -> None:
    response = client.put(
        "/v1/secrets/providers/openai",
        headers={
            "Authorization": f"Bearer {TOKEN}",
            "X-Codinal-Secret-Sync": SECRET_SYNC_TOKEN,
        },
        json={
            "api_key": "sk-test-do-not-echo",
            "unexpected": "also-secret",
        },
    )

    assert response.status_code == 400
    assert response.json() == {"detail": "invalid secret payload"}
    assert "sk-test-do-not-echo" not in response.text
    assert "also-secret" not in response.text


def test_oauth_callback_is_authenticated_consumed_once_and_never_echoes_code() -> None:
    received = []

    async def handler(code, metadata):
        received.append((code, metadata))

    coordinator = OAuthCoordinator(
        OAuthStateService(
            token_factory=lambda: "oauth-state-token-with-at-least-32-chars",
            clock=lambda: 100.0,
        )
    )
    coordinator.register("provider:openai", handler)
    attempt = coordinator.begin("provider:openai", {"pkce": "verifier"})
    services = SimpleNamespace(
        events=EventHub(),
        settings=FakeSettings(),
        secrets=ProviderSecretService(sync_token=SECRET_SYNC_TOKEN),
        oauth=coordinator,
    )
    oauth_client = TestClient(
        create_control_plane_app(token=TOKEN, services=services)
    )
    payload = {
        "flow": "provider:openai",
        "state": attempt.state,
        "code": "authorization-code-must-not-echo",
        "error": "",
    }

    unauthorized = oauth_client.post("/v1/oauth/callback", json=payload)
    webview_only = oauth_client.post(
        "/v1/oauth/callback",
        headers={"Authorization": f"Bearer {TOKEN}"},
        json=payload,
    )
    completed = oauth_client.post(
        "/v1/oauth/callback",
        headers={
            "Authorization": f"Bearer {TOKEN}",
            "X-Codinal-Secret-Sync": SECRET_SYNC_TOKEN,
        },
        json=payload,
    )
    replay = oauth_client.post(
        "/v1/oauth/callback",
        headers={
            "Authorization": f"Bearer {TOKEN}",
            "X-Codinal-Secret-Sync": SECRET_SYNC_TOKEN,
        },
        json=payload,
    )

    assert unauthorized.status_code == 401
    assert webview_only.status_code == 403
    assert completed.status_code == 200
    assert completed.json() == {"ok": True, "flow": "provider:openai"}
    assert "authorization-code-must-not-echo" not in completed.text
    assert replay.status_code == 400
    assert replay.json() == {
        "ok": False,
        "error": "unknown or expired OAuth state",
    }
    assert received == [
        ("authorization-code-must-not-echo", {"pkce": "verifier"})
    ]


def test_allowed_cors_preflight_does_not_require_bearer(
    client: TestClient,
) -> None:
    response = client.options(
        "/v1/settings",
        headers={
            "Origin": ALLOWED_ORIGIN,
            "Access-Control-Request-Method": "GET",
            "Access-Control-Request-Headers": "authorization",
        },
    )

    assert response.status_code == 200
    assert response.headers["access-control-allow-origin"] == ALLOWED_ORIGIN
    assert "authorization" in response.headers[
        "access-control-allow-headers"
    ].lower()


def test_cors_preflight_rejects_unknown_origin(client: TestClient) -> None:
    response = client.options(
        "/v1/settings",
        headers={
            "Origin": "https://attacker.example",
            "Access-Control-Request-Method": "GET",
            "Access-Control-Request-Headers": "authorization",
        },
    )

    assert response.status_code == 400
    assert "access-control-allow-origin" not in response.headers


@pytest.mark.parametrize(
    "path,subprotocols",
    [
        ("/ws/events", []),
        ("/ws/session/test-session", []),
        ("/ws/events", ["codinal.v1"]),
        ("/ws/events", [websocket_auth_protocol(TOKEN)]),
        ("/ws/events", ["codinal.v1", "codinal.auth.wrong-token"]),
        (f"/ws/events?token={TOKEN}", ["codinal.v1"]),
    ],
)
def test_websocket_rejects_missing_or_invalid_protocol_token(
    client: TestClient, path: str, subprotocols: list[str]
) -> None:
    with pytest.raises(WebSocketDisconnect) as exc_info:
        with client.websocket_connect(path, subprotocols=subprotocols):
            pass

    assert exc_info.value.code == 4401


@pytest.mark.parametrize("path", ["/ws/events", "/ws/session/test-session"])
def test_websocket_accepts_protocol_token_and_ping(
    client: TestClient, path: str
) -> None:
    with client.websocket_connect(
        path,
        subprotocols=["codinal.v1", websocket_auth_protocol(TOKEN)],
        headers={"Origin": ALLOWED_ORIGIN},
    ) as socket:
        assert socket.accepted_subprotocol == "codinal.v1"
        socket.send_text("ping")
        assert socket.receive_json() == {"type": "pong"}


def test_websocket_rejects_unknown_supplied_origin(
    client: TestClient,
) -> None:
    with pytest.raises(WebSocketDisconnect) as exc_info:
        with client.websocket_connect(
            "/ws/events",
            subprotocols=["codinal.v1", websocket_auth_protocol(TOKEN)],
            headers={"Origin": "https://attacker.example"},
        ):
            pass

    assert exc_info.value.code == 4403


def test_control_plane_rejects_short_session_token() -> None:
    services = SimpleNamespace(events=EventHub(), settings=FakeSettings())

    with pytest.raises(ValueError, match="at least 32 characters"):
        create_control_plane_app(token="too-short", services=services)


@pytest.mark.parametrize(
    "token",
    [
        "token with spaces that is definitely long enough",
        "token/with/slashes/that/is/long/enough",
        "token.with.dots.that.is.definitely.long.enough",
    ],
)
def test_control_plane_requires_url_safe_session_token(token: str) -> None:
    services = SimpleNamespace(events=EventHub(), settings=FakeSettings())

    with pytest.raises(ValueError, match="URL-safe"):
        create_control_plane_app(token=token, services=services)
