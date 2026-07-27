"""Fail-closed provider routing with isolated local-model credentials."""

from __future__ import annotations

import threading
from typing import Any, Optional
from urllib.parse import urlsplit

from .anthropic_provider import AnthropicProvider
from .base import ProviderClient
from .capabilities import capabilities_for
from .gemini_provider import GeminiProvider
from .openai_provider import OpenAIProvider

_CLOUD_PROVIDERS = {"openai", "anthropic", "gemini", "zai", "deepseek", "omniroute"}
_PROVIDERS = _CLOUD_PROVIDERS | {"ollama"}
_CUSTOM_PREFIX = "custom:"

# OpenAI-compatible cloud backends: provider name → (base_url, secret_profile).
# Each reuses OpenAIProvider with its own endpoint and secret-store entry.
_OPENAI_COMPATIBLE = {
    "zai": ("https://api.z.ai/api/paas/v4/", "zai"),
    "deepseek": ("https://api.deepseek.com", "deepseek"),
}

# OmniRoute is self-hosted (OpenAI-compatible gateway); its base_url is
# user-configurable via Settings rather than hardcoded. Default assumes a
# local gateway on the documented port.
_OMNIROUTE_DEFAULT_URL = "http://localhost:20128/v1"


def _is_custom(provider: str) -> bool:
    return provider.startswith(_CUSTOM_PREFIX)


