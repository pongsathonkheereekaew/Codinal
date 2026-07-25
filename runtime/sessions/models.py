# SPDX-License-Identifier: MIT
# Copyright (c) 2024 Andrew Ng
# Derived from andrewyng/openworker:
# coworker/sessions.py and coworker/roots.py @
# 54b4bfd82d75704a4079ecea4f8f622aa152dbde.
"""Session records and workspace roots."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Optional


@dataclass
class SessionRecord:
    session_id: str
    workspace: str
    model: str
    mode: str
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


@dataclass
class RootDir:
    path: Path
    writable: bool = False
    label: str = ""

    def __post_init__(self) -> None:
        self.path = Path(self.path).expanduser().resolve()
        if not self.label:
            self.label = self.path.name or str(self.path)
