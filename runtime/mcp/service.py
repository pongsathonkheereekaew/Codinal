"""Attach explicitly connected MCP servers to idle session engines."""

from __future__ import annotations

import asyncio
from typing import Any

from runtime.sessions import SessionService
from runtime.turns import (
    SessionBusyError,
    SessionNotFoundError,
    TurnCoordinator,
)

from .client import MCPManager
from .config import MCPServerDef
from .tools import register_mcp_tools


class MCPService:
    def __init__(
        self,
        *,
        manager: MCPManager,
        sessions: SessionService,
        turns: TurnCoordinator,
    ) -> None:
        self._manager = manager
        self._sessions = sessions
        self._turns = turns
        self._attached: dict[
            tuple[str, str],
            tuple[MCPServerDef, list[str]],
        ] = {}

    async def connect(
        self,
        session_id: str,
        server: MCPServerDef,
        *,
        approved: bool,
    ) -> dict[str, Any]:
        if self._turns.is_active(session_id):
            raise SessionBusyError("session already has an active turn")
        if self._sessions.get_engine(session_id) is None:
            raise SessionNotFoundError(session_id)
        key = (session_id, server.name)
        existing = self._attached.get(key)
        if existing is not None:
            definition, names = existing
            if definition != server:
                raise ValueError("MCP server definition changed")
            return {
                "ok": True,
                "server": server.name,
                "tools": list(names),
            }
        remote_tools = await self._manager.connect(
            server,
            approved=approved,
        )
        # A turn may have started while the transport was connecting. Never
        # mutate the advertised tool set mid-iteration.
        if self._turns.is_active(session_id):
            raise SessionBusyError("session already has an active turn")
        engine = self._sessions.get_engine(session_id)
        if engine is None:
            raise SessionNotFoundError(session_id)
        loop = asyncio.get_running_loop()
        names = register_mcp_tools(
            registry=engine.registry,
            manifest=engine.registry.manifest,
            server=server,
            mcp_tools=remote_tools,
            call_async=lambda tool, arguments: self._manager.call(
                server.name,
                tool,
                arguments,
            ),
            loop=loop,
        )
        self._attached[key] = (server, names)
        return {
            "ok": True,
            "server": server.name,
            "tools": list(names),
        }

    def list_connected(self, session_id: str) -> list[dict[str, Any]]:
        engine = self._sessions.get_engine(session_id)
        if engine is None:
            raise SessionNotFoundError(session_id)
        entries: list[dict[str, Any]] = []
        for (session, name), (server, tools) in self._attached.items():
            if session != session_id:
                continue
            entries.append(
                {
                    "name": server.name,
                    "transport": server.transport,
                    "url": server.url,
                    "command": server.command,
                    "cwd": server.cwd,
                    "tools": list(tools),
                    "include_tools": server.include_tools,
                    "exclude_tools": server.exclude_tools,
                }
            )
        entries.sort(key=lambda item: item["name"])
        return entries

    async def disconnect(self, session_id: str, name: str) -> dict[str, Any]:
        if self._turns.is_active(session_id):
            raise SessionBusyError("session already has an active turn")
        engine = self._sessions.get_engine(session_id)
        if engine is None:
            raise SessionNotFoundError(session_id)
        key = (session_id, name)
        existing = self._attached.pop(key, None)
        if existing is None:
            raise ValueError("MCP server not connected")
        server, names = existing
        for tool_name in names:
            engine.registry.unregister(tool_name)
        if not any(
            attached_name == name and attached_session != session_id
            for attached_session, attached_name in self._attached
        ):
            await self._manager.disconnect(server.name)
        return {
            "ok": True,
            "server": server.name,
            "tools": list(names),
        }

    async def aclose(self) -> None:
        await self._manager.aclose()
