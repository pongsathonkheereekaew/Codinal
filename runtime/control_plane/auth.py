"""Per-process bearer authentication for the loopback control plane."""

from __future__ import annotations

import json
import secrets
from collections.abc import Awaitable, Callable, Iterable
from typing import Any

ASGIApp = Callable[
    [dict[str, Any], Callable[..., Awaitable[Any]], Callable[..., Awaitable[Any]]],
    Awaitable[None],
]

WEBSOCKET_PROTOCOL = "codinal.v1"
_WEBSOCKET_AUTH_PREFIX = "codinal.auth."


def validate_session_token(token: str) -> str:
    if not isinstance(token, str) or len(token) < 32:
        raise ValueError("session token must contain at least 32 characters")
    if not all(
        character.isascii()
        and (character.isalnum() or character in "-_")
        for character in token
    ):
        raise ValueError("session token must use URL-safe characters")
    return token


def websocket_auth_protocol(token: str) -> str:
    return f"{_WEBSOCKET_AUTH_PREFIX}{validate_session_token(token)}"


class SessionAuthMiddleware:
    """Authenticate every HTTP and WebSocket request before routing."""

    def __init__(
        self,
        app: ASGIApp,
        *,
        token: str,
        allowed_origins: Iterable[str],
    ) -> None:
        self._app = app
        self._token = validate_session_token(token)
        self._websocket_protocol = websocket_auth_protocol(token)
        self._allowed_origins = frozenset(allowed_origins)

    async def __call__(
        self,
        scope: dict[str, Any],
        receive: Callable[..., Awaitable[Any]],
        send: Callable[..., Awaitable[Any]],
    ) -> None:
        scope_type = scope.get("type")
        if scope_type == "http":
            if self._valid_http_authorization(scope):
                await self._app(scope, receive, send)
            else:
                await self._reject_http(send)
            return

        if scope_type == "websocket":
            if not self._valid_websocket_origin(scope):
                await send({"type": "websocket.close", "code": 4403})
                return
            if not self._valid_websocket_protocol(scope):
                await send({"type": "websocket.close", "code": 4401})
                return

        await self._app(scope, receive, send)

    def _valid_http_authorization(self, scope: dict[str, Any]) -> bool:
        authorization = self._header(scope, b"authorization")
        prefix = b"Bearer "
        if not authorization.startswith(prefix):
            return False
        candidate = authorization[len(prefix) :]
        if not candidate or b" " in candidate:
            return False
        return secrets.compare_digest(
            candidate, self._token.encode("utf-8")
        )

    def _valid_websocket_protocol(self, scope: dict[str, Any]) -> bool:
        protocols = scope.get("subprotocols", ())
        return WEBSOCKET_PROTOCOL in protocols and any(
            secrets.compare_digest(protocol, self._websocket_protocol)
            for protocol in protocols
        )

    def _valid_websocket_origin(self, scope: dict[str, Any]) -> bool:
        origin = self._header(scope, b"origin")
        if not origin:
            return True
        try:
            value = origin.decode("ascii")
        except UnicodeDecodeError:
            return False
        return value in self._allowed_origins

    @staticmethod
    def _header(scope: dict[str, Any], name: bytes) -> bytes:
        for header_name, value in scope.get("headers", ()):
            if header_name.lower() == name:
                return value
        return b""

    @staticmethod
    async def _reject_http(
        send: Callable[..., Awaitable[Any]],
    ) -> None:
        body = json.dumps(
            {"detail": "unauthorized"}, separators=(",", ":")
        ).encode("utf-8")
        await send(
            {
                "type": "http.response.start",
                "status": 401,
                "headers": [
                    (b"content-type", b"application/json"),
                    (b"content-length", str(len(body)).encode("ascii")),
                    (b"www-authenticate", b"Bearer"),
                ],
            }
        )
        await send({"type": "http.response.body", "body": body})
