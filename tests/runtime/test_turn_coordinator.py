import asyncio
import sqlite3
import threading
from types import SimpleNamespace

import pytest

from runtime.events import Event, EventHub, EventType
from runtime.policy import Mode, PermissionEngine, ToolCall, ToolManifest
from runtime.providers import (
    AssistantTurn,
    ModelCapabilities,
    ProviderClient,
    StreamChunk,
)
from runtime.tools import ToolRegistry
from runtime.turn_engine import TurnEngine
from runtime.turns import (
    CodeCheckpointError,
    ExportBusyError,
    SessionBusyError,
    SessionNotFoundError,
    TurnCoordinator,
)
from runtime.sessions import (
    SessionRecord,
    TurnCheckpoint,
    TurnStatus,
)


class FakeSessions:
    def __init__(self, engine=None):
        self.engine = engine
        self.persisted = []
        self.checkpoints = []
        self.cleared_approvals = []
        self.requests = []

    def get_engine(self, session_id, *, workspace=None, agent="code"):
        self.requests.append((session_id, workspace, agent))
        return self.engine

    def persist(self, session_id):
        self.persisted.append(session_id)
        return True

    def persist_checkpoint(
        self,
        session_id,
        *,
        checkpoint,
        completed_tool_call_id=None,
    ):
        self.checkpoints.append(
            (
                session_id,
                checkpoint.status.value,
                list(checkpoint.active_tool_call_ids),
            )
        )
        if checkpoint.status is TurnStatus.IDLE:
            self.persisted.append(session_id)
        if completed_tool_call_id is not None:
            self.cleared_approvals.append(
                (session_id, completed_tool_call_id)
            )
        return True

    def list_sessions(self):
        return []

class ScriptedEngine:
    def __init__(self):
        self.messages = []
        self.roots = []
        self.interrupted = False

    async def run(self, user_input, *, source=None):
        self.messages.append({"role": "user", "content": user_input})
        yield Event(EventType.TURN_START, {"input": user_input})
        yield Event(EventType.ASSISTANT_DELTA, {"text": "hello"})
        yield Event(
            EventType.TURN_END,
            {"status": "completed", "iterations": 1},
        )

    def request_interrupt(self):
        self.interrupted = True


class FakeCodeCheckpoints:
    def __init__(self, pending=None, actions=None):
        self.begun = []
        self.captured = []
        self.finalized = []
        self.pending = pending
        self.actions = actions
        self.restore_pending = False

    def has_pending_restore(self, _session_id):
        return self.restore_pending

    def begin_checkpoint(
        self,
        session_id,
        *,
        message_count,
        attributed=False,
    ):
        self.begun.append(
            (session_id, message_count, attributed)
        )
        return SimpleNamespace(checkpoint_id="a" * 32)

    def capture_checkpoint(
        self,
        session_id,
        checkpoint_id,
        *,
        message_count,
    ):
        self.captured.append(
            (session_id, checkpoint_id, message_count)
        )
        if self.actions is not None:
            self.actions.append("capture")

    def finalize_checkpoint(self, session_id, checkpoint_id):
        self.finalized.append((session_id, checkpoint_id))
        if self.actions is not None:
            self.actions.append("finalize")

    def pending_checkpoint(self, _session_id):
        return self.pending

    def pending_checkpoints(self):
        return [self.pending] if self.pending is not None else []


def test_turn_streams_wire_events_and_persists_session(tmp_path):
    async def scenario():
        engine = ScriptedEngine()
        sessions = FakeSessions(engine)
        events = EventHub()
        received = []

        async def listener(message):
            received.append(message)

        events.subscribe_session("session-1", listener)
        turns = TurnCoordinator(sessions=sessions, events=events)

        result = await turns.start(
            "session-1",
            user_input="hello",
            workspace=tmp_path,
        )
        await turns.wait("session-1")
        return result, sessions, received, turns.outcome("session-1")

    result, sessions, received, outcome = asyncio.run(scenario())

    assert result == {"ok": True, "session_id": "session-1"}
    assert sessions.requests == [("session-1", tmp_path, "code")]
    assert sessions.persisted == ["session-1"]
    assert sessions.checkpoints == [
        ("session-1", "running", []),
        ("session-1", "idle", []),
    ]
    assert received == [
        {"type": "turn_start", "input": "hello"},
        {"type": "assistant_delta", "text": "hello"},
        {
            "type": "turn_end",
            "status": "completed",
            "iterations": 1,
        },
    ]
    assert outcome == {
        "type": "turn_end",
        "status": "completed",
        "iterations": 1,
    }


def test_turn_automatically_captures_code_and_conversation_checkpoint():
    async def scenario():
        actions = []
        checkpoints = FakeCodeCheckpoints(actions=actions)
        sessions = FakeSessions(ScriptedEngine())
        original_persist = sessions.persist_checkpoint

        def persist(*args, **kwargs):
            if kwargs["checkpoint"].status is TurnStatus.IDLE:
                actions.append("idle")
            return original_persist(*args, **kwargs)

        sessions.persist_checkpoint = persist
        turns = TurnCoordinator(
            sessions=sessions,
            events=EventHub(),
            code_checkpoints=checkpoints,
        )
        await turns.start("session-1", user_input="hello")
        await turns.wait("session-1")
        return checkpoints, actions

    checkpoints, actions = asyncio.run(scenario())

    assert checkpoints.begun == [("session-1", 0, True)]
    assert checkpoints.captured == [
        ("session-1", "a" * 32, 1)
    ]
    assert checkpoints.finalized == [
        ("session-1", "a" * 32)
    ]
    assert actions == ["capture", "idle", "finalize"]


