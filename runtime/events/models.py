# SPDX-License-Identifier: MIT
# Copyright (c) 2024 Andrew Ng
# Vendored from andrewyng/openworker:
# coworker/events.py @ 54b4bfd82d75704a4079ecea4f8f622aa152dbde.
"""Provider-neutral turn event contract."""

from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class EventType(str, Enum):
    TURN_START = "turn_start"
    ASSISTANT_DELTA = "assistant_delta"
    REASONING_DELTA = "reasoning_delta"
    ASSISTANT_MESSAGE = "assistant_message"
    TOOL_PROPOSED = "tool_proposed"
    PERMISSION_REQUIRED = "permission_required"
    DIRECTORY_REQUESTED = "directory_requested"
    QUESTION_REQUESTED = "question_requested"
    PLAN_PROPOSED = "plan_proposed"
    TOOL_STARTED = "tool_started"
    TOOL_FINISHED = "tool_finished"
    ITERATION_END = "iteration_end"
    TURN_END = "turn_end"
    ERROR = "error"
    INTERRUPTED = "interrupted"


@dataclass
class Event:
    type: EventType
    data: dict[str, Any] = field(default_factory=dict)
