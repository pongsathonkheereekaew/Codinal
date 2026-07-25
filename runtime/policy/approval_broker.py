"""Session-scoped bridge between TurnEngine approvals and the desktop UI."""

from __future__ import annotations

import asyncio
import hashlib
import threading
from dataclasses import dataclass
from typing import Any, Awaitable, Callable

from .approval import ApprovalOutcome, PermissionRequest


@dataclass
class _Pending:
    session_id: str
    approval_id: str
    request: PermissionRequest
    loop: asyncio.AbstractEventLoop
    future: asyncio.Future[ApprovalOutcome]
    resolved: bool = False


class ApprovalBroker:
    def __init__(self) -> None:
        self._lock = threading.RLock()
        self._pending: dict[tuple[str, str], _Pending] = {}
        self._closed = False

    @staticmethod
    def approval_id(session_id: str, tool_call_id: str) -> str:
        if not isinstance(session_id, str) or not isinstance(tool_call_id, str):
            raise ValueError("invalid approval identity")
        return hashlib.sha256(
            f"{session_id}\0{tool_call_id}".encode("utf-8")
        ).hexdigest()[:32]

    def approver(
        self,
        session_id: str,
    ) -> Callable[[PermissionRequest], Awaitable[ApprovalOutcome]]:
        async def approve(request: PermissionRequest) -> ApprovalOutcome:
            tool_call_id = request.tool_call_id or ""
            approval_id = self.approval_id(session_id, tool_call_id)
            loop = asyncio.get_running_loop()
            future: asyncio.Future[ApprovalOutcome] = loop.create_future()
            pending = _Pending(
                session_id=session_id,
                approval_id=approval_id,
                request=request,
                loop=loop,
                future=future,
            )
            key = (session_id, approval_id)
            with self._lock:
                if self._closed or key in self._pending:
                    return ApprovalOutcome.DENY
                self._pending[key] = pending
            try:
                return await future
            finally:
                with self._lock:
                    if self._pending.get(key) is pending:
                        self._pending.pop(key, None)

        return approve

    def pending(self, session_id: str) -> list[dict[str, Any]]:
        with self._lock:
            values = [
                pending
                for pending in self._pending.values()
                if pending.session_id == session_id
                and not pending.resolved
            ]
        return [
            {
                "approval_id": pending.approval_id,
                "tool_name": pending.request.tool_name,
                "arguments": pending.request.arguments,
                "reason": pending.request.reason,
                "risk": pending.request.risk,
                "command": pending.request.command,
            }
            for pending in values
        ]

    def resolve(
        self,
        session_id: str,
        approval_id: str,
        outcome: ApprovalOutcome,
    ) -> bool:
        key = (session_id, approval_id)
        with self._lock:
            pending = self._pending.get(key)
            if (
                pending is None
                or pending.resolved
                or not _outcome_applies(pending.request, outcome)
            ):
                return False
            pending.resolved = True
        pending.loop.call_soon_threadsafe(
            _complete,
            pending.future,
            outcome,
        )
        return True

    def close(self) -> None:
        with self._lock:
            self._closed = True
            pending = [
                item
                for item in self._pending.values()
                if not item.resolved
            ]
            for item in pending:
                item.resolved = True
        for item in pending:
            item.loop.call_soon_threadsafe(
                _complete,
                item.future,
                ApprovalOutcome.DENY,
            )


def _complete(
    future: asyncio.Future[ApprovalOutcome],
    outcome: ApprovalOutcome,
) -> None:
    if not future.done():
        future.set_result(outcome)


def _outcome_applies(
    request: PermissionRequest,
    outcome: ApprovalOutcome,
) -> bool:
    if outcome in {ApprovalOutcome.ONCE, ApprovalOutcome.DENY}:
        return True
    if outcome is ApprovalOutcome.ALWAYS_COMMAND:
        return request.risk == "exec" and bool(request.command)
    if outcome is ApprovalOutcome.ALWAYS_TOOL:
        return request.risk == "write_local"
    return False
