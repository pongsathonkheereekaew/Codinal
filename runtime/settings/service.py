# SPDX-License-Identifier: MIT
# Copyright (c) 2024 Andrew Ng
# Extracted and adapted from andrewyng/openworker:
# coworker/server/manager.py:1532-1855 @
# 54b4bfd82d75704a4079ecea4f8f622aa152dbde.
"""Persistent, non-secret application settings."""

from __future__ import annotations

import json
import os
import tempfile
from pathlib import Path
from typing import Any, Iterable, Protocol
from urllib.parse import urlsplit

from runtime.storage import UnsupportedSchemaVersionError
from runtime.storage.migrations import (
    backup_file,
    preserve_corrupt_file,
    restore_latest_backup,
    secure_directory,
    secure_file,
)

_PREFERENCES_SCHEMA_VERSION = 1
_ROUTING_PROFILES = {"manual", "quality", "balanced", "economy"}
_STIRLING_LOOPBACK_HOSTS = {"localhost", "127.0.0.1", "::1"}


def _normalize_executable_path(value: Any) -> tuple[str | None, str | None]:
    if not isinstance(value, str):
        return None, "Codex Security path must be a string"
    candidate = value.strip()
    if not candidate:
        return None, None
    if len(candidate.encode("utf-8")) > 4096 or not Path(candidate).is_absolute():
        return None, "Codex Security path must be an absolute path"
    return candidate, None


def _normalize_stirling_url(value: Any) -> tuple[str | None, str | None]:
    if not isinstance(value, str):
        return None, "stirling_url must be a string"
    candidate = value.strip()
    if not candidate:
        return None, None
    try:
        parsed = urlsplit(candidate)
        port = parsed.port
    except ValueError:
        return None, "invalid Stirling URL"
    if parsed.scheme != "http":
        return None, "Stirling URL must use http"
    if (
        parsed.hostname not in _STIRLING_LOOPBACK_HOSTS
        or port is None
        or port == 0
        or parsed.username is not None
        or parsed.password is not None
        or parsed.query
        or parsed.fragment
        or parsed.path not in {"", "/"}
    ):
        return None, "Stirling URL must be a loopback http URL with a port"
    host = parsed.hostname
    assert host is not None
    host_text = f"[{host}]" if ":" in host else host
    return f"http://{host_text}:{port}", None


def _migrate_preferences_to_v1(value: dict[str, Any]) -> None:
    value["schema_version"] = 1


_PREFERENCE_MIGRATIONS = {
    1: _migrate_preferences_to_v1,
}


def _migrate_preferences(
    value: dict[str, Any],
    current_version: int,
) -> dict[str, Any]:
    expected = set(
        range(current_version + 1, _PREFERENCES_SCHEMA_VERSION + 1)
    )
    if expected - set(_PREFERENCE_MIGRATIONS):
        raise RuntimeError("preferences migration chain has a version gap")
    for version in range(
        current_version + 1,
        _PREFERENCES_SCHEMA_VERSION + 1,
    ):
        _PREFERENCE_MIGRATIONS[version](value)
    return value


class PreferenceStore(Protocol):
    def load(self) -> dict[str, Any]: ...

    def save(self, preferences: dict[str, Any]) -> None: ...


