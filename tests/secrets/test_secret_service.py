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
        {"provider": "omniroute", "configured": False},
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


def test_omniroute_base_url_round_trips_through_set_and_get() -> None:
    service = ProviderSecretService()
    service.set_api_key(
        "omniroute",
        "omni-key",
        base_url="http://gateway.local:20128/v1",
    )

    assert service.get_base_url("omniroute") == "http://gateway.local:20128/v1"
    assert service.get("provider:omniroute") == {
        "api_key": "omni-key",
        "base_url": "http://gateway.local:20128/v1",
    }


def test_omniroute_base_url_returns_none_when_unset() -> None:
    service = ProviderSecretService()
    service.set_api_key("omniroute", "omni-key")

    assert service.get_base_url("omniroute") is None


@pytest.mark.parametrize(
    "base_url",
    [
        "ftp://gateway/v1",
        "not-a-url",
        "gateway.local",
        "//missing-scheme",
    ],
)
def test_omniroute_rejects_invalid_base_url(base_url: str) -> None:
    service = ProviderSecretService()
    with pytest.raises(ValueError, match="base_url"):
        service.set_api_key("omniroute", "omni-key", base_url=base_url)


def test_non_opt_in_provider_rejects_base_url() -> None:
    service = ProviderSecretService()
    with pytest.raises(ValueError, match="does not accept a base_url"):
        service.set_api_key("openai", "k", base_url="http://x/v1")


def test_omniroute_base_url_round_trips_through_bootstrap() -> None:
    payload = (
        '{"sync_token":"' + SYNC_TOKEN + '",'
        '"profiles":{"provider:omniroute":'
        '{"api_key":"omni-key","base_url":"http://gateway:20128/v1"}}}'
    )
    service = load_secret_bootstrap(io.StringIO(payload))

    assert service.get_base_url("omniroute") == "http://gateway:20128/v1"
    assert service.get("provider:omniroute")["api_key"] == "omni-key"


def test_custom_provider_round_trip() -> None:
    service = ProviderSecretService()
    service.set_custom_provider(
        "openrouter",
        base_url="https://openrouter.ai/api/v1",
        api_key="sk-or-test",
        failover_eligible=True,
    )

    assert service.custom_providers() == [
        {
            "slug": "openrouter",
            "base_url": "https://openrouter.ai/api/v1",
            "failover_eligible": True,
        }
    ]
    assert service.is_failover_eligible("custom:openrouter") is True


def test_custom_provider_delete() -> None:
    service = ProviderSecretService()
    service.set_custom_provider(
        "x", base_url="http://localhost:8080/v1", api_key="k"
    )
    assert service.custom_providers()

    service.delete_custom_provider("x")

    assert service.custom_providers() == []


def test_custom_provider_rejects_invalid_slug() -> None:
    service = ProviderSecretService()
    with pytest.raises(ValueError, match="slug"):
        service.set_custom_provider(
            "Bad Slug!", base_url="http://x/v1", api_key="k"
        )


def test_custom_provider_requires_base_url() -> None:
    service = ProviderSecretService()
    with pytest.raises(ValueError, match="base_url"):
        service.set_custom_provider("x", base_url="", api_key="k")


def test_custom_provider_rejects_invalid_url() -> None:
    service = ProviderSecretService()
    with pytest.raises(ValueError, match="base_url"):
        service.set_custom_provider(
            "x", base_url="ftp://bad/v1", api_key="k"
        )
