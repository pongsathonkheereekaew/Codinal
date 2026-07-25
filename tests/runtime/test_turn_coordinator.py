import asyncio

import pytest

from runtime.events import Event, EventHub, EventType
from runtime.policy import PermissionEngine, ToolCall, ToolManifest
from runtime.providers import AssistantTurn, ModelCapabilities, ProviderClient
from runtime.tools import ToolRegistry
from runtime.turn_engine import TurnEngine
from runtime.turns import (
    SessionBusyError,
    SessionNotFoundError,
    TurnCoordinator,
)


class FakeSessions:
    def __init__(self, engine=None):
        self.engine = engine
        self.persisted = []
        self.requests = []

    def get_engine(self, session_id, *, workspace=None, agent="code"):
        self.requests.append((session_id, workspace, agent))
        return self.engine

    def persist(self, session_id):
        self.persisted.append(session_id)
        return True


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
        return result, sessions, received

    result, sessions, received = asyncio.run(scenario())

    assert result == {"ok": True, "session_id": "session-1"}
    assert sessions.requests == [("session-1", tmp_path, "code")]
    assert sessions.persisted == ["session-1"]
    assert received == [
        {"type": "turn_start", "input": "hello"},
        {"type": "assistant_delta", "text": "hello"},
        {
            "type": "turn_end",
            "status": "completed",
            "iterations": 1,
        },
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
