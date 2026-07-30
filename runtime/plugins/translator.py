"""Translate ``codinal.plugin.v1`` manifests without executing their content."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from typing import Any, Mapping

from runtime.providers import ModelCapabilities
from runtime.providers.capabilities import capabilities_for


_SCHEMA = "codinal.plugin.v1"
_ASSET_KINDS = frozenset({"skills", "instructions", "mcp", "agents"})
_EXECUTABLE_ASSET_KINDS = frozenset({"hooks", "scripts", "executables"})
_MODEL_CAPABILITIES = frozenset(ModelCapabilities.__dataclass_fields__)
_MAX_MANIFEST_BYTES = 64 * 1024


@dataclass(frozen=True)
class PluginTranslation:
    """A canonical declarative plugin plus its dispatch compatibility result."""

    plugin_id: str
    publisher: str
    version: str
    host: str
    model: str
    digest: str
    assets: dict[str, tuple[dict[str, Any], ...]]
    requested_permissions: tuple[str, ...]
    compatible: bool
    diagnostics: tuple[str, ...]

    def require_compatible(self) -> None:
        """Raise at the dispatch boundary if this pair cannot run the plugin."""
        if not self.compatible:
            raise PluginCompatibilityError(
                f"cannot dispatch plugin {self.plugin_id}: {'; '.join(self.diagnostics)}"
            )


class PluginCompatibilityError(ValueError):
    """A host/model pair does not meet a plugin's declared requirements."""


@dataclass(frozen=True)
class CapabilityMatrix:
    """Host SSOT combined with conservative model capability defaults."""

    hosts: Mapping[str, Mapping[str, Any]]

    @classmethod
    def from_host_manifest(cls, manifest: Mapping[str, Any]) -> "CapabilityMatrix":
        hosts = manifest.get("hosts") if isinstance(manifest, Mapping) else None
        if not isinstance(hosts, Mapping):
            raise ValueError("host capability manifest must contain a hosts object")
        if not all(isinstance(name, str) and isinstance(entry, Mapping) for name, entry in hosts.items()):
            raise ValueError("host capability manifest contains an invalid host")
        return cls(hosts=hosts)

    @classmethod
    def from_host_manifest_file(cls, path: str) -> "CapabilityMatrix":
        """Load the host capability SSOT supplied by the embedding host."""
        import yaml

        with open(path, encoding="utf-8") as file:
            return cls.from_host_manifest(yaml.safe_load(file))

    def translate(self, manifest: Mapping[str, Any], *, host: str, model: str) -> PluginTranslation:
        host_entry = self.hosts.get(host)
        if not isinstance(host_entry, Mapping):
            data, canonical = _validated_manifest(manifest)
            return _translation(
                data,
                canonical,
                host,
                model,
                (f"host {host} is not declared in the capability matrix",),
            )
        capabilities = host_entry.get("capabilities", {})
        if not isinstance(capabilities, Mapping):
            capabilities = {}
        return translate_plugin(
            manifest,
            host=host,
            host_capabilities=capabilities,
            model=model,
            model_capabilities=capabilities_for(model),
        )


def translate_plugin(
    manifest: Mapping[str, Any],
    *,
    host: str,
    host_capabilities: Mapping[str, Mapping[str, Any]],
    model: str,
    model_capabilities: ModelCapabilities,
) -> PluginTranslation:
    """Validate and translate a plugin, reporting every unmet requirement.

    The translator intentionally returns no executable representation. Callers
    must refuse dispatch whenever ``compatible`` is false.
    """
    data, canonical = _validated_manifest(manifest)
    diagnostics = _compatibility_diagnostics(
        data,
        host=host,
        host_capabilities=host_capabilities,
        model=model,
        model_capabilities=model_capabilities,
    )
    return _translation(data, canonical, host, model, diagnostics)


