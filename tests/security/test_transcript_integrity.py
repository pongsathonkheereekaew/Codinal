"""Adversarial corpus: defenses do not corrupt the user-visible transcript.

The fence and the redactor are defense-in-depth on the OUTBOUND path. The
user's in-memory transcript (and what gets persisted) must keep full fidelity
so the user can see exactly what happened — only the copy that leaves the
trust boundary is scrubbed/wrapped. This suite pins that separation.
"""

from __future__ import annotations

import asyncio
import json

from runtime.policy import (
    Mode,
    PermissionEngine,
    RiskClass,
    ToolCall,
    ToolManifest,
    ToolSpec,
)
from runtime.providers import AssistantTurn, ModelCapabilities, ProviderClient
from runtime.secrets import ProviderSecretService, SecretRedactor
from runtime.tools import ToolRegistry
from runtime.turn_engine import TurnEngine
from runtime.turn_engine.content_fence import UNTRUSTED_SYSTEM_GUIDANCE


_KEY = "sk-test-EXFIL-1234567890abcdef"


def _schema(name):
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


class _CapturingProvider(ProviderClient):
    def __init__(self, turns):
        self.turns = list(turns)
        self.received = []

    def complete(self, *, messages=None, **kwargs):
        self.received.append(json.loads(json.dumps(messages or [])))
        return self.turns.pop(0)

    def capabilities(self, _model):
        return ModelCapabilities()


def _build_engine(tmp_path):
    secrets = ProviderSecretService()
    secrets.set_api_key("openai", _KEY)

    def read_env():
        return f"OPENAI_API_KEY={_KEY}"

    registry = ToolRegistry(ToolManifest())
    registry.manifest.add(
        ToolSpec(name="read_env", risk=RiskClass.READ, category="read")
    )
    registry.register(read_env, schema=_schema("read_env"))
    engine = TurnEngine(
        provider=_CapturingProvider(
            [
                AssistantTurn(tool_calls=[ToolCall("c1", "read_env", {})]),
                AssistantTurn(text="done"),
            ]
        ),
        registry=registry,
        permissions=PermissionEngine(tmp_path, mode=Mode.INTERACTIVE),
        model="openai:gpt-test",
        instructions="You are a test agent.",
        redactor=SecretRedactor(secrets),
    )
    return engine


def test_in_memory_transcript_keeps_raw_secret_and_fence(tmp_path):
    engine = _build_engine(tmp_path)

    asyncio.run(_collect(engine))

    # Tool result in the transcript is fenced (good) but NOT redacted — the
    # user sees the real content for fidelity. Only the outbound copy is scrubbed.
    tool_messages = [
        m for m in engine.messages if m.get("role") == "tool"
    ]
    assert tool_messages
    transcript_content = tool_messages[0]["content"]
    assert "<tool_result>" in transcript_content
    assert _KEY in transcript_content  # raw key preserved for the user


def test_outbound_feed_is_both_fenced_and_redacted(tmp_path):
    engine = _build_engine(tmp_path)

    asyncio.run(_collect(engine))

    outbound = engine.provider.received
    for batch in outbound:
        for message in batch:
            if message.get("role") != "tool":
                continue
            content = message["content"]
            # Still fenced.
            assert "<tool_result>" in content
            # But the secret is gone.
            assert _KEY not in content
            assert "[REDACTED:openai]" in content


def test_system_prompt_carries_untrusted_content_guidance(tmp_path):
    engine = _build_engine(tmp_path)

    asyncio.run(_collect(engine))

    system_messages = [
        m for m in engine.messages if m.get("role") == "system"
    ]
    assert system_messages
    assert UNTRUSTED_SYSTEM_GUIDANCE in system_messages[0]["content"]
    # And it reaches the provider.
    for batch in engine.provider.received:
        for message in batch:
            if message.get("role") == "system":
                assert UNTRUSTED_SYSTEM_GUIDANCE in message["content"]
                return
    raise AssertionError("system message never reached the provider")


async def _collect(engine):
    return [event async for event in engine.run("inspect")]
