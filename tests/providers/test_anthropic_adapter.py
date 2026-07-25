import sys
from types import SimpleNamespace

import pytest

from runtime.providers import AnthropicProvider, ToolCall
from runtime.providers.anthropic_provider import (
    convert_messages,
    resolve_api_key,
)
from runtime.secrets import ProviderSecretService


class FakeClient:
    def __init__(self, response):
        self.kwargs = {}

        def create(**kwargs):
            self.kwargs = kwargs
            return response

        self.messages = SimpleNamespace(create=create)
        self.beta = SimpleNamespace(
            messages=SimpleNamespace(create=create)
        )


def test_anthropic_key_comes_only_from_memory_secret_service(
    monkeypatch,
) -> None:
    monkeypatch.setenv(
        "ANTHROPIC_API_KEY",
        "environment-key-must-be-ignored",
    )
    secrets = ProviderSecretService()
    secrets.set_api_key("anthropic", "native-memory-key")

    assert resolve_api_key(secrets) == "native-memory-key"
    assert resolve_api_key(None) is None


def test_anthropic_system_and_parallel_tool_results_are_converted() -> None:
    system, messages = convert_messages(
        [
            {"role": "system", "content": "be precise"},
            {"role": "user", "content": "go"},
            {
                "role": "assistant",
                "content": "",
                "tool_calls": [
                    {
                        "id": "c1",
                        "type": "function",
                        "function": {"name": "a", "arguments": "{}"},
                    },
                    {
                        "id": "c2",
                        "type": "function",
                        "function": {"name": "b", "arguments": "{}"},
                    },
                ],
            },
            {"role": "tool", "tool_call_id": "c1", "content": "r1"},
            {"role": "tool", "tool_call_id": "c2", "content": "r2"},
        ]
    )

    assert system == "be precise"
    assert [message["role"] for message in messages] == [
        "user",
        "assistant",
        "user",
    ]
    assert [
        block["tool_use_id"] for block in messages[-1]["content"]
    ] == ["c1", "c2"]


def test_anthropic_complete_normalizes_tool_use() -> None:
    response = SimpleNamespace(
        content=[
            SimpleNamespace(
                type="tool_use",
                id="call_1",
                name="workspace.read_file",
                input={"path": "README.md"},
            )
        ],
        stop_reason="tool_use",
    )
    provider = AnthropicProvider(
        client=FakeClient(response),
        thinking_budget=0,
    )

    turn = provider.complete(
        model="claude-sonnet-4-6",
        messages=[{"role": "user", "content": "read"}],
    )

    assert turn.tool_calls == [
        ToolCall(
            id="call_1",
            name="workspace.read_file",
            arguments={"path": "README.md"},
        )
    ]
    assert turn.finish_reason == "tool_calls"


def test_anthropic_environment_key_is_never_echoed(
    monkeypatch,
) -> None:
    marker = "environment-key-must-not-echo"
    monkeypatch.setenv("ANTHROPIC_API_KEY", marker)
    monkeypatch.setitem(
        sys.modules,
        "anthropic",
        SimpleNamespace(Anthropic=lambda **_kwargs: object()),
    )

    with pytest.raises(RuntimeError) as caught:
        AnthropicProvider()._ensure_client()

    assert str(caught.value) == (
        "No Anthropic API key configured. Add it in Settings."
    )
    assert marker not in str(caught.value)