class ProviderRouter(ProviderClient):
    def __init__(
        self,
        secrets: Any,
        *,
        default_provider: str = "openai",
        ollama_url: str = "http://127.0.0.1:11434/v1",
    ) -> None:
        if default_provider not in _CLOUD_PROVIDERS:
            raise ValueError("unsupported default provider")
        self._validate_ollama_url(ollama_url)
        self._secrets = secrets
        self._default = default_provider
        self._ollama_url = ollama_url
        self._clients: dict[str, ProviderClient] = {}
        self._lock = threading.Lock()
        subscribe = getattr(secrets, "subscribe", None)
        if callable(subscribe):
            subscribe(self.invalidate)

    def resolve(self, model: str) -> tuple[ProviderClient, str]:
        provider, bare = self._split_model(model)
        return self._client(provider), bare

    def client_for(self, model: str) -> ProviderClient:
        return self.resolve(model)[0]

    def invalidate(self, provider: Optional[str] = None) -> None:
        if provider is not None and provider not in _PROVIDERS and not _is_custom(provider):
            raise ValueError("unsupported model provider")
        with self._lock:
            if provider is None:
                self._clients.clear()
            else:
                self._clients.pop(provider, None)

    def complete(
        self,
        *,
        model: str,
        messages: list[dict[str, Any]],
        tools: Optional[list[dict[str, Any]]] = None,
        **settings: Any,
    ):
        client, bare = self.resolve(model)
        return client.complete(
            model=bare,
            messages=messages,
            tools=tools,
            **settings,
        )

    def stream(
        self,
        *,
        model: str,
        messages: list[dict[str, Any]],
        tools: Optional[list[dict[str, Any]]] = None,
        **settings: Any,
    ):
        client, bare = self.resolve(model)
        return client.stream(
            model=bare,
            messages=messages,
            tools=tools,
            **settings,
        )

    def capabilities(self, model: str):
        self._split_model(model)
        return capabilities_for(model)

    def _client(self, provider: str) -> ProviderClient:
        with self._lock:
            client = self._clients.get(provider)
            if client is None:
                if provider == "openai":
                    client = OpenAIProvider(secrets=self._secrets)
                elif provider == "anthropic":
                    client = AnthropicProvider(secrets=self._secrets)
                elif provider == "gemini":
                    client = GeminiProvider(secrets=self._secrets)
                elif provider in _OPENAI_COMPATIBLE:
                    base_url, secret_profile = _OPENAI_COMPATIBLE[provider]
                    client = OpenAIProvider(
                        base_url=base_url,
                        secret_profile=secret_profile,
                        secrets=self._secrets,
                    )
                elif provider == "omniroute":
                    # Self-hosted OpenAI-compatible gateway: base_url comes from
                    # the secret store (user-configurable in Settings), falling
                    # back to the local default if unset.
                    base_url = self._omniroute_base_url()
                    client = OpenAIProvider(
                        base_url=base_url,
                        secret_profile="omniroute",
                        secrets=self._secrets,
                    )
                elif _is_custom(provider):
                    # User-registered OpenAI-compatible gateway (Phase 47A).
                    # base_url + secret_profile both come from the secret store.
                    base_url = self._custom_base_url(provider)
                    client = OpenAIProvider(
                        base_url=base_url,
                        secret_profile=provider,
                        secrets=self._secrets,
                    )
                else:
                    client = OpenAIProvider(
                        api_key="ollama-local",
                        base_url=self._ollama_url,
                        secrets=None,
                    )
                self._clients[provider] = client
            return client

    def _split_model(self, model: str) -> tuple[str, str]:
        if (
            not isinstance(model, str)
            or not 1 <= len(model) <= 256
            or not model.isascii()
            or not model.isprintable()
            or any(character.isspace() for character in model)
        ):
            raise ValueError("invalid model id")
        if ":" not in model:
            if "/" in model:
                raise ValueError("invalid model id")
            return self._default, model
        # Custom providers use a two-segment prefix: `custom:<slug>:<model>`.
        if model.startswith(_CUSTOM_PREFIX):
            remainder = model[len(_CUSTOM_PREFIX):]
            if ":" not in remainder:
                raise ValueError("invalid custom model id")
            slug, bare = remainder.split(":", 1)
            if not slug or not bare:
                raise ValueError("invalid custom model id")
            provider = f"{_CUSTOM_PREFIX}{slug}"
            if not self._custom_provider_known(provider):
                raise ValueError("unknown custom provider")
            return provider, bare
        provider, bare = model.split(":", 1)
        if provider not in _PROVIDERS:
            raise ValueError("unsupported model provider")
        if not bare:
            raise ValueError("invalid model id")
        return provider, bare

    def _custom_provider_known(self, provider: str) -> bool:
        """True if the custom provider is registered in the secret store."""
        lister = getattr(self._secrets, "custom_providers", None)
        if not callable(lister):
            return False
        slug = provider[len(_CUSTOM_PREFIX):]
        return any(row.get("slug") == slug for row in lister())

    @staticmethod
    def _validate_ollama_url(value: str) -> None:
        try:
            parsed = urlsplit(value)
            port = parsed.port
        except (TypeError, ValueError):
            raise ValueError("invalid Ollama URL") from None
        if (
            parsed.scheme != "http"
            or parsed.hostname not in {"localhost", "127.0.0.1", "::1"}
            or port is None
            or not 1 <= port <= 65535
            or parsed.path != "/v1"
            or parsed.username is not None
            or parsed.password is not None
            or parsed.query
            or parsed.fragment
        ):
            raise ValueError("invalid Ollama URL")

    def _omniroute_base_url(self) -> str:
        """Resolve OmniRoute's base_url from the secret store or fall back."""
        getter = getattr(self._secrets, "get_base_url", None)
        if callable(getter):
            value = getter("omniroute")
            if isinstance(value, str) and value:
                return value
        return _OMNIROUTE_DEFAULT_URL

    def _custom_base_url(self, provider: str) -> str:
        """Resolve a custom provider's base_url from the secret store.

        Custom providers must have a base_url (validated at registration); if
        it's somehow missing we raise rather than guess — the client would
        silently hit the default OpenAI endpoint otherwise.
        """
        getter = getattr(self._secrets, "get_base_url", None)
        if callable(getter):
            value = getter(provider)
            if isinstance(value, str) and value:
                return value
        raise RuntimeError(f"custom provider '{provider}' has no base_url")