def _translation(
    manifest: Mapping[str, Any],
    canonical: bytes,
    host: str,
    model: str,
    diagnostics: list[str] | tuple[str, ...],
) -> PluginTranslation:
    return PluginTranslation(
        plugin_id=manifest["id"],
        publisher=manifest["publisher"],
        version=manifest["version"],
        host=host,
        model=model,
        digest=f"sha256:{hashlib.sha256(canonical).hexdigest()}",
        assets={
            kind: tuple(dict(asset) for asset in assets)
            for kind, assets in manifest["assets"].items()
        },
        requested_permissions=tuple(manifest["requested_permissions"]),
        compatible=not diagnostics,
        diagnostics=tuple(diagnostics),
    )


def _validated_manifest(manifest: Mapping[str, Any]) -> tuple[dict[str, Any], bytes]:
    if not isinstance(manifest, Mapping):
        raise ValueError("plugin manifest must be a JSON object")
    allowed = {
        "schema", "id", "version", "publisher", "requested_permissions",
        "host_requirements", "model_requirements", "assets",
    }
    unknown = set(manifest) - allowed
    if unknown:
        raise ValueError("plugin manifest contains unsupported fields")
    data = dict(manifest)
    if data.get("schema") != _SCHEMA:
        raise ValueError(f"schema must be {_SCHEMA}")
    for field, maximum in (("id", 256), ("version", 64), ("publisher", 128)):
        value = data.get(field)
        if not isinstance(value, str) or not value or len(value) > maximum:
            raise ValueError(f"{field} must be a non-empty string up to {maximum} chars")
    for field in ("requested_permissions", "host_requirements", "model_requirements"):
        values = data.get(field, [])
        if not isinstance(values, list) or any(
            not isinstance(value, str) or not value or len(value) > 128
            for value in values
        ):
            raise ValueError(f"{field} must be a list of non-empty strings")
        if len(values) != len(set(values)):
            raise ValueError(f"{field} must not contain duplicates")
        data[field] = values
    unknown_model_requirements = set(data["model_requirements"]) - _MODEL_CAPABILITIES
    if unknown_model_requirements:
        raise ValueError("model_requirements contains unsupported capability")
    assets = data.get("assets")
    if not isinstance(assets, Mapping) or not assets:
        raise ValueError("assets must be a non-empty object")
    executable = set(assets) & _EXECUTABLE_ASSET_KINDS
    if executable:
        raise ValueError(
            f"assets contains unsupported executable content: {sorted(executable)[0]}"
        )
    invalid = set(assets) - _ASSET_KINDS
    if invalid:
        raise ValueError(f"assets contains unsupported kind: {sorted(invalid)[0]}")
    normalized_assets: dict[str, list[dict[str, Any]]] = {}
    for kind, values in assets.items():
        if not isinstance(values, list) or not all(isinstance(value, Mapping) for value in values):
            raise ValueError(f"assets.{kind} must be a list of objects")
        normalized_assets[kind] = [dict(value) for value in values]
    data["assets"] = normalized_assets
    try:
        canonical = json.dumps(data, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()
    except (TypeError, ValueError) as error:
        raise ValueError("plugin manifest must contain JSON values") from error
    if len(canonical) > _MAX_MANIFEST_BYTES:
        raise ValueError("plugin manifest is too large")
    return data, canonical


def _compatibility_diagnostics(
    manifest: Mapping[str, Any],
    *,
    host: str,
    host_capabilities: Mapping[str, Mapping[str, Any]],
    model: str,
    model_capabilities: ModelCapabilities,
) -> list[str]:
    diagnostics = []
    for capability in manifest["host_requirements"]:
        entry = host_capabilities.get(capability, {})
        status = entry.get("status") if isinstance(entry, Mapping) else None
        if status != "supported":
            diagnostics.append(
                f"host {host} lacks verified capability: {capability} ({status or 'missing'})"
            )
    for capability in manifest["model_requirements"]:
        if not getattr(model_capabilities, capability):
            diagnostics.append(f"model {model} lacks capability: {capability}")
    return diagnostics
