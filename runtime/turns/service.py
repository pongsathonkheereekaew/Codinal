"""One-active-turn-per-session coordinator and event bridge."""

from __future__ import annotations

import asyncio
from pathlib import Path
from typing import Any, AsyncIterator, Callable, Protocol

from runtime.events import Event, EventHub, EventType
from runtime.sessions import (
    SessionService,
    TurnCheckpoint,
    TurnStatus,
)


class SessionNotFoundError(LookupError):
    pass


class SessionBusyError(RuntimeError):
    pass


class SessionWorkspaceError(RuntimeError):
    pass


class ExportBusyError(RuntimeError):
    pass


class CodeCheckpointError(RuntimeError):
    pass


class CodeCheckpointControl(Protocol):
    def begin_checkpoint(
        self,
        session_id: str,
        *,
        message_count: int,
        attributed: bool = False,
    ) -> Any | None: ...

    def capture_checkpoint(
        self,
        session_id: str,
        checkpoint_id: str,
        *,
        message_count: int,
    ) -> Any: ...

    def finalize_checkpoint(
        self,
        session_id: str,
        checkpoint_id: str,
    ) -> Any: ...

    def pending_checkpoint(self, session_id: str) -> Any | None: ...

    def pending_checkpoints(self) -> list[Any]: ...

    def has_pending_restore(self, session_id: str) -> bool: ...


_SHUTDOWN_TIMEOUT_SECONDS = 2.0