def test_turn_does_not_finalize_code_checkpoint_when_idle_save_fails():
    class FailingIdleSessions(FakeSessions):
        def persist_checkpoint(self, session_id, *, checkpoint, **kwargs):
            if checkpoint.status is TurnStatus.IDLE:
                return False
            return super().persist_checkpoint(
                session_id,
                checkpoint=checkpoint,
                **kwargs,
            )

    async def scenario():
        checkpoints = FakeCodeCheckpoints()
        turns = TurnCoordinator(
            sessions=FailingIdleSessions(ScriptedEngine()),
            events=EventHub(),
            code_checkpoints=checkpoints,
        )
        await turns.start("session-1", user_input="hello")
        await turns.wait("session-1")
        return checkpoints

    checkpoints = asyncio.run(scenario())

    assert checkpoints.captured == [
        ("session-1", "a" * 32, 1)
    ]
    assert checkpoints.finalized == []


def test_turn_never_starts_when_automatic_checkpoint_fails():
    class FailingCheckpoints(FakeCodeCheckpoints):
        def begin_checkpoint(
            self,
            session_id,
            *,
            message_count,
            attributed=False,
        ):
            raise OSError("disk unavailable")

    async def scenario():
        engine = ScriptedEngine()
        turns = TurnCoordinator(
            sessions=FakeSessions(engine),
            events=EventHub(),
            code_checkpoints=FailingCheckpoints(),
        )
        with pytest.raises(
            CodeCheckpointError,
            match="checkpoint unavailable",
        ):
            await turns.start("session-1", user_input="must not run")
        return engine, turns

    engine, turns = asyncio.run(scenario())

    assert engine.messages == []
    assert turns.has_active_turns() is False


def test_turn_never_starts_while_checkpoint_restore_is_pending():
    async def scenario():
        engine = ScriptedEngine()
        checkpoints = FakeCodeCheckpoints()
        checkpoints.restore_pending = True
        turns = TurnCoordinator(
            sessions=FakeSessions(engine),
            events=EventHub(),
            code_checkpoints=checkpoints,
        )
        with pytest.raises(
            SessionBusyError,
            match="pending checkpoint restore",
        ):
            await turns.start("session-1", user_input="must wait")
        mutated = []
        with pytest.raises(
            SessionBusyError,
            match="pending checkpoint restore",
        ):
            await turns.mutate_when_idle(
                "session-1",
                lambda: mutated.append(True),
            )
        return engine, checkpoints, mutated

    engine, checkpoints, mutated = asyncio.run(scenario())

    assert engine.messages == []
    assert checkpoints.begun == []
    assert mutated == []


def test_context_resolution_and_turn_activation_share_snapshot_barrier():
    class BlockingEngine(ScriptedEngine):
        def __init__(self):
            super().__init__()
            self.release = asyncio.Event()

        async def run(self, user_input, *, source=None):
            self.messages.append({"role": "user", "content": user_input})
            yield Event(EventType.TURN_START, {"input": user_input})
            await self.release.wait()
            yield Event(EventType.TURN_END, {"status": "completed"})

    async def scenario():
        engine = BlockingEngine()
        turns = TurnCoordinator(
            sessions=FakeSessions(engine),
            events=EventHub(),
        )
        resolver_started = asyncio.Event()
        resolver_release = asyncio.Event()
        mutations = []

        async def resolve():
            resolver_started.set()
            await resolver_release.wait()
            return "resolved context"

        start_task = asyncio.create_task(
            turns.start(
                "session-1",
                user_input="unresolved",
                user_input_resolver=resolve,
            )
        )
        await resolver_started.wait()
        mutation_task = asyncio.create_task(
            turns.mutate_when_idle(
                "session-1",
                lambda: mutations.append("root removed"),
            )
        )
        await asyncio.sleep(0)
        assert mutation_task.done() is False
        resolver_release.set()
        await start_task
        with pytest.raises(SessionBusyError, match="active turn"):
            await mutation_task
        engine.release.set()
        await turns.wait("session-1")
        return mutations, engine.messages

    mutations, messages = asyncio.run(scenario())

    assert mutations == []
    assert messages == [{"role": "user", "content": "resolved context"}]


def test_tool_execution_is_write_ahead_checkpointed():
    class ToolEngine(ScriptedEngine):
        async def run(self, user_input, *, source=None):
            yield Event(EventType.TURN_START, {"input": user_input})
            yield Event(
                EventType.ASSISTANT_MESSAGE,
                {"text": None, "tool_calls": ["write_file"]},
            )
            yield Event(
                EventType.TOOL_STARTED,
                {"name": "write_file", "tool_call_id": "call-1"},
            )
            yield Event(
                EventType.TOOL_FINISHED,
                {
                    "name": "write_file",
                    "tool_call_id": "call-1",
                    "status": "ok",
                },
            )
            yield Event(EventType.TURN_END, {"status": "completed"})

    async def scenario():
        sessions = FakeSessions(ToolEngine())
        turns = TurnCoordinator(sessions=sessions, events=EventHub())
        await turns.start("session-1", user_input="write")
        await turns.wait("session-1")
        return sessions

    sessions = asyncio.run(scenario())

    assert sessions.checkpoints == [
        ("session-1", "running", []),
        ("session-1", "running", []),
        ("session-1", "executing", ["call-1"]),
        ("session-1", "running", []),
        ("session-1", "idle", []),
    ]
    assert sessions.cleared_approvals == [
        ("session-1", "call-1")
    ]


