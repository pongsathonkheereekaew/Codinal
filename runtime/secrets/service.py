"""In-memory provider secrets received from the native desktop host."""

from __future__ import annotations

import json
import re
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
MAX_CUSTOM_SLUG_BYTES = 64
# Custom provider slug: lowercase ascii, alnum or hyphen, cannot start/end with
# hyphen. Matches `custom:<slug>:<model>` ids used across the router + UI.
_CUSTOM_SLUG_RE = re.compile(r"^[a-z0-9][a-z0-9-]{0,63}$")
_CUSTOM_PREFIX = "custom:"

# Providers that may carry a user-configurable base_url alongside the api_key
# (self-hosted OpenAI-compatible gateways). Custom providers (custom:<slug>)
# always carry one; the listed natives opt in individually.
_PROVIDERS_WITH_BASE_URL = frozenset({"omniroute"})


def _valid_profile_keys(data: dict[str, Any]) -> bool:
    """A profile is {api_key} plus optional {base_url, failover_eligible}.

    `failover_eligible` is only meaningful for custom providers (it controls
    whether FailoverRouter may auto-switch to this provider).
    """
    keys = set(data)
    if keys == {"api_key"}:
        return True
    if keys == {"api_key", "base_url"}:
        return True
    return keys == {"api_key", "base_url", "failover_eligible"}


def _is_custom_provider(provider: str) -> bool:
    return provider.startswith(_CUSTOM_PREFIX)


def _custom_slug(provider: str) -> str | None:
    if not _is_custom_provider(provider):
        return None
    return provider[len(_CUSTOM_PREFIX):]


def _validate_custom_slug(slug: str) -> str:
    """Validate and return a normalized custom-provider slug."""
    if not isinstance(slug, str):
        raise ValueError("custom provider slug must be a string")
    normalized = slug.strip().lower()
    if not _CUSTOM_SLUG_RE.match(normalized):
        raise ValueError("invalid custom provider slug")
    if len(normalized.encode("utf-8")) > MAX_CUSTOM_SLUG_BYTES:
        raise ValueError("custom provider slug is too long")
    if normalized.startswith("-") or normalized.endswith("-"):
        raise ValueError("custom provider slug must not start or end with a hyphen")
    return normalized


