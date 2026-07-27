"""Attach explicitly connected MCP servers to idle session engines."""

from __future__ import annotations

import asyncio
from typing import Any, Optional

from runtime.audit import AuditLedger
from runtime.sessions import SessionService
from runtime.turns import (
    SessionBusyError,
    SessionNotFoundError,
    TurnCoordinator,
)

from .client import MCPManager
from .config import MCPServerDef
from .store import MCPStore
from .tools import register_mcp_tools


class MCPService:
    def __init__(
        self,
        *,
        manager: MCPManager,
        sessions: SessionService,
        turns: TurnCoordinator,
        store: Optional[MCPStore] = None,
        audit: Optional[AuditLedger] = None,
        redactor: Any = None,
    ) -> None:
        self._manager = manager
        self._sessions = sessions
        self._turns = turns
        self._store = store
        self._audit = audit
        self._redactor = redactor
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
        names = await self._attach(session_id, server, approved=approved)
        if self._store is not None:
            self._store.upsert(session_id, server, enabled=True)
        self._record(
            "connect",
            server=server,
            payload={"tools": list(names)},
        )
        return {
            "ok": True,
            "server": server.name,
            "tools": list(names),
        }

    async def _attach(
        self,
        session_id: str,
        server: MCPServerDef,
        *,
        approved: bool,
    ) -> list[str]:
        """Connect the transport and register tools on the session engine."""
        remote_tools = await self._manager.connect(server, approved=approved)
        # A turn may have started while the transport was connecting. Never
        # mutate the advertised tool set mid-iteration.
        if self._turns.is_active(session_id):
            raise SessionBusyError("session already has an active turn")
        engine = self._sessions.get_engine(session_id)
        if engine is None:
            raise SessionNotFoundError(session_id)
        loop = asyncio.get_running_loop()

        def _call_mcp(tool, arguments):
            # Redact registered secrets from arguments before they leave the
            # local trust boundary (MCP transport = live network/subprocess).
            if self._redactor is not None and arguments:
                arguments = self._redactor.redact_payload(arguments)
            return self._manager.call(server.name, tool, arguments)

        names = register_mcp_tools(
            registry=engine.registry,
            manifest=engine.registry.manifest,
            server=server,
            mcp_tools=remote_tools,
            call_async=_call_mcp,
            loop=loop,
        )
        self._attached[(session_id, server.name)] = (server, names)
        return names

    def _detach_tools(self, session_id: str, name: str) -> list[str]:
        """Unregister tools for an attached server. Returns the removed names."""
        key = (session_id, name)
        existing = self._attached.pop(key, None)
        if existing is None:
            return []
        _server, names = existing
        engine = self._sessions.get_engine(session_id)
        if engine is not None:
            for tool_name in names:
                engine.registry.unregister(tool_name)
        return list(names)

    def list_connected(self, session_id: str) -> list[dict[str, Any]]:
        engine = self._sessions.get_engine(session_id)
        if engine is None:
            raise SessionNotFoundError(session_id)
        entries: list[dict[str, Any]] = []
        for (session, name), (server, tools) in self._attached.items():
            if session != session_id:
                continue
            enabled = True
            if self._store is not None:
                stored = self._store.is_enabled(session_id, server.name)
                enabled = stored if stored is not None else True
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
                    "enabled": enabled,
                }
            )
        # If a store is present, also surface durable-but-disabled servers
        # that are not currently attached (so the UI can show + re-enable).
        if self._store is not None:
            attached_names = {
                name
                for (session, name) in self._attached
                if session == session_id
            }
            for server, enabled in self._store.list(session_id):
                if server.name in attached_names:
                    continue
                entries.append(
                    {
                        "name": server.name,
                        "transport": server.transport,
                        "url": server.url,
                        "command": server.command,
                        "cwd": server.cwd,
                        "tools": [],
                        "include_tools": server.include_tools,
                        "exclude_tools": server.exclude_tools,
                        "enabled": enabled,
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
        names = self._detach_tools(session_id, name)
        if not names:
            # May have been durable-but-disabled only; drop the row if present.
            if self._store is None or not self._store.delete(session_id, name):
                raise ValueError("MCP server not connected")
        server_def = None
        if self._store is not None:
            for server, _enabled in self._store.list(session_id):
                if server.name == name:
                    server_def = server
                    break
            self._store.delete(session_id, name)
        if not any(
            attached_name == name and attached_session != session_id
            for attached_session, attached_name in self._attached
        ):
            await self._manager.disconnect(name)
        self._record(
            "disconnect",
            server=server_def,
            name=name,
            payload={"tools": list(names)},
        )
        return {
            "ok": True,
            "server": name,
            "tools": list(names),
        }

    async def set_enabled(
        self,
        session_id: str,
        name: str,
        *,
        enabled: bool,
    ) -> dict[str, Any]:
        if self._turns.is_active(session_id):
            raise SessionBusyError("session already has an active turn")
        engine = self._sessions.get_engine(session_id)
        if engine is None:
            raise SessionNotFoundError(session_id)
        if self._store is None:
            raise ValueError("MCP server not connected")
        server_def = None
        for server, _enabled in self._store.list(session_id):
            if server.name == name:
                server_def = server
                break
        if server_def is None:
            raise ValueError("MCP server not connected")
        updated = self._store.set_enabled(session_id, name, enabled)
        if not updated:
            raise ValueError("MCP server not connected")
        if enabled:
            names = await self._attach(
                session_id,
                server_def,
                approved=True,
            )
        else:
            names = self._detach_tools(session_id, name)
            # Keep transport alive if another session uses the same server.
            if not any(
                attached_name == name and attached_session != session_id
                for attached_session, attached_name in self._attached
            ):
                await self._manager.disconnect(name)
        self._record(
            "enable" if enabled else "disable",
            server=server_def,
            payload={"tools": list(names)},
        )
        return {
            "ok": True,
            "server": name,
            "enabled": enabled,
            "tools": list(names),
        }

    async def recover(self) -> int:
        """Reconnect every durable+enabled server into its session engine.

        Called from the FastAPI lifespan on startup. Failures (server gone,
        session missing) are recorded as audit events and the row is left
        enabled so the next manual reconnect can retry.
        """
        if self._store is None:
            return 0
        recovered = 0
        for session_id, server in self._store.list_all_enabled():
            engine = self._sessions.get_engine(session_id)
            if engine is None:
                self._record(
                    "recover_failed",
                    server=server,
                    payload={"reason": "session missing"},
                )
                continue
            if (session_id, server.name) in self._attached:
                recovered += 1
                continue
            try:
                await self._attach(session_id, server, approved=True)
                self._record(
                    "recover",
                    server=server,
                    payload={"tools": []},
                )
                recovered += 1
            except Exception:
                self._record(
                    "recover_failed",
                    server=server,
                    payload={"reason": "transport unavailable"},
                )
        return recovered

    def _record(
        self,
        action: str,
        *,
        server: Optional[MCPServerDef],
        name: Optional[str] = None,
        payload: dict[str, Any],
    ) -> None:
        if self._audit is None:
            return
        subject = (server.name if server is not None else name) or ""
        meta = dict(payload)
        if server is not None:
            meta.setdefault("transport", server.transport)
        self._audit.record(
            "mcp",
            action,
            actor="host",
            subject=subject,
            payload=meta,
        )

    async def aclose(self) -> None:
        await self._manager.aclose()
