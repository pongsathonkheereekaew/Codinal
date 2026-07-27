"""Adversarial corpus: secret exfiltration via outbound channels.

A registered provider key must not reach (a) the provider feed, (b) the audit
ledger, or (c) an MCP tool argument unredacted. Each test plants the key in a
tool result or argument and asserts only ``[REDACTED:...]`` leaves the trust
boundary.
"""

from __future__ import annotations

import asyncio
import json

from runtime.audit import AuditLedger
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


def _build_engine(tmp_path, redactor, provider):
    secrets = ProviderSecretService()
    secrets.set_api_key("openai", _KEY)
    red = redactor or SecretRedactor(secrets)

    def read_file():
        return f"found this in env: {_KEY}"

    registry = ToolRegistry(ToolManifest())
    registry.manifest.add(
        ToolSpec(
            name="read_file",
            risk=RiskClass.READ,
            category="read",
            requires_approval=False,
        )
    )
    registry.register(read_file, schema=_schema("read_file"))
    return TurnEngine(
        provider=provider,
        registry=registry,
        permissions=PermissionEngine(tmp_path, mode=Mode.INTERACTIVE),
        model="openai:gpt-test",
        redactor=red,
    ), secrets


def test_secret_in_tool_result_does_not_reach_provider(tmp_path):
    provider = _CapturingProvider(
        [
            AssistantTurn(tool_calls=[ToolCall("c1", "read_file", {})]),
            AssistantTurn(text="done"),
        ]
    )
    engine, _ = _build_engine(tmp_path, None, provider)

    asyncio.run(_collect(engine))

    for batch in provider.received:
        for message in batch:
            content = json.dumps(message)
            assert _KEY not in content, (
                "raw provider key reached the provider feed"
            )
            if "[REDACTED:openai]" in content:
                assert _KEY not in content


def test_secret_in_tool_result_does_not_reach_audit_ledger(tmp_path):
    """Audit payloads must be redacted before persistence."""
    secrets = ProviderSecretService()
    secrets.set_api_key("openai", _KEY)
    ledger = AuditLedger(tmp_path / "audit", redactor=SecretRedactor(secrets))

    ledger.record(
        "test",
        "exfil_attempt",
        payload={"stdout": f"key={_KEY}"},
    )

    rows = ledger.list(domain="test")
    stored = json.dumps(rows)
    assert _KEY not in stored
    assert "[REDACTED:openai]" in stored
    # Chain still verifies (redaction happened before hashing).
    assert ledger.verify_chain() is True


def test_redactor_handles_key_in_tool_arguments(tmp_path):
    """A model trying to exfil via tool arguments is still redacted outbound."""
    secrets = ProviderSecretService()
    secrets.set_api_key("openai", _KEY)
    redactor = SecretRedactor(secrets)
    messages = [
        {
            "role": "assistant",
            "tool_calls": [
                {
                    "id": "c1",
                    "type": "function",
                    "function": {
                        "name": "write_file",
                        "arguments": json.dumps(
                            {"content": f"token={_KEY}"}
                        ),
                    },
                }
            ],
        }
    ]

    redacted = redactor.redact_messages(messages)

    assert _KEY not in redacted[0]["tool_calls"][0]["function"]["arguments"]
    assert "[REDACTED:openai]" in redacted[0]["tool_calls"][0]["function"]["arguments"]
    # Original untouched.
    assert _KEY in messages[0]["tool_calls"][0]["function"]["arguments"]


def test_transcript_keeps_original_while_outbound_is_scrubbed(tmp_path):
    provider = _CapturingProvider(
        [
            AssistantTurn(tool_calls=[ToolCall("c1", "read_file", {})]),
            AssistantTurn(text="done"),
        ]
    )
    engine, _ = _build_engine(tmp_path, None, provider)

    asyncio.run(_collect(engine))

    # In-memory transcript keeps the raw key (user sees fidelity).
    transcript = json.dumps(engine.messages)
    assert _KEY in transcript
    # Outbound feed does not.
    outbound = json.dumps(provider.received)
    assert _KEY not in outbound


async def _collect(engine):
    return [event async for event in engine.run("inspect")]
