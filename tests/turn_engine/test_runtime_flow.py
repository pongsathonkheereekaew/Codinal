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
