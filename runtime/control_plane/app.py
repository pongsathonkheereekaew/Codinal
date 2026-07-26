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
from fastapi.responses import JSONResponse, PlainTextResponse

from runtime.events import EventHub
from runtime.builds import MAX_PLAN_BUILD_CANDIDATES
from runtime.git import (
    CheckpointRestoreScope,
    GitWorkspaceError,
)
from runtime.interactions import InteractionPersistenceError
from runtime.mcp import MCPServerDef
from runtime.control_plane.input_validation import (
    MAX_TURN_BODY_BYTES,
    valid_turn_input,
)
from runtime.policy import ApprovalOutcome, ApprovalPersistenceError
from runtime.path_scope import scopes_overlap
from runtime.sessions.context import make_project_context_item
from runtime.storage import ExportTooLargeError
from runtime.turns import (
    CodeCheckpointError,
    ExportBusyError,
    SessionBusyError,
    SessionModelError,
    SessionNotFoundError,
    SessionWorkspaceError,
)
from runtime.workers import (
    WorkerHello,
    WorkerProtocolError,
    negotiate,
    worker_to_dict,
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
MAX_INTERACTION_BODY_BYTES = 128 * 1024
MAX_SESSION_FORK_BODY_BYTES = 1024
MAX_ROOT_BODY_BYTES = 8 * 1024
MAX_WORKER_BODY_BYTES = 64 * 1024
MAX_PLAN_BUILD_BODY_BYTES = 256 * 1024


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
        mode: str | None = None,
        model: str | None = None,
        source: dict[str, Any] | None = None,
        user_input_resolver: Any = None,
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

    async def mutate_when_idle(
        self,
        session_id: str,
        mutation: Any,
    ) -> Any: ...


class SessionControl(Protocol):
    def list_sessions(
        self,
        *,
        workspace: str | None = None,
    ) -> list[dict[str, Any]]: ...

    def search_sessions(
        self,
        query: str,
        *,
        limit: int,
    ) -> list[dict[str, Any]]: ...

    def messages(self, session_id: str) -> list[dict[str, Any]]: ...

    def export(self) -> dict[str, Any]: ...

    def export_markdown(self, session_id: str) -> dict[str, Any]: ...

    def roots(self, session_id: str) -> list[dict[str, Any]]: ...

    def tree(
        self,
        session_id: str,
        *,
        root: str,
        path: str,
        limit: int,
    ) -> dict[str, Any]: ...

    def project_search(
        self,
        session_id: str,
        *,
        query: str,
        mode: str,
        limit: int,
    ) -> dict[str, Any]: ...

    def cancel_project_search(self, session_id: str) -> bool: ...

    def project_index_status(self, session_id: str) -> dict[str, Any]: ...

    def rebuild_project_index(self, session_id: str) -> dict[str, Any]: ...

    def clear_project_index(self, session_id: str) -> dict[str, Any]: ...

    def project_context(
        self,
        session_id: str,
        *,
        root: str,
        path: str,
        kind: str,
    ) -> dict[str, Any]: ...

    def open_project_path(
        self,
        session_id: str,
        *,
        root: str,
        path: str,
        mode: str,
    ) -> dict[str, Any]: ...

    def project_root_identity(
        self,
        session_id: str,
        root: str,
    ) -> tuple[int, int] | None: ...

    def add_root(
        self,
        session_id: str,
        path: str,
        *,
        writable: bool = False,
    ) -> dict[str, Any]: ...

    def remove_root(
        self,
        session_id: str,
        path: str,
    ) -> dict[str, Any]: ...

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
        *,
        routing: dict[str, Any] | None = None,
    ) -> dict[str, Any]: ...

    def delete(self, session_id: str) -> dict[str, Any]: ...

    def fork(
        self,
        session_id: str,
        *,
        message_index: int,
    ) -> dict[str, Any]: ...

    def side_conversation(
        self,
        session_id: str,
        *,
        message_index: int,
    ) -> dict[str, Any]: ...

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

    def context_snapshot(
        self,
        session_id: str,
        *,
        root: str,
        expected_identity: tuple[int, int],
    ) -> dict[str, object]: ...

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


class InteractionControl(Protocol):
    def pending(self, session_id: str) -> list[dict[str, Any]]: ...

    def resolve(
        self,
        session_id: str,
        interaction_id: str,
        response: dict[str, Any],
    ) -> bool: ...

    def close(self) -> None: ...


class PlanControl(Protocol):
    def list_plan_artifacts(
        self,
        session_id: str,
    ) -> list[dict[str, Any]]: ...


class PlanBuildControl(Protocol):
    async def create(
        self,
        parent_session_id: str,
        *,
        plan_id: str,
        tasks: tuple[dict[str, Any], ...],
    ) -> dict[str, Any]: ...

    def list(self, parent_session_id: str) -> list[dict[str, Any]]: ...

    def candidate_diff(
        self,
        build_id: str,
        worker_id: str,
    ) -> dict[str, Any]: ...

    async def select(
        self,
        build_id: str,
        worker_id: str,
    ) -> dict[str, Any]: ...

    async def adopt(self, build_id: str) -> dict[str, object]: ...


class GoalControl(Protocol):
    async def create(
        self,
        session_id: str,
        **options: Any,
    ) -> dict[str, Any]: ...

    def list(self, session_id: str) -> list[dict[str, Any]]: ...

    async def continue_goal(self, goal_id: str) -> dict[str, Any]: ...

    async def add_evidence(
        self,
        goal_id: str,
        **options: Any,
    ) -> dict[str, Any]: ...

    async def audit(
        self,
        goal_id: str,
        **options: Any,
    ) -> dict[str, Any]: ...


class RestoreControl(Protocol):
    def restore(
        self,
        session_id: str,
        checkpoint_id: str,
        scope: CheckpointRestoreScope,
    ) -> dict[str, object]: ...

    def reconcile(self) -> int: ...


