import asyncio

from runtime.events import EventType
from runtime.policy import (
    ApprovalOutcome,
    Mode,
    PermissionEngine,
    ToolCall,
    ToolManifest,
)
from runtime.providers import AssistantTurn, ModelCapabilities, ProviderClient
from runtime.tools import ToolRegistry
from runtime.turn_engine import TurnEngine


def schema(name):
    return {
        "type": "function",
        "function": {
            "name": name,
            "description": name,
            "parameters": {
                "type": "object",
                "properties": {"path": {"type": "string"}},
                "required": ["path"],
                "additionalProperties": False,
            },
        },
    }


class SequenceProvider(ProviderClient):
    def __init__(self, turns):
        self.turns = list(turns)

    def complete(self, **_kwargs):
        return self.turns.pop(0)

    def capabilities(self, _model):
        return ModelCapabilities()


class RaisingProvider(ProviderClient):
    def complete(self, **_kwargs):
        raise RuntimeError("provider-secret-must-not-echo")

    def capabilities(self, _model):
        return ModelCapabilities()


async def collect(engine):
    return [event async for event in engine.run("start")]


def test_read_tool_executes_after_policy_auto_allows(tmp_path) -> None:
    calls = []

    def read_file(path):
        calls.append(path)
        return {"content": "ok"}

    registry = ToolRegistry(ToolManifest())
    registry.register(read_file, schema=schema("read_file"))
    provider = SequenceProvider(
        [
            AssistantTurn(
                tool_calls=[
                    ToolCall(
                        "call_1",
                        "read_file",
                        {"path": "README.md"},
                    )
                ]
            ),
            AssistantTurn(text="done"),
        ]
    )
    engine = TurnEngine(
        provider=provider,
        registry=registry,
        permissions=PermissionEngine(tmp_path, mode=Mode.INTERACTIVE),
        model="openai:gpt-test",
    )

    events = asyncio.run(collect(engine))

    assert calls == ["README.md"]
    assert EventType.TOOL_STARTED in [event.type for event in events]
    assert EventType.TOOL_FINISHED in [event.type for event in events]


def test_write_tool_cannot_execute_when_default_approver_denies(
    tmp_path,
) -> None:
    calls = []

    def write_file(path):
        calls.append(path)
        return {"ok": True}

    registry = ToolRegistry(ToolManifest())
    registry.register(write_file, schema=schema("write_file"))
    provider = SequenceProvider(
        [
            AssistantTurn(
                tool_calls=[
                    ToolCall(
                        "call_1",
                        "write_file",
                        {"path": "blocked.txt"},
                    )
                ]
            ),
            AssistantTurn(text="stopped"),
        ]
    )
    engine = TurnEngine(
        provider=provider,
        registry=registry,
        permissions=PermissionEngine(tmp_path, mode=Mode.INTERACTIVE),
        model="openai:gpt-test",
    )

    events = asyncio.run(collect(engine))

    assert calls == []
    assert EventType.PERMISSION_REQUIRED in [
        event.type for event in events
    ]
    denied = [
        event
        for event in events
        if event.type is EventType.TOOL_FINISHED
    ][0]
    assert denied.data["status"] == "denied"


def test_manifest_declared_write_tool_cannot_bypass_policy(tmp_path) -> None:
    calls = []

    def git_stage(path):
        calls.append(path)
        return {"ok": True}

    registry = ToolRegistry(ToolManifest())
    registry.register(git_stage, schema=schema("git_stage"))
    provider = SequenceProvider(
        [
            AssistantTurn(
                tool_calls=[
                    ToolCall("call_1", "git_stage", {"path": "README.md"})
                ]
            ),
            AssistantTurn(text="stopped"),
        ]
    )
    engine = TurnEngine(
        provider=provider,
        registry=registry,
        permissions=PermissionEngine(tmp_path, mode=Mode.INTERACTIVE),
        model="openai:gpt-test",
    )

    events = asyncio.run(collect(engine))

    assert calls == []
    denied = [
        event
        for event in events
        if event.type is EventType.TOOL_FINISHED
    ][0]
    assert denied.data["status"] == "denied"


