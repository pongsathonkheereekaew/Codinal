import platform
import sys
import time
from pathlib import Path
from types import SimpleNamespace

import pytest
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
    assert provider.tool_names == [
        "read_file",
        "list_files",
        "grep",
        "write_file",
        "replace_in_file",
        "run_shell",
    ]
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


def test_production_mutation_requires_approval_and_persists_result(
    tmp_path,
):
    class WriteThenAnswerProvider(ProviderClient):
        def __init__(self):
            self.calls = 0

        def complete(self, **_kwargs):
            self.calls += 1
            if self.calls == 1:
                return AssistantTurn(
                    tool_calls=[
                        ToolCall(
                            "write_call_1",
                            "write_file",
                            {
                                "path": "generated.txt",
                                "content": "approved mutation\n",
                            },
                        )
                    ]
                )
            return AssistantTurn(text="mutation complete")

        def capabilities(self, _model):
            return ModelCapabilities()

    approvals = []

    async def approve_once(request):
        approvals.append(request)
        return ApprovalOutcome.ONCE

    workspace = tmp_path / "workspace"
    workspace.mkdir()
    config = ServerConfig(
        token=TOKEN,
        port=43123,
        data_dir=tmp_path / "data",
        default_model="openai:gpt-test",
    )
    services = build_services(
        config,
        provider=WriteThenAnswerProvider(),
        approver=approve_once,
    )
    events = []

    with TestClient(
        create_control_plane_app(token=TOKEN, services=services)
    ) as client:
        with client.websocket_connect(
            "/ws/session/session-write",
            subprotocols=[
                "codinal.v1",
                websocket_auth_protocol(TOKEN),
            ],
        ) as socket:
            accepted = client.post(
                "/v1/sessions/session-write/turns",
                headers=AUTH,
                json={
                    "input": "create generated.txt",
                    "workspace": str(workspace),
                },
            )
            while not events or events[-1]["type"] != "turn_end":
                events.append(socket.receive_json())

    assert accepted.status_code == 202
    assert [approval.tool_name for approval in approvals] == ["write_file"]
    assert "permission_required" in [event["type"] for event in events]
    assert (workspace / "generated.txt").read_text(
        encoding="utf-8"
    ) == "approved mutation\n"
    tool_message = next(
        message
        for message in services.sessions.messages("session-write")
        if message.get("role") == "tool"
    )
    assert '"ok": true' in tool_message["content"]
    sandbox_directories = list((config.data_dir / "sandbox").iterdir())
    assert len(sandbox_directories) == 1

    deleted = services.sessions.delete("session-write")

    assert deleted == {"ok": True, "session_id": "session-write"}
    assert not sandbox_directories[0].exists()


@pytest.mark.skipif(
    platform.system() != "Darwin",
    reason="Seatbelt is a macOS release boundary",
)
def test_production_interrupt_kills_active_sandbox_command(tmp_path):
    class SleepingProvider(ProviderClient):
        def complete(self, **_kwargs):
            return AssistantTurn(
                tool_calls=[
                    ToolCall(
                        "shell_call_1",
                        "run_shell",
                        {
                            "command": (
                                f"{Path(sys.executable).resolve()} -c "
                                "\"import time; time.sleep(10)\""
                            ),
                        },
                    )
                ]
            )

        def capabilities(self, _model):
            return ModelCapabilities()

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
    services = build_services(
        config,
        provider=SleepingProvider(),
        approver=approve_once,
    )
    started_at = time.monotonic()
    events = []

    with TestClient(
        create_control_plane_app(token=TOKEN, services=services)
    ) as client:
        with client.websocket_connect(
            "/ws/session/session-shell",
            subprotocols=[
                "codinal.v1",
                websocket_auth_protocol(TOKEN),
            ],
        ) as socket:
            client.post(
                "/v1/sessions/session-shell/turns",
                headers=AUTH,
                json={
                    "input": "run the long command",
                    "workspace": str(workspace),
                },
            )
            while not events or events[-1]["type"] != "tool_started":
                events.append(socket.receive_json())
            interrupted = client.post(
                "/v1/sessions/session-shell/interrupt",
                headers=AUTH,
            )
            while events[-1]["type"] != "interrupted":
                events.append(socket.receive_json())

    assert interrupted.status_code == 200
    assert interrupted.json()["ok"] is True
    assert time.monotonic() - started_at < 2
    assert events[-1]["type"] == "interrupted"
    shell_result = next(
        message
        for message in services.sessions.messages("session-shell")
        if message.get("role") == "tool"
    )
    assert '"interrupted": true' in shell_result["content"]


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
