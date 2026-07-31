"""Deterministic, secret-free v1 control-plane contract export."""

from __future__ import annotations

from typing import Any


def v1_route_surface(app: Any) -> list[dict[str, object]]:
    """Return the complete public v1 HTTP/WebSocket surface in stable order."""
    routes = []
    for route in app.routes:
        path = getattr(route, "path", "")
        if not (path.startswith("/v1/") or path.startswith("/ws/")):
            continue
        methods = sorted(getattr(route, "methods", ()) or ())
        routes.append(
            {
                "path": path,
                "kind": "websocket" if path.startswith("/ws/") else "http",
                "methods": methods,
            }
        )
    return sorted(routes, key=lambda item: (str(item["path"]), str(item["kind"]), item["methods"]))