class ControlPlaneServices(Protocol):
    events: EventHub
    settings: SettingsView
    secrets: ProviderSecrets
    oauth: OAuthCallbacks
    turns: TurnControl
    sessions: SessionControl
    mcp: MCPControl | None
    git: GitControl | None
    restores: RestoreControl | None
    approvals: ApprovalControl | None
    interactions: InteractionControl | None
    plans: PlanControl | None
    workers: Any | None
    builds: PlanBuildControl | None
    goals: GoalControl | None


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
            restores = getattr(services, "restores", None)
            if restores is not None:
                await asyncio.to_thread(restores.reconcile)
            await services.turns.recover()
            goals = getattr(services, "goals", None)
            if goals is not None:
                await goals.recover()
            workers = getattr(services, "workers", None)
            if workers is not None:
                await workers.recover()
            builds = getattr(services, "builds", None)
            if builds is not None:
                await builds.recover()
            yield
        finally:
            goals = getattr(services, "goals", None)
            if goals is not None:
                await goals.shutdown()
            builds = getattr(services, "builds", None)
            if builds is not None:
                await builds.shutdown()
            workers = getattr(services, "workers", None)
            if workers is not None:
                await workers.shutdown()
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
                interactions = getattr(services, "interactions", None)
                if interactions is not None:
                    interactions.close()
                if workers is not None:
                    workers.store.close()
                if builds is not None:
                    builds.store.close()
                goal_store = getattr(goals, "store", None)
                if goal_store is not None:
                    goal_store.close()
                sessions = getattr(services, "sessions", None)
                close_sessions = getattr(sessions, "close", None)
                if close_sessions is not None:
                    close_sessions()

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
        view = services.settings.view()
        routing = getattr(services, "routing", None)
        if routing is not None:
            view["routing"] = routing.view(
                view.get("routing_profile", "manual")
            )
        return view

    @app.patch("/v1/settings/routing")
    async def update_routing_profile(
        request: Request,
    ) -> dict[str, Any]:
        body = await _read_bounded_object(
            request,
            limit=1024,
            detail="invalid routing profile",
        )
        if set(body) != {"profile"} or not isinstance(
            body.get("profile"),
            str,
        ):
            raise HTTPException(
                status_code=400,
                detail="invalid routing profile",
            )
        result = services.settings.set_routing_profile(body["profile"])
        if not result.get("ok"):
            raise HTTPException(
                status_code=400,
                detail=result.get("error", "invalid routing profile"),
            )
        routing = getattr(services, "routing", None)
        if routing is not None:
            result["routing"] = routing.view(result["routing_profile"])
        return result

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

    @app.get("/v1/sessions/search")
    async def search_sessions(
        q: str,
        limit: int = 50,
    ) -> list[dict[str, Any]]:
        if (
            not 1 <= len(q.strip()) <= 256
            or isinstance(limit, bool)
            or not 1 <= limit <= 100
        ):
            raise HTTPException(
                status_code=400,
                detail="invalid session search",
            )
        return await asyncio.to_thread(
            services.sessions.search_sessions,
            q.strip(),
            limit=limit,
        )

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

    @app.get("/v1/sessions/{session_id}/export.md")
    async def export_session_markdown(
        session_id: str,
    ) -> PlainTextResponse:
        _validate_public_session_id(session_id)
        try:
            result = await services.turns.export_when_idle(
                lambda: services.sessions.export_markdown(session_id)
            )
        except ExportBusyError:
            raise HTTPException(
                status_code=409,
                detail="cannot export while a turn is active",
            ) from None
        if not result.get("ok"):
            raise HTTPException(
                status_code=404,
                detail=result.get("error", "session not found"),
            )
        content = str(result.get("content", ""))
        if len(content.encode("utf-8")) > 32 * 1024 * 1024:
            raise HTTPException(
                status_code=413,
                detail="Markdown export exceeds the 32 MiB safety limit",
            )
        filename = str(result.get("filename", "codinal-conversation.md"))
        if not re.fullmatch(r"[a-z0-9][a-z0-9.-]{0,99}\.md", filename):
            filename = "codinal-conversation.md"
        return PlainTextResponse(
            content,
            media_type="text/markdown",
            headers={
                "Content-Disposition": f'attachment; filename="{filename}"',
                "Cache-Control": "no-store",
            },
        )

    @app.get("/v1/sessions/{session_id}/roots")
    async def session_roots(
        session_id: str,
    ) -> list[dict[str, Any]]:
        _validate_public_session_id(session_id)
        return services.sessions.roots(session_id)

    @app.get("/v1/sessions/{session_id}/tree")
    async def session_tree(
        session_id: str,
        root: str,
        path: str = "",
        limit: int = 200,
    ) -> dict[str, Any]:
        _validate_public_session_id(session_id)
        if (
            not 1 <= len(root) <= 4096
            or not Path(root).is_absolute()
            or len(path) > 4096
            or Path(path).is_absolute()
            or ".." in Path(path).parts
            or not 1 <= limit <= 500
        ):
            raise HTTPException(status_code=400, detail="invalid tree path")
        result = await asyncio.to_thread(
            services.sessions.tree,
            session_id,
            root=root,
            path=path,
            limit=limit,
        )
        if not result.get("ok"):
            status = (
                404
                if result.get("error")
                in {
                    "root is not part of the session",
                    "root is unavailable",
                }
                else 400
            )
            raise HTTPException(status_code=status, detail=result["error"])
        return result

    @app.post("/v1/sessions/{session_id}/context")
    async def create_project_context(
        session_id: str,
        request: Request,
    ) -> dict[str, Any]:
        _validate_public_session_id(session_id)
        descriptor = await _read_project_context(request)
        result = await _resolve_project_context(
            services,
            session_id,
            descriptor,
        )
        if not result.get("ok"):
            raise HTTPException(
                status_code=400,
                detail=result.get("error", "project context unavailable"),
            )
        return result

    @app.get("/v1/sessions/{session_id}/project/search")
    async def search_project(
        session_id: str,
        q: str,
        mode: str = "text",
        limit: int = 50,
    ) -> dict[str, Any]:
        _validate_public_session_id(session_id)
        if (
            not 1 <= len(q.encode("utf-8")) <= 256
            or "\x00" in q
            or mode not in {"text", "symbol", "semantic"}
            or not 1 <= limit <= 100
        ):
            raise HTTPException(
                status_code=400,
                detail="invalid project search",
            )
        result = await asyncio.to_thread(
            services.sessions.project_search,
            session_id,
            query=q,
            mode=mode,
            limit=limit,
        )
        if not result.get("ok"):
            status = (
                404
                if result.get("error") == "project roots unavailable"
                else 400
            )
            raise HTTPException(status_code=status, detail=result["error"])
        return result

    @app.get("/v1/sessions/{session_id}/project/index")
    async def project_index_status(
        session_id: str,
    ) -> dict[str, Any]:
        _validate_public_session_id(session_id)
        result = await asyncio.to_thread(
            services.sessions.project_index_status,
            session_id,
        )
        if not result.get("ok"):
            raise HTTPException(
                status_code=404,
                detail=result.get("error", "project index unavailable"),
            )
        return result

    @app.post("/v1/sessions/{session_id}/project/index")
    async def rebuild_project_index(
        session_id: str,
    ) -> dict[str, Any]:
        _validate_public_session_id(session_id)
        result = await asyncio.to_thread(
            services.sessions.rebuild_project_index,
            session_id,
        )
        if not result.get("ok"):
            raise HTTPException(
                status_code=(
                    409
                    if result.get("error")
                    == "semantic index build already active"
                    else 404
                ),
                detail=result.get("error", "project index unavailable"),
            )
        return result

    @app.delete("/v1/sessions/{session_id}/project/index")
    async def clear_project_index(
        session_id: str,
    ) -> dict[str, Any]:
        _validate_public_session_id(session_id)
        result = await asyncio.to_thread(
            services.sessions.clear_project_index,
            session_id,
        )
        if not result.get("ok"):
            raise HTTPException(
                status_code=(
                    409
                    if result.get("error")
                    == "semantic index build already active"
                    else 404
                ),
                detail=result.get("error", "project index unavailable"),
            )
        return result

    @app.delete("/v1/sessions/{session_id}/project/search")
    async def cancel_project_search(
        session_id: str,
    ) -> dict[str, bool]:
        _validate_public_session_id(session_id)
        return {
            "ok": services.sessions.cancel_project_search(session_id)
        }

    @app.post("/v1/sessions/{session_id}/project/open")
    async def open_project_path(
        session_id: str,
        request: Request,
    ) -> dict[str, Any]:
        _validate_public_session_id(session_id)
        descriptor = await _read_project_context(request, with_mode=True)
        try:
            result = await services.turns.mutate_when_idle(
                session_id,
                lambda: services.sessions.open_project_path(
                    session_id,
                    root=descriptor["root"],
                    path=descriptor["path"],
                    mode=descriptor["mode"],
                ),
            )
        except SessionBusyError as error:
            raise HTTPException(status_code=409, detail=str(error)) from None
        if not result.get("ok"):
            raise HTTPException(
                status_code=400,
                detail=result.get("error", "project path unavailable"),
            )
        return result

    @app.post("/v1/sessions/{session_id}/roots")
    async def add_session_root(
        session_id: str,
        request: Request,
    ) -> dict[str, Any]:
        _validate_public_session_id(session_id)
        path, writable = await _read_root_update(request, remove=False)
        try:
            result = await services.turns.mutate_when_idle(
                session_id,
                lambda: services.sessions.add_root(
                    session_id,
                    path,
                    writable=writable,
                ),
            )
        except SessionBusyError as error:
            raise HTTPException(status_code=409, detail=str(error)) from None
        if not result.get("ok"):
            status = (
                404
                if result.get("error") == "session not found"
                else 400
            )
            raise HTTPException(status_code=status, detail=result["error"])
        return result

    @app.delete("/v1/sessions/{session_id}/roots")
    async def remove_session_root(
        session_id: str,
        request: Request,
    ) -> dict[str, Any]:
        _validate_public_session_id(session_id)
        path, _writable = await _read_root_update(request, remove=True)
        try:
            result = await services.turns.mutate_when_idle(
                session_id,
                lambda: services.sessions.remove_root(session_id, path),
            )
        except SessionBusyError as error:
            raise HTTPException(status_code=409, detail=str(error)) from None
        if not result.get("ok"):
            status = (
                404
                if result.get("error") == "session not found"
                else 400
            )
            raise HTTPException(status_code=status, detail=result["error"])
        return result

    @app.patch("/v1/sessions/{session_id}")
    async def update_session(
        session_id: str,
        request: Request,
    ) -> dict[str, Any]:
        _validate_public_session_id(session_id)
        update = await _read_session_update(request)

        def mutate() -> dict[str, Any]:
            result: dict[str, Any] = {
                "ok": True,
                "session_id": session_id,
            }
            if "title" in update:
                result = services.sessions.rename(
                    session_id,
                    update["title"],
                )
            if result.get("ok") and (
                "pinned" in update or "archived" in update
            ):
                result = services.sessions.set_flags(
                    session_id,
                    pinned=update.get("pinned"),
                    archived=update.get("archived"),
                )
            if result.get("ok") and "model" in update:
                result = services.sessions.set_model(
                    session_id,
                    update["model"],
                )
            return result

        try:
            result = await services.turns.mutate_when_idle(
                session_id,
                mutate,
            )
        except SessionBusyError as error:
            raise HTTPException(
                status_code=409,
                detail=str(error),
            ) from None
        if not result.get("ok"):
            raise HTTPException(status_code=404, detail="session not found")
        return result

    @app.delete("/v1/sessions/{session_id}")
    async def delete_session(session_id: str) -> dict[str, Any]:
        _validate_public_session_id(session_id)
        try:
            result = await services.turns.mutate_when_idle(
                session_id,
                lambda: services.sessions.delete(session_id),
            )
        except SessionBusyError as error:
            raise HTTPException(
                status_code=409,
                detail=str(error),
            ) from None
        if result.get("cleanup_errors"):
            raise HTTPException(
                status_code=409,
                detail="session cleanup failed",
            )
        if not result.get("ok"):
            raise HTTPException(status_code=404, detail="session not found")
        return result

    async def branch_session(
        session_id: str,
        request: Request,
        brancher: Any,
    ) -> dict[str, Any]:
        _validate_public_session_id(session_id)
        message_index = await _read_session_fork(request)
        try:
            result = await services.turns.mutate_when_idle(
                session_id,
                lambda: brancher(
                    session_id,
                    message_index=message_index,
                ),
            )
        except SessionBusyError as error:
            raise HTTPException(status_code=409, detail=str(error)) from None
        if not result.get("ok"):
            status = (
                400
                if result.get("error")
                in {"invalid message index", "invalid fork boundary"}
                else 404
            )
            raise HTTPException(
                status_code=status,
                detail=result.get("error", "session not found"),
            )
        return result

    @app.post("/v1/sessions/{session_id}/fork")
    async def fork_session(
        session_id: str,
        request: Request,
    ) -> dict[str, Any]:
        return await branch_session(
            session_id,
            request,
            services.sessions.fork,
        )

    @app.post("/v1/sessions/{session_id}/side-conversations")
    async def create_side_conversation(
        session_id: str,
        request: Request,
    ) -> dict[str, Any]:
        return await branch_session(
            session_id,
            request,
            services.sessions.side_conversation,
        )

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
        if isinstance(turn.get("source"), dict):
            source = dict(turn["source"])
            source.pop("routing", None)
            turn["source"] = source or None
        routing_resolution = None
        routing = getattr(services, "routing", None)
        settings_view = services.settings.view()
        effective_profile = turn.get(
            "routing_profile",
            settings_view.get("routing_profile", "manual"),
        )
        if routing is not None:
            preferred_model = turn.get("model")
            routing_context_loader = getattr(
                services.sessions,
                "routing_context",
                None,
            )
            if callable(routing_context_loader):
                routing_context = await asyncio.to_thread(
                    routing_context_loader,
                    session_id,
                )
            else:
                selected_model = getattr(
                    services.sessions,
                    "selected_model",
                    None,
                )
                requirements = getattr(
                    services.sessions,
                    "routing_requirements",
                    None,
                )

                def load_legacy_routing_context() -> dict[str, Any]:
                    return {
                        "model": (
                            selected_model(session_id)
                            if callable(selected_model)
                            else None
                        ),
                        "required_capabilities": (
                            requirements(session_id)
                            if callable(requirements)
                            else ()
                        ),
                    }

                routing_context = await asyncio.to_thread(
                    load_legacy_routing_context
                )
            if not preferred_model:
                preferred_model = routing_context.get("model")
            if not preferred_model:
                preferred_model = settings_view.get("model", "")
            try:
                routing_resolution = routing.resolve(
                    effective_profile,
                    preferred_model=preferred_model or "",
                    user_input=turn["input"],
                    required_capabilities=routing_context.get(
                        "required_capabilities",
                        (),
                    ),
                )
            except ValueError as error:
                raise HTTPException(
                    status_code=409,
                    detail=str(error),
                ) from None
            turn["model"] = routing_resolution["selected_model"]
            turn["source"] = {
                **(turn.get("source") or {}),
                "routing": routing_resolution,
            }
        try:
            options: dict[str, Any] = {
                "user_input": turn["input"],
                "workspace": turn.get("workspace"),
                "agent": turn.get("agent", "code"),
                "model": turn.get("model"),
                "source": turn.get("source"),
            }
            if "mode" in turn:
                options["mode"] = turn["mode"]
            if turn.get("context"):
                async def resolve_input() -> str | list[dict[str, Any]]:
                    context_parts = await _resolve_turn_context(
                        services,
                        session_id,
                        turn["context"],
                    )
                    resolved = _with_context_parts(
                        turn["input"],
                        context_parts,
                    )
                    if not valid_turn_input(
                        resolved,
                        allow_context=True,
                    ):
                        raise HTTPException(
                            status_code=413,
                            detail=(
                                "project context exceeds the turn safety limit"
                            ),
                        )
                    return resolved

                options["user_input_resolver"] = resolve_input
            result = await services.turns.start(session_id, **options)
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
        except SessionModelError:
            raise HTTPException(
                status_code=409,
                detail="session model update failed",
            ) from None
        except CodeCheckpointError:
            raise HTTPException(
                status_code=409,
                detail="automatic code checkpoint unavailable",
            ) from None
        if routing_resolution is not None:
            result = {**result, "routing": routing_resolution}
        return JSONResponse(result, status_code=202)

    @app.get("/v1/sessions/{session_id}/workers")
    async def list_workers(session_id: str) -> list[dict[str, object]]:
        _validate_public_session_id(session_id)
        workers = getattr(services, "workers", None)
        if workers is None:
            return []
        records = await asyncio.to_thread(workers.list, session_id)
        return [worker_to_dict(record) for record in records]

    @app.post("/v1/workers/negotiate")
    async def negotiate_worker(request: Request) -> dict[str, object]:
        body = await _read_bounded_object(
            request,
            limit=16 * 1024,
            detail="invalid worker handshake",
        )
        if (
            set(body) != {"version", "worker_kind", "capabilities"}
            or not isinstance(body.get("version"), str)
            or not isinstance(body.get("worker_kind"), str)
            or not isinstance(body.get("capabilities"), list)
            or any(
                not isinstance(capability, str)
                for capability in body.get("capabilities", [])
            )
        ):
            raise HTTPException(
                status_code=400,
                detail="invalid worker handshake",
            )
        if body["worker_kind"] == "remote":
            raise HTTPException(
                status_code=501,
                detail="remote worker transport is unavailable",
            )
        try:
            capabilities = negotiate(
                WorkerHello(
                    version=body["version"],
                    worker_kind=body["worker_kind"],
                    capabilities=frozenset(body["capabilities"]),
                )
            )
        except WorkerProtocolError as error:
            raise HTTPException(status_code=409, detail=str(error)) from None
        return {
            "version": body["version"],
            "worker_kind": body["worker_kind"],
            "capabilities": sorted(capabilities),
        }

    @app.post("/v1/sessions/{session_id}/workers")
    async def create_worker(
        session_id: str,
        request: Request,
    ) -> JSONResponse:
        _validate_public_session_id(session_id)
        workers = getattr(services, "workers", None)
        if workers is None:
            raise HTTPException(
                status_code=503,
                detail="workers are unavailable",
            )
        body = await _read_worker_create(request)
        try:
            record = await workers.create(
                session_id,
                task=body["task"],
                ownership=tuple(body["ownership"]),
                dependencies=tuple(body.get("dependencies", [])),
                model=body["model"],
                worker_kind=body.get("worker_kind", "local"),
            )
        except (KeyError, SessionBusyError, ValueError) as error:
            raise HTTPException(
                status_code=409,
                detail=str(error),
            ) from None
        return JSONResponse(worker_to_dict(record), status_code=202)

    @app.post("/v1/workers/{worker_id}/steer")
    async def steer_worker(
        worker_id: str,
        request: Request,
    ) -> dict[str, object]:
        _validate_public_session_id(worker_id)
        workers = getattr(services, "workers", None)
        if workers is None:
            raise HTTPException(status_code=503, detail="workers are unavailable")
        text = await _read_worker_steer(request)
        try:
            ok = workers.steer(worker_id, text)
        except KeyError:
            raise HTTPException(status_code=404, detail="worker not found") from None
        return {"ok": ok, "worker_id": worker_id}

    @app.post("/v1/workers/{worker_id}/cancel")
    async def cancel_worker(worker_id: str) -> dict[str, object]:
        _validate_public_session_id(worker_id)
        workers = getattr(services, "workers", None)
        if workers is None:
            raise HTTPException(status_code=503, detail="workers are unavailable")
        try:
            ok = await workers.cancel(worker_id)
        except KeyError:
            raise HTTPException(status_code=404, detail="worker not found") from None
        return {"ok": ok, "worker_id": worker_id}

    @app.post("/v1/workers/{worker_id}/adopt")
    async def adopt_worker(worker_id: str) -> dict[str, object]:
        _validate_public_session_id(worker_id)
        workers = getattr(services, "workers", None)
        if workers is None:
            raise HTTPException(status_code=503, detail="workers are unavailable")
        try:
            return await workers.adopt(worker_id)
        except KeyError:
            raise HTTPException(status_code=404, detail="worker not found") from None
        except (GitWorkspaceError, ValueError) as error:
            raise HTTPException(status_code=409, detail=str(error)) from None

    @app.get("/v1/sessions/{session_id}/plan-builds")
    async def list_plan_builds(
        session_id: str,
    ) -> list[dict[str, Any]]:
        _validate_public_session_id(session_id)
        builds = getattr(services, "builds", None)
        if builds is None:
            return []
        return await asyncio.to_thread(builds.list, session_id)

    @app.post("/v1/sessions/{session_id}/plan-builds")
    async def create_plan_build(
        session_id: str,
        request: Request,
    ) -> JSONResponse:
        _validate_public_session_id(session_id)
        builds = getattr(services, "builds", None)
        if builds is None:
            raise HTTPException(
                status_code=503,
                detail="plan builds are unavailable",
            )
        body = await _read_plan_build_create(request)
        try:
            record = await builds.create(
                session_id,
                plan_id=body["plan_id"],
                tasks=tuple(body["tasks"]),
            )
        except (KeyError, SessionBusyError, ValueError) as error:
            raise HTTPException(status_code=409, detail=str(error)) from None
        return JSONResponse(record, status_code=202)

    @app.post("/v1/plan-builds/{build_id}/select")
    async def select_plan_build(
        build_id: str,
        request: Request,
    ) -> dict[str, Any]:
        _validate_public_session_id(build_id)
        builds = getattr(services, "builds", None)
        if builds is None:
            raise HTTPException(
                status_code=503,
                detail="plan builds are unavailable",
            )
        worker_id = await _read_plan_build_selection(request)
        try:
            return await builds.select(build_id, worker_id)
        except KeyError:
            raise HTTPException(status_code=404, detail="plan build not found") from None
        except ValueError as error:
            raise HTTPException(status_code=409, detail=str(error)) from None

    @app.get("/v1/plan-builds/{build_id}/candidates/{worker_id}/diff")
    async def plan_build_candidate_diff(
        build_id: str,
        worker_id: str,
    ) -> dict[str, Any]:
        _validate_public_session_id(build_id)
        _validate_public_session_id(worker_id)
        builds = getattr(services, "builds", None)
        if builds is None:
            raise HTTPException(
                status_code=503,
                detail="plan builds are unavailable",
            )
        try:
            return await asyncio.to_thread(
                builds.candidate_diff,
                build_id,
                worker_id,
            )
        except KeyError:
            raise HTTPException(status_code=404, detail="plan build not found") from None
        except ValueError as error:
            raise HTTPException(status_code=409, detail=str(error)) from None

    @app.post("/v1/plan-builds/{build_id}/adopt")
    async def adopt_plan_build(build_id: str) -> dict[str, object]:
        _validate_public_session_id(build_id)
        builds = getattr(services, "builds", None)
        if builds is None:
            raise HTTPException(
                status_code=503,
                detail="plan builds are unavailable",
            )
        try:
            return await builds.adopt(build_id)
        except KeyError:
            raise HTTPException(status_code=404, detail="plan build not found") from None
        except (GitWorkspaceError, ValueError) as error:
            raise HTTPException(status_code=409, detail=str(error)) from None

    @app.get("/v1/sessions/{session_id}/goals")
    async def list_goals(session_id: str) -> list[dict[str, Any]]:
        _validate_public_session_id(session_id)
        goals = getattr(services, "goals", None)
        if goals is None:
            return []
        return await asyncio.to_thread(goals.list, session_id)

    @app.post("/v1/sessions/{session_id}/goals")
    async def create_goal(
        session_id: str,
        request: Request,
    ) -> JSONResponse:
        _validate_public_session_id(session_id)
        goals = getattr(services, "goals", None)
        if goals is None:
            raise HTTPException(
                status_code=503,
                detail="goals are unavailable",
            )
        body = await _read_goal_create(request)
        try:
            record = await goals.create(
                session_id,
                objective=body["objective"],
                requirements=tuple(body["requirements"]),
                continuation_prompt=body["continuation_prompt"],
                token_budget=body.get("token_budget"),
                time_budget_seconds=body.get("time_budget_seconds"),
            )
        except KeyError:
            raise HTTPException(status_code=404, detail="session not found") from None
        except ValueError as error:
            raise HTTPException(status_code=409, detail=str(error)) from None
        return JSONResponse(record, status_code=201)

    @app.post("/v1/goals/{goal_id}/continue")
    async def continue_goal(goal_id: str) -> JSONResponse:
        _validate_public_session_id(goal_id)
        goals = getattr(services, "goals", None)
        if goals is None:
            raise HTTPException(
                status_code=503,
                detail="goals are unavailable",
            )
        try:
            record = await goals.continue_goal(goal_id)
        except KeyError:
            raise HTTPException(status_code=404, detail="goal not found") from None
        except (SessionBusyError, ValueError) as error:
            raise HTTPException(status_code=409, detail=str(error)) from None
        return JSONResponse(record, status_code=202)

    @app.post("/v1/goals/{goal_id}/evidence")
    async def add_goal_evidence(
        goal_id: str,
        request: Request,
    ) -> JSONResponse:
        _validate_public_session_id(goal_id)
        goals = getattr(services, "goals", None)
        if goals is None:
            raise HTTPException(
                status_code=503,
                detail="goals are unavailable",
            )
        body = await _read_goal_evidence(request)
        try:
            evidence = await goals.add_evidence(goal_id, **body)
        except KeyError:
            raise HTTPException(status_code=404, detail="goal not found") from None
        except ValueError as error:
            raise HTTPException(status_code=409, detail=str(error)) from None
        return JSONResponse(evidence, status_code=201)

    @app.post("/v1/goals/{goal_id}/audit")
    async def audit_goal(
        goal_id: str,
        request: Request,
    ) -> dict[str, Any]:
        _validate_public_session_id(goal_id)
        goals = getattr(services, "goals", None)
        if goals is None:
            raise HTTPException(
                status_code=503,
                detail="goals are unavailable",
            )
        body = await _read_goal_audit(request)
        try:
            return await goals.audit(
                goal_id,
                status=body["status"],
                summary=body["summary"],
                requirement_evidence={
                    requirement_id: tuple(evidence_ids)
                    for requirement_id, evidence_ids in body[
                        "requirement_evidence"
                    ].items()
                },
            )
        except KeyError:
            raise HTTPException(status_code=404, detail="goal not found") from None
        except ValueError as error:
            raise HTTPException(status_code=409, detail=str(error)) from None

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

    @app.get("/v1/sessions/{session_id}/interactions")
    async def list_interactions(
        session_id: str,
    ) -> list[dict[str, Any]]:
        _validate_public_session_id(session_id)
        interactions = getattr(services, "interactions", None)
        if interactions is None:
            return []
        return interactions.pending(session_id)

    @app.get("/v1/sessions/{session_id}/plans")
    async def list_plans(
        session_id: str,
    ) -> list[dict[str, Any]]:
        _validate_public_session_id(session_id)
        plans = getattr(services, "plans", None)
        if plans is None:
            return []
        return plans.list_plan_artifacts(session_id)

    @app.post(
        "/v1/sessions/{session_id}/interactions/{interaction_id}"
    )
    async def resolve_interaction(
        session_id: str,
        interaction_id: str,
        request: Request,
    ) -> dict[str, bool]:
        _validate_public_session_id(session_id)
        if re.fullmatch(r"[a-f0-9]{32}", interaction_id) is None:
            raise HTTPException(
                status_code=400,
                detail="invalid interaction id",
            )
        interactions = getattr(services, "interactions", None)
        if interactions is None:
            raise HTTPException(
                status_code=503,
                detail="interactions unavailable",
            )
        response = await _read_interaction_response(request)
        try:
            resolved = interactions.resolve(
                session_id,
                interaction_id,
                response,
            )
        except InteractionPersistenceError:
            raise HTTPException(
                status_code=503,
                detail="interaction response could not be saved",
            ) from None
        except ValueError:
            raise HTTPException(
                status_code=400,
                detail="invalid interaction response",
            ) from None
        if not resolved:
            raise HTTPException(
                status_code=409,
                detail="interaction is not pending",
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
        try:
            result = await services.turns.mutate_when_idle(
                session_id,
                lambda: services.git.apply_back(session_id),
            )
        except SessionBusyError as error:
            raise HTTPException(
                status_code=409,
                detail=str(error),
            ) from None
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
        if (
            services.git is None
            or not _has_checkpoint_session(
                services.git,
                session_id,
            )
        ):
            raise HTTPException(
                status_code=404,
                detail="checkpoint session not found",
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
        if (
            services.git is None
            or not _has_checkpoint_session(
                services.git,
                session_id,
            )
        ):
            raise HTTPException(
                status_code=404,
                detail="checkpoint session not found",
            )
        restores = getattr(services, "restores", None)
        if restores is None:
            raise HTTPException(
                status_code=409,
                detail="checkpoint restore unavailable",
            )
        try:
            result = await services.turns.restore_when_idle(
                lambda: restores.restore(
                    session_id,
                    checkpoint_id,
                    CheckpointRestoreScope(scope),
                )
            )
        except SessionBusyError:
            raise HTTPException(
                status_code=409,
                detail="session already has an active turn",
            ) from None
        except (GitWorkspaceError, ValueError) as error:
            if str(error) == "checkpoint not found":
                raise HTTPException(
                    status_code=404,
                    detail="checkpoint not found",
                ) from None
            raise HTTPException(
                status_code=409,
                detail=str(error),
            ) from None
        except RuntimeError as error:
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
_CONTEXT_FINGERPRINT = re.compile(r"[a-f0-9]{64}")


def _validate_public_session_id(session_id: str) -> None:
    if session_id.startswith("__") or _SESSION_ID.fullmatch(session_id) is None:
        raise HTTPException(status_code=400, detail="invalid session id")


async def _read_worker_create(request: Request) -> dict[str, Any]:
    body = await _read_bounded_object(
        request,
        limit=MAX_WORKER_BODY_BYTES,
        detail="invalid worker payload",
    )
    expected = {
        "task",
        "ownership",
        "dependencies",
        "model",
        "worker_kind",
    }
    ownership = body.get("ownership")
    dependencies = body.get("dependencies", [])
    if (
        not {"task", "ownership", "model"} <= set(body) <= expected
        or not _valid_utf8_text(
            body.get("task"),
            minimum=1,
            maximum=32 * 1024,
        )
        or not isinstance(ownership, list)
        or not 1 <= len(ownership) <= 32
        or any(not isinstance(path, str) for path in ownership)
        or len(set(ownership)) != len(ownership)
        or any(not _valid_worker_path(path) for path in ownership)
        or not isinstance(dependencies, list)
        or len(dependencies) > 32
        or any(not isinstance(item, str) for item in dependencies)
        or len(set(dependencies)) != len(dependencies)
        or any(
            not isinstance(item, str)
            or not item.startswith("worker-")
            or _SESSION_ID.fullmatch(item) is None
            for item in dependencies
        )
        or not _valid_utf8_text(
            body.get("model"),
            minimum=1,
            maximum=256,
        )
        or body.get("worker_kind", "local") != "local"
    ):
        raise HTTPException(status_code=400, detail="invalid worker payload")
    return body


async def _read_worker_steer(request: Request) -> str:
    body = await _read_bounded_object(
        request,
        limit=32 * 1024,
        detail="invalid worker steering",
    )
    text = body.get("text")
    if (
        set(body) != {"text"}
        or not isinstance(text, str)
        or not text.strip()
        or not _valid_utf8_text(text, minimum=1, maximum=32 * 1024)
    ):
        raise HTTPException(status_code=400, detail="invalid worker steering")
    return text.strip()


async def _read_plan_build_create(request: Request) -> dict[str, Any]:
    body = await _read_bounded_object(
        request,
        limit=MAX_PLAN_BUILD_BODY_BYTES,
        detail="invalid plan build payload",
    )
    tasks = body.get("tasks")
    if (
        set(body) != {"plan_id", "tasks"}
        or not isinstance(body.get("plan_id"), str)
        or re.fullmatch(r"[a-f0-9]{32}", body["plan_id"]) is None
        or not isinstance(tasks, list)
        or not 1 <= len(tasks) <= 20
    ):
        raise HTTPException(
            status_code=400,
            detail="invalid plan build payload",
        )
    task_ids: list[str] = []
    scopes: list[tuple[str, ...]] = []
    candidate_count = 0
    for task in tasks:
        if not isinstance(task, dict):
            raise HTTPException(
                status_code=400,
                detail="invalid plan build payload",
            )
        ownership = task.get("ownership")
        candidates = task.get("candidates")
        if (
            set(task) != {"task_id", "ownership", "candidates"}
            or not isinstance(task.get("task_id"), str)
            or re.fullmatch(
                r"[A-Za-z0-9][A-Za-z0-9_-]{0,63}",
                task["task_id"],
            )
            is None
            or not isinstance(ownership, list)
            or not 1 <= len(ownership) <= 32
            or any(not isinstance(path, str) for path in ownership)
            or len(set(ownership)) != len(ownership)
            or any(not _valid_worker_path(path) for path in ownership)
            or not isinstance(candidates, list)
            or not 2 <= len(candidates) <= 4
        ):
            raise HTTPException(
                status_code=400,
                detail="invalid plan build payload",
            )
        for candidate in candidates:
            if (
                not isinstance(candidate, dict)
                or not {"model"} <= set(candidate) <= {"model", "instruction"}
                or not _valid_utf8_text(
                    candidate.get("model"),
                    minimum=1,
                    maximum=256,
                )
                or not _valid_utf8_text(
                    candidate.get("instruction", ""),
                    minimum=0,
                    maximum=32 * 1024,
                )
            ):
                raise HTTPException(
                    status_code=400,
                    detail="invalid plan build payload",
                )
        task_ids.append(task["task_id"])
        scopes.append(tuple(ownership))
        candidate_count += len(candidates)
    if (
        candidate_count > MAX_PLAN_BUILD_CANDIDATES
        or len(set(task_ids)) != len(task_ids)
        or any(
        scopes_overlap(scopes[left], scopes[right])
        for left in range(len(scopes))
        for right in range(left + 1, len(scopes))
        )
    ):
        raise HTTPException(
            status_code=400,
            detail="invalid plan build payload",
        )
    return body


async def _read_plan_build_selection(request: Request) -> str:
    body = await _read_bounded_object(
        request,
        limit=1024,
        detail="invalid plan build selection",
    )
    worker_id = body.get("worker_id")
    if (
        set(body) != {"worker_id"}
        or not isinstance(worker_id, str)
        or not worker_id.startswith("worker-")
        or _SESSION_ID.fullmatch(worker_id) is None
    ):
        raise HTTPException(
            status_code=400,
            detail="invalid plan build selection",
        )
    return worker_id


async def _read_goal_create(request: Request) -> dict[str, Any]:
    body = await _read_bounded_object(
        request,
        limit=128 * 1024,
        detail="invalid goal payload",
    )
    allowed = {
        "objective",
        "requirements",
        "continuation_prompt",
        "token_budget",
        "time_budget_seconds",
    }
    requirements = body.get("requirements")
    if (
        not {"objective", "requirements", "continuation_prompt"}
        <= set(body)
        <= allowed
        or not _valid_utf8_text(
            body.get("objective"),
            minimum=1,
            maximum=64 * 1024,
        )
        or not _valid_utf8_text(
            body.get("continuation_prompt"),
            minimum=1,
            maximum=32 * 1024,
        )
        or not isinstance(requirements, list)
        or not 1 <= len(requirements) <= 20
        or not _valid_optional_integer(
            body.get("token_budget"),
            maximum=100_000_000,
        )
        or not _valid_optional_integer(
            body.get("time_budget_seconds"),
            maximum=31 * 24 * 60 * 60,
        )
    ):
        raise HTTPException(status_code=400, detail="invalid goal payload")
    requirement_ids: list[str] = []
    for requirement in requirements:
        if (
            not isinstance(requirement, dict)
            or set(requirement) != {"requirement_id", "text"}
            or not isinstance(requirement.get("requirement_id"), str)
            or re.fullmatch(
                r"[A-Za-z0-9][A-Za-z0-9_-]{0,63}",
                requirement["requirement_id"],
            )
            is None
            or not _valid_utf8_text(
                requirement.get("text"),
                minimum=1,
                maximum=8192,
            )
        ):
            raise HTTPException(
                status_code=400,
                detail="invalid goal payload",
            )
        requirement_ids.append(requirement["requirement_id"])
    if len(requirement_ids) != len(set(requirement_ids)):
        raise HTTPException(status_code=400, detail="invalid goal payload")
    return body


async def _read_goal_evidence(request: Request) -> dict[str, Any]:
    body = await _read_bounded_object(
        request,
        limit=64 * 1024,
        detail="invalid goal evidence",
    )
    if (
        set(body)
        != {"requirement_id", "kind", "summary", "result", "passed"}
        or not isinstance(body.get("requirement_id"), str)
        or (
            body["requirement_id"]
            and re.fullmatch(
                r"[A-Za-z0-9][A-Za-z0-9_-]{0,63}",
                body["requirement_id"],
            )
            is None
        )
        or body.get("kind") not in {"verification", "blocker"}
        or body.get("kind") == "verification"
        and body.get("passed") is not True
        or body.get("kind") == "blocker"
        and body.get("passed") is not False
        or not _valid_utf8_text(
            body.get("summary"),
            minimum=1,
            maximum=8192,
        )
        or not _valid_utf8_text(
            body.get("result"),
            minimum=0,
            maximum=32 * 1024,
        )
        or not isinstance(body.get("passed"), bool)
    ):
        raise HTTPException(
            status_code=400,
            detail="invalid goal evidence",
        )
    return body


async def _read_goal_audit(request: Request) -> dict[str, Any]:
    body = await _read_bounded_object(
        request,
        limit=128 * 1024,
        detail="invalid goal audit",
    )
    mapping = body.get("requirement_evidence")
    if (
        set(body) != {"status", "summary", "requirement_evidence"}
        or body.get("status") not in {"complete", "blocked"}
        or not _valid_utf8_text(
            body.get("summary"),
            minimum=1,
            maximum=32 * 1024,
        )
        or not isinstance(mapping, dict)
        or len(mapping) > 20
    ):
        raise HTTPException(status_code=400, detail="invalid goal audit")
    for requirement_id, evidence_ids in mapping.items():
        if (
            not isinstance(requirement_id, str)
            or re.fullmatch(
                r"[A-Za-z0-9][A-Za-z0-9_-]{0,63}",
                requirement_id,
            )
            is None
            or not isinstance(evidence_ids, list)
            or not 1 <= len(evidence_ids) <= 100
            or len(evidence_ids) != len(set(evidence_ids))
            or any(
                not isinstance(evidence_id, str)
                or not evidence_id.startswith("evidence-")
                or _SESSION_ID.fullmatch(evidence_id) is None
                for evidence_id in evidence_ids
            )
        ):
            raise HTTPException(
                status_code=400,
                detail="invalid goal audit",
            )
    return body


def _valid_optional_integer(value: object, *, maximum: int) -> bool:
    return (
        value is None
        or not isinstance(value, bool)
        and isinstance(value, int)
        and 1 <= value <= maximum
    )


async def _read_bounded_object(
    request: Request,
    *,
    limit: int,
    detail: str,
) -> dict[str, Any]:
    try:
        chunks = []
        size = 0
        async for chunk in request.stream():
            size += len(chunk)
            if size > limit:
                raise HTTPException(status_code=400, detail=detail)
            chunks.append(chunk)
        body = json.loads(b"".join(chunks))
    except (json.JSONDecodeError, UnicodeDecodeError):
        raise HTTPException(status_code=400, detail=detail) from None
    if not isinstance(body, dict):
        raise HTTPException(status_code=400, detail=detail)
    return body


def _valid_worker_path(value: Any) -> bool:
    if (
        not isinstance(value, str)
        or not _valid_utf8_text(value, minimum=1, maximum=4096)
        or value.startswith("/")
        or "\\" in value
    ):
        return False
    parts = value.split("/")
    return all(part not in {"", ".", ".."} for part in parts)


def _valid_utf8_text(
    value: Any,
    *,
    minimum: int,
    maximum: int,
) -> bool:
    if not isinstance(value, str):
        return False
    try:
        size = len(value.encode("utf-8"))
    except UnicodeEncodeError:
        return False
    return minimum <= size <= maximum


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
            "mode",
            "model",
            "routing_profile",
            "source",
            "context",
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
            "mode" in body
            and (
                not isinstance(body["mode"], str)
                or body["mode"]
                not in {
                    "auto",
                    "custom",
                    "discuss",
                    "interactive",
                    "plan",
                }
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
            "routing_profile" in body
            and (
                not isinstance(body["routing_profile"], str)
                or body["routing_profile"]
                not in {"manual", "quality", "balanced", "economy"}
            )
        )
        or (
            "source" in body
            and (
                not isinstance(body["source"], dict)
                or len(json.dumps(body["source"]).encode("utf-8")) > 16_384
            )
        )
        or (
            "context" in body
            and (
                not isinstance(body["context"], list)
                or not 1 <= len(body["context"]) <= 8
                or any(
                    not _valid_context_descriptor(
                        descriptor,
                        fingerprint=True,
                    )
                    for descriptor in body["context"]
                )
            )
        )
    ):
        raise HTTPException(status_code=400, detail="invalid turn payload")
    return body


async def _read_project_context(
    request: Request,
    *,
    with_mode: bool = False,
) -> dict[str, str]:
    try:
        chunks = []
        size = 0
        async for chunk in request.stream():
            size += len(chunk)
            if size > MAX_ROOT_BODY_BYTES:
                raise HTTPException(
                    status_code=400,
                    detail="invalid project context",
                )
            chunks.append(chunk)
        body = json.loads(b"".join(chunks))
    except (json.JSONDecodeError, UnicodeDecodeError):
        raise HTTPException(
            status_code=400,
            detail="invalid project context",
        ) from None
    if (
        not _valid_context_descriptor(body, mode=with_mode)
        or (
            with_mode
            and (
                body.get("mode") not in {"open", "reveal"}
                or body.get("kind") not in {"file", "folder"}
            )
        )
    ):
        raise HTTPException(
            status_code=400,
            detail="invalid project context",
        )
    return body


def _valid_context_descriptor(
    descriptor: Any,
    *,
    fingerprint: bool = False,
    mode: bool = False,
) -> bool:
    expected = {"kind", "root", "path"}
    if fingerprint:
        expected.add("fingerprint")
    if mode:
        expected.add("mode")
    return bool(
        isinstance(descriptor, dict)
        and set(descriptor) == expected
        and descriptor.get("kind") in {"file", "folder", "git"}
        and isinstance(descriptor.get("root"), str)
        and 1 <= len(descriptor["root"]) <= 4096
        and Path(descriptor["root"]).is_absolute()
        and isinstance(descriptor.get("path"), str)
        and len(descriptor["path"]) <= 4096
        and not Path(descriptor["path"]).is_absolute()
        and ".." not in Path(descriptor["path"]).parts
        and (
            not fingerprint
            or (
                isinstance(descriptor.get("fingerprint"), str)
                and _CONTEXT_FINGERPRINT.fullmatch(
                    descriptor["fingerprint"]
                )
                is not None
            )
        )
        and (not mode or isinstance(descriptor.get("mode"), str))
    )


async def _resolve_turn_context(
    services: Any,
    session_id: str,
    descriptors: list[dict[str, str]],
) -> list[dict[str, str]]:
    parts = []
    for descriptor in descriptors:
        result = await _resolve_project_context(
            services,
            session_id,
            descriptor,
        )
        item = result.get("item") if result.get("ok") else None
        if (
            not isinstance(item, dict)
            or item.get("fingerprint") != descriptor["fingerprint"]
        ):
            raise HTTPException(
                status_code=409,
                detail=(
                    "project context changed; refresh it before sending"
                ),
            )
        part = item.get("content_part")
        if (
            not isinstance(part, dict)
            or part.get("type") != "text"
            or not isinstance(part.get("text"), str)
        ):
            raise HTTPException(
                status_code=409,
                detail="project context is unavailable",
            )
        parts.append(part)
    return parts


async def _resolve_project_context(
    services: Any,
    session_id: str,
    descriptor: dict[str, str],
) -> dict[str, Any]:
    if descriptor["kind"] != "git":
        return await asyncio.to_thread(
            services.sessions.project_context,
            session_id,
            root=descriptor["root"],
            path=descriptor["path"],
            kind=descriptor["kind"],
        )
    roots = await asyncio.to_thread(services.sessions.roots, session_id)
    selected_root = next(
        (
            root
            for root in roots
            if root.get("path") == descriptor["root"]
            and root.get("available") is not False
        ),
        None,
    )
    if (
        selected_root is None
        or descriptor["path"]
        or services.git is None
    ):
        return {"ok": False, "error": "Git context unavailable"}
    expected_identity = await asyncio.to_thread(
        services.sessions.project_root_identity,
        session_id,
        descriptor["root"],
    )
    if expected_identity is None:
        return {"ok": False, "error": "Git context unavailable"}
    try:
        snapshot = await asyncio.to_thread(
            services.git.context_snapshot,
            session_id,
            root=descriptor["root"],
            expected_identity=expected_identity,
        )
    except GitWorkspaceError:
        return {"ok": False, "error": "Git context unavailable"}
    if not snapshot.get("ok"):
        return {"ok": False, "error": "Git context unavailable"}
    return {
        "ok": True,
        "item": make_project_context_item(
            kind="git",
            root=descriptor["root"],
            path="",
            label=(
                f"{selected_root.get('label') or 'Project'} · Git changes"
            ),
            content=str(snapshot.get("content", "")),
            truncated=bool(snapshot.get("truncated")),
        ),
    }


def _with_context_parts(
    user_input: str | list[dict[str, Any]],
    context_parts: list[dict[str, str]],
) -> list[dict[str, Any]]:
    if isinstance(user_input, str):
        return [*context_parts, {"type": "text", "text": user_input}]
    return [*context_parts, *user_input]


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


async def _read_interaction_response(
    request: Request,
) -> dict[str, Any]:
    try:
        chunks: list[bytes] = []
        size = 0
        async for chunk in request.stream():
            size += len(chunk)
            if size > MAX_INTERACTION_BODY_BYTES:
                raise HTTPException(
                    status_code=400,
                    detail="invalid interaction response",
                )
            chunks.append(chunk)
        body = json.loads(b"".join(chunks))
    except (json.JSONDecodeError, UnicodeDecodeError):
        raise HTTPException(
            status_code=400,
            detail="invalid interaction response",
        ) from None
    if not isinstance(body, dict):
        raise HTTPException(
            status_code=400,
            detail="invalid interaction response",
        )
    return body


def _has_checkpoint_session(git: Any, session_id: str) -> bool:
    checker = getattr(git, "has_checkpoint_session", None)
    if callable(checker):
        return bool(checker(session_id))
    return git.load(session_id) is not None


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


async def _read_session_fork(request: Request) -> int:
    try:
        chunks: list[bytes] = []
        size = 0
        async for chunk in request.stream():
            size += len(chunk)
            if size > MAX_SESSION_FORK_BODY_BYTES:
                raise HTTPException(
                    status_code=400,
                    detail="invalid session fork",
                )
            chunks.append(chunk)
        body = json.loads(b"".join(chunks))
    except (json.JSONDecodeError, UnicodeDecodeError):
        raise HTTPException(
            status_code=400,
            detail="invalid session fork",
        ) from None
    if (
        not isinstance(body, dict)
        or set(body) != {"message_index"}
        or isinstance(body["message_index"], bool)
        or not isinstance(body["message_index"], int)
        or body["message_index"] < 0
    ):
        raise HTTPException(
            status_code=400,
            detail="invalid session fork",
        )
    return body["message_index"]


async def _read_root_update(
    request: Request,
    *,
    remove: bool,
) -> tuple[str, bool]:
    try:
        chunks = []
        size = 0
        async for chunk in request.stream():
            size += len(chunk)
            if size > MAX_ROOT_BODY_BYTES:
                raise HTTPException(
                    status_code=400,
                    detail="invalid root update",
                )
            chunks.append(chunk)
        body = json.loads(b"".join(chunks))
    except (json.JSONDecodeError, UnicodeDecodeError):
        raise HTTPException(
            status_code=400,
            detail="invalid root update",
        ) from None
    expected = {"path"} if remove else {"path", "writable"}
    if (
        not isinstance(body, dict)
        or set(body) != expected
        or not isinstance(body.get("path"), str)
        or not 1 <= len(body["path"]) <= 4096
        or not Path(body["path"]).is_absolute()
        or (
            not remove
            and not isinstance(body.get("writable"), bool)
        )
    ):
        raise HTTPException(
            status_code=400,
            detail="invalid root update",
        )
    return body["path"], bool(body.get("writable", False))


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
