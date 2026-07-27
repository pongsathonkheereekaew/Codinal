import json
import sys
from types import SimpleNamespace

import pytest

from runtime.providers import AssistantTurn, OpenAIProvider, ToolCall
from runtime.providers.openai_provider import resolve_api_key
from runtime.secrets import ProviderSecretService


class FakeCompletions:
    def __init__(self, response):
        self.response = response
        self.calls = []

    def create(self, **kwargs):
        self.calls.append(kwargs)
        return self.response


class FakeClient:
    def __init__(self, response):
        self.chat = SimpleNamespace(
            completions=FakeCompletions(response)
        )


def response(content=None, tool_calls=None, finish_reason="stop"):
    message = SimpleNamespace(content=content, tool_calls=tool_calls)
    choice = SimpleNamespace(message=message, finish_reason=finish_reason)
    return SimpleNamespace(choices=[choice])


def test_openai_key_comes_only_from_memory_secret_service(
    monkeypatch,
) -> None:
    monkeypatch.setenv("OPENAI_API_KEY", "environment-key-must-be-ignored")
    secrets = ProviderSecretService()
    secrets.set_api_key("openai", "native-memory-key")

    assert resolve_api_key(secrets) == "native-memory-key"
    assert resolve_api_key(None) is None


def test_complete_normalizes_text_and_tool_calls() -> None:
    raw_call = SimpleNamespace(
        id="call_1",
        function=SimpleNamespace(
            name="workspace.read_file",
            arguments=json.dumps({"path": "README.md"}),
        ),
    )
    client = FakeClient(
        response(tool_calls=[raw_call], finish_reason="tool_calls")
    )
    provider = OpenAIProvider(client=client)

    turn = provider.complete(
        model="gpt-5.6-sol",
        messages=[{"role": "user", "content": "read"}],
        tools=[
            {
                "type": "function",
                "function": {"name": "workspace.read_file"},
            }
        ],
    )

    assert isinstance(turn, AssistantTurn)
    assert turn.tool_calls == [
        ToolCall(
            id="call_1",
            name="workspace.read_file",
            arguments={"path": "README.md"},
        )
    ]
    assert client.chat.completions.calls[0]["reasoning_effort"] == "none"


def test_foreign_provider_sidecars_never_reach_openai() -> None:
    client = FakeClient(response(content="ok"))
    provider = OpenAIProvider(client=client)

    provider.complete(
        model="gpt-5.6-sol",
        messages=[
            {
                "role": "assistant",
                "content": "previous",
                "_gemini": {"signature": "private"},
            }
        ],
    )

    assert client.chat.completions.calls[0]["messages"] == [
        {"role": "assistant", "content": "previous"}
    ]


def test_environment_key_is_ignored_and_never_echoed_in_error(
    monkeypatch,
) -> None:
    marker = "environment-key-must-not-echo"
    monkeypatch.setenv("OPENAI_API_KEY", marker)
    monkeypatch.setitem(
        sys.modules,
        "openai",
        SimpleNamespace(OpenAI=lambda **_kwargs: object()),
    )

    with pytest.raises(RuntimeError) as caught:
        OpenAIProvider()._ensure_client()

    assert str(caught.value) == (
        "No OpenAI API key configured. Add it in Settings."
    )
    assert marker not in str(caught.value)


def test_complete_raises_on_empty_content_gateway_response() -> None:
    """A 200 OK with no message content (OmniRoute/OpenRouter upstream flake)
    must surface an actionable error, not a silent 'no content' turn."""
    client = FakeClient(response(content=None, finish_reason="stop"))
    provider = OpenAIProvider(client=client, base_url="http://localhost:20128/v1")

    with pytest.raises(RuntimeError, match="returned an empty response") as exc:
        provider.complete(model="auto", messages=[{"role": "user", "content": "hi"}])
    assert "OmniRoute" in str(exc.value)


def test_complete_passes_through_when_content_present() -> None:
    """Non-empty content must not trip the empty-response guard."""
    client = FakeClient(response(content="hello", finish_reason="stop"))
    provider = OpenAIProvider(client=client)

    turn = provider.complete(model="gpt-4o", messages=[{"role": "user", "content": "hi"}])

    assert turn.text == "hello"


def test_complete_passes_through_when_tool_calls_present() -> None:
    """Tool calls without text content are valid (tool-only turn)."""
    raw_call = SimpleNamespace(
        id="call_1",
        function=SimpleNamespace(name="run_shell", arguments="{}"),
    )
    client = FakeClient(
        response(content=None, tool_calls=[raw_call], finish_reason="tool_calls")
    )
    provider = OpenAIProvider(client=client)

    turn = provider.complete(model="gpt-4o", messages=[{"role": "user", "content": "hi"}])

    assert turn.has_tool_calls
    assert turn.tool_calls[0].name == "run_shell"
