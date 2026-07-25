import pytest

from runtime.policy import ToolCall, ToolCallValidationError
from runtime.providers import (
    AssistantTurn,
    ModelCapabilities,
    ProviderClient,
    StreamChunk,
)
from runtime.providers.capabilities import capabilities_for


class FixtureProvider(ProviderClient):
    def complete(self, *, model, messages, tools=None, **settings):
        return AssistantTurn(text=f"{model}:{messages[-1]['content']}")

    def capabilities(self, model):
        return ModelCapabilities(streaming=False)


def test_assistant_turn_revalidates_provider_tool_calls() -> None:
    turn = AssistantTurn(
        tool_calls=[
            ToolCall(
                id="call_01",
                name="workspace.read_file",
                arguments={"path": "README.md"},
            )
        ]
    )

    assert turn.has_tool_calls
    assert turn.tool_calls[0].name == "workspace.read_file"


def test_assistant_turn_rejects_provider_calls_that_bypass_contract() -> None:
    with pytest.raises(
        ToolCallValidationError,
        match="^invalid tool-call payload$",
    ):
        AssistantTurn(
            tool_calls=[
                ToolCall(
                    id="call_01",
                    name="workspace.read_file",
                    arguments={"line": float("nan")},
                )
            ]
        )


def test_provider_default_stream_wraps_one_complete_turn() -> None:
    provider = FixtureProvider()

    chunks = list(
        provider.stream(
            model="fixture",
            messages=[{"role": "user", "content": "hello"}],
        )
    )

    assert chunks == [
        StreamChunk(turn=AssistantTurn(text="fixture:hello"))
    ]


def test_pdf_capability_matches_each_provider_wire_protocol() -> None:
    assert capabilities_for("anthropic:claude-sonnet").pdf is True
    assert capabilities_for("gemini:gemini-pro").pdf is True
    assert capabilities_for("openai:gpt-5.6").pdf is False
