"""One-active-turn-per-session coordinator and event bridge."""

from __future__ import annotations

import asyncio
from pathlib import Path
from typing import Any, AsyncIterator, Awaitable, Callable, Protocol
from uuid import uuid4

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


class SessionModelError(RuntimeError):
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
        self._waiting: set[str] = set()
        self._durability_tasks: set[asyncio.Task[Any]] = set()
        self._outcomes: dict[str, dict[str, Any]] = {}
        self._turn_ids: dict[str, str] = {}
        self._turn_tasks: dict[str, asyncio.Task[None]] = {}
        self._turn_receipts: dict[str, dict[str, Any]] = {}
        self._snapshot_barrier = asyncio.Lock()
        self._shutting_down = False

    async def start(
        self,
        session_id: str,
        *,
        user_input: str | list[dict[str, Any]],
        workspace: str | Path | None = None,
        agent: str = "code",
        mode: str | None = None,
        model: str | None = None,
        source: dict[str, Any] | None = None,
        user_input_resolver: Callable[
            [], Awaitable[str | list[dict[str, Any]]]
        ]
        | None = None,
    ) -> dict[str, Any]:
        async with self._snapshot_barrier:
            return await self._start(
                session_id,
                user_input=user_input,
                workspace=workspace,
                agent=agent,
                mode=mode,
                model=model,
                source=source,
                user_input_resolver=user_input_resolver,
            )

    async def _start(
        self,
        session_id: str,
        *,
        user_input: str | list[dict[str, Any]],
        workspace: str | Path | None,
        agent: str,
        mode: str | None,
        model: str | None,
        source: dict[str, Any] | None,
        user_input_resolver: Callable[
            [], Awaitable[str | list[dict[str, Any]]]
        ]
        | None,
    ) -> dict[str, Any]:
        if self._shutting_down:
            raise SessionBusyError("turn coordinator is shutting down")
        if workspace is None and not self._sessions.exists(session_id):
            raise SessionNotFoundError(session_id)
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
                if mode is not None:
                    engine_options["mode"] = mode
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
        if user_input_resolver is not None:
            user_input = await user_input_resolver()
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
            if model is not None:
                try:
                    model_options: dict[str, Any] = {}
                    if (
                        isinstance(source, dict)
                        and isinstance(source.get("routing"), dict)
                    ):
                        model_options["routing"] = source["routing"]
                    switched = await asyncio.to_thread(
                        self._sessions.set_model,
                        session_id,
                        model,
                        **model_options,
                    )
                except Exception:
                    switched = {"ok": False}
                if not switched.get("ok"):
                    if (
                        code_checkpoint_id is not None
                        and self._code_checkpoints is not None
                    ):
                        try:
                            await asyncio.to_thread(
                                self._code_checkpoints.finalize_checkpoint,
                                session_id,
                                code_checkpoint_id,
                            )
                        except Exception:
                            pass
                    raise SessionModelError(
                        "session model update failed"
                    )

            turn_id = f"turn-{uuid4()}"
            task = asyncio.create_task(
                self._run(
                    session_id,
                    turn_id,
                    engine,
                    user_input,
                    source=source,
                    code_checkpoint_id=code_checkpoint_id,
                )
            )
            self._outcomes.pop(session_id, None)
            self._active[session_id] = task
            self._turn_ids[session_id] = turn_id
            self._turn_tasks[turn_id] = task
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
            durability_quiesced = True
            durability_deadline = (
                asyncio.get_running_loop().time()
                + _SHUTDOWN_TIMEOUT_SECONDS
            )
            while self._durability_tasks:
                remaining = (
                    durability_deadline
                    - asyncio.get_running_loop().time()
                )
                if remaining <= 0:
                    durability_quiesced = False
                    break
                _, pending_durability = await asyncio.wait(
                    tuple(self._durability_tasks),
                    timeout=remaining,
                )
                if pending_durability:
                    durability_quiesced = False
                    break
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
                session_id = next(
                    (
                        candidate
                        for candidate, active in self._engines.items()
                        if active is engine
                    ),
                    None,
                )
                if session_id in self._waiting:
                    task = self._active.get(str(session_id))
                    if task is not None and not task.done():
                        task.cancel()
                    continue
                try:
                    engine.request_interrupt()
                except Exception:
                    pass
        quiesced = durability_quiesced
        if tasks:
            _, pending = await asyncio.wait(
                tasks,
                timeout=_SHUTDOWN_TIMEOUT_SECONDS,
            )
            quiesced = quiesced and not pending
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
                if (
                    pending_code_checkpoint is None
                    and self._code_checkpoints is not None
                ):
                    before_message_count = next(
                        (
                            index
                            for index in range(
                                len(record.messages) - 1,
                                -1,
                                -1,
                            )
                            if record.messages[index].get("role")
                            == "user"
                        ),
                        len(record.messages),
                    )
                    pending_code_checkpoint = (
                        await asyncio.to_thread(
                            self._code_checkpoints.begin_checkpoint,
                            session_id,
                            message_count=before_message_count,
                            attributed=True,
                        )
                    )
                _prepare_engine_turn(engine)
                turn_id = f"turn-{uuid4()}"
                task = asyncio.create_task(
                    self._resume(
                        session_id,
                        turn_id,
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
                self._turn_ids[session_id] = turn_id
                self._turn_tasks[turn_id] = task
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
        turn_id: str,
        engine: Any,
        user_input: str | list[dict[str, Any]],
        *,
        source: dict[str, Any] | None,
        code_checkpoint_id: str | None,
    ) -> None:
        await self._drive(
            session_id,
            turn_id,
            engine,
            engine.run(user_input, source=source),
            code_checkpoint_id=code_checkpoint_id,
        )

    async def _resume(
        self,
        session_id: str,
        turn_id: str,
        engine: Any,
        *,
        active_tool_call_ids: list[str],
        code_checkpoint_id: str | None,
    ) -> None:
        await self._drive(
            session_id,
            turn_id,
            engine,
            engine.resume_after_crash(
                active_tool_call_ids=active_tool_call_ids
            ),
            code_checkpoint_id=code_checkpoint_id,
        )

    async def _drive(
        self,
        session_id: str,
        turn_id: str,
        engine: Any,
        events: AsyncIterator[Event],
        *,
        code_checkpoint_id: str | None,
    ) -> None:
        terminal: dict[str, Any] | None = None
        terminal_persisted = False
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
                            persistence = asyncio.create_task(
                                asyncio.to_thread(
                                    self._sessions.persist_checkpoint,
                                    session_id,
                                    **persistence_options,
                                )
                            )
                            self._durability_tasks.add(persistence)
                            persistence.add_done_callback(
                                self._durability_tasks.discard
                            )
                            persisted = await asyncio.shield(
                                persistence
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
                        terminal_persist = getattr(
                            self._sessions,
                            "persist_terminal_checkpoint",
                            None,
                        )
                        if terminal is not None and terminal_persist is not None:
                            persisted = await asyncio.to_thread(
                                terminal_persist,
                                session_id,
                                checkpoint=TurnCheckpoint(),
                                turn_id=turn_id,
                                outcome=terminal,
                            )
                        else:
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
                terminal_persisted = terminal is not None and persisted
            current = asyncio.current_task()
            if terminal is not None and terminal_persisted:
                if len(self._turn_receipts) >= 2048:
                    self._turn_receipts.pop(
                        next(iter(self._turn_receipts))
                    )
                self._turn_receipts[turn_id] = {
                    "turn_id": turn_id,
                    "session_id": session_id,
                    "outcome": dict(terminal),
                    "message_count": len(engine.messages),
                }
            if self._active.get(session_id) is current:
                self._active.pop(session_id, None)
                if self._turn_ids.get(session_id) == turn_id:
                    self._turn_ids.pop(session_id, None)
                self._engines.pop(session_id, None)
                self._executing.pop(session_id, None)
                self._waiting.discard(session_id)
                if not _engine_is_quiescent(engine):
                    self._retired_engines.append(engine)
            self._turn_tasks.pop(turn_id, None)
            if terminal is not None:
                if (
                    session_id not in self._outcomes
                    and len(self._outcomes) >= 1024
                ):
                    self._outcomes.pop(next(iter(self._outcomes)))
                self._outcomes[session_id] = dict(terminal)
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
            self._waiting.discard(session_id)
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
        if event.type in {
            EventType.PERMISSION_REQUIRED,
            EventType.DIRECTORY_REQUESTED,
            EventType.PLAN_PROPOSED,
            EventType.QUESTION_REQUESTED,
        }:
            self._waiting.add(session_id)
            return TurnCheckpoint(TurnStatus.AWAITING_APPROVAL)
        return None

    def interrupt(self, session_id: str) -> bool:
        task = self._active.get(session_id)
        engine = self._engines.get(session_id)
        if task is None or task.done() or engine is None:
            return False
        engine.request_interrupt()
        return True

    def steer(self, session_id: str, text: str) -> bool:
        if (
            not isinstance(text, str)
            or not text.strip()
            or len(text.encode("utf-8")) > 32 * 1024
        ):
            return False
        engine = self._engines.get(session_id)
        if not self.is_active(session_id) or engine is None:
            return False
        engine.queue_steering(text.strip(), source={"kind": "worker_steer"})
        return True

    def is_active(self, session_id: str) -> bool:
        task = self._active.get(session_id)
        return (
            session_id in self._starting
            or task is not None
            and not task.done()
        )

    def outcome(self, session_id: str) -> dict[str, Any] | None:
        outcome = self._outcomes.get(session_id)
        return dict(outcome) if outcome is not None else None

    def turn_id(self, session_id: str) -> str | None:
        return self._turn_ids.get(session_id)

    def receipt(self, turn_id: str) -> dict[str, Any] | None:
        receipt = self._turn_receipts.get(turn_id)
        if receipt is None:
            durable = getattr(self._sessions, "turn_receipt", None)
            receipt = durable(turn_id) if durable is not None else None
        if receipt is None:
            return None
        return {
            **receipt,
            "outcome": dict(receipt["outcome"]),
        }

    def latest_receipt(
        self,
        session_id: str,
    ) -> dict[str, Any] | None:
        for turn_id in reversed(self._turn_receipts):
            receipt = self._turn_receipts[turn_id]
            if receipt["session_id"] == session_id:
                return {
                    **receipt,
                    "outcome": dict(receipt["outcome"]),
                }
        durable = getattr(
            self._sessions,
            "latest_turn_receipt",
            None,
        )
        return durable(session_id) if durable is not None else None

    async def wait_turn(self, turn_id: str) -> bool:
        if turn_id in self._turn_receipts:
            return True
        task = self._turn_tasks.get(turn_id)
        if task is None:
            return False
        await asyncio.shield(task)
        return turn_id in self._turn_receipts

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
