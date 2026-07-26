import asyncio
import time

from runtime.events import EventType
from runtime.policy import Mode, PermissionEngine, ToolCall, ToolManifest
from runtime.providers import (
    AssistantTurn,
    ModelCapabilities,
    ProviderClient,
    StreamChunk,
)
from runtime.tools import ToolRegistry
from runtime.turn_engine import TurnEngine


def no_args_schema(name):
    return {
        "type": "function",
        "function": {
            "name": name,
            "description": name,
            "parameters": {
                "type": "object",
                "properties": {},
                "required": [],
                "additionalProperties": False,
            },
        },
    }


async def collect(engine):
    return [event async for event in engine.run("start")]


class StreamingProvider(ProviderClient):
    def complete(self, **_kwargs):
        raise AssertionError("stream path should be used")

    def capabilities(self, _model):
        return ModelCapabilities()

    def stream(self, **_kwargs):
        yield StreamChunk(text_delta="Hel")
        yield StreamChunk(text_delta="lo")
        yield StreamChunk(turn=AssistantTurn(text="Hello"))


def test_streaming_turn_emits_deltas_and_completes(tmp_path):
    permissions = PermissionEngine(tmp_path, mode=Mode.INTERACTIVE)
    engine = TurnEngine(
        provider=StreamingProvider(),
        registry=ToolRegistry(ToolManifest()),
        permissions=permissions,
        model="openai:gpt-test",
    )

    events = asyncio.run(collect(engine))

    assert engine.roots is permissions.roots
    assert [
        event.data["text"]
        for event in events
        if event.type is EventType.ASSISTANT_DELTA
    ] == ["Hel", "lo"]
    assert events[-1].type is EventType.TURN_END
    assert events[-1].data["status"] == "completed"


class LoopingProvider(ProviderClient):
    def __init__(self):
        self.calls = 0

    def complete(self, **_kwargs):
        self.calls += 1
        return AssistantTurn(
            tool_calls=[ToolCall(f"call_{self.calls}", "list_files", {})]
        )

    def capabilities(self, _model):
        return ModelCapabilities()


def test_max_iteration_rail_stops_tool_loop(tmp_path):
    provider = LoopingProvider()

    def list_files():
        return []

    registry = ToolRegistry(ToolManifest())
    registry.register(list_files, schema=no_args_schema("list_files"))
    engine = TurnEngine(
        provider=provider,
        registry=registry,
        permissions=PermissionEngine(tmp_path, mode=Mode.INTERACTIVE),
        model="openai:gpt-test",
        max_iterations=3,
    )

    events = asyncio.run(collect(engine))

    assert provider.calls == 3
    assert events[-1].type is EventType.TURN_END
    assert events[-1].data["status"] == "max_iterations_exceeded"


class EndlessStreamProvider(ProviderClient):
    def complete(self, **_kwargs):
        raise AssertionError("stream path should be used")

    def capabilities(self, _model):
        return ModelCapabilities()

    def stream(self, **_kwargs):
        for index in range(100):
            yield StreamChunk(text_delta=f"{index} ")
            time.sleep(0.005)


def test_interrupt_mid_stream_persists_partial_answer(tmp_path):
    engine = TurnEngine(
        provider=EndlessStreamProvider(),
        registry=ToolRegistry(ToolManifest()),
        permissions=PermissionEngine(tmp_path, mode=Mode.INTERACTIVE),
        model="openai:gpt-test",
    )

    async def interrupt_after_delta():
        events = []
        async for event in engine.run("start"):
            events.append(event)
            if event.type is EventType.ASSISTANT_DELTA:
                engine.request_interrupt()
        return events

    events = asyncio.run(interrupt_after_delta())

    assert events[-1].type is EventType.INTERRUPTED
    assert engine.messages[-2]["role"] == "assistant"
    assert engine.messages[-2]["content"]
    assert engine.messages[-1]["kind"] == "interrupted"


def test_crash_resume_never_replays_tool_marked_as_executing(tmp_path):
    class RecoveryProvider(ProviderClient):
        def complete(self, **_kwargs):
            return AssistantTurn(text="recovery acknowledged")

        def capabilities(self, _model):
            return ModelCapabilities()

    executions = []

    def write_file():
        executions.append("replayed")
        return {"ok": True}

    registry = ToolRegistry(ToolManifest())
    registry.register(write_file, schema=no_args_schema("write_file"))
    engine = TurnEngine(
        provider=RecoveryProvider(),
        registry=registry,
        permissions=PermissionEngine(tmp_path, mode=Mode.INTERACTIVE),
        model="openai:gpt-test",
        messages=[
            {"role": "user", "content": "write it"},
            {
                "role": "assistant",
                "content": None,
                "tool_calls": [
                    {
                        "id": "call-1",
                        "type": "function",
                        "function": {
                            "name": "write_file",
                            "arguments": "{}",
                        },
                    },
                    {
                        "id": "call-2",
                        "type": "function",
                        "function": {
                            "name": "write_file",
                            "arguments": "{}",
                        },
                    },
                ],
            },
        ],
    )

    events = asyncio.run(
        _collect_crash_resume(
            engine,
            active_tool_call_ids=["call-1", "call-2"],
        )
    )

    assert executions == []
    recovered_calls = {
        message.get("tool_call_id")
        for message in engine.messages
        if message.get("role") == "tool"
        and "outcome is unknown" in message.get("content", "")
    }
    assert recovered_calls == {"call-1", "call-2"}
    assert events[-1].type is EventType.TURN_END