def test_missing_session_is_rejected(tmp_path):
    async def scenario():
        turns = TurnCoordinator(
            sessions=FakeSessions(),
            events=EventHub(),
        )
        await turns.start(
            "missing",
            user_input="hello",
            workspace=tmp_path,
        )

    with pytest.raises(SessionNotFoundError):
        asyncio.run(scenario())


def test_second_active_turn_is_rejected_and_interrupt_reaches_engine():
    class BlockingEngine(ScriptedEngine):
        def __init__(self):
            super().__init__()
            self.release = asyncio.Event()

        async def run(self, user_input, *, source=None):
            yield Event(EventType.TURN_START, {"input": user_input})
            await self.release.wait()
            yield Event(EventType.TURN_END, {"status": "completed"})

        def request_interrupt(self):
            super().request_interrupt()
            self.release.set()

    async def scenario():
        engine = BlockingEngine()
        turns = TurnCoordinator(
            sessions=FakeSessions(engine),
            events=EventHub(),
        )
        await turns.start("session-1", user_input="first")
        with pytest.raises(SessionBusyError):
            await turns.start("session-1", user_input="second")
        assert turns.interrupt("session-1") is True
        await turns.wait("session-1")
        return engine

    engine = asyncio.run(scenario())

    assert engine.interrupted is True


def test_cached_engine_is_prepared_at_each_turn_boundary():
    class PreparedEngine(ScriptedEngine):
        def __init__(self):
            super().__init__()
            self.prepared = 0

        def prepare_turn(self):
            self.prepared += 1

    async def scenario():
        engine = PreparedEngine()
        turns = TurnCoordinator(
            sessions=FakeSessions(engine),
            events=EventHub(),
        )
        await turns.start("session-1", user_input="first")
        await turns.wait("session-1")
        await turns.start("session-1", user_input="second")
        await turns.wait("session-1")
        return engine

    engine = asyncio.run(scenario())

    assert engine.prepared == 2


def test_workspace_preparation_is_nonblocking_and_counts_as_active():
    class SlowSessions(FakeSessions):
        def __init__(self, engine):
            super().__init__(engine)
            self.started = threading.Event()
            self.release = threading.Event()

        def get_engine(self, session_id, *, workspace=None, agent="code"):
            self.started.set()
            self.release.wait(timeout=2)
            return super().get_engine(
                session_id,
                workspace=workspace,
                agent=agent,
            )

    async def scenario():
        sessions = SlowSessions(ScriptedEngine())
        turns = TurnCoordinator(sessions=sessions, events=EventHub())
        first = asyncio.create_task(
            turns.start("session-1", user_input="first")
        )
        while not sessions.started.is_set():
            await asyncio.sleep(0)
        assert turns.is_active("session-1") is True
        with pytest.raises(SessionBusyError):
            await turns.start("session-1", user_input="second")
        event_loop_advanced = False
        await asyncio.sleep(0)
        event_loop_advanced = True
        sessions.release.set()
        await first
        await turns.wait("session-1")
        return event_loop_advanced

    assert asyncio.run(scenario()) is True


def test_export_excludes_new_turn_start_until_snapshot_finishes():
    class ObservableSessions(FakeSessions):
        def __init__(self, engine):
            super().__init__(engine)
            self.engine_requested = threading.Event()

        def get_engine(self, session_id, *, workspace=None, agent="code"):
            self.engine_requested.set()
            return super().get_engine(
                session_id,
                workspace=workspace,
                agent=agent,
            )

    async def scenario():
        sessions = ObservableSessions(ScriptedEngine())
        turns = TurnCoordinator(sessions=sessions, events=EventHub())
        export_started = threading.Event()
        release_export = threading.Event()

        def export():
            export_started.set()
            release_export.wait(timeout=2)
            return {"export_version": 1}

        export_task = asyncio.create_task(turns.export_when_idle(export))
        while not export_started.is_set():
            await asyncio.sleep(0)
        start_task = asyncio.create_task(
            turns.start("session-1", user_input="after export")
        )
        await asyncio.sleep(0)
        assert sessions.engine_requested.is_set() is False
        release_export.set()
        assert await export_task == {"export_version": 1}
        await start_task
        await turns.wait("session-1")
        return sessions

    sessions = asyncio.run(scenario())

    assert sessions.engine_requested.is_set() is True


def test_export_refuses_while_turn_is_active():
    class BlockingEngine(ScriptedEngine):
        def __init__(self):
            super().__init__()
            self.release = asyncio.Event()

        async def run(self, user_input, *, source=None):
            yield Event(EventType.TURN_START, {"input": user_input})
            await self.release.wait()
            yield Event(EventType.TURN_END, {"status": "completed"})

    async def scenario():
        engine = BlockingEngine()
        turns = TurnCoordinator(
            sessions=FakeSessions(engine),
            events=EventHub(),
        )
        await turns.start("session-1", user_input="active")
        with pytest.raises(ExportBusyError):
            await turns.export_when_idle(lambda: {"export_version": 1})
        engine.release.set()
        await turns.wait("session-1")

    asyncio.run(scenario())


