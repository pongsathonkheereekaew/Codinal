"""Authenticated loopback HTTP and WebSocket control plane."""

from __future__ import annotations

import asyncio
import json
import re
from contextlib import asynccontextmanager, suppress
from pathlib import Path
from typing import Any, Protocol

from fastapi import (
    FastAPI,
    HTTPException,
    Request,
    WebSocket,
    WebSocketDisconnect,
)
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from runtime.events import EventHub
from runtime.git import CheckpointState, GitWorkspaceError
from runtime.mcp import MCPServerDef
from runtime.control_plane.input_validation import (
    MAX_TURN_BODY_BYTES,
    valid_turn_input,
)
from runtime.policy import ApprovalOutcome, ApprovalPersistenceError
from runtime.storage import ExportTooLargeError
from runtime.turns import (
    CodeCheckpointError,
    ExportBusyError,
    SessionBusyError,
    SessionNotFoundError,
    SessionWorkspaceError,
)

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
MAX_CHECKPOINT_RESTORE_BODY_BYTES = 1024


class SettingsView(Protocol):
    def view(self) -> dict[str, Any]: ...


class ProviderSecrets(Protocol):
    def status(self) -> list[dict[str, Any]]: ...

    def set_api_key(self, provider: str, api_key: str) -> dict[str, Any]: ...

    def delete_api_key(self, provider: str) -> dict[str, Any]: ...

    def authorize_sync(self, candidate: str) -> bool: ...


class OAuthCallbacks(Protocol):
    async def complete(
        self,
        *,
        flow: str,
        state: str,
        code: str,
        error: str = "",
    ) -> dict[str, Any]: ...


class TurnControl(Protocol):
    async def recover(self) -> int: ...

    async def shutdown(self) -> bool | None: ...

    async def start(
        self,
        session_id: str,
        *,
        user_input: str | list[dict[str, Any]],
        workspace: str | None = None,
        agent: str = "code",
        model: str | None = None,
        source: dict[str, Any] | None = None,
    ) -> dict[str, Any]: ...

    def interrupt(self, session_id: str) -> bool: ...

    def is_active(self, session_id: str) -> bool: ...

    def has_active_turns(self) -> bool: ...

    async def export_when_idle(
        self,
        exporter: Any,
    ) -> dict[str, Any]: ...

    async def restore_when_idle(
        self,
        restore: Any,
    ) -> dict[str, Any]: ...


class SessionControl(Protocol):
    def list_sessions(
        self,
        *,
        workspace: str | None = None,
    ) -> list[dict[str, Any]]: ...

    def messages(self, session_id: str) -> list[dict[str, Any]]: ...

    def export(self) -> dict[str, Any]: ...

    def roots(self, session_id: str) -> list[dict[str, Any]]: ...

    def rename(self, session_id: str, title: str) -> dict[str, Any]: ...

    def set_flags(
        self,
        session_id: str,
        *,
        pinned: bool | None = None,
        archived: bool | None = None,
    ) -> dict[str, Any]: ...

    def set_model(
        self,
        session_id: str,
        model: str,
    ) -> dict[str, Any]: ...

    def delete(self, session_id: str) -> dict[str, Any]: ...

    def restore_conversation(
        self,
        session_id: str,
        *,
        message_count: int,
    ) -> bool: ...


class MCPControl(Protocol):
    async def connect(
        self,
        session_id: str,
        server: MCPServerDef,
        *,
        approved: bool,
    ) -> dict[str, Any]: ...

    async def aclose(self) -> None: ...


class GitControl(Protocol):
    def load(self, session_id: str) -> Any | None: ...

    def status(self, session_id: str) -> dict[str, object]: ...

    def diff(
        self,
        session_id: str,
        *,
        staged: bool = False,
        against_base: bool = False,
        path: str | None = None,
    ) -> dict[str, object]: ...

    def apply_back(self, session_id: str) -> dict[str, object]: ...

    def list_checkpoints(self, session_id: str) -> list[Any]: ...

    def load_checkpoint(self, checkpoint_id: str) -> Any | None: ...

    def restore_checkpoint_code(
        self,
        session_id: str,
        checkpoint_id: str,
    ) -> dict[str, object]: ...

    def reapply_checkpoint_code(
        self,
        session_id: str,
        checkpoint_id: str,
    ) -> dict[str, object]: ...

    def discard_checkpoint_history(
        self,
        session_id: str,
        checkpoint_id: str,
    ) -> int: ...

    def close(self) -> None: ...