class ProviderSecretService:
    """Provider credentials that never persist in the Python runtime."""

    def __init__(
        self,
        profiles: dict[str, dict[str, Any]] | None = None,
        *,
        sync_token: str | None = None,
        managed_policy=None,
    ) -> None:
        self._lock = threading.RLock()
        self._profiles: dict[str, dict[str, Any]] = {}
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
                or (
                    "failover_eligible" in data
                    and not isinstance(data["failover_eligible"], bool)
                )
            ):
                raise ValueError("invalid secret profile")
            provider = profile.removeprefix("provider:")
            if _is_custom_provider(provider):
                if "base_url" not in data:
                    raise ValueError("invalid secret profile")
                self.set_custom_provider(
                    _custom_slug(provider) or "",
                    base_url=data["base_url"],
                    api_key=data["api_key"],
                    failover_eligible=bool(data.get("failover_eligible", False)),
                )
            else:
                self.set_api_key(
                    provider,
                    data["api_key"],
                    base_url=data.get("base_url"),
                )

    def get(self, profile: str) -> dict[str, Any] | None:
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

    # --- Custom OpenAI-compatible provider registry (Phase 47A) ---
    #
    # Custom providers are user-registered OpenAI-compatible gateways
    # (OmniRoute, OpenRouter, OneAPI, local vLLM). They live alongside the
    # native SUPPORTED_PROVIDERS but are dynamic: the user adds/removes them
    # at runtime via Settings. Each stores {api_key, base_url, failover_eligible}
    # under `provider:custom:<slug>`.

    def set_custom_provider(
        self,
        slug: str,
        *,
        base_url: str,
        api_key: str,
        failover_eligible: bool = False,
    ) -> dict[str, Any]:
        """Register or update a custom OpenAI-compatible provider."""
        normalized_slug = _validate_custom_slug(slug)
        normalized_key = api_key if isinstance(api_key, str) else ""
        if not normalized_key.strip():
            raise ValueError("api_key must not be empty")
        if normalized_key != normalized_key.strip():
            raise ValueError("api_key must not contain surrounding whitespace")
        if len(normalized_key.encode("utf-8")) > MAX_API_KEY_BYTES:
            raise ValueError("api_key is too large")
        if not isinstance(failover_eligible, bool):
            raise ValueError("failover_eligible must be a boolean")
        provider = f"{_CUSTOM_PREFIX}{normalized_slug}"
        normalized_url = self._validate_base_url(provider, base_url)
        if normalized_url is None:
            raise ValueError("custom provider requires a base_url")
        if self._managed_policy is not None and not self._managed_policy.provider_allowed(provider):
            raise ValueError(f"provider '{provider}' denied by managed policy")
        with self._lock:
            profile = f"provider:{provider}"
            previous = self._profiles.get(profile)
            self._profiles[profile] = {
                "api_key": normalized_key,
                "base_url": normalized_url,
                "failover_eligible": failover_eligible,
            }
            try:
                self._notify(provider)
            except Exception:
                if previous is None:
                    self._profiles.pop(profile, None)
                else:
                    self._profiles[profile] = previous
                raise RuntimeError("provider secret change rejected") from None
        return {
            "slug": normalized_slug,
            "base_url": normalized_url,
            "failover_eligible": failover_eligible,
            "configured": True,
        }

    def delete_custom_provider(self, slug: str) -> dict[str, Any]:
        normalized_slug = _validate_custom_slug(slug)
        provider = f"{_CUSTOM_PREFIX}{normalized_slug}"
        with self._lock:
            profile = f"provider:{provider}"
            previous = self._profiles.pop(profile, None)
            if previous is not None:
                try:
                    self._notify(provider)
                except Exception:
                    self._profiles[profile] = previous
                    raise RuntimeError(
                        "provider secret change rejected"
                    ) from None
        return {"slug": normalized_slug, "configured": False}

    def custom_providers(self) -> list[dict[str, Any]]:
        """List registered custom providers (without exposing api_key)."""
        with self._lock:
            rows: list[dict[str, Any]] = []
            for profile, data in self._profiles.items():
                if not profile.startswith("provider:custom:"):
                    continue
                slug = profile.removeprefix("provider:custom:")
                rows.append({
                    "slug": slug,
                    "base_url": data.get("base_url", ""),
                    "failover_eligible": bool(data.get("failover_eligible", False)),
                })
            rows.sort(key=lambda row: row["slug"])
            return rows

    def is_failover_eligible(self, provider: str) -> bool:
        """Whether a custom provider may participate in auto-failover."""
        with self._lock:
            data = self._profiles.get(f"provider:{provider}")
            if not isinstance(data, dict):
                return False
            return bool(data.get("failover_eligible", False))

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

        Custom providers (`custom:<slug>`) and providers in
        ``_PROVIDERS_WITH_BASE_URL`` may carry one; for all others a non-None
        value is rejected so the wire schema stays tight. Returns the
        normalized URL or None.
        """
        if base_url is None:
            return None
        if provider not in _PROVIDERS_WITH_BASE_URL and not _is_custom_provider(provider):
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
                or (
                    "failover_eligible" in data
                    and not isinstance(data["failover_eligible"], bool)
                )
            ):
                raise ValueError
            provider = profile.removeprefix("provider:")
            if _is_custom_provider(provider):
                if "base_url" not in data:
                    raise ValueError
                service.set_custom_provider(
                    _custom_slug(provider) or "",
                    base_url=data["base_url"],
                    api_key=data["api_key"],
                    failover_eligible=bool(data.get("failover_eligible", False)),
                )
            else:
                service.set_api_key(
                    provider,
                    data["api_key"],
                    base_url=data.get("base_url"),
                )
        return service
    except (json.JSONDecodeError, ValueError, TypeError) as error:
        raise ValueError("invalid secret bootstrap") from error
