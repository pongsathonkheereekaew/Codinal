# SPDX-License-Identifier: MIT
# Copyright (c) 2024 Andrew Ng
# Derived from andrewyng/openworker:
# coworker/sessions.py and coworker/roots.py @
# 54b4bfd82d75704a4079ecea4f8f622aa152dbde.
"""Session records and workspace roots."""

from __future__ import annotations

import os
import stat
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any, Optional


class TurnStatus(str, Enum):
    IDLE = "idle"
    RUNNING = "running"
    AWAITING_APPROVAL = "awaiting_approval"
    EXECUTING = "executing"


@dataclass(frozen=True)
class TurnCheckpoint:
    status: TurnStatus = TurnStatus.IDLE
    active_tool_call_ids: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if (
            len(set(self.active_tool_call_ids))
            != len(self.active_tool_call_ids)
            or any(
                not isinstance(tool_call_id, str)
                or not 1 <= len(tool_call_id) <= 256
                for tool_call_id in self.active_tool_call_ids
            )
            or (
                self.status is TurnStatus.EXECUTING
                and not self.active_tool_call_ids
            )
            or (
                self.status is not TurnStatus.EXECUTING
                and bool(self.active_tool_call_ids)
            )
        ):
            raise ValueError("invalid turn checkpoint")

    @classmethod
    def executing(
        cls,
        tool_call_ids: set[str],
    ) -> "TurnCheckpoint":
        return cls(
            TurnStatus.EXECUTING,
            tuple(sorted(tool_call_ids)),
        )


@dataclass
class SessionRecord:
    session_id: str
    workspace: str
    model: str
    mode: str
    workspace_device: Optional[int] = None
    workspace_inode: Optional[int] = None
    source_workspace: Optional[str] = None
    messages: list[dict[str, Any]] = field(default_factory=list)
    title: Optional[str] = None
    agent: str = "code"
    message_count: int = 0
    updated_at: Optional[str] = None
    extra_roots: list[dict[str, Any]] = field(default_factory=list)
    grants: dict[str, Any] = field(default_factory=dict)
    pinned: bool = False
    archived: bool = False
    origin: Optional[str] = None
    origin_label: Optional[str] = None
    origin_session_id: Optional[str] = None
    turn_checkpoint: TurnCheckpoint = field(
        default_factory=TurnCheckpoint
    )


@dataclass(frozen=True)
class SessionSearchHit:
    record: SessionRecord
    excerpt: Optional[str] = None
    message_index: Optional[int] = None


@dataclass
class RootDir:
    path: Path
    writable: bool = False
    label: str = ""
    device: Optional[int] = None
    inode: Optional[int] = None

    def __post_init__(self) -> None:
        path = Path(self.path).expanduser()
        resolved = path.resolve(strict=True)
        metadata = os.stat(path, follow_symlinks=False)
        if (
            path.is_symlink()
            or resolved != path.absolute()
            or not stat.S_ISDIR(metadata.st_mode)
        ):
            raise ValueError("root must be a real directory")
        identity = (int(metadata.st_dev), int(metadata.st_ino))
        if self.device is None and self.inode is None:
            self.device, self.inode = identity
        elif (
            self.device is None
            or self.inode is None
            or identity != (self.device, self.inode)
        ):
            raise ValueError("root identity changed")
        self.path = resolved
        if not self.label:
            self.label = self.path.name or str(self.path)