class TurnCoordinator:
    def __init__(
        self,
        *,
        sessions: SessionService,
        events: EventHub,
        code_checkpoints: CodeCheckpointControl | None = None,
    ) -> None:
        self._sessions = sessions
        self._events = events
        self._code_checkpoints = code_checkpoints
        self._active: dict[str, asyncio.Task[None]] = {}
        self._engines: dict[str, Any] = {}
        self._retired_engines: list[Any] = []
        self._starting: set[str] = set()
        self._executing: dict[str, set[str]] = {}
        self._snapshot_barrier = asyncio.Lock()
        self._shutting_down = False

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
        if self._shutting_down:
            raise SessionBusyError("turn coordinator is shutting down")
        active = self._active.get(session_id)
        if (
            session_id in self._starting
            or active is not None
            and not active.done()
        ):
            raise SessionBusyError("session already has an active turn")
        if (
            self._code_checkpoints is not None
            and await asyncio.to_thread(
                self._code_checkpoints.has_pending_restore,
                session_id,
            )
        ):
            raise SessionBusyError(
                "session has a pending checkpoint restore"
            )

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
        self._starting.add(session_id)
        try:
            try:
                _prepare_engine_turn(engine)
                code_checkpoint_id = await self._begin_code_checkpoint(
                    session_id,
                    engine,
                )
            except Exception:
                raise CodeCheckpointError(
                    "automatic code checkpoint unavailable"
                ) from None

            task = asyncio.create_task(
                self._run(
                    session_id,
                    engine,
                    user_input,
                    source=source,
                    code_checkpoint_id=code_checkpoint_id,
                )
            )
            self._active[session_id] = task
            self._engines[session_id] = engine
        finally:
            self._starting.discard(session_id)
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

    async def restore_when_idle(
        self,
        restore: Callable[[], dict[str, Any]],
    ) -> dict[str, Any]:
        """Restore durable state while excluding concurrent turn starts."""
        async with self._snapshot_barrier:
            if self.has_active_turns():
                raise SessionBusyError(
                    "session already has an active turn"
                )
            return await asyncio.to_thread(restore)

    async def mutate_when_idle(
        self,
        session_id: str,
        mutation: Callable[[], Any],
    ) -> Any:
        """Run a session mutation outside turns and pending restores."""
        async with self._snapshot_barrier:
            if self.is_active(session_id):
                raise SessionBusyError(
                    "session already has an active turn"
                )
            if (
                self._code_checkpoints is not None
                and await asyncio.to_thread(
                    self._code_checkpoints.has_pending_restore,
                    session_id,
                )
            ):
                raise SessionBusyError(
                    "session has a pending checkpoint restore"
                )
            return await asyncio.to_thread(mutation)

    def has_active_turns(self) -> bool:
        return bool(self._starting) or any(
            not task.done() for task in self._active.values()
        )

    async def shutdown(self) -> bool:
        """Stop live work while preserving its latest durable checkpoint."""
        async with self._snapshot_barrier:
            self._shutting_down = True
            tasks = [
                task
                for task in self._active.values()
                if not task.done()
            ]
            self._retired_engines = [
                engine
                for engine in self._retired_engines
                if not _engine_is_quiescent(engine)
            ]
            active_engines = tuple(self._engines.values())
            engines = active_engines + tuple(
                engine
                for engine in self._retired_engines
                if all(
                    engine is not active
                    for active in active_engines
                )
            )
            for engine in engines:
                try:
                    engine.request_interrupt()
                except Exception:
                    pass
        quiesced = True
        if tasks:
            _, pending = await asyncio.wait(
                tasks,
                timeout=_SHUTDOWN_TIMEOUT_SECONDS,
            )
            quiesced = not pending
            for task in pending:
                task.cancel()
            if pending:
                await asyncio.gather(
                    *pending,
                    return_exceptions=True,
                )
        quiesced = quiesced and all(
            _engine_is_quiescent(engine)
            for engine in engines
        )
        return quiesced

    async def recover(self) -> int:
        """Resume durable non-idle turns exactly once per process."""
        recovered = 0
        async with self._snapshot_barrier:
            records = await asyncio.to_thread(
                self._sessions.recoverable_sessions
            )
            recoverable_ids = {
                record.session_id for record in records
            }
            await self._finalize_idle_checkpoints(
                recoverable_ids
            )
            for record in records:
                session_id = record.session_id
                if self.is_active(session_id):
                    continue
                self._starting.add(session_id)
                try:
                    engine = await asyncio.to_thread(
                        self._sessions.get_engine,
                        session_id,
                    )
                except Exception:
                    try:
                        await asyncio.to_thread(
                            self._sessions.mark_recovery_failed,
                            session_id,
                        )
                    except Exception:
                        pass
                    await self._events.publish_session(
                        session_id,
                        {
                            "type": "error",
                            "error": (
                                "interrupted turn recovery failed"
                            ),
                        },
                    )
                    continue
                finally:
                    self._starting.discard(session_id)
                if engine is None:
                    continue
                active_tool_call_ids = (
                    list(
                        record.turn_checkpoint.active_tool_call_ids
                    )
                    if record.turn_checkpoint.status
                    is TurnStatus.EXECUTING
                    else []
                )
                self._executing[session_id] = set(
                    active_tool_call_ids
                )
                pending_code_checkpoint = (
                    await asyncio.to_thread(
                        self._code_checkpoints.pending_checkpoint,
                        session_id,
                    )
                    if self._code_checkpoints is not None
                    else None
                )
                _prepare_engine_turn(engine)
                task = asyncio.create_task(
                    self._resume(
                        session_id,
                        engine,
                        active_tool_call_ids=active_tool_call_ids,
                        code_checkpoint_id=(
                            str(
                                pending_code_checkpoint.checkpoint_id
                            )
                            if pending_code_checkpoint is not None
                            else None
                        ),
                    )
                )
                self._active[session_id] = task
                self._engines[session_id] = engine
                recovered += 1
        return recovered

    async def _finalize_idle_checkpoints(
        self,
        recoverable_ids: set[str],
    ) -> None:
        if self._code_checkpoints is None:
            return
        sessions = await asyncio.to_thread(
            self._sessions.list_sessions
        )
        message_counts = {
            str(session["session_id"]): int(session["messages"])
            for session in sessions
        }
        pending = await asyncio.to_thread(
            self._code_checkpoints.pending_checkpoints
        )
        for checkpoint in pending:
            session_id = str(checkpoint.session_id)
            if (
                session_id in recoverable_ids
                or not checkpoint.after_tree
                or message_counts.get(session_id)
                != checkpoint.after_message_count
            ):
                continue
            try:
                await asyncio.to_thread(
                    self._code_checkpoints.finalize_checkpoint,
                    session_id,
                    str(checkpoint.checkpoint_id),
                )
            except Exception:
                await self._events.publish_session(
                    session_id,
                    {
                        "type": "error",
                        "error": (
                            "code checkpoint recovery failed"
                        ),
                    },
                )

    async def _run(
        self,
        session_id: str,
        engine: Any,
        user_input: str | list[dict[str, Any]],
        *,
        source: dict[str, Any] | None,
        code_checkpoint_id: str | None,
    ) -> None:
        await self._drive(
            session_id,
            engine,
            engine.run(user_input, source=source),
            code_checkpoint_id=code_checkpoint_id,
        )

    async def _resume(
        self,
        session_id: str,
        engine: Any,
        *,
        active_tool_call_ids: list[str],
        code_checkpoint_id: str | None,
    ) -> None:
        await self._drive(
            session_id,
            engine,
            engine.resume_after_crash(
                active_tool_call_ids=active_tool_call_ids
            ),
            code_checkpoint_id=code_checkpoint_id,
        )

    async def _drive(
        self,
        session_id: str,
        engine: Any,
        events: AsyncIterator[Event],
        *,
        code_checkpoint_id: str | None,
    ) -> None:
        terminal: dict[str, Any] | None = None
        cancelled = False
        durability_failed = False
        try:
            async for event in events:
                message = _wire_event(event)
                if event.type in {
                    EventType.TURN_END,
                    EventType.ERROR,
                    EventType.INTERRUPTED,
                }:
                    terminal = message
                else:
                    checkpoint = self._checkpoint_for_event(
                        session_id,
                        event,
                    )
                    if checkpoint is not None:
                        completed_id = (
                            event.data.get("tool_call_id")
                            if event.type is EventType.TOOL_FINISHED
                            else None
                        )
                        persistence_options: dict[str, Any] = {
                            "checkpoint": checkpoint,
                        }
                        if isinstance(completed_id, str):
                            persistence_options[
                                "completed_tool_call_id"
                            ] = completed_id
                        try:
                            persisted = await asyncio.to_thread(
                                self._sessions.persist_checkpoint,
                                session_id,
                                **persistence_options,
                            )
                        except Exception:
                            durability_failed = True
                            raise
                        if not persisted:
                            durability_failed = True
                            raise RuntimeError(
                                "conversation checkpoint failed"
                            )
                    await self._events.publish_session(
                        session_id,
                        message,
                    )
        except asyncio.CancelledError:
            cancelled = True
            raise
        except Exception:
            terminal = {
                "type": "error",
                "error": "turn execution failed",
            }
        finally:
            if durability_failed:
                await self._events.publish_session(
                    session_id,
                    {
                        "type": "error",
                        "error": "conversation persistence failed",
                    },
                )
            elif (
                not cancelled
                and (
                    not self._shutting_down
                    or terminal is not None
                )
            ):
                checkpoint_captured = True
                if (
                    code_checkpoint_id is not None
                    and self._code_checkpoints is not None
                ):
                    try:
                        await asyncio.to_thread(
                            self._code_checkpoints.capture_checkpoint,
                            session_id,
                            code_checkpoint_id,
                            message_count=len(engine.messages),
                        )
                    except Exception:
                        checkpoint_captured = False
                        await self._events.publish_session(
                            session_id,
                            {
                                "type": "error",
                                "error": (
                                    "code checkpoint persistence failed"
                                ),
                            },
                        )
                if not checkpoint_captured:
                    persisted = False
                else:
                    try:
                        persisted = await asyncio.to_thread(
                            self._sessions.persist_checkpoint,
                            session_id,
                            checkpoint=TurnCheckpoint(),
                        )
                    except Exception:
                        persisted = False
                if (
                    persisted
                    and code_checkpoint_id is not None
                    and self._code_checkpoints is not None
                ):
                    try:
                        await asyncio.to_thread(
                            self._code_checkpoints.finalize_checkpoint,
                            session_id,
                            code_checkpoint_id,
                        )
                    except Exception:
                        await self._events.publish_session(
                            session_id,
                            {
                                "type": "error",
                                "error": (
                                    "code checkpoint persistence failed"
                                ),
                            },
                        )
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
                self._executing.pop(session_id, None)
                if not _engine_is_quiescent(engine):
                    self._retired_engines.append(engine)
            if terminal is not None:
                await self._events.publish_session(session_id, terminal)

    async def _begin_code_checkpoint(
        self,
        session_id: str,
        engine: Any,
    ) -> str | None:
        if self._code_checkpoints is None:
            return None
        checkpoint = await asyncio.to_thread(
            self._code_checkpoints.begin_checkpoint,
            session_id,
            message_count=len(engine.messages),
            attributed=True,
        )
        return (
            str(checkpoint.checkpoint_id)
            if checkpoint is not None
            else None
        )

    def _checkpoint_for_event(
        self,
        session_id: str,
        event: Event,
    ) -> TurnCheckpoint | None:
        executing = self._executing.setdefault(session_id, set())
        if event.type is EventType.TOOL_STARTED:
            tool_call_id = event.data.get("tool_call_id")
            if isinstance(tool_call_id, str):
                executing.add(tool_call_id)
            return TurnCheckpoint.executing(executing)
        if event.type is EventType.TOOL_FINISHED:
            tool_call_id = event.data.get("tool_call_id")
            if isinstance(tool_call_id, str):
                executing.discard(tool_call_id)
            if executing:
                return TurnCheckpoint.executing(executing)
            return TurnCheckpoint(TurnStatus.RUNNING)
        if event.type in {
            EventType.TURN_START,
            EventType.ASSISTANT_MESSAGE,
        }:
            if executing:
                return TurnCheckpoint.executing(executing)
            return TurnCheckpoint(TurnStatus.RUNNING)
        if event.type is EventType.PERMISSION_REQUIRED:
            return TurnCheckpoint(TurnStatus.AWAITING_APPROVAL)
        return None

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


def _engine_is_quiescent(engine: Any) -> bool:
    checker = getattr(engine, "is_quiescent", None)
    return True if checker is None else bool(checker())


def _prepare_engine_turn(engine: Any) -> None:
    prepare = getattr(engine, "prepare_turn", None)
    if callable(prepare):
        prepare()
