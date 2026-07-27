# SPDX-License-Identifier: MIT
# Copyright (c) 2024 Andrew Ng
# Adapted from andrewyng/openworker:
# coworker/mcp/tools.py @ 54b4bfd82d75704a4079ecea4f8f622aa152dbde.
"""Register remote MCP tools behind the local policy chokepoint."""

from __future__ import annotations

import asyncio
import hashlib
import json
import re
from typing import Any, Awaitable, Callable

from runtime.policy import RiskClass, ToolManifest, ToolSpec
from runtime.tools.registry import ToolRegistry

from .config import MCPServerDef

CallAsync = Callable[[str, dict[str, Any]], Awaitable[Any]]
_INVALID_NAME = re.compile(r"[^A-Za-z0-9_-]")
_MAX_NAME = 64
_MAX_SCHEMA_BYTES = 65_536
_DEFAULT_CALL_TIMEOUT_SECONDS = 120.0


def tool_name(server: str, tool: str) -> str:
    raw = f"mcp__{server}__{tool}"
    sanitized = _INVALID_NAME.sub("_", raw)
    if sanitized == raw and len(sanitized) <= _MAX_NAME:
        return sanitized
    digest = hashlib.sha256(raw.encode("utf-8")).hexdigest()[:8]
    return f"{sanitized[:_MAX_NAME - 9]}_{digest}"


def register_mcp_tools(
    *,
    registry: ToolRegistry,
    manifest: ToolManifest,
    server: MCPServerDef,
    mcp_tools: list[Any],
    call_async: CallAsync,
    loop: asyncio.AbstractEventLoop,
    timeout: float = _DEFAULT_CALL_TIMEOUT_SECONDS,
) -> list[str]:
    names = []
    for remote_tool in _filtered(mcp_tools, server):
        remote_name = getattr(remote_tool, "name", "")
        if (
            not isinstance(remote_name, str)
            or not 1 <= len(remote_name) <= 256
        ):
            raise ValueError("invalid MCP tool name")
        name = tool_name(server.name, remote_name)
        if name in manifest.tools:
            raise ValueError("MCP tool name collision")
        schema = _openai_schema(name, remote_tool)

        def invoke(_remote: str = remote_name, **arguments: Any) -> Any:
            future = asyncio.run_coroutine_threadsafe(
                call_async(_remote, arguments),
                loop,
            )
            return future.result(timeout)

        invoke.__name__ = name
        manifest.add(
            ToolSpec(
                name=name,
                risk=RiskClass.EXTERNAL,
                category="mcp",
                requires_approval=True,
                description=schema["function"]["description"],
            )
        )
        registry.register(invoke, schema=schema)
        names.append(name)
    return names


def _filtered(tools: list[Any], server: MCPServerDef) -> list[Any]:
    selected = tools
    if server.include_tools is not None:
        allowed = set(server.include_tools)
        selected = [
            tool
            for tool in selected
            if getattr(tool, "name", None) in allowed
        ]
    if server.exclude_tools:
        blocked = set(server.exclude_tools)
        selected = [
            tool
            for tool in selected
            if getattr(tool, "name", None) not in blocked
        ]
    return selected


def _openai_schema(name: str, remote_tool: Any) -> dict[str, Any]:
    raw = getattr(remote_tool, "inputSchema", None) or {
        "type": "object",
        "properties": {},
    }
    try:
        encoded = json.dumps(raw, allow_nan=False, sort_keys=True)
        parameters = json.loads(encoded)
    except (TypeError, ValueError, OverflowError):
        raise ValueError("invalid MCP tool schema") from None
    properties = (
        parameters.get("properties")
        if isinstance(parameters, dict)
        else None
    )
    required = (
        parameters.get("required", [])
        if isinstance(parameters, dict)
        else None
    )
    if (
        len(encoded.encode("utf-8")) > _MAX_SCHEMA_BYTES
        or not isinstance(parameters, dict)
        or parameters.get("type") != "object"
        or not isinstance(properties, dict)
        or not isinstance(required, list)
        or any(
            not isinstance(item, str) or item not in properties
            for item in required
        )
    ):
        raise ValueError("invalid MCP tool schema")
    parameters["required"] = required
    parameters["additionalProperties"] = False
    description = str(
        getattr(remote_tool, "description", "") or f"MCP tool {name}"
    )[:1024]
    return {
        "type": "function",
        "function": {
            "name": name,
            "description": description,
            "parameters": parameters,
        },
    }
