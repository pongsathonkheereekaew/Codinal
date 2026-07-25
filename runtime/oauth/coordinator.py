"""OAuth flow registration and one-time callback completion."""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from typing import Any

from .state import OAuthAttempt, OAuthStateService

OAuthCallbackHandler = Callable[
    [str, dict[str, Any]], Awaitable[dict[str, Any] | None]
]


class OAuthCoordinator:
    def __init__(self, states: OAuthStateService | None = None) -> None:
        self._states = states or OAuthStateService()
        self._handlers: dict[str, OAuthCallbackHandler] = {}

    def register(self, flow: str, handler: OAuthCallbackHandler) -> None:
        if flow in self._handlers:
            raise ValueError("OAuth flow is already registered")
        if not callable(handler):
            raise ValueError("OAuth handler must be callable")
        self._handlers[flow] = handler

    def begin(
        self, flow: str, metadata: dict[str, Any] | None = None
    ) -> OAuthAttempt:
        if flow not in self._handlers:
            raise ValueError("unsupported OAuth flow")
        return self._states.begin(flow, metadata)

    async def complete(
        self,
        *,
        flow: str,
        state: str,
        code: str,
        error: str = "",
    ) -> dict[str, Any]:
        handler = self._handlers.get(flow)
        if handler is None:
            return {"ok": False, "error": "unsupported OAuth flow"}
        has_code = isinstance(code, str) and bool(code)
        has_error = isinstance(error, str) and bool(error)
        if (
            has_code == has_error
            or (has_code and len(code.encode("utf-8")) > 8192)
            or (has_error and len(error.encode("utf-8")) > 256)
        ):
            return {"ok": False, "error": "invalid OAuth callback"}

        metadata = self._states.consume(state, flow)
        if metadata is None:
            return {
                "ok": False,
                "error": "unknown or expired OAuth state",
            }
        if has_error:
            return {"ok": False, "error": "OAuth authorization failed"}
        try:
            await handler(code, metadata)
        except Exception:
            return {"ok": False, "error": "OAuth completion failed"}
        return {"ok": True, "flow": flow}