def test_manifest_declared_write_executes_after_explicit_approval(
    tmp_path,
) -> None:
    calls = []
    requests = []

    def git_stage(path):
        calls.append(path)
        return {"ok": True}

    async def approve(request):
        requests.append(request)
        return ApprovalOutcome.ONCE

    registry = ToolRegistry(ToolManifest())
    registry.register(git_stage, schema=schema("git_stage"))
    provider = SequenceProvider(
        [
            AssistantTurn(
                tool_calls=[
                    ToolCall("call_1", "git_stage", {"path": "README.md"})
                ]
            ),
            AssistantTurn(text="done"),
        ]
    )
    engine = TurnEngine(
        provider=provider,
        registry=registry,
        permissions=PermissionEngine(tmp_path, mode=Mode.INTERACTIVE),
        model="openai:gpt-test",
        approver=approve,
    )

    events = asyncio.run(collect(engine))

    assert calls == ["README.md"]
    assert requests[0].risk == "write_local"
    finished = [
        event
        for event in events
        if event.type is EventType.TOOL_FINISHED
    ][0]
    assert finished.data["status"] == "ok"


def test_unregistered_control_tool_cannot_invoke_callback(tmp_path) -> None:
    questions = []

    async def ask_user(arguments, _tool_call_id):
        questions.append(arguments)
        return {"answer": "approved"}

    provider = SequenceProvider(
        [
            AssistantTurn(
                tool_calls=[
                    ToolCall(
                        "call_1",
                        "ask_user",
                        {"question": "Grant access?"},
                    )
                ]
            ),
            AssistantTurn(text="stopped"),
        ]
    )
    engine = TurnEngine(
        provider=provider,
        registry=ToolRegistry(ToolManifest()),
        permissions=PermissionEngine(tmp_path, mode=Mode.INTERACTIVE),
        model="openai:gpt-test",
        question_asker=ask_user,
    )

    events = asyncio.run(collect(engine))

    assert questions == []
    denied = [
        event
        for event in events
        if event.type is EventType.TOOL_FINISHED
    ][0]
    assert denied.data["status"] == "error"


def test_provider_exception_details_are_not_exposed(tmp_path) -> None:
    engine = TurnEngine(
        provider=RaisingProvider(),
        registry=ToolRegistry(ToolManifest()),
        permissions=PermissionEngine(tmp_path, mode=Mode.INTERACTIVE),
        model="openai:gpt-test",
    )

    events = asyncio.run(collect(engine))

    error = [event for event in events if event.type is EventType.ERROR][0]
    assert error.data == {
        "error": "model request failed",
        "error_type": "provider_error",
    }
    assert "provider-secret-must-not-echo" not in str(events)
    assert "provider-secret-must-not-echo" not in str(engine.messages)


def test_tool_exception_details_are_not_exposed(tmp_path) -> None:
    def read_file(path):
        raise RuntimeError(f"tool-secret-must-not-echo:{path}")

    registry = ToolRegistry(ToolManifest())
    registry.register(read_file, schema=schema("read_file"))
    provider = SequenceProvider(
        [
            AssistantTurn(
                tool_calls=[
                    ToolCall(
                        "call_1",
                        "read_file",
                        {"path": "secret.txt"},
                    )
                ]
            ),
            AssistantTurn(text="done"),
        ]
    )
    engine = TurnEngine(
        provider=provider,
        registry=registry,
        permissions=PermissionEngine(tmp_path, mode=Mode.INTERACTIVE),
        model="openai:gpt-test",
    )

    events = asyncio.run(collect(engine))

    failed = [
        event
        for event in events
        if event.type is EventType.TOOL_FINISHED
    ][0]
    assert failed.data["status"] == "error"
    assert "tool-secret-must-not-echo" not in str(events)
    assert "tool-secret-must-not-echo" not in str(engine.messages)