def test_checkpoint_restore_excludes_turn_start_until_mutation_finishes():
    class ObservableSessions(FakeSessions):
        def __init__(self, engine):
            super().__init__(engine)
            self.engine_requested = threading.Event()

        def get_engine(self, session_id, *, workspace=None, agent="code"):
            self.engine_requested.set()
            return super().get_engine(
                session_id,
                workspace=workspace,
                agent=agent,
            )

    async def scenario():
        sessions = ObservableSessions(ScriptedEngine())
        turns = TurnCoordinator(sessions=sessions, events=EventHub())
        restore_started = threading.Event()
        release_restore = threading.Event()

        def restore():
            restore_started.set()
            release_restore.wait(timeout=2)
            return {"ok": True}

        restore_task = asyncio.create_task(
            turns.restore_when_idle(restore)
        )
        while not restore_started.is_set():
            await asyncio.sleep(0)
        start_task = asyncio.create_task(
            turns.start("session-1", user_input="after restore")
        )
        await asyncio.sleep(0)
        assert sessions.engine_requested.is_set() is False
        release_restore.set()
        assert await restore_task == {"ok": True}
        await start_task
        await turns.wait("session-1")

    asyncio.run(scenario())


def test_checkpoint_restore_refuses_while_turn_is_active():
    class BlockingEngine(ScriptedEngine):
        def __init__(self):
            super().__init__()
            self.release = asyncio.Event()

        async def run(self, user_input, *, source=None):
            yield Event(EventType.TURN_START, {"input": user_input})
            await self.release.wait()
            yield Event(EventType.TURN_END, {"status": "completed"})

    async def scenario():
        engine = BlockingEngine()
        turns = TurnCoordinator(
            sessions=FakeSessions(engine),
            events=EventHub(),
        )
        await turns.start("session-1", user_input="active")
        with pytest.raises(SessionBusyError):
            await turns.restore_when_idle(lambda: {"ok": True})
        engine.release.set()
        await turns.wait("session-1")

    asyncio.run(scenario())


def test_startup_recovery_resumes_durable_session_once(tmp_path):
    class RecoverableEngine(ScriptedEngine):
        def __init__(self):
            super().__init__()
            self.recovered = []

        async def resume_after_crash(self, *, active_tool_call_ids=None):
            self.recovered.append(list(active_tool_call_ids or []))
            yield Event(EventType.TURN_START, {"input": "(recovered)"})
            yield Event(EventType.TURN_END, {"status": "completed"})

    class RecoverableSessions(FakeSessions):
        def __init__(self, engine):
            super().__init__(engine)
            self.record = SessionRecord(
                session_id="session-1",
                workspace=str(tmp_path),
                model="test-model",
                mode="interactive",
                turn_checkpoint=TurnCheckpoint.executing(
                    {"call-1"}
                ),
            )

        def recoverable_sessions(self):
            return [self.record]

    async def scenario():
        engine = RecoverableEngine()
        sessions = RecoverableSessions(engine)
        turns = TurnCoordinator(sessions=sessions, events=EventHub())
        recovered = await turns.recover()
        duplicate = await turns.recover()
        await turns.wait("session-1")
        return recovered, duplicate, engine, sessions

    recovered, duplicate, engine, sessions = asyncio.run(scenario())

    assert recovered == 1
    assert duplicate == 0
    assert engine.recovered == [["call-1"]]
    assert sessions.checkpoints == [
        ("session-1", "executing", ["call-1"]),
        ("session-1", "idle", []),
    ]


def test_startup_recovery_completes_pending_code_checkpoint(tmp_path):
    class RecoverableEngine(ScriptedEngine):
        async def resume_after_crash(self, *, active_tool_call_ids=None):
            yield Event(EventType.TURN_START, {"input": "(recovered)"})
            yield Event(EventType.TURN_END, {"status": "completed"})

    class RecoverableSessions(FakeSessions):
        def __init__(self, engine):
            super().__init__(engine)
            self.record = SessionRecord(
                session_id="session-1",
                workspace=str(tmp_path),
                model="test-model",
                mode="interactive",
                turn_checkpoint=TurnCheckpoint(TurnStatus.RUNNING),
            )

        def recoverable_sessions(self):
            return [self.record]

    async def scenario():
        checkpoints = FakeCodeCheckpoints(
            pending=SimpleNamespace(
                checkpoint_id="b" * 32,
                session_id="session-1",
                after_tree="",
                after_message_count=0,
            )
        )
        turns = TurnCoordinator(
            sessions=RecoverableSessions(RecoverableEngine()),
            events=EventHub(),
            code_checkpoints=checkpoints,
        )
        assert await turns.recover() == 1
        await turns.wait("session-1")
        return checkpoints

    checkpoints = asyncio.run(scenario())

    assert checkpoints.captured == [
        ("session-1", "b" * 32, 0)
    ]
    assert checkpoints.finalized == [
        ("session-1", "b" * 32)
    ]


