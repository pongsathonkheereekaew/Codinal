from concurrent.futures import ThreadPoolExecutor

from runtime.oauth import OAuthStateService


def test_oauth_state_is_consumed_exactly_once() -> None:
    service = OAuthStateService(
        token_factory=lambda: "state-token-with-at-least-32-characters",
        clock=lambda: 100.0,
    )
    attempt = service.begin("provider:openai", {"redirect": "codinal://oauth"})

    assert attempt.state == "state-token-with-at-least-32-characters"
    assert attempt.expires_in == 600
    assert service.consume(attempt.state, "provider:openai") == {
        "redirect": "codinal://oauth"
    }
    assert service.consume(attempt.state, "provider:openai") is None


def test_wrong_flow_does_not_consume_valid_state() -> None:
    service = OAuthStateService(
        token_factory=lambda: "state-token-with-at-least-32-characters",
        clock=lambda: 100.0,
    )
    attempt = service.begin("provider:openai", {"pkce": "verifier"})

    assert service.consume(attempt.state, "provider:anthropic") is None
    assert service.consume(attempt.state, "provider:openai") == {
        "pkce": "verifier"
    }


def test_begin_retries_invalid_state_token() -> None:
    tokens = iter(
        [
            "too-short",
            "valid-state-token-with-at-least-32-chars",
        ]
    )
    service = OAuthStateService(
        token_factory=lambda: next(tokens),
        clock=lambda: 100.0,
    )

    attempt = service.begin("provider:openai")

    assert attempt.state == "valid-state-token-with-at-least-32-chars"


def test_pending_capacity_evicts_oldest_attempt() -> None:
    tokens = iter(
        [
            "state-token-000000000000000000000001",
            "state-token-000000000000000000000002",
            "state-token-000000000000000000000003",
        ]
    )
    service = OAuthStateService(
        max_pending=2,
        token_factory=lambda: next(tokens),
        clock=lambda: 100.0,
    )
    first = service.begin("provider:openai")
    second = service.begin("provider:openai")
    third = service.begin("provider:openai")

    assert service.consume(first.state, "provider:openai") is None
    assert service.consume(second.state, "provider:openai") == {}
    assert service.consume(third.state, "provider:openai") == {}


def test_expired_state_is_rejected_and_removed() -> None:
    now = [100.0]
    service = OAuthStateService(
        ttl_seconds=10,
        token_factory=lambda: "state-token-with-at-least-32-characters",
        clock=lambda: now[0],
    )
    attempt = service.begin("provider:openai")
    now[0] = 110.0

    assert service.consume(attempt.state, "provider:openai") is None
    now[0] = 101.0
    assert service.consume(attempt.state, "provider:openai") is None


def test_concurrent_callbacks_have_exactly_one_winner() -> None:
    service = OAuthStateService(
        token_factory=lambda: "state-token-with-at-least-32-characters",
        clock=lambda: 100.0,
    )
    attempt = service.begin("provider:openai", {"code_verifier": "pkce"})

    with ThreadPoolExecutor(max_workers=8) as executor:
        results = list(
            executor.map(
                lambda _: service.consume(
                    attempt.state, "provider:openai"
                ),
                range(16),
            )
        )

    assert results.count({"code_verifier": "pkce"}) == 1
    assert results.count(None) == 15
