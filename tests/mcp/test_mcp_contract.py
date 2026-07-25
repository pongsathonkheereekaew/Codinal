import asyncio
from types import SimpleNamespace

import pytest

from runtime.mcp import (
    MCPManager,
    MCPServerDef,
    register_mcp_tools,
    tool_name,
)
from runtime.mcp.client import _result_payload, _safe_stdio_environment
from runtime.policy import (
    Mode,
    PermissionEngine,
    RiskClass,
    ToolManifest,
    classify,
)
from runtime.tools import ToolRegistry


@pytest.mark.parametrize(
    "url",
    [
        "http://example.com/mcp",
        "https://user:password@example.com/mcp",
        "https://example.com/mcp?token=plaintext",
        "file:///tmp/mcp",
    ],
)
def test_http_server_rejects_insecure_or_credential_bearing_urls(url):
    with pytest.raises(ValueError, match="invalid MCP HTTP URL"):
        MCPServerDef(name="server", transport="http", url=url)


def test_http_server_accepts_https_and_loopback_http():
    assert MCPServerDef(
        name="remote",
        transport="http",
        url="https://mcp.example.com/v1",
    ).url == "https://mcp.example.com/v1"
    assert MCPServerDef(
        name="local",
        transport="http",
        url="http://127.0.0.1:43123/mcp",
    ).url == "http://127.0.0.1:43123/mcp"


def test_stdio_server_uses_executable_and_argv_not_shell_string(tmp_path):
    server = MCPServerDef(
        name="local",
        transport="stdio",
        command="python3",
        args=["-m", "example"],
        cwd=str(tmp_path),
    )

    assert server.command == "python3"
    assert server.args == ["-m", "example"]
    with pytest.raises(ValueError, match="invalid MCP command"):
        MCPServerDef(
            name="bad",
            transport="stdio",
            command="python3 -m example",
        )


def test_connect_requires_explicit_host_approval():
    manager = MCPManager()
    server = MCPServerDef(
        name="remote",
        transport="http",
        url="https://mcp.example.com/v1",
    )

    async def scenario():
        await manager.connect(server, approved=False)

    with pytest.raises(PermissionError, match="explicit approval"):
        asyncio.run(scenario())


def test_sanitized_tool_names_are_bounded_and_collision_resistant():
    first = tool_name("server", "tool.with.dot")
    second = tool_name("server", "tool_with_dot")
    long = tool_name("server" * 20, "tool" * 20)

    assert first != second
    assert len(first) <= 64
    assert len(second) <= 64
    assert len(long) <= 64


def test_registered_mcp_tool_is_manifest_external_and_policy_gated(
    tmp_path,
):
    calls = []
    manifest = ToolManifest()
    registry = ToolRegistry(manifest)
    server = MCPServerDef(
        name="docs",
        transport="http",
        url="https://mcp.example.com/v1",
    )
    remote_tool = SimpleNamespace(
        name="search",
        description="Search remote docs",
        inputSchema={
            "type": "object",
            "properties": {"query": {"type": "string"}},
            "required": ["query"],
        },
    )

    async def scenario():
        loop = asyncio.get_running_loop()

        async def call_async(name, arguments):
            calls.append((name, arguments))
            return {"matches": 1}

        names = register_mcp_tools(
            registry=registry,
            manifest=manifest,
            server=server,
            mcp_tools=[remote_tool],
            call_async=call_async,
            loop=loop,
        )
        result = await asyncio.to_thread(
            registry.execute,
            names[0],
            {"query": "policy"},
        )
        return names, result

    names, result = asyncio.run(scenario())
    metadata = manifest.metadata_for(names[0])
    decision = PermissionEngine(
        tmp_path,
        mode=Mode.INTERACTIVE,
    ).evaluate(
        names[0],
        {"query": "policy"},
        metadata,
    )

    assert result == {"matches": 1}
    assert calls == [("search", {"query": "policy"})]
    assert classify(names[0], metadata) is RiskClass.EXTERNAL
    assert decision.allowed is False
    assert decision.needs_user is True
    schema = registry.schemas()[0]["function"]["parameters"]
    assert schema["additionalProperties"] is False


def test_invalid_or_oversized_mcp_schema_is_rejected():
    manifest = ToolManifest()
    registry = ToolRegistry(manifest)
    server = MCPServerDef(
        name="docs",
        transport="http",
        url="https://mcp.example.com/v1",
    )
    invalid = SimpleNamespace(
        name="bad",
        description="bad",
        inputSchema={"type": "array"},
    )
    loop = asyncio.new_event_loop()

    try:
        with pytest.raises(ValueError, match="invalid MCP tool schema"):
            register_mcp_tools(
                registry=registry,
                manifest=manifest,
                server=server,
                mcp_tools=[invalid],
                call_async=lambda _name, _arguments: None,
                loop=loop,
            )
    finally:
        loop.close()


def test_remote_error_body_and_control_tokens_are_not_forwarded(
    monkeypatch,
):
    monkeypatch.setenv(
        "CODINAL_SESSION_TOKEN",
        "control-token-must-not-reach-mcp",
    )
    result = SimpleNamespace(
        isError=True,
        content=[
            SimpleNamespace(
                type="text",
                text="remote-secret-must-not-echo",
            )
        ],
        structuredContent=None,
    )

    payload = _result_payload(result)
    environment = _safe_stdio_environment()

    assert payload == {"error": "MCP tool failed"}
    assert "remote-secret-must-not-echo" not in str(payload)
    assert "CODINAL_SESSION_TOKEN" not in environment