def test_startup_finalizes_captured_checkpoint_for_idle_session():
    class IdleSessions(FakeSessions):
        def recoverable_sessions(self):
            return []

        def list_sessions(self):
            return [
                {
                    "session_id": "session-1",
                    "messages": 2,
                }
            ]

    async def scenario():
        checkpoints = FakeCodeCheckpoints(
            pending=SimpleNamespace(
                checkpoint_id="c" * 32,
                session_id="session-1",
                after_tree="d" * 40,
                after_message_count=2,
            )
        )
        turns = TurnCoordinator(
            sessions=IdleSessions(),
            events=EventHub(),
            code_checkpoints=checkpoints,
        )
        assert await turns.recover() == 0
        return checkpoints

    checkpoints = asyncio.run(scenario())

    assert checkpoints.finalized == [
        ("session-1", "c" * 32)
    ]


def test_startup_recovery_failure_is_persisted_and_published(tmp_path):
    class BrokenRecoverySessions(FakeSessions):
        def __init__(self):
            super().__init__()
            self.failures = []
            self.record = SessionRecord(
                session_id="session-1",
                workspace=str(tmp_path),
                model="test-model",
                mode="interactive",
                turn_checkpoint=TurnCheckpoint(TurnStatus.RUNNING),
            )

        def recoverable_sessions(self):
            return [self.record]

        def get_engine(self, *args, **kwargs):
            raise RuntimeError("private reconstruction failure")

        def mark_recovery_failed(self, session_id):
            self.failures.append(session_id)
            return True

    async def scenario():
        sessions = BrokenRecoverySessions()
        events = EventHub()
        published = []

        async def listener(message):
            published.append(message)

        events.subscribe_session("session-1", listener)
        turns = TurnCoordinator(sessions=sessions, events=events)
        recovered = await turns.recover()
        return recovered, sessions, published

    recovered, sessions, published = asyncio.run(scenario())

    assert recovered == 0
    assert sessions.failures == ["session-1"]
    assert published == [
        {
            "type": "error",
            "error": "interrupted turn recovery failed",
        }
    ]


def test_graceful_shutdown_preserves_last_non_idle_checkpoint():
    class AwaitingApprovalEngine(ScriptedEngine):
        def __init__(self):
            super().__init__()
            self.release = asyncio.Event()

        async def run(self, user_input, *, source=None):
            yield Event(EventType.TURN_START, {"input": user_input})
            yield Event(
                EventType.PERMISSION_REQUIRED,
                {"approval_id": "safe-id", "name": "write_file"},
            )
            await self.release.wait()

        def request_interrupt(self):
            super().request_interrupt()
            self.release.set()

    async def scenario():
        sessions = FakeSessions(AwaitingApprovalEngine())
        turns = TurnCoordinator(sessions=sessions, events=EventHub())
        await turns.start("session-1", user_input="write")
        while len(sessions.checkpoints) < 2:
            await asyncio.sleep(0)
        await turns.shutdown()
        return sessions

    sessions = asyncio.run(scenario())

    assert sessions.checkpoints == [
        ("session-1", "running", []),
        ("session-1", "awaiting_approval", []),
    ]
    assert sessions.persisted == []


def test_shutdown_waits_for_prompt_checkpoint_before_cancelling_turn():
    class AwaitingQuestionEngine(ScriptedEngine):
        async def run(self, user_input, *, source=None):
            yield Event(EventType.TURN_START, {"input": user_input})
            yield Event(
                EventType.QUESTION_REQUESTED,
                {"interaction_id": "safe-id", "question": "Choose?"},
            )
            await asyncio.Event().wait()

    class BlockingSessions(FakeSessions):
        def __init__(self, engine):
            super().__init__(engine)
            self.checkpoint_started = threading.Event()
            self.release_checkpoint = threading.Event()

        def persist_checkpoint(self, session_id, *, checkpoint, **kwargs):
            if checkpoint.status is TurnStatus.AWAITING_APPROVAL:
                self.checkpoint_started.set()
                self.release_checkpoint.wait(timeout=5)
            return super().persist_checkpoint(
                session_id,
                checkpoint=checkpoint,
                **kwargs,
            )

    async def scenario():
        sessions = BlockingSessions(AwaitingQuestionEngine())
        turns = TurnCoordinator(sessions=sessions, events=EventHub())
        await turns.start("session-1", user_input="ask")
        while not sessions.checkpoint_started.is_set():
            await asyncio.sleep(0)
        shutdown = asyncio.create_task(turns.shutdown())
        await asyncio.sleep(0.05)
        assert not shutdown.done()
        sessions.release_checkpoint.set()
        assert await shutdown is True
        return sessions

    sessions = asyncio.run(scenario())

    assert sessions.checkpoints[-1] == (
        "session-1",
        "awaiting_approval",
        [],
    )
    assert sessions.persisted == []


