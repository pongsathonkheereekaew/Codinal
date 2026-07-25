import asyncio

from runtime.oauth import OAuthCoordinator, OAuthStateService


def test_callback_consumes_state_before_invoking_registered_handler() -> None:
    received = []

    async def handler(code, metadata):
        received.append((code, metadata))
        return {"account": "user@example.com"}

    coordinator = OAuthCoordinator(
        OAuthStateService(
            token_factory=lambda: "state-token-with-at-least-32-characters",
            clock=lambda: 100.0,
        )
    )
    coordinator.register("provider:openai", handler)
    attempt = coordinator.begin(
        "provider:openai", {"code_verifier": "pkce-verifier"}
    )

    first = asyncio.run(
        coordinator.complete(
            flow="provider:openai",
            state=attempt.state,
            code="authorization-code",
        )
    )
    replay = asyncio.run(
        coordinator.complete(
            flow="provider:openai",
            state=attempt.state,
            code="authorization-code",
        )
    )

    assert first == {
        "ok": True,
        "flow": "provider:openai",
    }
    assert replay == {"ok": False, "error": "unknown or expired OAuth state"}
    assert received == [
        (
            "authorization-code",
            {"code_verifier": "pkce-verifier"},
        )
    ]


def test_provider_error_consumes_state_without_invoking_handler() -> None:
    calls = []

    async def handler(code, metadata):
        calls.append((code, metadata))

    coordinator = OAuthCoordinator(
        OAuthStateService(
            token_factory=lambda: "state-token-with-at-least-32-characters",
            clock=lambda: 100.0,
        )
    )
    coordinator.register("provider:openai", handler)
    attempt = coordinator.begin("provider:openai")

    result = asyncio.run(
        coordinator.complete(
            flow="provider:openai",
            state=attempt.state,
            code="",
            error="access_denied",
        )
    )

    assert result == {"ok": False, "error": "OAuth authorization failed"}
    assert calls == []
    assert asyncio.run(
        coordinator.complete(
            flow="provider:openai",
            state=attempt.state,
            code="authorization-code",
        )
    ) == {"ok": False, "error": "unknown or expired OAuth state"}


def test_malformed_callback_does_not_consume_valid_state() -> None:
    async def handler(code, metadata):
        return None

    coordinator = OAuthCoordinator(
        OAuthStateService(
            token_factory=lambda: "state-token-with-at-least-32-characters",
            clock=lambda: 100.0,
        )
    )
    coordinator.register("provider:openai", handler)
    attempt = coordinator.begin("provider:openai")

    malformed = asyncio.run(
        coordinator.complete(
            flow="provider:openai",
            state=attempt.state,
            code="authorization-code",
            error="access_denied",
        )
    )
    valid = asyncio.run(
        coordinator.complete(
            flow="provider:openai",
            state=attempt.state,
            code="authorization-code",
        )
    )

    assert malformed == {"ok": False, "error": "invalid OAuth callback"}
    assert valid == {"ok": True, "flow": "provider:openai"}
