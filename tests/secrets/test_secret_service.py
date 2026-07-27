import io

import pytest

from runtime.secrets import (
    ProviderSecretService,
    load_secret_bootstrap,
)

SYNC_TOKEN = "test-secret-sync-token-with-at-least-32-chars"


def test_provider_secret_service_never_returns_values_in_status() -> None:
    service = ProviderSecretService(
        {
            "provider:openai": {
                "api_key": "sk-test-do-not-leak",
            }
        }
    )

    assert service.status() == [
        {"provider": "anthropic", "configured": False},
        {"provider": "gemini", "configured": False},
        {"provider": "openai", "configured": True},
        {"provider": "zai", "configured": False},
        {"provider": "deepseek", "configured": False},
        {"provider": "github", "configured": False},
    ]
    assert "sk-test-do-not-leak" not in repr(service.status())


def test_provider_secret_service_returns_defensive_copy() -> None:
    service = ProviderSecretService()
    assert service.set_api_key("anthropic", "secret-value") == {
        "provider": "anthropic",
        "configured": True,
    }

    profile = service.get("provider:anthropic")
    assert profile == {"api_key": "secret-value"}
    assert profile is not None
    profile["api_key"] = "changed"

    assert service.get("provider:anthropic") == {
        "api_key": "secret-value"
    }


@pytest.mark.parametrize(
    "provider",
    ["", "unknown", "../openai", "OPENAI", "openai:other"],
)
def test_provider_secret_service_rejects_unknown_provider(
    provider: str,
) -> None:
    service = ProviderSecretService()

    with pytest.raises(ValueError, match="unsupported provider"):
        service.set_api_key(provider, "secret-value")


def test_provider_secret_service_rejects_empty_key() -> None:
    service = ProviderSecretService()

    with pytest.raises(ValueError, match="must not be empty"):
        service.set_api_key("openai", "  ")


def test_provider_secret_service_rejects_oversized_key() -> None:
    service = ProviderSecretService()

    with pytest.raises(ValueError, match="too large"):
        service.set_api_key("openai", "x" * 16_385)


def test_provider_secret_service_delete_is_idempotent() -> None:
    service = ProviderSecretService()
    service.set_api_key("gemini", "secret-value")

    assert service.delete_api_key("gemini") == {
        "provider": "gemini",
        "configured": False,
    }


def test_secret_change_listener_failure_rolls_back_without_echoing_key() -> None:
    marker = "new-key-must-not-echo"
    service = ProviderSecretService()
    service.set_api_key("openai", "old-key")

    def reject(_provider):
        raise RuntimeError(marker)

    service.subscribe(reject)

    with pytest.raises(RuntimeError) as caught:
        service.set_api_key("openai", marker)

    assert str(caught.value) == "provider secret change rejected"
    assert marker not in str(caught.value)
    assert service.get("provider:openai") == {"api_key": "old-key"}
    assert service.delete_api_key("gemini") == {
        "provider": "gemini",
        "configured": False,
    }


def test_load_secret_bootstrap_accepts_known_provider_profiles() -> None:
    stream = io.StringIO(
        '{"sync_token":"' + SYNC_TOKEN + '",'
        '"profiles":{"provider:openai":{"api_key":"openai-secret"},'
        '"provider:gemini":{"api_key":"gemini-secret"}}}'
    )

    service = load_secret_bootstrap(stream)

    assert service.get("provider:openai") == {"api_key": "openai-secret"}
    assert service.get("provider:gemini") == {"api_key": "gemini-secret"}
    assert service.authorize_sync(SYNC_TOKEN)
    assert not service.authorize_sync("wrong-token")


@pytest.mark.parametrize(
    "payload",
    [
        "not-json",
        "[]",
        '{"profiles":{}}',
        '{"sync_token":"too-short","profiles":{}}',
        '{"sync_token":"' + SYNC_TOKEN + '","profiles":[]}',
        '{"sync_token":"' + SYNC_TOKEN + '","profiles":{"provider:unknown":{"api_key":"secret"}}}',
        '{"sync_token":"' + SYNC_TOKEN + '","profiles":{"provider:openai":{"api_key":""}}}',
        '{"sync_token":"' + SYNC_TOKEN + '","profiles":{"provider:openai":{"api_key":123}}}',
        '{"sync_token":"' + SYNC_TOKEN + '","profiles":{"provider:openai":{"api_key":"secret","extra":"x"}}}',
    ],
)
def test_load_secret_bootstrap_fails_closed(payload: str) -> None:
    with pytest.raises(ValueError, match="secret bootstrap"):
        load_secret_bootstrap(io.StringIO(payload))


def test_load_secret_bootstrap_rejects_oversized_payload() -> None:
    payload = (
        '{"sync_token":"' + SYNC_TOKEN + '","profiles":{}}'
        + ("x" * 262_145)
    )

    with pytest.raises(ValueError, match="too large"):
        load_secret_bootstrap(io.StringIO(payload))
