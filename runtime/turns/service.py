"""One-active-turn-per-session coordinator and event bridge."""

from __future__ import annotations

import asyncio
from pathlib import Path
from typing import Any, Callable

from runtime.events import Event, EventHub, EventType
from runtime.sessions import SessionService


class SessionNotFoundError(LookupError):
    pass


class SessionBusyError(RuntimeError):
    pass


class SessionWorkspaceError(RuntimeError):
    pass


class ExportBusyError(RuntimeError):
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
        self._starting: set[str] = set()
        self._snapshot_barrier = asyncio.Lock()

    async def start(
        self,
        session_id: str,
        *,
        user_input: str | list[dict[str, Any]],
        workspace: str | Path | None = None,
        agent: str = "code",
        model: str | None = None,
        source: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        async with self._snapshot_barrier:
            return await self._start(
                session_id,
                user_input=user_input,
                workspace=workspace,
                agent=agent,
                model=model,
                source=source,
            )

    async def _start(
        self,
        session_id: str,
        *,
        user_input: str | list[dict[str, Any]],
        workspace: str | Path | None,
        agent: str,
        model: str | None,
        source: dict[str, Any] | None,
    ) -> dict[str, Any]:
        active = self._active.get(session_id)
        if (
            session_id in self._starting
            or active is not None
            and not active.done()
        ):
            raise SessionBusyError("session already has an active turn")

        self._starting.add(session_id)
        try:
            try:
                engine_options: dict[str, Any] = {
                    "workspace": workspace,
                    "agent": agent,
                }
                if model is not None:
                    engine_options["model"] = model
                engine = await asyncio.to_thread(
                    self._sessions.get_engine,
                    session_id,
                    **engine_options,
                )
            except Exception:
                raise SessionWorkspaceError(
                    "session workspace preparation failed"
                ) from None
        finally:
            self._starting.discard(session_id)
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

    async def export_when_idle(
        self,
        exporter: Callable[[], dict[str, Any]],
    ) -> dict[str, Any]:
        """Take a durable snapshot while excluding new turn starts."""
        async with self._snapshot_barrier:
            if self.has_active_turns():
                raise ExportBusyError(
                    "cannot export while a turn is active"
                )
            return await asyncio.to_thread(exporter)

    def has_active_turns(self) -> bool:
        return bool(self._starting) or any(
            not task.done() for task in self._active.values()
        )

    async def _run(
        self,
        session_id: str,
        engine: Any,
        user_input: str | list[dict[str, Any]],
        *,
        source: dict[str, Any] | None,
    ) -> None:
        terminal: dict[str, Any] | None = None
        try:
            async for event in engine.run(user_input, source=source):
                message = _wire_event(event)
                if event.type in {
                    EventType.TURN_END,
                    EventType.ERROR,
                    EventType.INTERRUPTED,
                }:
                    terminal = message
                else:
                    await self._events.publish_session(
                        session_id,
                        message,
                    )
        except Exception:
            terminal = {
                "type": "error",
                "error": "turn execution failed",
            }
        finally:
            try:
                persisted = await asyncio.to_thread(
                    self._sessions.persist,
                    session_id,
                )
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
            if terminal is not None:
                await self._events.publish_session(session_id, terminal)

    def interrupt(self, session_id: str) -> bool:
        task = self._active.get(session_id)
        engine = self._engines.get(session_id)
        if task is None or task.done() or engine is None:
            return False
        engine.request_interrupt()
        return True

    def is_active(self, session_id: str) -> bool:
        task = self._active.get(session_id)
        return (
            session_id in self._starting
            or task is not None
            and not task.done()
        )

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
