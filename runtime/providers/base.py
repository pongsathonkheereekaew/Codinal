# SPDX-License-Identifier: MIT
# Copyright (c) 2024 Andrew Ng
# Adapted from andrewyng/openworker:
# coworker/providers/base.py @
# 54b4bfd82d75704a4079ecea4f8f622aa152dbde.
"""Provider-neutral model access contract."""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, Optional

from runtime.policy import ToolCall, parse_tool_calls


@dataclass
class AssistantTurn:
    text: Optional[str] = None
    tool_calls: list[ToolCall] = field(default_factory=list)
    finish_reason: Optional[str] = None
    raw: Any = field(default=None, repr=False, compare=False)
    reasoning: Optional[str] = None
    extras: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        self.tool_calls = list(
            parse_tool_calls(
                [
                    {
                        "id": call.id,
                        "name": call.name,
                        "arguments": call.arguments,
                    }
                    for call in self.tool_calls
                ]
            )
        )

    @property
    def has_tool_calls(self) -> bool:
        return bool(self.tool_calls)


@dataclass(frozen=True)
class ModelCapabilities:
    tools: bool = True
    vision: bool = False
    pdf: bool = False
    parallel_tool_calls: bool = True
    streaming: bool = True


@dataclass
class StreamChunk:
    text_delta: Optional[str] = None
    reasoning_delta: Optional[str] = None
    turn: Optional[AssistantTurn] = None


class ProviderClient(ABC):
    @abstractmethod
    def complete(
        self,
        *,
        model: str,
        messages: list[dict[str, Any]],
        tools: Optional[list[dict[str, Any]]] = None,
        **settings: Any,
    ) -> AssistantTurn:
        """Return one assistant turn."""

    @abstractmethod
    def capabilities(self, model: str) -> ModelCapabilities:
        """Return capability flags for a model."""

    def stream(
        self,
        *,
        model: str,
        messages: list[dict[str, Any]],
        tools: Optional[list[dict[str, Any]]] = None,
        **settings: Any,
    ):
        yield StreamChunk(
            turn=self.complete(
                model=model,
                messages=messages,
                tools=tools,
                **settings,
            )
        )