class JsonPreferenceStore:
    """Atomic JSON persistence for non-secret preferences."""

    def __init__(self, path: str | Path) -> None:
        self.path = Path(path).expanduser()

    def load(self) -> dict[str, Any]:
        try:
            serialized = self.path.read_text(encoding="utf-8")
        except FileNotFoundError:
            return {}
        try:
            value = json.loads(serialized)
        except json.JSONDecodeError:
            return self._recover()
        if not isinstance(value, dict):
            return self._recover()
        version = value.get("schema_version", 0)
        if not isinstance(version, int) or isinstance(version, bool):
            return self._recover()
        if version < 0 or version > _PREFERENCES_SCHEMA_VERSION:
            raise UnsupportedSchemaVersionError(
                f"preferences schema v{version} is outside supported range "
                f"0..{_PREFERENCES_SCHEMA_VERSION}"
            )
        if version < _PREFERENCES_SCHEMA_VERSION:
            backup_file(
                self.path,
                version,
                _PREFERENCES_SCHEMA_VERSION,
            )
            value = _migrate_preferences(value, version)
            self.save(value)
        return value

    def _recover(self) -> dict[str, Any]:
        preserve_corrupt_file(self.path)
        restored = restore_latest_backup(
            self.path,
            self._valid_backup,
        )
        if restored is not None:
            return self.load()
        recovered = {"schema_version": _PREFERENCES_SCHEMA_VERSION}
        self.save(recovered)
        return recovered

    @staticmethod
    def _valid_backup(path: Path) -> bool:
        try:
            value = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return False
        if not isinstance(value, dict):
            return False
        version = value.get("schema_version", 0)
        return (
            isinstance(version, int)
            and not isinstance(version, bool)
            and 0 <= version <= _PREFERENCES_SCHEMA_VERSION
        )

    def save(self, preferences: dict[str, Any]) -> None:
        preferences = dict(preferences)
        version = preferences.get(
            "schema_version",
            _PREFERENCES_SCHEMA_VERSION,
        )
        if (
            not isinstance(version, int)
            or isinstance(version, bool)
            or version < 0
            or version > _PREFERENCES_SCHEMA_VERSION
        ):
            raise UnsupportedSchemaVersionError(
                "cannot save unsupported preferences schema"
            )
        preferences["schema_version"] = _PREFERENCES_SCHEMA_VERSION
        secure_directory(self.path.parent)
        temporary_path = None
        try:
            with tempfile.NamedTemporaryFile(
                mode="w",
                encoding="utf-8",
                dir=self.path.parent,
                prefix=f".{self.path.name}.",
                suffix=".tmp",
                delete=False,
            ) as temporary:
                temporary_path = Path(temporary.name)
                json.dump(preferences, temporary, indent=2, sort_keys=True)
                temporary.write("\n")
                temporary.flush()
                os.fsync(temporary.fileno())
            os.replace(temporary_path, self.path)
            secure_file(self.path)
        finally:
            if temporary_path is not None:
                temporary_path.unlink(missing_ok=True)


