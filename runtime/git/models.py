"""Persistent Git worktree state."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from pathlib import Path


class WorktreeState(str, Enum):
    CREATING = "creating"
    ACTIVE = "active"
    APPLIED = "applied"
    CONFLICT = "conflict"
    FAILED = "failed"


@dataclass(frozen=True)
class GitWorkspaceRecord:
    session_id: str
    source_root: Path
    git_common_dir: Path
    source_branch: str
    base_commit: str
    worktree_path: Path
    session_branch: str
    source_dirty: bool
    state: WorktreeState
    created_at: str = ""
    updated_at: str = ""
