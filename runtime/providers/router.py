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

_CLOUD_PROVIDERS = {"openai", "anthropic", "gemini"}
_PROVIDERS = _CLOUD_PROVIDERS | {"ollama"}


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
        if provider is not None and provider not in _PROVIDERS:
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
        provider, bare = model.split(":", 1)
        if provider not in _PROVIDERS:
            raise ValueError("unsupported model provider")
        if not bare:
            raise ValueError("invalid model id")
        return provider, bare

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