class ApprovalControl(Protocol):
    def pending(self, session_id: str) -> list[dict[str, Any]]: ...

    def resolve(
        self,
        session_id: str,
        approval_id: str,
        outcome: ApprovalOutcome,
    ) -> bool: ...

    def close(self) -> None: ...


class ControlPlaneServices(Protocol):
    events: EventHub
    settings: SettingsView
    secrets: ProviderSecrets
    oauth: OAuthCallbacks
    turns: TurnControl
    sessions: SessionControl
    mcp: MCPControl | None
    git: GitControl | None
    approvals: ApprovalControl | None


def create_control_plane_app(
    *,
    token: str,
    services: ControlPlaneServices,
    allowed_origins: tuple[str, ...] = DEFAULT_ALLOWED_ORIGINS,
) -> FastAPI:
    validate_session_token(token)

    @asynccontextmanager
    async def lifespan(_app: FastAPI):
        try:
            await services.turns.recover()
            yield
        finally:
            quiesced = await services.turns.shutdown()
            if quiesced is not False:
                mcp = getattr(services, "mcp", None)
                if mcp is not None:
                    await mcp.aclose()
                git = getattr(services, "git", None)
                if git is not None:
                    git.close()
                approvals = getattr(services, "approvals", None)
                if approvals is not None:
                    approvals.close()

    app = FastAPI(
        title="Codinal Control Plane",
        docs_url=None,
        redoc_url=None,
        openapi_url=None,
        lifespan=lifespan,
    )
    app.state.services = services

    @app.get("/v1/health")
    async def health() -> dict[str, str]:
        return {"status": "ok"}

    @app.get("/v1/settings")
    async def settings() -> dict[str, Any]:
        return services.settings.view()

    @app.get("/v1/sessions")
    async def list_sessions(
        workspace: str | None = None,
    ) -> list[dict[str, Any]]:
        if workspace is not None and (
            not 1 <= len(workspace) <= 4096
            or not Path(workspace).is_absolute()
        ):
            raise HTTPException(status_code=400, detail="invalid workspace")
        return services.sessions.list_sessions(workspace=workspace)

    @app.get("/v1/data/export")
    async def export_data() -> JSONResponse:
        try:
            payload = await services.turns.export_when_idle(
                services.sessions.export
            )
        except ExportBusyError:
            raise HTTPException(
                status_code=409,
                detail="cannot export while a turn is active",
            ) from None
        except ExportTooLargeError:
            raise HTTPException(
                status_code=413,
                detail=(
                    "conversation export exceeds the 32 MiB safety limit"
                ),
            ) from None
        return JSONResponse(
            payload,
            headers={
                "Content-Disposition": (
                    'attachment; filename="codinal-export-v1.json"'
                ),
                "Cache-Control": "no-store",
            },
        )

    @app.get("/v1/sessions/{session_id}/messages")
    async def session_messages(
        session_id: str,
    ) -> list[dict[str, Any]]:
        _validate_public_session_id(session_id)
        return services.sessions.messages(session_id)

    @app.get("/v1/sessions/{session_id}/roots")
    async def session_roots(
        session_id: str,
    ) -> list[dict[str, Any]]:
        _validate_public_session_id(session_id)
        return services.sessions.roots(session_id)

    @app.patch("/v1/sessions/{session_id}")
    async def update_session(
        session_id: str,
        request: Request,
    ) -> dict[str, Any]:
        _validate_public_session_id(session_id)
        update = await _read_session_update(request)
        if "model" in update and services.turns.is_active(session_id):
            raise HTTPException(
                status_code=409,
                detail="session already has an active turn",
            )
        result: dict[str, Any] = {"ok": True, "session_id": session_id}
        if "title" in update:
            result = services.sessions.rename(session_id, update["title"])
            if not result.get("ok"):
                raise HTTPException(status_code=404, detail="session not found")
        if "pinned" in update or "archived" in update:
            result = services.sessions.set_flags(
                session_id,
                pinned=update.get("pinned"),
                archived=update.get("archived"),
            )
            if not result.get("ok"):
                raise HTTPException(status_code=404, detail="session not found")
        if "model" in update:
            result = services.sessions.set_model(
                session_id,
                update["model"],
            )
            if not result.get("ok"):
                raise HTTPException(status_code=404, detail="session not found")
        return result

    @app.delete("/v1/sessions/{session_id}")
    async def delete_session(session_id: str) -> dict[str, Any]:
        _validate_public_session_id(session_id)
        if services.turns.is_active(session_id):
            raise HTTPException(
                status_code=409,
                detail="session already has an active turn",
            )
        result = services.sessions.delete(session_id)
        if result.get("cleanup_errors"):
            raise HTTPException(
                status_code=409,
                detail="session cleanup failed",
            )
        if not result.get("ok"):
            raise HTTPException(status_code=404, detail="session not found")
        return result

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

    @app.post("/v1/oauth/callback")
    async def oauth_callback(request: Request) -> JSONResponse:
        _authorize_secret_sync(request, services.secrets)
        callback = await _read_oauth_callback(request)
        result = await services.oauth.complete(**callback)
        return JSONResponse(
            result,
            status_code=200 if result.get("ok") else 400,
        )

    @app.post("/v1/sessions/{session_id}/turns")
    async def start_turn(
        session_id: str,
        request: Request,
    ) -> JSONResponse:
        _validate_public_session_id(session_id)
        turn = await _read_turn(request)
        try:
            result = await services.turns.start(
                session_id,
                user_input=turn["input"],
                workspace=turn.get("workspace"),
                agent=turn.get("agent", "code"),
                model=turn.get("model"),
                source=turn.get("source"),
            )
        except SessionNotFoundError:
            raise HTTPException(status_code=404, detail="session not found") from None
        except SessionBusyError:
            raise HTTPException(
                status_code=409,
                detail="session already has an active turn",
            ) from None
        except SessionWorkspaceError:
            raise HTTPException(
                status_code=409,
                detail="session workspace preparation failed",
            ) from None
        except CodeCheckpointError:
            raise HTTPException(
                status_code=409,
                detail="automatic code checkpoint unavailable",
            ) from None
        return JSONResponse(result, status_code=202)

    @app.post("/v1/sessions/{session_id}/interrupt")
    async def interrupt_turn(session_id: str) -> dict[str, Any]:
        _validate_public_session_id(session_id)
        return {
            "ok": services.turns.interrupt(session_id),
            "session_id": session_id,
        }

    @app.get("/v1/sessions/{session_id}/approvals")
    async def list_approvals(session_id: str) -> list[dict[str, Any]]:
        _validate_public_session_id(session_id)
        approvals = getattr(services, "approvals", None)
        if approvals is None:
            return []
        return approvals.pending(session_id)

    @app.post("/v1/sessions/{session_id}/approvals/{approval_id}")
    async def resolve_approval(
        session_id: str,
        approval_id: str,
        request: Request,
    ) -> dict[str, bool]:
        _validate_public_session_id(session_id)
        if re.fullmatch(r"[a-f0-9]{32}", approval_id) is None:
            raise HTTPException(status_code=400, detail="invalid approval id")
        approvals = getattr(services, "approvals", None)
        if approvals is None:
            raise HTTPException(status_code=503, detail="approvals unavailable")
        outcome = await _read_approval(request)
        try:
            resolved = approvals.resolve(
                session_id,
                approval_id,
                outcome,
            )
        except ApprovalPersistenceError:
            raise HTTPException(
                status_code=503,
                detail="approval decision could not be saved",
            ) from None
        if not resolved:
            raise HTTPException(
                status_code=409,
                detail="approval is not pending or outcome is not applicable",
            )
        return {"ok": True}

    @app.post("/v1/sessions/{session_id}/mcp/connect")
    async def connect_mcp(
        session_id: str,
        request: Request,
    ) -> dict[str, Any]:
        _validate_public_session_id(session_id)
        if services.mcp is None:
            raise HTTPException(status_code=503, detail="MCP unavailable")
        server = await _read_mcp_server(request)
        try:
            return await services.mcp.connect(
                session_id,
                server,
                approved=True,
            )
        except SessionNotFoundError:
            raise HTTPException(status_code=404, detail="session not found") from None
        except SessionBusyError:
            raise HTTPException(
                status_code=409,
                detail="session already has an active turn",
            ) from None
        except PermissionError:
            raise HTTPException(
                status_code=403,
                detail="MCP connect denied",
            ) from None
        except ValueError:
            raise HTTPException(
                status_code=409,
                detail="MCP server definition changed",
            ) from None
        except RuntimeError:
            raise HTTPException(
                status_code=502,
                detail="MCP connection failed",
            ) from None

    @app.get("/v1/sessions/{session_id}/git/status")
    async def git_status(session_id: str) -> dict[str, object]:
        _validate_public_session_id(session_id)
        if services.git is None or services.git.load(session_id) is None:
            raise HTTPException(status_code=404, detail="Git session not found")
        try:
            return await asyncio.to_thread(
                services.git.status,
                session_id,
            )
        except GitWorkspaceError:
            raise HTTPException(
                status_code=409,
                detail="Git status unavailable",
            ) from None

    @app.get("/v1/sessions/{session_id}/git/diff")
    async def git_diff(
        session_id: str,
        staged: bool = False,
        against_base: bool = False,
        path: str | None = None,
    ) -> dict[str, object]:
        _validate_public_session_id(session_id)
        if services.git is None or services.git.load(session_id) is None:
            raise HTTPException(status_code=404, detail="Git session not found")
        try:
            return await asyncio.to_thread(
                services.git.diff,
                session_id,
                staged=staged,
                against_base=against_base,
                path=path,
            )
        except GitWorkspaceError:
            raise HTTPException(
                status_code=409,
                detail="Git diff unavailable",
            ) from None

    @app.post("/v1/sessions/{session_id}/git/apply")
    async def git_apply(session_id: str) -> JSONResponse:
        _validate_public_session_id(session_id)
        if services.git is None or services.git.load(session_id) is None:
            raise HTTPException(status_code=404, detail="Git session not found")
        if services.turns.is_active(session_id):
            raise HTTPException(
                status_code=409,
                detail="session already has an active turn",
            )
        try:
            result = await asyncio.to_thread(
                services.git.apply_back,
                session_id,
            )
        except GitWorkspaceError as error:
            raise HTTPException(
                status_code=409,
                detail=str(error),
            ) from None
        return JSONResponse(
            result,
            status_code=200 if result.get("ok") else 409,
        )

    @app.get("/v1/sessions/{session_id}/checkpoints")
    async def list_checkpoints(
        session_id: str,
    ) -> list[dict[str, Any]]:
        _validate_public_session_id(session_id)
        if services.git is None or services.git.load(session_id) is None:
            raise HTTPException(
                status_code=404,
                detail="Git session not found",
            )
        records = await asyncio.to_thread(
            services.git.list_checkpoints,
            session_id,
        )
        return [
            {
                "checkpoint_id": record.checkpoint_id,
                "before_message_count": record.before_message_count,
                "after_message_count": record.after_message_count,
                "created_at": record.created_at,
            }
            for record in records
        ]

    @app.post(
        "/v1/sessions/{session_id}/checkpoints/"
        "{checkpoint_id}/restore"
    )
    async def restore_checkpoint(
        session_id: str,
        checkpoint_id: str,
        request: Request,
    ) -> JSONResponse:
        _validate_public_session_id(session_id)
        if re.fullmatch(r"[0-9a-f]{32}", checkpoint_id) is None:
            raise HTTPException(
                status_code=400,
                detail="invalid checkpoint id",
            )
        scope = await _read_checkpoint_scope(request)
        if services.git is None or services.git.load(session_id) is None:
            raise HTTPException(
                status_code=404,
                detail="Git session not found",
            )
        checkpoint = await asyncio.to_thread(
            services.git.load_checkpoint,
            checkpoint_id,
        )
        if (
            checkpoint is None
            or checkpoint.session_id != session_id
            or checkpoint.state is not CheckpointState.COMPLETED
        ):
            raise HTTPException(
                status_code=404,
                detail="checkpoint not found",
            )

        def restore() -> dict[str, Any]:
            code_restored = False
            try:
                if scope in {"code", "both"}:
                    services.git.restore_checkpoint_code(
                        session_id,
                        checkpoint_id,
                    )
                    code_restored = True
                if scope in {"conversation", "both"}:
                    restored = services.sessions.restore_conversation(
                        session_id,
                        message_count=checkpoint.before_message_count,
                    )
                    if not restored:
                        raise RuntimeError(
                            "checkpoint conversation not found"
                        )
                    services.git.discard_checkpoint_history(
                        session_id,
                        checkpoint_id,
                    )
            except (GitWorkspaceError, ValueError, RuntimeError):
                if code_restored and scope == "both":
                    try:
                        services.git.reapply_checkpoint_code(
                            session_id,
                            checkpoint_id,
                        )
                    except Exception:
                        raise RuntimeError(
                            "checkpoint rollback failed"
                        ) from None
                raise
            return {
                "ok": True,
                "checkpoint_id": checkpoint_id,
                "scope": scope,
            }

        try:
            result = await services.turns.restore_when_idle(restore)
        except SessionBusyError:
            raise HTTPException(
                status_code=409,
                detail="session already has an active turn",
            ) from None
        except RuntimeError as error:
            if str(error) == "checkpoint rollback failed":
                raise HTTPException(
                    status_code=500,
                    detail="checkpoint rollback failed",
                ) from None
            raise HTTPException(
                status_code=409,
                detail=str(error),
            ) from None
        except (GitWorkspaceError, ValueError) as error:
            raise HTTPException(
                status_code=409,
                detail=str(error),
            ) from None
        return JSONResponse(result)

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