def test_shutdown_drains_prompt_checkpoints_created_while_waiting():
    class AwaitingQuestionEngine(ScriptedEngine):
        def __init__(self, gate=None):
            super().__init__()
            self.gate = gate

        async def run(self, user_input, *, source=None):
            yield Event(EventType.TURN_START, {"input": user_input})
            if self.gate is not None:
                await self.gate.wait()
            yield Event(
                EventType.QUESTION_REQUESTED,
                {"interaction_id": "safe-id", "question": "Choose?"},
            )
            await asyncio.Event().wait()

    class BlockingSessions(FakeSessions):
        def __init__(self, engines):
            super().__init__()
            self.engines = engines
            self.started = {
                session_id: threading.Event()
                for session_id in engines
            }
            self.release = {
                session_id: threading.Event()
                for session_id in engines
            }

        def get_engine(self, session_id, **_kwargs):
            return self.engines[session_id]

        def persist_checkpoint(self, session_id, *, checkpoint, **kwargs):
            if checkpoint.status is TurnStatus.AWAITING_APPROVAL:
                self.started[session_id].set()
                self.release[session_id].wait(timeout=5)
            return super().persist_checkpoint(
                session_id,
                checkpoint=checkpoint,
                **kwargs,
            )

    async def scenario():
        second_gate = asyncio.Event()
        sessions = BlockingSessions(
            {
                "session-1": AwaitingQuestionEngine(),
                "session-2": AwaitingQuestionEngine(second_gate),
            }
        )
        turns = TurnCoordinator(sessions=sessions, events=EventHub())
        await turns.start("session-1", user_input="first")
        await turns.start("session-2", user_input="second")
        while not sessions.started["session-1"].is_set():
            await asyncio.sleep(0)
        shutdown = asyncio.create_task(turns.shutdown())
        await asyncio.sleep(0.05)
        second_gate.set()
        while not sessions.started["session-2"].is_set():
            await asyncio.sleep(0)
        sessions.release["session-1"].set()
        await asyncio.sleep(0.05)
        assert not shutdown.done()
        sessions.release["session-2"].set()
        assert await shutdown is True

    asyncio.run(scenario())


def test_shutdown_reports_prompt_checkpoint_durability_timeout(
    monkeypatch,
):
    monkeypatch.setattr(
        "runtime.turns.service._SHUTDOWN_TIMEOUT_SECONDS",
        0.01,
    )

    class AwaitingQuestionEngine(ScriptedEngine):
        async def run(self, user_input, *, source=None):
            yield Event(EventType.TURN_START, {"input": user_input})
            yield Event(
                EventType.QUESTION_REQUESTED,
                {"interaction_id": "safe-id", "question": "Choose?"},
            )
            await asyncio.Event().wait()

    class BlockingSessions(FakeSessions):
        def __init__(self, engine):
            super().__init__(engine)
            self.started = threading.Event()
            self.release = threading.Event()

        def persist_checkpoint(self, session_id, *, checkpoint, **kwargs):
            if checkpoint.status is TurnStatus.AWAITING_APPROVAL:
                self.started.set()
                self.release.wait(timeout=5)
            return super().persist_checkpoint(
                session_id,
                checkpoint=checkpoint,
                **kwargs,
            )

    async def scenario():
        sessions = BlockingSessions(AwaitingQuestionEngine())
        turns = TurnCoordinator(sessions=sessions, events=EventHub())
        await turns.start("session-1", user_input="ask")
        while not sessions.started.is_set():
            await asyncio.sleep(0)
        quiesced = await turns.shutdown()
        sessions.release.set()
        return quiesced

    assert asyncio.run(scenario()) is False


def test_graceful_shutdown_persists_completed_tool_progress():
    class FinishingEngine(ScriptedEngine):
        def __init__(self):
            super().__init__()
            self.release = asyncio.Event()

        async def run(self, user_input, *, source=None):
            yield Event(EventType.TURN_START, {"input": user_input})
            yield Event(
                EventType.TOOL_STARTED,
                {"name": "write_file", "tool_call_id": "call-1"},
            )
            await self.release.wait()
            yield Event(
                EventType.TOOL_FINISHED,
                {
                    "name": "write_file",
                    "tool_call_id": "call-1",
                    "status": "ok",
                },
            )
            yield Event(
                EventType.TURN_END,
                {"status": "completed"},
            )

        def request_interrupt(self):
            super().request_interrupt()
            self.release.set()

    async def scenario():
        sessions = FakeSessions(FinishingEngine())
        turns = TurnCoordinator(
            sessions=sessions,
            events=EventHub(),
        )
        await turns.start("session-1", user_input="write")
        while len(sessions.checkpoints) < 2:
            await asyncio.sleep(0)
        assert await turns.shutdown() is True
        return sessions

    sessions = asyncio.run(scenario())

    assert sessions.checkpoints[-2:] == [
        ("session-1", "running", []),
        ("session-1", "idle", []),
    ]
    assert sessions.cleared_approvals == [
        ("session-1", "call-1")
    ]


def test_shutdown_interrupts_and_quiesces_blocked_sync_work():
    class BlockingSyncEngine(ScriptedEngine):
        def __init__(self):
            super().__init__()
            self.started = threading.Event()
            self.release = threading.Event()

        async def run(self, user_input, *, source=None):
            yield Event(EventType.TURN_START, {"input": user_input})

            def blocked_tool():
                self.started.set()
                self.release.wait(timeout=5)

            await asyncio.to_thread(blocked_tool)

        def request_interrupt(self):
            super().request_interrupt()
            self.release.set()

    async def scenario():
        engine = BlockingSyncEngine()
        sessions = FakeSessions(engine)
        turns = TurnCoordinator(sessions=sessions, events=EventHub())
        await turns.start("session-1", user_input="block")
        while not engine.started.is_set():
            await asyncio.sleep(0)
        quiesced = await turns.shutdown()
        return engine, turns, quiesced

    engine, turns, quiesced = asyncio.run(scenario())

    assert quiesced is True
    assert engine.interrupted is True
    assert engine.release.is_set()
    assert turns.has_active_turns() is False