class SettingsService:
    DEFAULT_SESSIONS_PEEK = 5
    DEFAULT_PDF_MAX_PAGES = 20
    DEFAULT_PDF_MAX_MB = 10

    def __init__(
        self,
        store: PreferenceStore,
        *,
        default_model: str,
        curated_models: Iterable[str] = (),
    ) -> None:
        normalized_default = (default_model or "").strip()
        if not normalized_default:
            raise ValueError("default_model must not be empty")
        self._store = store
        self._preferences = store.load()
        self._model = (
            str(self._preferences.get("default_model") or "").strip()
            or normalized_default
        )
        self._curated_models = tuple(
            dict.fromkeys(
                model.strip()
                for model in curated_models
                if isinstance(model, str) and model.strip()
            )
        )

    def view(self) -> dict[str, Any]:
        return {
            "model": self._model,
            "models": self._models(),
            "routing_profile": self._routing_profile(),
            "onboarded": bool(self._preferences.get("onboarded", False)),
            "nav_layout": self._nav_layout(),
            "sessions_peek": self._sessions_peek(),
            "pdf": self._pdf_preferences(),
            "failover_enabled": self._failover_enabled(),
            "stirling_url": self._stirling_url(),
            "codex_security_bin": self._codex_security_bin(),
        }

    def _failover_enabled(self) -> bool:
        """Auto-failover toggle (default True). When off, FailoverRouter
        delegates straight to the wrapped router — zero behavior change."""
        return bool(self._preferences.get("failover_enabled", True))

    def _stirling_url(self) -> str | None:
        normalized, _ = _normalize_stirling_url(
            self._preferences.get("stirling_url", "")
        )
        return normalized

    def _codex_security_bin(self) -> str | None:
        normalized, _ = _normalize_executable_path(
            self._preferences.get("codex_security_bin", "")
        )
        return normalized

    def set_default_model(self, model: str) -> dict[str, Any]:
        normalized = (model or "").strip()
        if not normalized:
            return {"ok": False, "error": "empty model"}
        self._model = normalized
        self._preferences["default_model"] = normalized
        self._persist()
        return {"ok": True, **self.view()}

    def set_routing_profile(self, profile: str) -> dict[str, Any]:
        normalized = (profile or "").strip()
        if normalized not in _ROUTING_PROFILES:
            return {"ok": False, "error": "invalid routing profile"}
        sentinel = object()
        previous = self._preferences.get("routing_profile", sentinel)
        self._preferences["routing_profile"] = normalized
        try:
            self._persist()
        except Exception:
            if previous is sentinel:
                self._preferences.pop("routing_profile", None)
            else:
                self._preferences["routing_profile"] = previous
            raise
        return {"ok": True, "routing_profile": normalized}

    def set_failover_enabled(self, enabled: bool) -> dict[str, Any]:
        normalized = bool(enabled)
        sentinel = object()
        previous = self._preferences.get("failover_enabled", sentinel)
        self._preferences["failover_enabled"] = normalized
        try:
            self._persist()
        except Exception:
            if previous is sentinel:
                self._preferences.pop("failover_enabled", None)
            else:
                self._preferences["failover_enabled"] = previous
            raise
        return {"ok": True, "failover_enabled": normalized}

    def set_stirling_url(self, value: str) -> dict[str, Any]:
        normalized, error = _normalize_stirling_url(value)
        if error:
            return {"ok": False, "error": error}
        sentinel = object()
        previous = self._preferences.get("stirling_url", sentinel)
        if normalized is None:
            self._preferences.pop("stirling_url", None)
        else:
            self._preferences["stirling_url"] = normalized
        try:
            self._persist()
        except Exception:
            if previous is sentinel:
                self._preferences.pop("stirling_url", None)
            else:
                self._preferences["stirling_url"] = previous
            raise
        return {"ok": True, "stirling_url": normalized}

    def set_codex_security_bin(self, value: str) -> dict[str, Any]:
        normalized, error = _normalize_executable_path(value)
        if error:
            return {"ok": False, "error": error}
        sentinel = object()
        previous = self._preferences.get("codex_security_bin", sentinel)
        if normalized is None:
            self._preferences.pop("codex_security_bin", None)
        else:
            self._preferences["codex_security_bin"] = normalized
        try:
            self._persist()
        except Exception:
            if previous is sentinel:
                self._preferences.pop("codex_security_bin", None)
            else:
                self._preferences["codex_security_bin"] = previous
            raise
        return {"ok": True, "codex_security_bin": normalized}

    def set_onboarded(self, value: bool = True) -> dict[str, Any]:
        self._preferences["onboarded"] = bool(value)
        self._persist()
        return {"ok": True, "onboarded": bool(value)}

    def add_model(self, model: str) -> dict[str, Any]:
        normalized = (model or "").strip()
        if not normalized:
            return {"ok": False, "error": "empty model"}
        hidden = [
            item
            for item in self._string_list("hidden_models")
            if item != normalized
        ]
        self._set_list("hidden_models", hidden, remove_empty=True)
        custom = self._string_list("models")
        if normalized not in self._curated_models and normalized not in custom:
            custom.append(normalized)
        self._preferences["models"] = custom
        self._persist()
        return {"ok": True, **self.view()}

    def add_models(self, models: Iterable[str]) -> dict[str, Any]:
        """Persist a batch of discovered models in one atomic preference write."""
        normalized = list(
            dict.fromkeys(
                model.strip()
                for model in models
                if isinstance(model, str) and model.strip()
            )
        )
        if any(
            len(model.encode("utf-8")) > 256
            or any(ord(character) < 32 for character in model)
            for model in normalized
        ):
            return {"ok": False, "error": "invalid model"}
        hidden = [
            item
            for item in self._string_list("hidden_models")
            if item not in normalized
        ]
        self._set_list("hidden_models", hidden, remove_empty=True)
        custom = self._string_list("models")
        for model in normalized:
            if model not in self._curated_models and model not in custom:
                custom.append(model)
        self._preferences["models"] = custom
        self._persist()
        return {"ok": True, **self.view()}

    def remove_model(self, model: str) -> dict[str, Any]:
        normalized = (model or "").strip()
        self._preferences["models"] = [
            item for item in self._string_list("models") if item != normalized
        ]
        if normalized in self._curated_models:
            hidden = self._string_list("hidden_models")
            if normalized not in hidden:
                hidden.append(normalized)
            self._preferences["hidden_models"] = hidden
        self._persist()
        return {"ok": True, **self.view()}

    def set_nav_layout(self, nav_layout: str) -> dict[str, Any]:
        value = "grouped" if (nav_layout or "").strip() == "grouped" else "flat"
        self._preferences["nav_layout"] = value
        self._persist()
        return {"ok": True, "nav_layout": value}

    def set_sessions_peek(self, value: Any) -> dict[str, Any]:
        try:
            normalized = max(1, min(int(value), 50))
        except (TypeError, ValueError):
            return {"ok": False, "error": "sessions_peek must be a number"}
        self._preferences["sessions_peek"] = normalized
        self._persist()
        return {"ok": True, "sessions_peek": normalized}

    def set_pdf_preferences(
        self,
        *,
        fallback: Any = None,
        max_pages: Any = None,
        max_mb: Any = None,
    ) -> dict[str, Any]:
        current = self._pdf_preferences()
        next_fallback = current["fallback"] if fallback is None else fallback
        if next_fallback not in {"text", "images"}:
            return {"ok": False, "error": "pdf fallback must be text or images"}
        try:
            next_pages = (
                current["max_pages"]
                if max_pages is None
                else max(1, min(int(max_pages), 100))
            )
        except (TypeError, ValueError):
            return {"ok": False, "error": "pdf max_pages must be a number"}
        try:
            next_mb = (
                current["max_mb"]
                if max_mb is None
                else max(1, min(int(max_mb), 10))
            )
        except (TypeError, ValueError):
            return {"ok": False, "error": "pdf max_mb must be a number"}

        self._preferences.update(
            {
                "pdf_fallback": next_fallback,
                "pdf_max_pages": next_pages,
                "pdf_max_mb": next_mb,
            }
        )
        self._persist()
        return {"ok": True, "pdf": self._pdf_preferences()}

    def _models(self) -> list[str]:
        hidden = set(self._string_list("hidden_models"))
        candidates = [*self._curated_models, *self._string_list("models")]
        visible = [model for model in candidates if model not in hidden]
        return list(dict.fromkeys([self._model, *visible]))

    def _nav_layout(self) -> str:
        return (
            "grouped"
            if self._preferences.get("nav_layout") == "grouped"
            else "flat"
        )

    def _routing_profile(self) -> str:
        profile = self._preferences.get("routing_profile")
        return profile if profile in _ROUTING_PROFILES else "manual"

    def _sessions_peek(self) -> int:
        try:
            value = int(
                self._preferences.get(
                    "sessions_peek",
                    self.DEFAULT_SESSIONS_PEEK,
                )
            )
        except (TypeError, ValueError):
            value = self.DEFAULT_SESSIONS_PEEK
        return max(1, min(value, 50))

    def _pdf_preferences(self) -> dict[str, Any]:
        fallback = self._preferences.get("pdf_fallback")
        try:
            max_pages = int(
                self._preferences.get(
                    "pdf_max_pages",
                    self.DEFAULT_PDF_MAX_PAGES,
                )
            )
        except (TypeError, ValueError):
            max_pages = self.DEFAULT_PDF_MAX_PAGES
        try:
            max_mb = int(
                self._preferences.get(
                    "pdf_max_mb",
                    self.DEFAULT_PDF_MAX_MB,
                )
            )
        except (TypeError, ValueError):
            max_mb = self.DEFAULT_PDF_MAX_MB
        return {
            "fallback": fallback if fallback in {"text", "images"} else "text",
            "max_pages": max(1, min(max_pages, 100)),
            "max_mb": max(1, min(max_mb, 10)),
        }

    def _string_list(self, key: str) -> list[str]:
        value = self._preferences.get(key)
        if not isinstance(value, list):
            return []
        return [item for item in value if isinstance(item, str) and item]

    def _set_list(
        self, key: str, value: list[str], *, remove_empty: bool = False
    ) -> None:
        if value or not remove_empty:
            self._preferences[key] = value
        else:
            self._preferences.pop(key, None)

    def _persist(self) -> None:
        self._store.save(dict(self._preferences))
