# Vendored from andrewyng/openworker@54b4bfd (coworker/risk.py)
# MIT, Copyright (c) 2024 Andrew Ng. Faithful copy.
"""Risk classes for tools — the intrinsic side-effect category that drives
permission gating. Effective risk = optional override ?? manifest metadata ??
built-in fallback table ?? requires_approval ?? read."""
from __future__ import annotations

from enum import Enum
from typing import Any, Callable, Optional


class RiskClass(str, Enum):
    READ = "read"
    WRITE_LOCAL = "write_local"
    EXEC = "exec"
    EXTERNAL = "external"


WRITE_TOOLS = {"write_file", "replace_in_file", "apply_patch", "apply_unified_diff"}
SHELL_TOOL = "run_shell"

_BASE: dict[str, RiskClass] = {
    **{name: RiskClass.WRITE_LOCAL for name in WRITE_TOOLS},
    SHELL_TOOL: RiskClass.EXEC,
}

RiskOverrides = Callable[[str], Optional["RiskClass"]]


def classify(
    tool_name: str, metadata: Any = None, overrides: Optional[RiskOverrides] = None
) -> RiskClass:
    if overrides is not None:
        ov = overrides(tool_name)
        if ov is not None:
            return ov
    declared = getattr(metadata, "risk", None)
    if isinstance(declared, RiskClass):
        return declared
    base = _BASE.get(tool_name)
    if base is not None:
        return base
    if bool(getattr(metadata, "requires_approval", False)):
        return RiskClass.EXTERNAL
    return RiskClass.READ


def is_consequential(risk: RiskClass) -> bool:
    return risk is not RiskClass.READ
