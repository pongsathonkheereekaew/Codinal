# Codinal original — declarative tool manifest (harness SSOT per ADR D7).
"""Tool manifest — the declarative registry of tool risk metadata. This is the
harness-owned SSOT (D7: "tool manifest = ชื่อ + perms" lives in harness). In v1
it ships as Python data alongside the engine; Phase 2+ can externalize it to
``harness/policy/tools.yaml`` (user-editable) once the tool surface stabilizes.

A ToolSpec carries the metadata the engine reads (``classify`` falls back to
``requires_approval`` -> EXTERNAL when no by-name base entry exists)."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional

from .risk import RiskClass


@dataclass(frozen=True)
class ToolSpec:
    name: str
    risk: RiskClass
    category: str = "core"            # core | connector | mcp | subagent
    requires_approval: bool = False   # surfaced as metadata.requires_approval
    target_arg: Optional[str] = None  # for external-risk standing rules
    description: str = ""


# v1 built-in tool surface (coding MVP). Connector tools are a non-goal.
DEFAULT_TOOLS: tuple[ToolSpec, ...] = (
    # READ
    ToolSpec("read_file", RiskClass.READ, description="Read a file in the workspace."),
    ToolSpec("list_files", RiskClass.READ, description="List files/dirs."),
    ToolSpec("grep", RiskClass.READ, description="Search file contents."),
    ToolSpec("git_status", RiskClass.READ, description="git status"),
    ToolSpec("git_diff", RiskClass.READ, description="git diff"),
    ToolSpec("git_log", RiskClass.READ, description="git log"),
    # WRITE_LOCAL
    ToolSpec("write_file", RiskClass.WRITE_LOCAL, description="Write/overwrite a file."),
    ToolSpec("replace_in_file", RiskClass.WRITE_LOCAL, description="Surgical string replace."),
    ToolSpec("apply_patch", RiskClass.WRITE_LOCAL, description="Apply unified diff."),
    ToolSpec("apply_unified_diff", RiskClass.WRITE_LOCAL, description="Apply unified diff."),
    # EXEC
    ToolSpec("run_shell", RiskClass.EXEC, description="Run a shell command (sandboxed)."),
    # git mutations are WRITE_LOCAL on the worktree (no push in v1)
    ToolSpec("git_stage", RiskClass.WRITE_LOCAL, description="git add"),
    ToolSpec("git_commit", RiskClass.WRITE_LOCAL, description="git commit on session branch"),
)


@dataclass
class ToolManifest:
    """Registry of tool risk metadata. ``metadata_for`` returns an object the
    PermissionEngine reads via getattr (category / requires_approval)."""
    tools: dict[str, ToolSpec] = field(default_factory=lambda: {t.name: t for t in DEFAULT_TOOLS})

    def add(self, spec: ToolSpec) -> None:
        self.tools[spec.name] = spec

    def remove(self, name: str) -> None:
        """Drop a tool declaration so it can be re-registered later (MCP lifecycle)."""
        self.tools.pop(name, None)

    def metadata_for(self, name: str):
        spec = self.tools.get(name)
        if spec is None:
            return None
        # Cheap object with the attributes classify() / evaluate() read.
        return _Meta(
            spec.risk,
            spec.category,
            spec.requires_approval,
            spec.target_arg,
        )


@dataclass(frozen=True)
class _Meta:
    risk: RiskClass
    category: str
    requires_approval: bool
    target_arg: Optional[str]
