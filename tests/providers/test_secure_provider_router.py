import pytest

from runtime.providers import (
    AnthropicProvider,
    GeminiProvider,
    OpenAIProvider,
    ProviderRouter,
)
from runtime.secrets import ProviderSecretService


def test_router_builds_and_caches_supported_cloud_clients() -> None:
    secrets = ProviderSecretService()
    router = ProviderRouter(secrets)

    openai = router.client_for("openai:gpt-5.6-sol")
    anthropic = router.client_for("anthropic:claude-sonnet-4-6")
    gemini = router.client_for("gemini:gemini-2.5-flash")
    zai = router.client_for("zai:glm-4.6")
    deepseek = router.client_for("deepseek:deepseek-chat")

    assert isinstance(openai, OpenAIProvider)
    assert isinstance(anthropic, AnthropicProvider)
    assert isinstance(gemini, GeminiProvider)
    assert isinstance(zai, OpenAIProvider)
    assert isinstance(deepseek, OpenAIProvider)
    assert router.client_for("openai:gpt-5.6-terra") is openai
    assert router.client_for("zai:glm-4.5-air") is zai
    assert router.resolve("anthropic:claude-sonnet-4-6") == (
        anthropic,
        "claude-sonnet-4-6",
    )


def test_router_rejects_unknown_or_ambiguous_provider_prefixes() -> None:
    router = ProviderRouter(ProviderSecretService())

    with pytest.raises(ValueError, match="^unsupported model provider$"):
        router.resolve("unknown:model")
    with pytest.raises(ValueError, match="^invalid model id$"):
        router.resolve("openai:")
    with pytest.raises(ValueError, match="^invalid model id$"):
        router.resolve("openai/gpt-5")


def test_bare_models_use_explicit_default_provider() -> None:
    router = ProviderRouter(
        ProviderSecretService(),
        default_provider="gemini",
    )

    client, bare = router.resolve("gemini-2.5-flash")

    assert isinstance(client, GeminiProvider)
    assert bare == "gemini-2.5-flash"


@pytest.mark.parametrize(
    "url",
    [
        "https://127.0.0.1:11434/v1",
        "http://example.com:11434/v1",
        "http://127.0.0.1:11434",
        "http://user@127.0.0.1:11434/v1",
        "http://127.0.0.1:11434/v1?key=x",
    ],
)
def test_ollama_rejects_non_loopback_or_ambiguous_urls(url) -> None:
    with pytest.raises(ValueError, match="^invalid Ollama URL$"):
        ProviderRouter(ProviderSecretService(), ollama_url=url)


def test_ollama_never_receives_cloud_secret_store() -> None:
    secrets = ProviderSecretService()
    secrets.set_api_key("openai", "cloud-key-must-not-leak")
    router = ProviderRouter(
        secrets,
        ollama_url="http://127.0.0.1:11434/v1",
    )

    client, bare = router.resolve("ollama:qwen2.5-coder:32b")

    assert isinstance(client, OpenAIProvider)
    assert client._api_key == "ollama-local"
    assert client._secrets is None
    assert client._base_url == "http://127.0.0.1:11434/v1"
    assert bare == "qwen2.5-coder:32b"


@pytest.mark.parametrize(
    "model, base_url, profile",
    [
        ("zai:glm-4.6", "https://api.z.ai/api/paas/v4/", "zai"),
        ("deepseek:deepseek-chat", "https://api.deepseek.com", "deepseek"),
    ],
)
def test_openai_compatible_backend_uses_own_endpoint_and_profile(
    model, base_url, profile
) -> None:
    """ZAI/DeepSeek reuse OpenAIProvider but point at their own base_url and
    read their own secret profile — never OpenAI's key."""
    secrets = ProviderSecretService()
    secrets.set_api_key("openai", "openai-key-must-not-leak")
    secrets.set_api_key(profile, f"{profile}-key")
    router = ProviderRouter(secrets)

    client, bare = router.resolve(model)

    assert isinstance(client, OpenAIProvider)
    assert client._base_url == base_url
    assert client._secret_profile == profile
    assert client._secrets is secrets
    # The per-profile key resolves; OpenAI's does not leak across.
    from runtime.providers.openai_provider import resolve_api_key

    assert (
        resolve_api_key(client._secrets, client._secret_profile)
        == f"{profile}-key"
    )
    assert bare == model.split(":", 1)[1]


def test_invalidate_rebuilds_only_selected_provider() -> None:
    router = ProviderRouter(ProviderSecretService())
    old_openai = router.client_for("openai:gpt-5.6-sol")
    old_gemini = router.client_for("gemini:gemini-2.5-flash")

    router.invalidate("openai")

    assert router.client_for("openai:gpt-5.6-sol") is not old_openai
    assert router.client_for("gemini:gemini-2.5-flash") is old_gemini


def test_secret_changes_automatically_invalidate_cached_cloud_client() -> None:
    secrets = ProviderSecretService()
    router = ProviderRouter(secrets)
    old_openai = router.client_for("openai:gpt-5.6-sol")

    secrets.set_api_key("openai", "new-memory-key")

    assert router.client_for("openai:gpt-5.6-sol") is not old_openai
