"""In-memory provider secrets received from the native desktop host."""

from __future__ import annotations

import json
import secrets
import threading
from typing import Any, Callable, TextIO
from urllib.parse import urlsplit

SUPPORTED_PROVIDERS = (
    "anthropic",
    "gemini",
    "openai",
    "zai",
    "deepseek",
    "omniroute",
    "github",
)
MAX_BOOTSTRAP_BYTES = 256 * 1024
MAX_API_KEY_BYTES = 16 * 1024
MAX_BASE_URL_BYTES = 512

# Providers that may carry a user-configurable base_url alongside the api_key
# (self-hosted OpenAI-compatible gateways: OmniRoute, future vLLM/LM Studio).
_PROVIDERS_WITH_BASE_URL = frozenset({"omniroute"})


def _valid_profile_keys(data: dict[str, str]) -> bool:
    """A profile is {api_key} optionally plus {base_url} for opt-in providers."""
    keys = set(data)
    if keys == {"api_key"}:
        return True
    return keys == {"api_key", "base_url"}


class ProviderSecretService:
    """Provider credentials that never persist in the Python runtime."""

    def __init__(
        self,
        profiles: dict[str, dict[str, str]] | None = None,
        *,
        sync_token: str | None = None,
        managed_policy=None,
    ) -> None:
        self._lock = threading.RLock()
        self._profiles: dict[str, dict[str, str]] = {}
        self._listeners: list[Callable[[str], None]] = []
        self._sync_token = self._validate_sync_token(sync_token)
        self._managed_policy = managed_policy
        for profile, data in (profiles or {}).items():
            if (
                not isinstance(profile, str)
                or not profile.startswith("provider:")
                or not isinstance(data, dict)
                or not _valid_profile_keys(data)
                or not isinstance(data["api_key"], str)
                or ("base_url" in data and not isinstance(data["base_url"], str))
            ):
                raise ValueError("invalid secret profile")
            self.set_api_key(
                profile.removeprefix("provider:"),
                data["api_key"],
                base_url=data.get("base_url"),
            )

    def get(self, profile: str) -> dict[str, str] | None:
        with self._lock:
            value = self._profiles.get(profile)
            return dict(value) if value is not None else None

    def get_base_url(self, provider: str) -> str | None:
        """Return the configured base_url for an opt-in provider, or None."""
        with self._lock:
            data = self._profiles.get(f"provider:{provider}")
            if not isinstance(data, dict):
                return None
            value = data.get("base_url")
            return value if isinstance(value, str) and value else None

    def snapshot(self) -> dict[str, str]:
        """Return ``{provider: api_key}`` for internal redaction only.

        Co-located callers (the outbound redactor) need the raw key values to
        scrub exact matches before provider send / audit persistence. This
        never crosses a process or trust boundary.
        """
        with self._lock:
            return {
                provider.removeprefix("provider:"): data["api_key"]
                for provider, data in self._profiles.items()
                if isinstance(data, dict) and isinstance(data.get("api_key"), str)
            }

    def authorize_sync(self, candidate: str) -> bool:
        return (
            self._sync_token is not None
            and isinstance(candidate, str)
            and secrets.compare_digest(candidate, self._sync_token)
        )

    def subscribe(self, listener: Callable[[str], None]) -> None:
        if not callable(listener):
            raise ValueError("secret listener must be callable")
        with self._lock:
            self._listeners.append(listener)

    def status(self) -> list[dict[str, Any]]:
        with self._lock:
            configured = set(self._profiles)
        return [
            {
                "provider": provider,
                "configured": f"provider:{provider}" in configured,
            }
            for provider in SUPPORTED_PROVIDERS
        ]

    def set_api_key(
        self,
        provider: str,
        api_key: str,
        *,
        base_url: str | None = None,
    ) -> dict[str, Any]:
        normalized_provider = self._validate_provider(provider)
        if self._managed_policy is not None and not self._managed_policy.provider_allowed(normalized_provider):
            raise ValueError(f"provider '{normalized_provider}' denied by managed policy")
        normalized_key = api_key if isinstance(api_key, str) else ""
        if not normalized_key.strip():
            raise ValueError("api_key must not be empty")
        if normalized_key != normalized_key.strip():
            raise ValueError("api_key must not contain surrounding whitespace")
        if len(normalized_key.encode("utf-8")) > MAX_API_KEY_BYTES:
            raise ValueError("api_key is too large")
        normalized_base_url = self._validate_base_url(normalized_provider, base_url)
        with self._lock:
            profile = f"provider:{normalized_provider}"
            previous = self._profiles.get(profile)
            new_profile: dict[str, str] = {"api_key": normalized_key}
            if normalized_base_url is not None:
                new_profile["base_url"] = normalized_base_url
            self._profiles[profile] = new_profile
            try:
                self._notify(normalized_provider)
            except Exception:
                if previous is None:
                    self._profiles.pop(profile, None)
                else:
                    self._profiles[profile] = previous
                raise RuntimeError("provider secret change rejected") from None
        return {"provider": normalized_provider, "configured": True}

    def delete_api_key(self, provider: str) -> dict[str, Any]:
        normalized_provider = self._validate_provider(provider)
        with self._lock:
            profile = f"provider:{normalized_provider}"
            previous = self._profiles.pop(profile, None)
            if previous is not None:
                try:
                    self._notify(normalized_provider)
                except Exception:
                    self._profiles[profile] = previous
                    raise RuntimeError(
                        "provider secret change rejected"
                    ) from None
        return {"provider": normalized_provider, "configured": False}

    def _notify(self, provider: str) -> None:
        for listener in tuple(self._listeners):
            listener(provider)

    @staticmethod
    def _validate_provider(provider: str) -> str:
        normalized = provider.strip() if isinstance(provider, str) else ""
        if normalized not in SUPPORTED_PROVIDERS:
            raise ValueError("unsupported provider")
        return normalized

    @staticmethod
    def _validate_base_url(provider: str, base_url: str | None) -> str | None:
        """Validate an optional self-hosted base_url for opt-in providers.

        Only providers in ``_PROVIDERS_WITH_BASE_URL`` may carry one; for all
        others a non-None value is rejected so the wire schema stays tight.
        Returns the normalized URL or None.
        """
        if base_url is None:
            return None
        if provider not in _PROVIDERS_WITH_BASE_URL:
            raise ValueError(f"provider '{provider}' does not accept a base_url")
        if not isinstance(base_url, str):
            raise ValueError("base_url must be a string")
        normalized = base_url.strip()
        if not normalized:
            return None
        if len(normalized.encode("utf-8")) > MAX_BASE_URL_BYTES:
            raise ValueError("base_url is too large")
        try:
            parsed = urlsplit(normalized)
        except (TypeError, ValueError) as error:
            raise ValueError("invalid base_url") from error
        if parsed.scheme not in {"http", "https"} or not parsed.netloc:
            raise ValueError("base_url must be an http(s) URL")
        return normalized

    @staticmethod
    def _validate_sync_token(sync_token: str | None) -> str | None:
        if sync_token is None:
            return None
        if (
            not isinstance(sync_token, str)
            or len(sync_token) < 32
            or not all(
                character.isascii()
                and (character.isalnum() or character in "-_")
                for character in sync_token
            )
        ):
            raise ValueError("invalid secret sync token")
        return sync_token


def load_secret_bootstrap(stream: TextIO) -> ProviderSecretService:
    payload = stream.read(MAX_BOOTSTRAP_BYTES + 1)
    if len(payload.encode("utf-8")) > MAX_BOOTSTRAP_BYTES:
        raise ValueError("secret bootstrap is too large")
    try:
        document = json.loads(payload)
        if (
            not isinstance(document, dict)
            or set(document) != {"profiles", "sync_token"}
            or not isinstance(document["profiles"], dict)
            or not isinstance(document["sync_token"], str)
        ):
            raise ValueError
        service = ProviderSecretService(sync_token=document["sync_token"])
        for profile, data in document["profiles"].items():
            if (
                not isinstance(profile, str)
                or not profile.startswith("provider:")
                or not isinstance(data, dict)
                or not _valid_profile_keys(data)
                or not isinstance(data["api_key"], str)
                or ("base_url" in data and not isinstance(data["base_url"], str))
            ):
                raise ValueError
            service.set_api_key(
                profile.removeprefix("provider:"),
                data["api_key"],
                base_url=data.get("base_url"),
            )
        return service
    except (json.JSONDecodeError, ValueError, TypeError) as error:
        raise ValueError("invalid secret bootstrap") from error
