import json

from runtime.mcp import MCPServerDef, MCPStore


def _http_server(name: str = "server-a") -> MCPServerDef:
    return MCPServerDef(
        name=name,
        transport="http",
        url="https://example.test/mcp",
    )


def _stdio_server(name: str = "server-b") -> MCPServerDef:
    return MCPServerDef(
        name=name,
        transport="stdio",
        command="/usr/bin/python",
        args=["-m", "demo"],
    )


def test_mcp_store_round_trips_definitions_and_survives_restart(tmp_path):
    first = MCPStore(tmp_path)
    first.upsert("session-1", _http_server())
    first.upsert("session-1", _stdio_server())
    first.upsert("session-2", _http_server("server-c"))
    first.close()

    restarted = MCPStore(tmp_path)
    entries = restarted.list("session-1")
    assert [server.name for server, _enabled in entries] == [
        "server-a",
        "server-b",
    ]
    http_server, http_enabled = entries[0]
    assert http_server == _http_server()
    assert http_enabled is True
    assert restarted.list("session-2")[0][0].name == "server-c"
    restarted.close()


def test_mcp_store_lists_only_enabled_connections(tmp_path):
    store = MCPStore(tmp_path)
    store.upsert("session-1", _http_server(), enabled=True)
    store.upsert("session-1", _stdio_server(), enabled=False)
    store.upsert("session-2", _http_server("server-c"), enabled=True)

    enabled = store.list_all_enabled()
    assert [(sid, server.name) for sid, server in enabled] == [
        ("session-1", "server-a"),
        ("session-2", "server-c"),
    ]
    store.close()


def test_mcp_store_toggles_enabled_without_dropping_definition(tmp_path):
    store = MCPStore(tmp_path)
    store.upsert("session-1", _http_server(), enabled=True)

    assert store.set_enabled("session-1", "server-a", False) is True
    assert store.is_enabled("session-1", "server-a") is False
    assert store.list_all_enabled() == []

    assert store.set_enabled("session-1", "server-a", True) is True
    server, enabled = store.list("session-1")[0]
    assert server == _http_server()
    assert enabled is True
    store.close()


def test_mcp_store_upsert_replaces_changed_definition(tmp_path):
    store = MCPStore(tmp_path)
    store.upsert("session-1", _http_server())
    updated = MCPServerDef(
        name="server-a",
        transport="http",
        url="https://example.test/mcp-v2",
    )
    store.upsert("session-1", updated)

    server, _ = store.list("session-1")[0]
    assert server.url == "https://example.test/mcp-v2"
    store.close()


def test_mcp_store_delete_and_delete_session(tmp_path):
    store = MCPStore(tmp_path)
    store.upsert("session-1", _http_server())
    store.upsert("session-1", _stdio_server())

    assert store.delete("session-1", "server-a") is True
    assert store.delete("session-1", "server-a") is False
    assert [s.name for s, _ in store.list("session-1")] == ["server-b"]

    assert store.delete_session("session-1") == 1
    assert store.list("session-1") == []
    store.close()


def test_mcp_store_recovers_from_corrupt_database_preserving_evidence(tmp_path):
    first = MCPStore(tmp_path)
    first.upsert("session-1", _http_server())
    first.close()

    (tmp_path / "mcp.db").write_bytes(b"corrupt mcp db")

    recovered = MCPStore(tmp_path)
    assert recovered.list("session-1") == []

    preserved = list((tmp_path / "recovery").glob("mcp.db.corrupt-*.preserved"))
    assert preserved and preserved[0].read_bytes() == b"corrupt mcp db"

    events_log = json.loads(
        (tmp_path / "recovery" / "events.jsonl").read_text().splitlines()[0]
    )
    assert events_log["action"] == "preserved_corrupt_state"
    recovered.close()
