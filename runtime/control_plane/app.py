"""Authenticated loopback HTTP and WebSocket control plane."""

from __future__ import annotations

import asyncio
import json
from contextlib import suppress
from typing import Any, Protocol

from fastapi import (
    FastAPI,
    HTTPException,
    Request,
    WebSocket,
    WebSocketDisconnect,
)
from fastapi.middleware.cors import CORSMiddleware

from runtime.events import EventHub

from .auth import (
    WEBSOCKET_PROTOCOL,
    SessionAuthMiddleware,
    validate_session_token,
)

DEFAULT_ALLOWED_ORIGINS = (
    "tauri://localhost",
    "http://tauri.localhost",
    "https://tauri.localhost",
    "http://localhost:1420",
    "http://127.0.0.1:1420",
)


class SettingsView(Protocol):
    def view(self) -> dict[str, Any]: ...


class ProviderSecrets(Protocol):
    def status(self) -> list[dict[str, Any]]: ...

    def set_api_key(self, provider: str, api_key: str) -> dict[str, Any]: ...

    def delete_api_key(self, provider: str) -> dict[str, Any]: ...

    def authorize_sync(self, candidate: str) -> bool: ...


class ControlPlaneServices(Protocol):
    events: EventHub
    settings: SettingsView
    secrets: ProviderSecrets


def create_control_plane_app(
    *,
    token: str,
    services: ControlPlaneServices,
    allowed_origins: tuple[str, ...] = DEFAULT_ALLOWED_ORIGINS,
) -> FastAPI:
    validate_session_token(token)
    app = FastAPI(
        title="Codinal Control Plane",
        docs_url=None,
        redoc_url=None,
        openapi_url=None,
    )
    app.state.services = services

    @app.get("/v1/health")
    async def health() -> dict[str, str]:
        return {"status": "ok"}

    @app.get("/v1/settings")
    async def settings() -> dict[str, Any]:
        return services.settings.view()

    @app.get("/v1/secrets/providers")
    async def provider_secret_status() -> list[dict[str, Any]]:
        return services.secrets.status()

    @app.put("/v1/secrets/providers/{provider}")
    async def provider_secret_set(
        provider: str, request: Request
    ) -> dict[str, Any]:
        _authorize_secret_sync(request, services.secrets)
        api_key = await _read_api_key(request)
        try:
            return services.secrets.set_api_key(provider, api_key)
        except ValueError as error:
            raise HTTPException(status_code=400, detail=str(error)) from None

    @app.delete("/v1/secrets/providers/{provider}")
    async def provider_secret_delete(
        provider: str, request: Request
    ) -> dict[str, Any]:
        _authorize_secret_sync(request, services.secrets)
        try:
            return services.secrets.delete_api_key(provider)
        except ValueError as error:
            raise HTTPException(status_code=400, detail=str(error)) from None

    @app.websocket("/ws/events")
    async def global_events(websocket: WebSocket) -> None:
        await _serve_events(websocket, services.events.subscribe_global)

    @app.websocket("/ws/session/{session_id}")
    async def session_events(websocket: WebSocket, session_id: str) -> None:
        await _serve_events(
            websocket,
            lambda listener: services.events.subscribe_session(
                session_id, listener
            ),
        )

    app.add_middleware(
        SessionAuthMiddleware,
        token=token,
        allowed_origins=allowed_origins,
    )
    app.add_middleware(
        CORSMiddleware,
        allow_origins=list(allowed_origins),
        allow_methods=["GET", "POST", "PATCH", "DELETE"],
        allow_headers=["Authorization", "Content-Type"],
        allow_credentials=False,
    )
    return app


async def _read_api_key(request: Request) -> str:
    try:
        body = await request.json()
    except (json.JSONDecodeError, UnicodeDecodeError):
        raise HTTPException(status_code=400, detail="invalid secret payload") from None
    if (
        not isinstance(body, dict)
        or set(body) != {"api_key"}
        or not isinstance(body["api_key"], str)
        or not 1 <= len(body["api_key"]) <= 16_384
    ):
        raise HTTPException(status_code=400, detail="invalid secret payload")
    return body["api_key"]


def _authorize_secret_sync(
    request: Request,
    secrets: ProviderSecrets,
) -> None:
    candidate = request.headers.get("X-Codinal-Secret-Sync", "")
    if not secrets.authorize_sync(candidate):
        raise HTTPException(status_code=403, detail="secret sync forbidden")


async def _serve_events(
    websocket: WebSocket,
    subscribe: Any,
) -> None:
    await websocket.accept(subprotocol=WEBSOCKET_PROTOCOL)
    messages: asyncio.Queue[dict[str, Any]] = asyncio.Queue(maxsize=256)

    async def listener(message: dict[str, Any]) -> None:
        messages.put_nowait(message)

    async def sender() -> None:
        while True:
            await websocket.send_json(await messages.get())

    unsubscribe = subscribe(listener)
    sender_task = asyncio.create_task(sender())
    try:
        while True:
            message = await websocket.receive_text()
            if message == "ping":
                messages.put_nowait({"type": "pong"})
    except WebSocketDisconnect:
        pass
    finally:
        unsubscribe()
        sender_task.cancel()
        with suppress(asyncio.CancelledError):
            await sender_task