def test_shutdown_reports_noncooperative_worker_before_teardown(
    monkeypatch,
):
    monkeypatch.setattr(
        "runtime.turns.service._SHUTDOWN_TIMEOUT_SECONDS",
        0.01,
    )

    class NonCooperativeEngine(ScriptedEngine):
        def __init__(self):
            super().__init__()
            self.started = threading.Event()
            self.release = threading.Event()

        async def run(self, user_input, *, source=None):
            yield Event(EventType.TURN_START, {"input": user_input})

            def blocked_tool():
                self.started.set()
                self.release.wait(timeout=5)

            await asyncio.to_thread(blocked_tool)

    async def scenario():
        engine = NonCooperativeEngine()
        turns = TurnCoordinator(
            sessions=FakeSessions(engine),
            events=EventHub(),
        )
        await turns.start("session-1", user_input="block")
        while not engine.started.is_set():
            await asyncio.sleep(0)
        quiesced = await turns.shutdown()
        engine.release.set()
        return quiesced

    assert asyncio.run(scenario()) is False


def test_shutdown_reports_detached_provider_stream_worker(tmp_path):
    class WedgedProvider(ProviderClient):
        def __init__(self):
            self.started = threading.Event()
            self.release = threading.Event()

        def complete(self, **_kwargs):
            raise AssertionError("stream path should be used")

        def capabilities(self, _model):
            return ModelCapabilities()

        def stream(self, **_kwargs):
            self.started.set()
            self.release.wait(timeout=5)
            yield StreamChunk(
                turn=AssistantTurn(text="too late")
            )

    async def scenario():
        provider = WedgedProvider()
        engine = TurnEngine(
            provider=provider,
            registry=ToolRegistry(ToolManifest()),
            permissions=PermissionEngine(
                tmp_path,
                mode=Mode.INTERACTIVE,
            ),
            model="openai:gpt-test",
        )
        turns = TurnCoordinator(
            sessions=FakeSessions(engine),
            events=EventHub(),
        )
        await turns.start("session-1", user_input="stream")
        while not provider.started.is_set():
            await asyncio.sleep(0)
        quiesced = await turns.shutdown()
        provider.release.set()
        while not engine.is_quiescent():
            await asyncio.sleep(0)
        return quiesced

    assert asyncio.run(scenario()) is False


def test_shutdown_remembers_provider_worker_after_turn_retires(
    tmp_path,
):
    class WedgedProvider(ProviderClient):
        def __init__(self):
            self.started = threading.Event()
            self.release = threading.Event()

        def complete(self, **_kwargs):
            raise AssertionError("stream path should be used")

        def capabilities(self, _model):
            return ModelCapabilities()

        def stream(self, **_kwargs):
            self.started.set()
            self.release.wait(timeout=5)
            yield StreamChunk(
                turn=AssistantTurn(text="too late")
            )

    async def scenario():
        provider = WedgedProvider()
        engine = TurnEngine(
            provider=provider,
            registry=ToolRegistry(ToolManifest()),
            permissions=PermissionEngine(
                tmp_path,
                mode=Mode.INTERACTIVE,
            ),
            model="openai:gpt-test",
        )
        turns = TurnCoordinator(
            sessions=FakeSessions(engine),
            events=EventHub(),
        )
        await turns.start("session-1", user_input="stream")
        while not provider.started.is_set():
            await asyncio.sleep(0)
        assert turns.interrupt("session-1") is True
        await turns.wait("session-1")
        quiesced = await turns.shutdown()
        provider.release.set()
        while not engine.is_quiescent():
            await asyncio.sleep(0)
        return quiesced

    assert asyncio.run(scenario()) is False


def test_shutdown_rejects_start_that_was_waiting_on_snapshot_barrier():
    async def scenario():
        turns = TurnCoordinator(
            sessions=FakeSessions(ScriptedEngine()),
            events=EventHub(),
        )
        await turns.shutdown()
        with pytest.raises(SessionBusyError, match="shutting down"):
            await turns.start("session-1", user_input="late")

    asyncio.run(scenario())


def test_shutdown_at_tool_started_still_persists_write_ahead_state():
    class RacingEngine(ScriptedEngine):
        def __init__(self):
            super().__init__()
            self.allow_tool_started = asyncio.Event()

        async def run(self, user_input, *, source=None):
            yield Event(EventType.TURN_START, {"input": user_input})
            await self.allow_tool_started.wait()
            yield Event(
                EventType.TOOL_STARTED,
                {"name": "write_file", "tool_call_id": "call-1"},
            )
            await asyncio.sleep(3600)

        def request_interrupt(self):
            super().request_interrupt()
            self.allow_tool_started.set()

    async def scenario():
        engine = RacingEngine()
        sessions = FakeSessions(engine)
        turns = TurnCoordinator(sessions=sessions, events=EventHub())
        await turns.start("session-1", user_input="write")
        while not sessions.checkpoints:
            await asyncio.sleep(0)
        await turns.shutdown()
        return sessions

    sessions = asyncio.run(scenario())

    assert sessions.checkpoints[-1] == (
        "session-1",
        "executing",
        ["call-1"],
    )


