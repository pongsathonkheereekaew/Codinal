"""One-active-turn-per-session coordinator and event bridge."""

from __future__ import annotations

import asyncio
from pathlib import Path
from typing import Any

from runtime.events import Event, EventHub
from runtime.sessions import SessionService


class SessionNotFoundError(LookupError):
    pass


class SessionBusyError(RuntimeError):
    pass


class TurnCoordinator:
    def __init__(
        self,
        *,
        sessions: SessionService,
        events: EventHub,
    ) -> None:
        self._sessions = sessions
        self._events = events
        self._active: dict[str, asyncio.Task[None]] = {}
        self._engines: dict[str, Any] = {}

    async def start(
        self,
        session_id: str,
        *,
        user_input: str | list[dict[str, Any]],
        workspace: str | Path | None = None,
        agent: str = "code",
        source: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        active = self._active.get(session_id)
        if active is not None and not active.done():
            raise SessionBusyError("session already has an active turn")

        engine = self._sessions.get_engine(
            session_id,
            workspace=workspace,
            agent=agent,
        )
        if engine is None:
            raise SessionNotFoundError(session_id)

        task = asyncio.create_task(
            self._run(
                session_id,
                engine,
                user_input,
                source=source,
            )
        )
        self._active[session_id] = task
        self._engines[session_id] = engine
        return {"ok": True, "session_id": session_id}

    async def _run(
        self,
        session_id: str,
        engine: Any,
        user_input: str | list[dict[str, Any]],
        *,
        source: dict[str, Any] | None,
    ) -> None:
        try:
            async for event in engine.run(user_input, source=source):
                await self._events.publish_session(
                    session_id,
                    _wire_event(event),
                )
        except Exception:
            await self._events.publish_session(
                session_id,
                {
                    "type": "error",
                    "error": "turn execution failed",
                },
            )
        finally:
            try:
                persisted = self._sessions.persist(session_id)
            except Exception:
                persisted = False
            if not persisted:
                await self._events.publish_session(
                    session_id,
                    {
                        "type": "error",
                        "error": "conversation persistence failed",
                    },
                )
            current = asyncio.current_task()
            if self._active.get(session_id) is current:
                self._active.pop(session_id, None)
                self._engines.pop(session_id, None)

    def interrupt(self, session_id: str) -> bool:
        task = self._active.get(session_id)
        engine = self._engines.get(session_id)
        if task is None or task.done() or engine is None:
            return False
        engine.request_interrupt()
        return True

    async def wait(self, session_id: str) -> bool:
        task = self._active.get(session_id)
        if task is None:
            return False
        await asyncio.shield(task)
        return True


def _wire_event(event: Event) -> dict[str, Any]:
    return {
        **event.data,
        "type": event.type.value,
    }
