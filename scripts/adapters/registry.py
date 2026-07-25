"""Host adapter registry. Returns the adapter class for a host name, or None
when no implemented adapter exists yet (capabilities stay `unverified`)."""
from __future__ import annotations

from adapters.base import Adapter, PolicyLinkAdapter
from adapters.opencode import OpenCodeAdapter

# OpenCode has a full behavioral adapter (Tier-1 verified).
# Every other host uses the config-driven PolicyLinkAdapter — it provisions the
# symlink-based wiring install.sh already performed and reports capabilities
# honestly (host-specific native-permission/config-merge work stays unverified).
_REGISTRY: dict[str, type[Adapter]] = {
    "opencode": OpenCodeAdapter,
    "claude-code": PolicyLinkAdapter,
    "codex": PolicyLinkAdapter,
    "cursor": PolicyLinkAdapter,
    "gemini-cli": PolicyLinkAdapter,
    "zcode": PolicyLinkAdapter,
    "openclaw": PolicyLinkAdapter,
    "hermes": PolicyLinkAdapter,
}


def get(name: str) -> type[Adapter] | None:
    return _REGISTRY.get(name)


def implemented() -> list[str]:
    return sorted(_REGISTRY)
