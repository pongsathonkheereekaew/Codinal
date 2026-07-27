import asyncio
from types import SimpleNamespace

import pytest

from runtime.audit import AuditLedger
from runtime.mcp import MCPServerDef, MCPService, MCPStore
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
            "enabled": True,
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


def _service_with_store(tmp_path, manager=None):
    manager = manager or FakeManager()
    registry = ToolRegistry(ToolManifest())
    engine = SimpleNamespace(registry=registry)
    sessions = FakeSessions(engine)
    turns = FakeTurns()
    store = MCPStore(tmp_path)
    audit = AuditLedger(tmp_path)
    service = MCPService(
        manager=manager,
        sessions=sessions,
        turns=turns,
        store=store,
        audit=audit,
    )
    return service, manager, store, audit, engine


def test_connect_persists_to_store_and_emits_audit(tmp_path):
    service, manager, store, audit, engine = _service_with_store(tmp_path)
    connected = asyncio.run(service.connect("session-1", server(), approved=True))
    assert connected["ok"] is True

    persisted = store.list("session-1")
    assert len(persisted) == 1
    assert persisted[0][0] == server()
    assert persisted[0][1] is True

    events = audit.list(domain="mcp")
    assert [event["action"] for event in events] == ["connect"]
    assert events[0]["subject"] == "docs"
    assert audit.verify_chain() is True


def test_disable_detaches_tools_and_enable_re_registers(tmp_path):
    service, manager, store, audit, engine = _service_with_store(tmp_path)
    asyncio.run(service.connect("session-1", server(), approved=True))
    tool_name = engine.registry.names()[0]
    assert tool_name == "mcp__docs__search"

    disabled = asyncio.run(service.set_enabled("session-1", "docs", enabled=False))
    assert disabled["enabled"] is False
    assert tool_name not in engine.registry.names()
    assert store.is_enabled("session-1", "docs") is False

    enabled = asyncio.run(service.set_enabled("session-1", "docs", enabled=True))
    assert enabled["enabled"] is True
    assert tool_name in engine.registry.names()
    assert store.is_enabled("session-1", "docs") is True

    actions = [event["action"] for event in audit.list(domain="mcp")]
    assert actions == ["enable", "disable", "connect"]
    assert audit.verify_chain() is True


def test_disable_surfaces_durable_disabled_server_in_list(tmp_path):
    service, manager, store, audit, engine = _service_with_store(tmp_path)
    asyncio.run(service.connect("session-1", server(), approved=True))
    asyncio.run(service.set_enabled("session-1", "docs", enabled=False))

    listed = service.list_connected("session-1")
    assert listed == [
        {
            "name": "docs",
            "transport": "http",
            "url": "https://mcp.example.com/v1",
            "command": None,
            "cwd": None,
            "tools": [],
            "include_tools": None,
            "exclude_tools": [],
            "enabled": False,
        }
    ]


def test_disconnect_removes_durable_row(tmp_path):
    service, manager, store, audit, engine = _service_with_store(tmp_path)
    asyncio.run(service.connect("session-1", server(), approved=True))
    assert store.list("session-1")

    asyncio.run(service.disconnect("session-1", "docs"))
    assert store.list("session-1") == []
    actions = [event["action"] for event in audit.list(domain="mcp")]
    assert actions == ["disconnect", "connect"]


def test_recover_reconnects_enabled_and_skips_disabled(tmp_path):
    # First lifecycle: connect docs (enabled) + disable it, then connect a
    # second server that stays enabled.
    manager = FakeManager()
    store = MCPStore(tmp_path)
    audit = AuditLedger(tmp_path)

    docs = server()
    cache = MCPServerDef(
        name="cache",
        transport="http",
        url="https://mcp.example.com/cache",
    )

    registry = ToolRegistry(ToolManifest())
    engine = SimpleNamespace(registry=registry)
    sessions = FakeSessions(engine)
    turns = FakeTurns()
    service = MCPService(
        manager=manager,
        sessions=sessions,
        turns=turns,
        store=store,
        audit=audit,
    )
    asyncio.run(service.connect("session-1", docs, approved=True))
    asyncio.run(service.connect("session-1", cache, approved=True))
    asyncio.run(service.set_enabled("session-1", "docs", enabled=False))
    # Clear the in-memory attachments to simulate a fresh process.
    service._attached.clear()
    registry_a = ToolRegistry(ToolManifest())
    engine.registry = registry_a

    recovered = asyncio.run(service.recover())
    # cache (enabled) reconnects; docs (disabled) stays dormant.
    assert recovered == 1
    assert "mcp__cache__search" in registry_a.names()
    assert "mcp__docs__search" not in registry_a.names()
    assert store.is_enabled("session-1", "docs") is False
    assert store.is_enabled("session-1", "cache") is True

    actions = [event["action"] for event in audit.list(domain="mcp")]
    assert "recover" in actions
    assert audit.verify_chain() is True


def test_recover_without_store_is_noop():
    service = MCPService(
        manager=FakeManager(),
        sessions=FakeSessions(None),
        turns=FakeTurns(),
    )
    assert asyncio.run(service.recover()) == 0


def test_recover_records_failure_when_transport_unavailable(tmp_path):
    class FailingManager(FakeManager):
        async def connect(self, _server, *, approved):
            raise RuntimeError("transport gone")

    service, manager, store, audit, engine = _service_with_store(
        tmp_path, manager=FailingManager()
    )
    store.upsert("session-1", server(), enabled=True)
    recovered = asyncio.run(service.recover())
    assert recovered == 0
    actions = [event["action"] for event in audit.list(domain="mcp")]
    assert actions == ["recover_failed"]
