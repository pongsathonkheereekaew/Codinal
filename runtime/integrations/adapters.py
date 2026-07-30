"""Host renderers for already-resolved, declarative integration actions."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping


@dataclass(frozen=True)
class RenderedIntegration:
    actions: tuple[dict[str, Any], ...]
    diagnostics: tuple[str, ...]


def render_actions(manifest: Mapping[str, Any], *, supported: set[str]) -> RenderedIntegration:
    """Render only logical actions; never execute plugin-provided code."""
    actions: list[dict[str, Any]] = []
    diagnostics: list[str] = []
    for kind, assets in manifest.get("assets", {}).items():
        if kind not in {"skills", "agents", "mcp"}:
            diagnostics.append(f"rejected unsupported integration asset: {kind}")
            continue
        if kind not in supported:
            diagnostics.append(f"host does not support integration action: {kind}")
            continue
        for asset in assets:
            actions.append({"kind": kind, **dict(asset)})
    return RenderedIntegration(tuple(actions), tuple(diagnostics))
