"""Extension package model — manifest + provenance metadata."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


_VALID_KINDS = frozenset({"skill", "plugin", "hook", "mcp", "agent"})


@dataclass(frozen=True)
class ExtensionPackage:
    """A registered extension with provenance metadata.

    ``manifest_hash`` is the SHA-256 of the canonical JSON of the manifest
    dict at registration time. ``verify()`` in the registry re-computes and
    compares to detect tampering.
    """

    id: str
    kind: str
    name: str
    version: str
    publisher: str
    requested_permissions: tuple[str, ...]
    enabled: bool
    manifest_hash: str
    manifest: str  # canonical JSON stored for re-verification

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "kind": self.kind,
            "name": self.name,
            "version": self.version,
            "publisher": self.publisher,
            "requested_permissions": list(self.requested_permissions),
            "enabled": self.enabled,
            "manifest_hash": self.manifest_hash,
        }


def validate_manifest(manifest: Any) -> dict[str, Any]:
    """Validate the shape of an extension manifest dict. Raises ValueError."""
    if not isinstance(manifest, dict):
        raise ValueError("manifest must be a JSON object")
    kind = manifest.get("kind")
    name = manifest.get("name")
    version = manifest.get("version")
    publisher = manifest.get("publisher")
    if kind not in _VALID_KINDS:
        raise ValueError(f"kind must be one of {sorted(_VALID_KINDS)}")
    if not isinstance(name, str) or not 1 <= len(name) <= 128:
        raise ValueError("name must be 1-128 chars")
    if not isinstance(version, str) or not 1 <= len(version) <= 64:
        raise ValueError("version must be 1-64 chars")
    if not isinstance(publisher, str) or not 1 <= len(publisher) <= 128:
        raise ValueError("publisher must be 1-128 chars")
    perms = manifest.get("requested_permissions", [])
    if not isinstance(perms, list) or not all(
        isinstance(p, str) and 1 <= len(p) <= 128 for p in perms
    ):
        raise ValueError("requested_permissions must be a list of strings")
    if len(perms) > 64:
        raise ValueError("too many requested_permissions (max 64)")
    return manifest
