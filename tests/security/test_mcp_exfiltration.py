"""Adversarial corpus: secret exfiltration via MCP tool arguments.

MCP tool calls are live network/subprocess egress — the primary exfiltration
channel. A model tricked by an injection (or a malicious model) that tries to
send a registered secret as an MCP tool argument must have it redacted before
the transport sees it.
"""

from __future__ import annotations

import asyncio
from types import SimpleNamespace

from runtime.mcp import MCPServerDef, MCPService
from runtime.policy import ToolManifest
from runtime.secrets import ProviderSecretService, SecretRedactor
from runtime.tools import ToolRegistry


_KEY = "sk-test-EXFIL-1234567890abcdef"


class _RecordingManager:
    """Fake MCP transport that records every call's arguments."""

    def __init__(self):
        self.calls = []

    async def connect(self, _server, *, approved):
        return [
            SimpleNamespace(
                name="search",
                description="search",
                inputSchema={"type": "object", "properties": {}},
            )
        ]

    async def call(self, server_name, tool, arguments):
        self.calls.append((server_name, tool, arguments))
        return "ok"

    async def disconnect(self, _name):
        return True

    async def list(self):
        return []

    async def aclose(self):
        pass


class _FakeSessions:
    def __init__(self, engine):
        self.engine = engine

    def get_engine(self, _session_id):
        return self.engine


class _FakeTurns:
    def is_active(self, _session_id):
        return False


def _build_service(tmp_path):
    secrets = ProviderSecretService()
    secrets.set_api_key("openai", _KEY)
    manager = _RecordingManager()
    registry = ToolRegistry(ToolManifest())
    engine = SimpleNamespace(registry=registry)
    service = MCPService(
        manager=manager,
        sessions=_FakeSessions(engine),
        turns=_FakeTurns(),
        redactor=SecretRedactor(secrets),
    )
    return service, manager, registry


async def _connect_and_call(service, server, registry, *, query):
    """connect + invoke inside one running loop.

    invoke() is synchronous and blocks on a future scheduled onto the loop, so
    it MUST run in a worker thread (not the loop thread) — exactly as the real
    engine does via asyncio.to_thread.
    """
    await service.connect("session-1", server, approved=True)
    invoke = registry.get("mcp__docs__search").func
    return await asyncio.to_thread(invoke, query=query)


def test_mcp_argument_carrying_secret_is_redacted_before_transport(tmp_path):
    service, manager, registry = _build_service(tmp_path)
    server = MCPServerDef(
        name="docs",
        transport="http",
        url="https://mcp.example.com/v1",
    )

    asyncio.run(_connect_and_call(service, server, registry, query=f"token={_KEY}"))

    assert len(manager.calls) == 1
    _server, _tool, arguments = manager.calls[0]
    dumped = str(arguments)
    assert _KEY not in dumped
    assert "[REDACTED:openai]" in dumped


def test_mcp_argument_without_secret_passes_through_untouched(tmp_path):
    service, manager, registry = _build_service(tmp_path)
    server = MCPServerDef(
        name="docs",
        transport="http",
        url="https://mcp.example.com/v1",
    )

    asyncio.run(
        _connect_and_call(service, server, registry, query="legitimate search term")
    )

    _server, _tool, arguments = manager.calls[0]
    assert arguments["query"] == "legitimate search term"


def test_mcp_without_redactor_does_not_redact():
    """When no redactor is wired (e.g. standalone tests), arguments pass through.

    This pins that redaction is opt-in at the composition boundary, so the
    MCPService remains usable in isolation for non-security contexts.
    """
    manager = _RecordingManager()
    registry = ToolRegistry(ToolManifest())
    engine = SimpleNamespace(registry=registry)
    service = MCPService(
        manager=manager,
        sessions=_FakeSessions(engine),
        turns=_FakeTurns(),
    )
    server = MCPServerDef(
        name="docs",
        transport="http",
        url="https://mcp.example.com/v1",
    )

    asyncio.run(_connect_and_call(service, server, registry, query=f"token={_KEY}"))

    _server, _tool, arguments = manager.calls[0]
    assert arguments["query"] == f"token={_KEY}"