def test_second_crash_during_multi_tool_recovery_remains_resumable(
    tmp_path,
):
    class RecoveryProvider(ProviderClient):
        def complete(self, **_kwargs):
            return AssistantTurn(text="recovered")

        def capabilities(self, _model):
            return ModelCapabilities()

    messages = [
        {"role": "user", "content": "inspect"},
        {
            "role": "assistant",
            "content": None,
            "tool_calls": [
                {
                    "id": call_id,
                    "type": "function",
                    "function": {
                        "name": "list_files",
                        "arguments": "{}",
                    },
                }
                for call_id in ("call-1", "call-2")
            ],
        },
    ]
    registry = ToolRegistry(ToolManifest())

    def list_files():
        return []

    registry.register(
        list_files,
        schema=no_args_schema("list_files"),
    )
    first = TurnEngine(
        provider=RecoveryProvider(),
        registry=registry,
        permissions=PermissionEngine(tmp_path, mode=Mode.INTERACTIVE),
        model="openai:gpt-test",
        messages=messages,
    )

    async def crash_after_first_reconciled_call():
        events = []
        async for event in first.resume_after_crash(
            active_tool_call_ids=["call-1", "call-2"]
        ):
            events.append(event)
            if event.type is EventType.TOOL_FINISHED:
                break
        return events

    first_events = asyncio.run(crash_after_first_reconciled_call())
    assert first_events[-1].data["tool_call_id"] == "call-1"
    assert {
        message.get("tool_call_id")
        for message in first.messages
        if message.get("role") == "tool"
    } == {"call-1"}

    second = TurnEngine(
        provider=RecoveryProvider(),
        registry=registry,
        permissions=PermissionEngine(tmp_path, mode=Mode.INTERACTIVE),
        model="openai:gpt-test",
        messages=first.messages,
    )
    second_events = asyncio.run(
        _collect_crash_resume(
            second,
            active_tool_call_ids=["call-2"],
        )
    )

    assert second_events[-1].type is EventType.TURN_END
    assert {
        message.get("tool_call_id")
        for message in second.messages
        if message.get("role") == "tool"
    } == {"call-1", "call-2"}


def test_crash_after_final_assistant_message_does_not_call_provider_again(
    tmp_path,
):
    class NeverProvider(ProviderClient):
        def complete(self, **_kwargs):
            raise AssertionError("completed answer must not be regenerated")

        def capabilities(self, _model):
            return ModelCapabilities()

    engine = TurnEngine(
        provider=NeverProvider(),
        registry=ToolRegistry(ToolManifest()),
        permissions=PermissionEngine(tmp_path, mode=Mode.INTERACTIVE),
        model="openai:gpt-test",
        messages=[
            {"role": "user", "content": "answer"},
            {"role": "assistant", "content": "already complete"},
        ],
    )

    events = asyncio.run(
        _collect_crash_resume(engine, active_tool_call_ids=[])
    )

    assert [event.type for event in events] == [
        EventType.TURN_START,
        EventType.TURN_END,
    ]


async def _collect_crash_resume(engine, *, active_tool_call_ids):
    return [
        event
        async for event in engine.resume_after_crash(
            active_tool_call_ids=active_tool_call_ids
        )
    ]


def test_outbound_pdf_adaptation_does_not_mutate_history(
    tmp_path,
    monkeypatch,
):
    engine = TurnEngine(
        provider=StreamingProvider(),
        registry=ToolRegistry(ToolManifest()),
        permissions=PermissionEngine(tmp_path, mode=Mode.INTERACTIVE),
        model="openai:gpt-test",
    )
    file_part = {
        "type": "file",
        "file": {
            "filename": "doc.pdf",
            "file_data": "data:application/pdf;base64,AA==",
        },
    }
    engine.messages.append(
        {
            "role": "user",
            "content": [{"type": "text", "text": "read"}, file_part],
        }
    )
    monkeypatch.setattr(
        "runtime.turn_engine.pdf_support.extract_text",
        lambda _file_data: "local text",
    )

    outbound = engine._outbound_messages()

    assert outbound[-1]["content"][1]["type"] == "text"
    assert "local text" in outbound[-1]["content"][1]["text"]
    assert engine.messages[-1]["content"][1] is file_part


def test_pdf_adaptation_does_not_block_the_event_loop(tmp_path, monkeypatch):
    engine = TurnEngine(
        provider=StreamingProvider(),
        registry=ToolRegistry(ToolManifest()),
        permissions=PermissionEngine(tmp_path, mode=Mode.INTERACTIVE),
        model="openai:gpt-test",
    )
    content = [
        {"type": "text", "text": "read"},
        {
            "type": "file",
            "file": {
                "filename": "doc.pdf",
                "file_data": "data:application/pdf;base64,AA==",
            },
        },
    ]

    def slow_extract(_file_data):
        time.sleep(0.25)
        return "local text"

    monkeypatch.setattr(
        "runtime.turn_engine.pdf_support.extract_text",
        slow_extract,
    )

    async def run_with_probe():
        async def collect_content():
            return [event async for event in engine.run(content)]

        started = time.monotonic()
        task = asyncio.create_task(collect_content())
        await asyncio.sleep(0.02)
        probe_elapsed = time.monotonic() - started
        await task
        return probe_elapsed

    elapsed = asyncio.run(run_with_probe())

    assert elapsed < 0.15
