# SPDX-License-Identifier: MIT
# Copyright (c) 2024 Andrew Ng
# Extracted and adapted from andrewyng/openworker:
# coworker/server/manager.py:2194-2227 @
# 54b4bfd82d75704a4079ecea4f8f622aa152dbde.
"""Global and per-session async event fan-out."""

from __future__ import annotations

from typing import Any, Awaitable, Callable

Event = dict[str, Any]
Listener = Callable[[Event], Awaitable[None]]
Unsubscribe = Callable[[], None]


class EventHub:
    def __init__(self) -> None:
        self._global_listeners: set[Listener] = set()
        self._session_listeners: dict[str, set[Listener]] = {}

    def subscribe_global(self, listener: Listener) -> Unsubscribe:
        self._global_listeners.add(listener)
        return lambda: self._global_listeners.discard(listener)

    def subscribe_session(
        self, session_id: str, listener: Listener
    ) -> Unsubscribe:
        self._session_listeners.setdefault(session_id, set()).add(listener)
        return lambda: self._unsubscribe_session(session_id, listener)

    async def publish_global(self, message: Event) -> None:
        for listener in tuple(self._global_listeners):
            try:
                await listener(message)
            except Exception:
                self._global_listeners.discard(listener)

    async def publish_session(self, session_id: str, message: Event) -> None:
        for listener in tuple(self._session_listeners.get(session_id, ())):
            try:
                await listener(message)
            except Exception:
                self._unsubscribe_session(session_id, listener)

    def _unsubscribe_session(self, session_id: str, listener: Listener) -> None:
        listeners = self._session_listeners.get(session_id)
        if listeners is None:
            return
        listeners.discard(listener)
        if not listeners:
            self._session_listeners.pop(session_id, None)
