# SPDX-License-Identifier: MIT
# Copyright (c) 2024 Andrew Ng
# Adapted from andrewyng/openworker:
# coworker/mcp/client.py @ 54b4bfd82d75704a4079ecea4f8f622aa152dbde.
"""Explicit-connect async MCP lifecycle over the official SDK."""

from __future__ import annotations

import asyncio
import os
from contextlib import AsyncExitStack
from typing import Any, Optional

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client
from mcp.client.streamable_http import streamablehttp_client

from .config import MCPServerDef


class _Connection:
    def __init__(self, session: ClientSession, tools: list[Any]) -> None:
        self.session = session
        self.tools = tools
        self.shutdown = asyncio.Event()


class MCPManager:
    def __init__(self) -> None:
        self._connections: dict[str, _Connection] = {}
        self._tasks: dict[str, asyncio.Task[None]] = {}
        self._lock = asyncio.Lock()

    async def connect(
        self,
        server: MCPServerDef,
        *,
        approved: bool,
    ) -> list[Any]:
        """Connect only after an explicit host/user approval action."""
        if approved is not True:
            raise PermissionError("MCP connect requires explicit approval")
        async with self._lock:
            existing = self._connections.get(server.name)
            if existing is not None:
                return list(existing.tools)
            ready = asyncio.get_running_loop().create_future()
            task = asyncio.create_task(self._serve(server, ready))
            self._tasks[server.name] = task
            connection = await ready
            self._connections[server.name] = connection
            return list(connection.tools)

    async def call(
        self,
        server_name: str,
        tool_name: str,
        arguments: Optional[dict[str, Any]] = None,
    ) -> Any:
        connection = self._connections.get(server_name)
        if connection is None:
            raise RuntimeError("MCP server is not connected")
        result = await connection.session.call_tool(
            tool_name,
            arguments or {},
        )
        return _result_payload(result)

    async def aclose(self) -> None:
        for connection in tuple(self._connections.values()):
            connection.shutdown.set()
        for task in tuple(self._tasks.values()):
            try:
                await asyncio.wait_for(asyncio.shield(task), timeout=5)
            except asyncio.TimeoutError:
                task.cancel()
            except Exception:
                pass
        self._connections.clear()
        self._tasks.clear()

    async def _serve(
        self,
        server: MCPServerDef,
        ready: asyncio.Future,
    ) -> None:
        try:
            async with AsyncExitStack() as stack:
                if server.transport == "http":
                    read, write, *_ = await stack.enter_async_context(
                        streamablehttp_client(server.url or "")
                    )
                else:
                    params = StdioServerParameters(
                        command=server.command or "",
                        args=list(server.args),
                        env=_safe_stdio_environment(),
                        cwd=server.cwd,
                    )
                    read, write = await stack.enter_async_context(
                        stdio_client(params)
                    )
                session = await stack.enter_async_context(
                    ClientSession(read, write)
                )
                await session.initialize()
                listed = await session.list_tools()
                connection = _Connection(session, list(listed.tools))
                if not ready.done():
                    ready.set_result(connection)
                await connection.shutdown.wait()
        except Exception:
            if not ready.done():
                ready.set_exception(
                    RuntimeError("MCP connection failed")
                )
        finally:
            self._connections.pop(server.name, None)
            self._tasks.pop(server.name, None)


def _safe_stdio_environment() -> dict[str, str]:
    allowed = ("PATH", "HOME", "LANG", "LC_ALL", "TMPDIR")
    return {
        key: os.environ[key]
        for key in allowed
        if key in os.environ
    }


def _result_payload(result: Any) -> Any:
    texts = []
    for block in getattr(result, "content", None) or []:
        text = getattr(block, "text", None)
        if text is not None:
            texts.append(text)
        else:
            texts.append(f"[{getattr(block, 'type', 'content')}]")
    body = "\n".join(texts)
    if getattr(result, "isError", False):
        return {"error": "MCP tool failed"}
    structured = getattr(result, "structuredContent", None)
    if structured is not None and not body:
        return structured
    return body
