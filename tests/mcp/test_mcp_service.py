import asyncio
from types import SimpleNamespace

import pytest

from runtime.mcp import MCPServerDef, MCPService
from runtime.policy import ToolManifest
from runtime.tools import ToolRegistry
from runtime.turns import SessionBusyError, SessionNotFoundError


class FakeSessions:
    def __init__(self, engine):
        self.engine = engine

    def get_engine(self, _session_id):
        return self.engine


class FakeTurns:
    def __init__(self):
        self.active = False

    def is_active(self, _session_id):
        return self.active


class FakeManager:
    def __init__(self, turns=None):
        self.turns = turns
        self.connects = 0

    async def connect(self, _server, *, approved):
        assert approved is True
        self.connects += 1
        if self.turns is not None:
            self.turns.active = True
        return [
            SimpleNamespace(
                name="search",
                description="search",
                inputSchema={
                    "type": "object",
                    "properties": {},
                },
            )
        ]

    async def call(self, _server, _tool, _arguments):
        return {}

    async def aclose(self):
        pass


def server():
    return MCPServerDef(
        name="docs",
        transport="http",
        url="https://mcp.example.com/v1",
    )


def test_missing_session_does_not_open_external_connection():
    manager = FakeManager()
    service = MCPService(
        manager=manager,
        sessions=FakeSessions(None),
        turns=FakeTurns(),
    )

    with pytest.raises(SessionNotFoundError):
        asyncio.run(
            service.connect("missing", server(), approved=True)
        )

    assert manager.connects == 0


def test_turn_starting_during_connect_blocks_registry_mutation():
    turns = FakeTurns()
    manager = FakeManager(turns)
    registry = ToolRegistry(ToolManifest())
    engine = SimpleNamespace(registry=registry)
    service = MCPService(
        manager=manager,
        sessions=FakeSessions(engine),
        turns=turns,
    )

    with pytest.raises(SessionBusyError):
        asyncio.run(
            service.connect("session-1", server(), approved=True)
        )

    assert manager.connects == 1
    assert registry.names() == []
