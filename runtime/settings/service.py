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


class PreferenceStore(Protocol):
    def load(self) -> dict[str, Any]: ...

    def save(self, preferences: dict[str, Any]) -> None: ...


class JsonPreferenceStore:
    """Atomic JSON persistence for non-secret preferences."""

    def __init__(self, path: str | Path) -> None:
        self.path = Path(path).expanduser()

    def load(self) -> dict[str, Any]:
        try:
            value = json.loads(self.path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return {}
        return value if isinstance(value, dict) else {}

    def save(self, preferences: dict[str, Any]) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
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
            "onboarded": bool(self._preferences.get("onboarded", False)),
            "nav_layout": self._nav_layout(),
            "sessions_peek": self._sessions_peek(),
            "pdf": self._pdf_preferences(),
        }

    def set_default_model(self, model: str) -> dict[str, Any]:
        normalized = (model or "").strip()
        if not normalized:
            return {"ok": False, "error": "empty model"}
        self._model = normalized
        self._preferences["default_model"] = normalized
        self._persist()
        return {"ok": True, **self.view()}

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
