"""Fail-closed integration dispatch gateway."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping

from runtime.plugins import CapabilityMatrix, translate_integration
from runtime.providers.capabilities import capabilities_for

from .catalog import CatalogRecord, IntegrationCatalog


class IntegrationResolutionError(ValueError):
    pass


@dataclass(frozen=True)
class ResolvedIntegration:
    record: CatalogRecord
    manifest: dict[str, Any]


class IntegrationResolver:
    """The sole gate for catalog integrity, compatibility, and permissions."""

    def __init__(self, catalog: IntegrationCatalog, capabilities: CapabilityMatrix, *, host: str) -> None:
        self.catalog = catalog
        self.capabilities = capabilities
        self.host = host

    def resolve(self, requested: list[Mapping[str, Any]], *, model: str, granted_permissions: set[str]) -> tuple[ResolvedIntegration, ...]:
        resolved = []
        for item in requested:
            integration_id, version = _request(item)
            record = self.catalog.get(integration_id, version)
            if record is None:
                raise IntegrationResolutionError(f"integration is not installed: {integration_id}@{version}")
            if record.status != "enabled-compatible":
                raise IntegrationResolutionError(f"integration is not dispatchable: {integration_id}@{version} ({record.status})")
            manifest = self.catalog.load_manifest(record)
            translation = self.capabilities.translate(manifest, host=self.host, model=model)
            if not translation.compatible:
                raise IntegrationResolutionError("; ".join(translation.diagnostics))
            missing = set(translation.requested_permissions) - granted_permissions
            if missing:
                raise IntegrationResolutionError(f"integration permissions not granted: {', '.join(sorted(missing))}")
            resolved.append(ResolvedIntegration(record, manifest))
        return tuple(resolved)


def _request(item: Mapping[str, Any]) -> tuple[str, str]:
    integration_id = item.get("id")
    version = item.get("version")
    if not isinstance(integration_id, str) or not isinstance(version, str):
        raise IntegrationResolutionError("integration request requires id and version")
    return integration_id, version
