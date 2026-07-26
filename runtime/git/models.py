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


class CheckpointState(str, Enum):
    PENDING = "pending"
    COMPLETED = "completed"


class CheckpointCaptureMode(str, Enum):
    ATTRIBUTED = "attributed"
    WHOLE_TREE = "whole_tree"


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


@dataclass(frozen=True)
class CodeCheckpointRecord:
    checkpoint_id: str
    session_id: str
    before_tree: str
    after_tree: str = ""
    before_message_count: int = 0
    after_message_count: int = 0
    state: CheckpointState = CheckpointState.PENDING
    capture_mode: CheckpointCaptureMode = CheckpointCaptureMode.WHOLE_TREE
    created_at: str = ""
    updated_at: str = ""


@dataclass(frozen=True)
class CheckpointFileRecord:
    checkpoint_id: str
    path: str
    before_blob: str = ""
    after_blob: str = ""
    before_mode: int = 0
    after_mode: int = 0
