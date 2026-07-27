# Vendored from andrewyng/openworker@54b4bfd (coworker/permissions.py)
# MIT, Copyright (c) 2024 Andrew Ng.
# Codinal adaptation: standing_rule_candidate() no longer imports
# coworker.connectors.tool_defs (connectors are a non-goal in v1).
# target_arg_for() returns None locally -> no connector standing rules in v1.
"""Permission engine — decides allow / deny / ask-user for each proposed tool
call. Modes: Plan/Discuss (read-only) · Interactive (auto reads, ask on
writes/commands) · Auto (allow, still path-scoped) · Custom (interactive +
auto-allow configured tools). Refined by argument patterns (path-under-root,
command argv-token prefix) and a session allowlist.

Security note (P0 from handoff, closed by design here): command allowlisting
uses argv-TOKEN prefix matching after rejecting shell operators, NOT string
prefix matching. ``git status`` matches ``git status -s`` but never
``git status && rm -rf ~`` (operators rejected) nor ``git statusfoo``.
"""
from __future__ import annotations

import os
import shlex
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any, Optional

from runtime.path_scope import owns_path

from .risk import (
    RiskClass,
    RiskOverrides,
    classify,
    is_consequential,
)

def _has_shell_operators(command: str) -> bool:
    """Return whether command uses shell syntax outside quoted argv values.

    The executor never invokes a shell, so punctuation inside a quoted
    argument (for example Python source passed to ``python -c``) is data.
    """
    quote: Optional[str] = None
    escaped = False
    index = 0
    while index < len(command):
        character = command[index]
        if escaped:
            escaped = False
        elif character == "\\" and quote != "'":
            escaped = True
        elif quote is not None:
            if character == quote:
                quote = None
        elif character in {"'", '"'}:
            quote = character
        elif character in {";", "&", "|", ">", "<", "`", "(", ")", "\n", "\r"}:
            return True
        elif character == "$" and command[index : index + 2] == "$(":
            return True
        index += 1
    return False


def parse_command_argv(command: str) -> list[str]:
    """Parse a command into argv while refusing shell evaluation syntax."""
    if not isinstance(command, str) or not command.strip():
        raise ValueError("invalid command")
    if len(command) > 32_768 or _has_shell_operators(command):
        raise ValueError("shell syntax is not supported")
    try:
        argv = shlex.split(command)
    except ValueError:
        raise ValueError("invalid command") from None
    if not argv:
        raise ValueError("invalid command")
    return argv


class Mode(str, Enum):
    DISCUSS = "discuss"
    PLAN = "plan"
    INTERACTIVE = "interactive"
    AUTO = "auto"
    CUSTOM = "custom"


READ_ONLY_MODES = frozenset({Mode.DISCUSS, Mode.PLAN})
INTERACTIVE_CONSENT_TOOLS = frozenset(
    {"propose_plan", "request_directory"}
)


@dataclass
class Decision:
    allowed: bool
    reason: str = ""
    needs_user: bool = False
    rule: str = ""


def target_arg_for(tool_name: str) -> Optional[str]:
    # Codinal v1: connectors deferred -> no connector tool has a target arg.
    # Phase 2+ (connectors) populates this from harness/policy/manifest.
    return None


def standing_rule_candidate(
    tool_name: str,
    arguments: dict[str, Any],
    metadata: Any = None,
    overrides: Optional[RiskOverrides] = None,
) -> Optional[str]:
    """Target value iff this call is eligible for a task-scoped standing rule.
    External-risk only; the tool must declare a target argument and name one.
    Codinal v1: always returns None (no connectors)."""
    if classify(tool_name, metadata, overrides) is not RiskClass.EXTERNAL:
        return None
    arg = target_arg_for(tool_name)
    if arg is None:
        return None
    value = str((arguments or {}).get(arg) or "").strip()
    return value or None


