import time
from types import SimpleNamespace

from fastapi.testclient import TestClient

from runtime.control_plane import (
    create_control_plane_app,
    websocket_auth_protocol,
)
from runtime.control_plane.server import ServerConfig, build_services
from runtime.providers import AssistantTurn, ModelCapabilities, ProviderClient
from runtime.policy import ApprovalOutcome, ToolCall


TOKEN = "test-session-token-with-at-least-32-characters"
AUTH = {"Authorization": f"Bearer {TOKEN}"}


class ReadThenAnswerProvider(ProviderClient):
    def __init__(self):
        self.calls = 0
        self.tool_names = []

    def complete(self, *, tools=None, **_kwargs):
        self.calls += 1
        self.tool_names = [
            tool["function"]["name"] for tool in (tools or [])
        ]
        if self.calls == 1:
            return AssistantTurn(
                tool_calls=[
                    ToolCall(
                        "call_1",
                        "read_file",
                        {"path": "README.md"},
                    )
                ]
            )
        return AssistantTurn(text="workspace inspected")

    def capabilities(self, _model):
        return ModelCapabilities()


def test_production_sidecar_turn_streams_tools_and_survives_restart(
    tmp_path,
):
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    (workspace / "README.md").write_text(
        "Codinal workspace",
        encoding="utf-8",
    )
    config = ServerConfig(
        token=TOKEN,
        port=43123,
        data_dir=tmp_path / "data",
        default_model="openai:gpt-test",
    )
    provider = ReadThenAnswerProvider()
    services = build_services(config, provider=provider)
    events = []

    with TestClient(
        create_control_plane_app(token=TOKEN, services=services)
    ) as client:
        with client.websocket_connect(
            "/ws/session/session-1",
            subprotocols=[
                "codinal.v1",
                websocket_auth_protocol(TOKEN),
            ],
        ) as socket:
            accepted = client.post(
                "/v1/sessions/session-1/turns",
                headers=AUTH,
                json={
                    "input": "inspect README",
                    "workspace": str(workspace),
                },
            )
            while not events or events[-1]["type"] != "turn_end":
                events.append(socket.receive_json())

    deadline = time.monotonic() + 1
    while not services.sessions.list_sessions():
        assert time.monotonic() < deadline
        time.sleep(0.01)

    assert accepted.status_code == 202
    assert provider.tool_names == ["read_file", "list_files", "grep"]
    assert [event["type"] for event in events] == [
        "turn_start",
        "assistant_message",
        "tool_proposed",
        "tool_started",
        "tool_finished",
        "iteration_end",
        "assistant_message",
        "turn_end",
    ]
    tool_result = [
        message
        for message in services.sessions.messages("session-1")
        if message.get("role") == "tool"
    ][0]
    assert "Codinal workspace" in tool_result["content"]

    restarted = build_services(
        config,
        provider=ReadThenAnswerProvider(),
    )
    persisted = restarted.sessions.messages("session-1")

    assert persisted == services.sessions.messages("session-1")
    assert persisted[-1]["content"] == "workspace inspected"


def test_explicit_mcp_connect_registers_policy_gated_session_tool(
    tmp_path,
):
    class MCPProvider(ProviderClient):
        def __init__(self):
            self.calls = 0

        def complete(self, *, tools=None, **_kwargs):
            self.calls += 1
            if self.calls == 1:
                return AssistantTurn(text="session ready")
            if self.calls == 2:
                mcp_name = next(
                    tool["function"]["name"]
                    for tool in tools
                    if tool["function"]["name"].startswith("mcp__")
                )
                return AssistantTurn(
                    tool_calls=[
                        ToolCall(
                            "mcp_call_1",
                            mcp_name,
                            {"query": "policy"},
                        )
                    ]
                )
            return AssistantTurn(text="remote result used")

        def capabilities(self, _model):
            return ModelCapabilities()

    class FakeMCPManager:
        def __init__(self):
            self.connected = []
            self.called = []
            self.closed = False

        async def connect(self, server, *, approved):
            self.connected.append((server.name, approved))
            return [
                SimpleNamespace(
                    name="search",
                    description="Search remote docs",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "query": {"type": "string"}
                        },
                        "required": ["query"],
                    },
                )
            ]

        async def call(self, server, tool, arguments):
            self.called.append((server, tool, arguments))
            return {"matches": ["policy.md"]}

        async def aclose(self):
            self.closed = True

    async def approve_once(_request):
        return ApprovalOutcome.ONCE

    workspace = tmp_path / "workspace"
    workspace.mkdir()
    config = ServerConfig(
        token=TOKEN,
        port=43123,
        data_dir=tmp_path / "data",
        default_model="openai:gpt-test",
    )
    manager = FakeMCPManager()
    services = build_services(
        config,
        provider=MCPProvider(),
        mcp_manager=manager,
        approver=approve_once,
    )

    with TestClient(
        create_control_plane_app(token=TOKEN, services=services)
    ) as client:
        with client.websocket_connect(
            "/ws/session/session-1",
            subprotocols=[
                "codinal.v1",
                websocket_auth_protocol(TOKEN),
            ],
        ) as socket:
            unauthorized_connect = client.post(
                "/v1/sessions/session-1/mcp/connect",
                json={
                    "server": {
                        "name": "docs",
                        "transport": "http",
                        "url": "https://mcp.example.com/v1",
                    }
                },
            )
            first = client.post(
                "/v1/sessions/session-1/turns",
                headers=AUTH,
                json={
                    "input": "prepare",
                    "workspace": str(workspace),
                },
            )
            while socket.receive_json()["type"] != "turn_end":
                pass
            connected = client.post(
                "/v1/sessions/session-1/mcp/connect",
                headers=AUTH,
                json={
                    "server": {
                        "name": "docs",
                        "transport": "http",
                        "url": "https://mcp.example.com/v1",
                    }
                },
            )
            second = client.post(
                "/v1/sessions/session-1/turns",
                headers=AUTH,
                json={"input": "search policy"},
            )
            second_events = []
            while (
                not second_events
                or second_events[-1]["type"] != "turn_end"
            ):
                second_events.append(socket.receive_json())

    assert unauthorized_connect.status_code == 401
    assert first.status_code == 202
    assert connected.status_code == 200
    assert connected.json()["tools"][0].startswith("mcp__docs__search")
    assert second.status_code == 202
    assert manager.connected == [("docs", True)]
    assert manager.called == [
        ("docs", "search", {"query": "policy"})
    ]
    assert "permission_required" in [
        event["type"] for event in second_events
    ]
    assert second_events[-1]["type"] == "turn_end"
    assert manager.closed is True
