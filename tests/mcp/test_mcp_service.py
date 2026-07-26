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
        self.disconnects: list[tuple[str, int]] = []
        self.connected: set[str] = set()

    async def connect(self, _server, *, approved):
        assert approved is True
        self.connects += 1
        self.connected.add(_server.name)
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

    async def disconnect(self, server_name: str) -> bool:
        self.disconnects.append((server_name, len(self.disconnects) + 1))
        existed = server_name in self.connected
        self.connected.discard(server_name)
        return existed

    async def list(self):
        return sorted(self.connected)

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


def test_list_connected_mcp_servers():
    manager = FakeManager()
    registry = ToolRegistry(ToolManifest())
    engine = SimpleNamespace(registry=registry)
    service = MCPService(
        manager=manager,
        sessions=FakeSessions(SimpleNamespace(registry=registry)),
        turns=FakeTurns(),
    )

    connected = asyncio.run(service.connect("session-1", server(), approved=True))

    assert connected["server"] == "docs"
    assert service.list_connected("session-1") == [
        {
            "name": "docs",
            "transport": "http",
            "url": "https://mcp.example.com/v1",
            "command": None,
            "cwd": None,
            "tools": [connected["tools"][0]],
            "include_tools": None,
            "exclude_tools": [],
        }
    ]


def test_disconnect_detaches_tools_and_closes_shared_manager_connection():
    turns = FakeTurns()
    manager = FakeManager()

    class SplitSessions:
        def __init__(self) -> None:
            self._engines = {
                "session-1": SimpleNamespace(
                    registry=ToolRegistry(ToolManifest())
                ),
                "session-2": SimpleNamespace(
                    registry=ToolRegistry(ToolManifest())
                ),
            }

        def get_engine(self, session_id: str):
            return self._engines[session_id]

    sessions = SplitSessions()
    service = MCPService(
        manager=manager,
        sessions=sessions,
        turns=turns,
    )

    connected = asyncio.run(service.connect("session-1", server(), approved=True))
    assert connected["tools"]
    first = asyncio.run(service.connect("session-2", server(), approved=True))
    assert first["tools"][0] == connected["tools"][0]

    disconnected = asyncio.run(service.disconnect("session-1", "docs"))
    assert "docs__search" not in sessions.get_engine("session-1").registry.names()
    assert "mcp__docs__search" in sessions.get_engine("session-2").registry.names()
    assert disconnected["server"] == "docs"
    assert manager.disconnects == []

    second = asyncio.run(service.disconnect("session-2", "docs"))
    assert second["server"] == "docs"
    assert manager.disconnects == [("docs", 1)]