@dataclass
class PermissionEngine:
    workspace_root: Path
    mode: Mode = Mode.INTERACTIVE
    allowed_commands: list[str] = field(default_factory=list)
    auto_allow_tools: set[str] = field(default_factory=set)
    session_allow_tools: set[str] = field(default_factory=set)
    session_allow_commands: set[str] = field(default_factory=set)
    task_rules: dict[str, set[str]] = field(default_factory=dict)
    risk_overrides: Optional[RiskOverrides] = None
    roots: Optional[list] = None
    write_scope: tuple[str, ...] = ()
    managed_policy: Any = None  # Optional[ManagedPolicy]

    def __post_init__(self) -> None:
        self.workspace_root = Path(self.workspace_root).expanduser().resolve()
        self.auto_allow_tools = set(self.auto_allow_tools)
        self.write_scope = tuple(self.write_scope)
        if self.roots is None:
            metadata = os.stat(self.workspace_root, follow_symlinks=False)
            self.roots = [
                {
                    "path": self.workspace_root,
                    "writable": True,
                    "_device": int(metadata.st_dev),
                    "_inode": int(metadata.st_ino),
                }
            ]

    def _resolved_roots(self) -> list[tuple[Path, bool]]:
        out: list[tuple[Path, bool]] = []
        for r in self.roots or []:
            if isinstance(r, dict):
                p, w = r["path"], bool(r.get("writable", False))
            elif isinstance(r, (str, Path)):
                p, w = r, True
            else:
                p, w = getattr(r, "path"), bool(getattr(r, "writable", False))
            path = Path(p).expanduser()
            device = (
                r.get("_device")
                if isinstance(r, dict)
                else getattr(r, "device", None)
            )
            inode = (
                r.get("_inode")
                if isinstance(r, dict)
                else getattr(r, "inode", None)
            )
            try:
                resolved = path.resolve(strict=True)
                metadata = os.stat(path, follow_symlinks=False)
                if (
                    device is None
                    or inode is None
                    or path.is_symlink()
                    or resolved != path.absolute()
                    or (int(metadata.st_dev), int(metadata.st_ino))
                    != (int(device), int(inode))
                ):
                    continue
            except (OSError, ValueError):
                continue
            out.append((resolved, w))
        return out

    def evaluate(
        self, tool_name: str, arguments: dict[str, Any], metadata: Any = None
    ) -> Decision:
        arguments = arguments or {}
        # Managed-policy deny precedence: checked BEFORE every allow path.
        # A managed deny is absolute — the user cannot override it.
        if self.managed_policy is not None:
            if not self.managed_policy.tool_allowed(tool_name):
                return Decision(
                    False,
                    f"tool '{tool_name}' denied by managed policy",
                )
            command = arguments.get("command", "")
            if isinstance(command, str) and command:
                if not self.managed_policy.command_allowed(command):
                    return Decision(
                        False,
                        f"command denied by managed policy",
                    )
        is_connector = getattr(metadata, "category", "") == "connector"
        is_interactive = (
            getattr(metadata, "category", "") == "interactive"
            and tool_name in INTERACTIVE_CONSENT_TOOLS
        )
        risk = classify(tool_name, metadata, self.risk_overrides)
        is_write = risk is RiskClass.WRITE_LOCAL
        is_shell = risk is RiskClass.EXEC
        consequential = is_consequential(risk)

        if is_interactive and consequential:
            return Decision(
                True,
                "final consent is handled by the interactive tool",
            )

        if self.mode in READ_ONLY_MODES and consequential:
            return Decision(False, f"{self.mode.value} mode is read-only", needs_user=False)

        if is_write:
            path = arguments.get("path")
            if (
                path is not None
                and self.write_scope
                and not owns_path(
                    self.workspace_root,
                    self.write_scope,
                    path,
                )
            ):
                return Decision(
                    False,
                    f"path is outside worker ownership: {path}",
                )
            if path is not None and not self._under_writable_root(path):
                return Decision(False, f"path is not in a writable directory: {path}")

        if not consequential:
            return Decision(True, "low risk")

        if self.mode is Mode.AUTO:
            return Decision(True, "full access")

        if is_shell:
            command = str(arguments.get("command", ""))
            if self._command_allowed(command):
                return Decision(True, "command on allowlist")
            if command and command in self.session_allow_commands:
                return Decision(True, "command allowed for session")
        if tool_name in self.session_allow_tools and not is_connector:
            return Decision(True, "tool allowed for session")

        if tool_name in self.task_rules:
            target = standing_rule_candidate(
                tool_name, arguments, metadata, self.risk_overrides
            )
            if target and target in self.task_rules[tool_name]:
                rule = f"{tool_name} -> {target}"
                return Decision(True, f"allowed by standing rule: {rule}", rule=rule)

        if self.mode is Mode.CUSTOM and tool_name in self.auto_allow_tools:
            return Decision(True, "auto-allowed by config")

        return Decision(False, "requires approval", needs_user=True)

    def allow_tool_for_session(self, tool_name: str) -> None:
        self.session_allow_tools.add(tool_name)

    def allow_command_for_session(self, command: str) -> None:
        if command:
            self.session_allow_commands.add(command)

    def _candidate(self, path: str) -> Path:
        p = Path(path).expanduser()
        return p.resolve() if p.is_absolute() else (self.workspace_root / p).resolve()

    def _under_writable_root(self, path: str) -> bool:
        candidate = self._candidate(path)
        for rp, writable in self._resolved_roots():
            if not writable:
                continue
            try:
                candidate.relative_to(rp)
                return True
            except ValueError:
                continue
        return False

    def _command_allowed(self, command: str) -> bool:
        try:
            argv = parse_command_argv(command)
        except ValueError:
            return False
        for allowed in self.allowed_commands:
            try:
                prefix = parse_command_argv(allowed)
            except ValueError:
                continue
            if prefix and argv[: len(prefix)] == prefix:
                return True
        return False