_SESSION_ID = re.compile(r"[A-Za-z0-9][A-Za-z0-9_-]{0,127}")
_AGENT = re.compile(r"[A-Za-z][A-Za-z0-9_-]{0,31}")


def _validate_public_session_id(session_id: str) -> None:
    if session_id.startswith("__") or _SESSION_ID.fullmatch(session_id) is None:
        raise HTTPException(status_code=400, detail="invalid session id")


async def _read_turn(request: Request) -> dict[str, Any]:
    try:
        chunks: list[bytes] = []
        size = 0
        async for chunk in request.stream():
            size += len(chunk)
            if size > MAX_TURN_BODY_BYTES:
                raise HTTPException(
                    status_code=400,
                    detail="invalid turn payload",
                )
            chunks.append(chunk)
        payload = b"".join(chunks)
        body = json.loads(payload)
    except (json.JSONDecodeError, UnicodeDecodeError):
        raise HTTPException(status_code=400, detail="invalid turn payload") from None
    if (
        not isinstance(body, dict)
        or not {"input"} <= set(body) <= {
            "input",
            "workspace",
            "agent",
            "model",
            "source",
        }
        or not valid_turn_input(body["input"])
        or (
            "workspace" in body
            and (
                not isinstance(body["workspace"], str)
                or not 1 <= len(body["workspace"]) <= 4096
                or not Path(body["workspace"]).is_absolute()
            )
        )
        or (
            "agent" in body
            and (
                not isinstance(body["agent"], str)
                or _AGENT.fullmatch(body["agent"]) is None
            )
        )
        or (
            "model" in body
            and (
                not isinstance(body["model"], str)
                or not 1 <= len(body["model"].encode("utf-8")) <= 256
                or not body["model"].strip()
                or any(ord(character) < 32 for character in body["model"])
            )
        )
        or (
            "source" in body
            and (
                not isinstance(body["source"], dict)
                or len(json.dumps(body["source"]).encode("utf-8")) > 16_384
            )
        )
    ):
        raise HTTPException(status_code=400, detail="invalid turn payload")
    return body


