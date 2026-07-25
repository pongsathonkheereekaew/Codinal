# Codinal original — approval port matching the seam engine.py expects
# (coworker/engine.py:29-49 @ 54b4bfd: ApprovalOutcome + PermissionRequest +
# Approver). Vendoring engine.py in Phase 2 will use these verbatim.
"""Approval port — the interactive surface the TurnEngine calls when a tool
needs user approval (Decision.needs_user). The engine yields a
PermissionRequest via the approver; the user's outcome is recorded back into
the PermissionEngine (allow_tool_for_session / allow_command_for_session)."""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Any, Awaitable, Callable


class ApprovalOutcome(str, Enum):
    ONCE = "once"                      # allow this one call only
    ALWAYS_TOOL = "always_tool"        # allow this tool for the session
    ALWAYS_COMMAND = "always_command"  # allow this exact command for the session
    DENY = "deny"


@dataclass
class PermissionRequest:
    tool_name: str
    arguments: dict[str, Any]
    risk: str               # RiskClass value
    reason: str             # why approval is needed
    command: str = ""       # set for EXEC risk (the command string)


# Approver: takes a PermissionRequest, returns the user's decision.
Approver = Callable[[PermissionRequest], Awaitable[ApprovalOutcome]]


async def deny_all(_req: PermissionRequest) -> ApprovalOutcome:
    """Default approver — denies everything. Codinal's host wires the real
    UI-backed approver (WebView prompt -> ApprovalOutcome). Mirrors
    engine.py:_deny_all."""
    return ApprovalOutcome.DENY
