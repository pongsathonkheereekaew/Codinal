import sys
from types import SimpleNamespace

import pytest

from runtime.providers import GeminiProvider, ToolCall
from runtime.providers.gemini_provider import resolve_api_key
from runtime.secrets import ProviderSecretService


def test_gemini_key_comes_only_from_memory_secret_service(
    monkeypatch,
) -> None:
    monkeypatch.setenv("GEMINI_API_KEY", "ignored-gemini-env-key")
    monkeypatch.setenv("GOOGLE_API_KEY", "ignored-google-env-key")
    secrets = ProviderSecretService()
    secrets.set_api_key("gemini", "native-memory-key")

    assert resolve_api_key(secrets) == "native-memory-key"
    assert resolve_api_key(None) is None


def test_gemini_complete_normalizes_function_calls() -> None:
    part = SimpleNamespace(
        function_call=SimpleNamespace(
            name="workspace.read_file",
            args={"path": "README.md"},
        ),
        thought_signature=None,
    )
    response = SimpleNamespace(
        candidates=[
            SimpleNamespace(
                content=SimpleNamespace(parts=[part]),
                finish_reason=SimpleNamespace(name="STOP"),
            )
        ]
    )
    models = SimpleNamespace(
        generate_content=lambda **_kwargs: response
    )
    provider = GeminiProvider(
        client=SimpleNamespace(models=models)
    )

    turn = provider.complete(
        model="gemini-2.5-flash",
        messages=[{"role": "user", "content": "read"}],
    )

    assert turn.tool_calls == [
        ToolCall(
            id="call_0",
            name="workspace.read_file",
            arguments={"path": "README.md"},
        )
    ]
    assert turn.finish_reason == "tool_calls"


def test_gemini_environment_keys_are_never_echoed(
    monkeypatch,
) -> None:
    marker = "environment-key-must-not-echo"
    monkeypatch.setenv("GEMINI_API_KEY", marker)
    monkeypatch.setitem(
        sys.modules,
        "google",
        SimpleNamespace(
            genai=SimpleNamespace(Client=lambda **_kwargs: object())
        ),
    )

    with pytest.raises(RuntimeError) as caught:
        GeminiProvider()._ensure_client()

    assert str(caught.value) == (
        "No Gemini API key configured. Add it in Settings."
    )
    assert marker not in str(caught.value)