async def _read_approval(request: Request) -> ApprovalOutcome:
    try:
        body = await request.json()
    except (json.JSONDecodeError, UnicodeDecodeError):
        raise HTTPException(
            status_code=400,
            detail="invalid approval payload",
        ) from None
    if (
        not isinstance(body, dict)
        or set(body) != {"outcome"}
        or not isinstance(body["outcome"], str)
    ):
        raise HTTPException(status_code=400, detail="invalid approval payload")
    try:
        return ApprovalOutcome(body["outcome"])
    except ValueError:
        raise HTTPException(
            status_code=400,
            detail="invalid approval payload",
        ) from None


async def _read_checkpoint_scope(request: Request) -> str:
    try:
        chunks: list[bytes] = []
        size = 0
        async for chunk in request.stream():
            size += len(chunk)
            if size > MAX_CHECKPOINT_RESTORE_BODY_BYTES:
                raise HTTPException(
                    status_code=400,
                    detail="invalid checkpoint restore payload",
                )
            chunks.append(chunk)
        body = json.loads(b"".join(chunks))
    except (json.JSONDecodeError, UnicodeDecodeError):
        raise HTTPException(
            status_code=400,
            detail="invalid checkpoint restore payload",
        ) from None
    if (
        not isinstance(body, dict)
        or set(body) != {"scope"}
        or body["scope"] not in {
            "code",
            "conversation",
            "both",
        }
    ):
        raise HTTPException(
            status_code=400,
            detail="invalid checkpoint restore payload",
        )
    return str(body["scope"])


