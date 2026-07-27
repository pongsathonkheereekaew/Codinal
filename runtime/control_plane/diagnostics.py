"""Secret-safe local support bundle for diagnostics.

Assembles a redacted, on-demand diagnostic snapshot for the user to copy/share
when reporting an issue. Built in-process and returned to the desktop host,
which writes it to a user-chosen path (Tauri file dialog). The Copy action IS
the explicit consent — no telemetry, no auto-upload, no background collection.

What goes IN (all secret-safe):
  - runtime version, uptime, component health
  - recent audit events (already redacted by the AuditLedger redactor)
  - provider config state (configured flags only — never keys)
  - session/worker/goal counts (no message bodies)

What stays OUT:
  - provider API keys / OAuth tokens
  - message bodies, tool arguments/results (beyond what's in audit)
  - file contents, workspace paths beyond what audit already recorded
  - any secret the redactor would have scrubbed
"""

from __future__ import annotations

import time
from typing import Any


def build_support_bundle(
    services: Any,
    *,
    started_at: float,
    max_events: int = 200,
) -> dict[str, Any]:
    """Assemble a secret-safe diagnostic bundle.

    Reuses ``_component_health`` (defined in app.py) for the structured health
    block, then layers recent audit events on top. Never pulls message bodies
    or secrets.
    """
    from .app import _component_health

    health = _component_health(services, started_at=started_at)
    audit = getattr(services, "audit", None)
    events: list[dict[str, Any]] = []
    chain_verified: Any = "unavailable"
    if audit is not None and hasattr(audit, "list"):
        try:
            events = audit.list(limit=max_events)
        except Exception:
            events = []
        if hasattr(audit, "verify_chain"):
            try:
                chain_verified = audit.verify_chain()
            except Exception:
                chain_verified = "degraded"
    return {
        "bundle_version": 1,
        "generated_at": time.time(),
        "health": health,
        "audit": {
            "chain_verified": chain_verified,
            "events": events,
        },
    }
