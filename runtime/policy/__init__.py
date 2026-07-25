"""Codinal policy engine — the harness-controlled chokepoint.

Provenance: vendored from andrewyng/openworker@54b4bfd
(coworker/risk.py, coworker/permissions.py), MIT, Copyright (c) 2024 Andrew Ng.
Adapted for Codinal: standing_rule_candidate no longer imports connectors
(deferred — non-goal v1); otherwise faithful.

This is the seam the vendored TurnEngine (runtime/turn_engine) calls before
executing any tool (engine.py:60-78 @ 54b4bfd). It MUST decide allow/deny/ask;
the runtime never bypasses it. Risk classes map to harness agent-guardrails:
read / write_local / exec / external.

Placement: code lives in runtime/ (it runs in the Python sidecar and ships in
the .app bundle). The DECLARATIVE tool manifest + risk posture live in
harness/policy/ (harness SSOT, user-editable). See ADR-0001 D7 + M4.
"""
from .risk import RiskClass, classify, is_consequential
from .permissions import (
    Decision,
    Mode,
    PermissionEngine,
    READ_ONLY_MODES,
    standing_rule_candidate,
)
from .approval import ApprovalOutcome, Approver, deny_all
from .manifest import ToolManifest, ToolSpec

__all__ = [
    "RiskClass",
    "classify",
    "is_consequential",
    "Decision",
    "Mode",
    "PermissionEngine",
    "READ_ONLY_MODES",
    "standing_rule_candidate",
    "ApprovalOutcome",
    "Approver",
    "deny_all",
    "ToolManifest",
    "ToolSpec",
]