def test_checkpoint_failure_never_clears_last_durable_recovery_state():
    class ToolEngine(ScriptedEngine):
        async def run(self, user_input, *, source=None):
            yield Event(EventType.TURN_START, {"input": user_input})
            yield Event(
                EventType.TOOL_STARTED,
                {"name": "write_file", "tool_call_id": "call-1"},
            )
            raise AssertionError("execution must stop when checkpoint fails")

    class FailingCheckpointSessions(FakeSessions):
        def persist_checkpoint(self, session_id, *, checkpoint):
            super().persist_checkpoint(
                session_id,
                checkpoint=checkpoint,
            )
            return checkpoint.status is not TurnStatus.EXECUTING

    async def scenario():
        sessions = FailingCheckpointSessions(ToolEngine())
        turns = TurnCoordinator(sessions=sessions, events=EventHub())
        await turns.start("session-1", user_input="write")
        await turns.wait("session-1")
        return sessions

    sessions = asyncio.run(scenario())

    assert sessions.checkpoints == [
        ("session-1", "running", []),
        ("session-1", "executing", ["call-1"]),
    ]
    assert sessions.persisted == []


def test_checkpoint_exception_never_writes_idle_fallback():
    class ToolEngine(ScriptedEngine):
        async def run(self, user_input, *, source=None):
            yield Event(EventType.TURN_START, {"input": user_input})
            yield Event(
                EventType.TOOL_STARTED,
                {"name": "write_file", "tool_call_id": "call-1"},
            )
            yield Event(
                EventType.TOOL_FINISHED,
                {
                    "name": "write_file",
                    "tool_call_id": "call-1",
                    "status": "ok",
                },
            )

    class RaisingCheckpointSessions(FakeSessions):
        def persist_checkpoint(
            self,
            session_id,
            *,
            checkpoint,
            completed_tool_call_id=None,
        ):
            if completed_tool_call_id == "call-1":
                raise sqlite3.IntegrityError(
                    "simulated atomic rollback"
                )
            return super().persist_checkpoint(
                session_id,
                checkpoint=checkpoint,
            )

    async def scenario():
        sessions = RaisingCheckpointSessions(ToolEngine())
        turns = TurnCoordinator(
            sessions=sessions,
            events=EventHub(),
        )
        await turns.start("session-1", user_input="write")
        await turns.wait("session-1")
        return sessions

    sessions = asyncio.run(scenario())

    assert sessions.checkpoints == [
        ("session-1", "running", []),
        ("session-1", "executing", ["call-1"]),
    ]
    assert sessions.persisted == []


def test_unexpected_engine_error_is_value_sanitized_and_persisted():
    class FailingEngine(ScriptedEngine):
        async def run(self, user_input, *, source=None):
            raise RuntimeError("turn-secret-must-not-echo")
            yield

    async def scenario():
        sessions = FakeSessions(FailingEngine())
        events = EventHub()
        received = []

        async def listener(message):
            received.append(message)

        events.subscribe_session("session-1", listener)
        turns = TurnCoordinator(sessions=sessions, events=events)
        await turns.start("session-1", user_input="hello")
        await turns.wait("session-1")
        return sessions, received

    sessions, received = asyncio.run(scenario())

    assert sessions.persisted == ["session-1"]
    assert received == [
        {"type": "error", "error": "turn execution failed"}
    ]
    assert "turn-secret-must-not-echo" not in str(received)


def test_coordinator_runs_real_policy_bound_turn_engine(tmp_path):
    class Provider(ProviderClient):
        def __init__(self):
            self.turns = [
                AssistantTurn(
                    tool_calls=[
                        ToolCall("call_1", "list_files", {})
                    ]
                ),
                AssistantTurn(text="done"),
            ]

        def complete(self, **_kwargs):
            return self.turns.pop(0)

        def capabilities(self, _model):
            return ModelCapabilities()

    calls = []

    def list_files():
        calls.append(True)
        return ["README.md"]

    registry = ToolRegistry(ToolManifest())
    registry.register(
        list_files,
        schema={
            "type": "function",
            "function": {
                "name": "list_files",
                "description": "list files",
                "parameters": {
                    "type": "object",
                    "properties": {},
                    "required": [],
                    "additionalProperties": False,
                },
            },
        },
    )
    engine = TurnEngine(
        provider=Provider(),
        registry=registry,
        permissions=PermissionEngine(tmp_path),
        model="openai:gpt-test",
    )

    async def scenario():
        events = EventHub()
        received = []

        async def listener(message):
            received.append(message)

        events.subscribe_session("session-1", listener)
        turns = TurnCoordinator(
            sessions=FakeSessions(engine),
            events=events,
        )
        await turns.start("session-1", user_input="list")
        await turns.wait("session-1")
        return received

    received = asyncio.run(scenario())

    assert calls == [True]
    assert [message["type"] for message in received] == [
        "turn_start",
        "assistant_message",
        "tool_proposed",
        "tool_started",
        "tool_finished",
        "iteration_end",
        "assistant_message",
        "turn_end",
    ]
