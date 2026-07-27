"""Managed policy — organization allowlists with deny precedence.

Loaded once at startup from a JSON file (path via ``CODINAL_MANAGED_POLICY`` env).
The file lives outside ``data_dir`` so the user cannot silently rewrite it.
Managed deny always wins over user allow at every control point.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Optional


@dataclass(frozen=True)
class ManagedPolicy:
    """Organization-level allowlists + denylists. All fields optional.

    ``None`` means "unrestricted" for that dimension.
    """

    allowed_providers: Optional[frozenset[str]] = None
    allowed_models: Optional[frozenset[str]] = None
    denied_tools: frozenset[str] = frozenset()
    denied_commands: frozenset[str] = frozenset()

    @staticmethod
    def from_file(path: Optional[Path]) -> Optional["ManagedPolicy"]:
        """Load from JSON. Returns None if path is None or file absent."""
        if path is None:
            return None
        if not path.is_file():
            return None
        try:
            raw = json.loads(path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, UnicodeDecodeError, OSError):
            return None
        if not isinstance(raw, dict):
            return None
        return ManagedPolicy(
            allowed_providers=_to_frozenset(raw.get("allowed_providers")),
            allowed_models=_to_frozenset(raw.get("allowed_models")),
            denied_tools=_to_frozenset(raw.get("denied_tools")) or frozenset(),
            denied_commands=_to_frozenset(raw.get("denied_commands")) or frozenset(),
        )

    def provider_allowed(self, provider: str) -> bool:
        if self.allowed_providers is None:
            return True
        return provider in self.allowed_providers

    def model_allowed(self, model: str) -> bool:
        if self.allowed_models is None:
            return True
        return model in self.allowed_models

    def tool_allowed(self, name: str) -> bool:
        return name not in self.denied_tools

    def command_allowed(self, command: str) -> bool:
        for denied in self.denied_commands:
            if command == denied or command.startswith(denied + " "):
                return False
        return True

    def to_dict(self) -> dict:
        return {
            "active": True,
            "allowed_providers": (
                sorted(self.allowed_providers) if self.allowed_providers else None
            ),
            "allowed_models": (
                sorted(self.allowed_models) if self.allowed_models else None
            ),
            "denied_tools": sorted(self.denied_tools),
            "denied_commands": sorted(self.denied_commands),
        }


def _to_frozenset(value) -> Optional[frozenset[str]]:
    if value is None:
        return None
    if isinstance(value, list) and all(isinstance(v, str) for v in value):
        return frozenset(value)
    return frozenset()