async def _read_session_update(request: Request) -> dict[str, Any]:
    try:
        body = await request.json()
    except (json.JSONDecodeError, UnicodeDecodeError):
        raise HTTPException(
            status_code=400,
            detail="invalid session update",
        ) from None
    if (
        not isinstance(body, dict)
        or not body
        or not set(body) <= {"title", "pinned", "archived", "model"}
        or (
            "title" in body
            and (
                not isinstance(body["title"], str)
                or len(body["title"].encode("utf-8")) > 512
            )
        )
        or (
            "pinned" in body
            and not isinstance(body["pinned"], bool)
        )
        or (
            "archived" in body
            and not isinstance(body["archived"], bool)
        )
        or (
            "model" in body
            and (
                not isinstance(body["model"], str)
                or not 1 <= len(body["model"].encode("utf-8")) <= 256
                or any(ord(character) < 32 for character in body["model"])
            )
        )
    ):
        raise HTTPException(status_code=400, detail="invalid session update")
    return body


async def _read_mcp_server(request: Request) -> MCPServerDef:
    try:
        body = await request.json()
    except (json.JSONDecodeError, UnicodeDecodeError):
        raise HTTPException(status_code=400, detail="invalid MCP server") from None
    allowed = {
        "name",
        "transport",
        "command",
        "args",
        "cwd",
        "url",
        "include_tools",
        "exclude_tools",
    }
    server = body.get("server") if isinstance(body, dict) else None
    try:
        encoded = json.dumps(server, allow_nan=False)
    except (TypeError, ValueError, OverflowError):
        encoded = ""
    if (
        not isinstance(body, dict)
        or set(body) != {"server"}
        or not isinstance(server, dict)
        or not set(server) <= allowed
        or len(encoded.encode("utf-8")) > 65_536
    ):
        raise HTTPException(status_code=400, detail="invalid MCP server")
    try:
        return MCPServerDef(**server)
    except (TypeError, ValueError):
        raise HTTPException(status_code=400, detail="invalid MCP server") from None


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


async def _read_oauth_callback(request: Request) -> dict[str, str]:
    try:
        body = await request.json()
    except (json.JSONDecodeError, UnicodeDecodeError):
        raise HTTPException(status_code=400, detail="invalid OAuth callback") from None
    if (
        not isinstance(body, dict)
        or set(body) != {"flow", "state", "code", "error"}
        or not all(isinstance(value, str) for value in body.values())
        or not 1 <= len(body["flow"]) <= 128
        or not 32 <= len(body["state"]) <= 256
        or len(body["code"].encode("utf-8")) > 8192
        or len(body["error"].encode("utf-8")) > 256
    ):
        raise HTTPException(status_code=400, detail="invalid OAuth callback")
    return body


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
