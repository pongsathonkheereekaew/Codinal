"""Authenticated loopback HTTP and WebSocket control plane."""

from __future__ import annotations

import asyncio
import json
import os
import re
import time
import uuid
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
from fastapi.responses import JSONResponse, PlainTextResponse, Response

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
from runtime.policy import PermissionRequest
from runtime.sandbox import InvalidCommandError, SandboxUnavailableError
from runtime.path_scope import scopes_overlap
from runtime.preview import detect_devserver_urls
from runtime.artifacts import check_stirling_health
from runtime.providers.ollama import discover_ollama_models
from runtime.sessions.context import make_project_context_item
from runtime.security import SecurityScanError
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
MAX_ARTIFACT_BODY_BYTES = 1024
MAX_ARTIFACT_PATH_BYTES = 4096
MAX_CHECKPOINT_RESTORE_BODY_BYTES = 1024
MAX_INTERACTION_BODY_BYTES = 128 * 1024
MAX_SESSION_FORK_BODY_BYTES = 1024
MAX_ROOT_BODY_BYTES = 8 * 1024
MAX_WORKER_BODY_BYTES = 64 * 1024
MAX_PLAN_BUILD_BODY_BYTES = 256 * 1024
MAX_TERMINAL_COMMAND_BYTES = 32 * 1024
MAX_TERMINAL_TIMEOUT_SECONDS = 600.0
MCP_SERVER_NAME = r"[A-Za-z0-9][A-Za-z0-9_-]{0,63}"


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

    def list_artifacts(self, session_id: str) -> list[dict[str, Any]]: ...

    def read_artifact(self, session_id: str, path: str) -> dict[str, Any]: ...

    def reveal_artifact(
        self,
        session_id: str,
        path: str,
        *,
        mode: str = "reveal",
    ) -> dict[str, Any]: ...

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

    def workspace_files(
        self, session_id: str, *, limit: int
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

    def get_engine(
        self,
        session_id: str,
        *,
        workspace: str | None = None,
        agent: str = "code",
        mode: str | None = None,
        model: str | None = None,
    ) -> object | None: ...

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

    def list_connected(self, session_id: str) -> list[dict[str, Any]]: ...

    async def disconnect(
        self,
        session_id: str,
        name: str,
    ) -> dict[str, Any]: ...

    async def set_enabled(
        self,
        session_id: str,
        name: str,
        *,
        enabled: bool,
    ) -> dict[str, Any]: ...

    async def recover(self) -> int: ...

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
        commit: str | None = None,
    ) -> dict[str, object]: ...

    def stage(self, session_id: str, path: str = ".") -> dict[str, object]: ...

    def commit(
        self,
        session_id: str,
        message: str,
    ) -> dict[str, object]: ...

    def log(
        self,
        session_id: str,
        *,
        limit: int = 50,
    ) -> dict[str, object]: ...

    def graph(
        self,
        session_id: str,
        *,
        limit: int = 50,
    ) -> dict[str, object]: ...

    def push(
        self,
        session_id: str,
        *,
        remote: str = "origin",
        set_upstream: bool = False,
    ) -> dict[str, object]: ...

    def apply_back(self, session_id: str) -> dict[str, object]: ...

    def apply_selected(
        self,
        session_id: str,
        paths: list[str],
    ) -> dict[str, object]: ...

    def changed_files(self, session_id: str) -> dict[str, object]: ...

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


class GitHubControl(Protocol):
    def create_pr(
        self,
        source_root: Any,
        session_branch: str,
        *,
        title: str,
        body: str = "",
        base: str = "",
        remote: str = "origin",
    ) -> dict[str, object]: ...

    def find_pr(
        self,
        source_root: Any,
        session_branch: str,
        *,
        remote: str = "origin",
    ) -> dict[str, object]: ...

    def list_checks(
        self,
        source_root: Any,
        ref: str,
        *,
        remote: str = "origin",
    ) -> dict[str, object]: ...

    def merge_pr(
        self,
        source_root: Any,
        session_branch: str,
        *,
        method: str = "squash",
        remote: str = "origin",
    ) -> dict[str, object]: ...

    def add_review_comment(
        self,
        source_root: Any,
        session_branch: str,
        *,
        body: str,
        remote: str = "origin",
    ) -> dict[str, object]: ...

    def post_merge_cleanup(
        self,
        source_root: Any,
        session_branch: str,
        *,
        remote: str = "origin",
    ) -> dict[str, object]: ...


class PreviewControl(Protocol):
    def add_evidence(
        self,
        session_id: str,
        kind: str,
        content: Any,
    ) -> dict[str, Any]: ...

    def list_evidence(self, session_id: str) -> list[dict[str, Any]]: ...

    def clear_evidence(self, session_id: str) -> int: ...


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
    github: GitHubControl | None
    preview: PreviewControl | None
    restores: RestoreControl | None
    approvals: ApprovalControl | None
    interactions: InteractionControl | None
    plans: PlanControl | None
    workers: Any | None
    builds: PlanBuildControl | None
    goals: GoalControl | None
    audit: Any | None
    extensions: Any | None
    managed_policy: Any | None


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
            git_service = getattr(services, "git", None)
            if git_service is not None and hasattr(
                git_service, "reconcile_crashed_applies"
            ):
                await asyncio.to_thread(
                    git_service.reconcile_crashed_applies
                )
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
            mcp = getattr(services, "mcp", None)
            if mcp is not None:
                await mcp.recover()
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
                    close_approvals = getattr(approvals, "close", None)
                    if close_approvals is not None:
                        awaitable = close_approvals()
                        if hasattr(awaitable, "__await__"):
                            await awaitable
                interactions = getattr(services, "interactions", None)
                if interactions is not None:
                    close_interactions = getattr(interactions, "close", None)
                    if close_interactions is not None:
                        awaitable = close_interactions()
                        if hasattr(awaitable, "__await__"):
                            await awaitable
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
    app.state.started_at = time.time()

    @app.get("/v1/health")
    async def health() -> dict[str, str]:
        return {"status": "ok"}

    @app.get("/v1/status")
    async def status() -> dict[str, Any]:
        return _component_health(services, started_at=app.state.started_at)

    @app.get("/v1/audit")
    async def audit_log(
        domain: str | None = None,
        limit: int = 100,
    ) -> dict[str, Any]:
        ledger = getattr(services, "audit", None)
        if ledger is None:
            raise HTTPException(
                status_code=503,
                detail="audit ledger unavailable",
            )
        bounded = max(1, min(int(limit), 500))
        events = ledger.list(domain=domain, limit=bounded)
        return {
            "events": events,
            "chain_verified": ledger.verify_chain(),
        }

    @app.get("/v1/audit/export")
    async def audit_export(
        domain: str | None = None,
    ) -> Response:
        ledger = getattr(services, "audit", None)
        if ledger is None:
            raise HTTPException(
                status_code=503,
                detail="audit ledger unavailable",
            )
        events = ledger.list(domain=domain, limit=1_000_000)
        payload = json.dumps(
            {
                "export_version": 1,
                "chain_verified": ledger.verify_chain(),
                "total": len(events),
                "events": events,
            },
            indent=2,
        )
        return Response(
            content=payload,
            media_type="application/json",
            headers={
                "Content-Disposition": "attachment; filename=codinal-audit.json",
            },
        )

    @app.get("/v1/policy")
    async def managed_policy() -> dict[str, Any]:
        policy = getattr(services, "managed_policy", None)
        if policy is None:
            return {"active": False}
        return policy.to_dict()

    @app.get("/v1/extensions")
    async def list_extensions() -> list[dict[str, Any]]:
        ext = getattr(services, "extensions", None)
        if ext is None:
            raise HTTPException(status_code=503, detail="extensions unavailable")
        return [pkg.to_dict() for pkg in ext.list()]

    @app.post("/v1/extensions")
    async def register_extension(request: Request) -> dict[str, Any]:
        ext = getattr(services, "extensions", None)
        if ext is None:
            raise HTTPException(status_code=503, detail="extensions unavailable")
        body = await _read_bounded_object(
            request, limit=12 * 1024, detail="invalid extension manifest"
        )
        if set(body) != {"manifest"}:
            raise HTTPException(status_code=400, detail="invalid extension manifest")
        manifest = body.get("manifest") if isinstance(body, dict) else None
        if not isinstance(manifest, dict):
            raise HTTPException(status_code=400, detail="manifest is required")
        try:
            pkg = await asyncio.to_thread(ext.register, manifest)
        except ValueError as error:
            raise HTTPException(status_code=400, detail=str(error)) from None
        _audit_action(services, "extension", "register", subject=pkg.id)
        return pkg.to_dict()

    @app.patch("/v1/extensions/{package_id}")
    async def toggle_extension(
        package_id: str,
        request: Request,
    ) -> dict[str, Any]:
        ext = getattr(services, "extensions", None)
        if ext is None:
            raise HTTPException(status_code=503, detail="extensions unavailable")
        try:
            body = await request.json()
        except (json.JSONDecodeError, UnicodeDecodeError):
            raise HTTPException(status_code=400, detail="invalid request") from None
        enabled = body.get("enabled") if isinstance(body, dict) else None
        if not isinstance(enabled, bool):
            raise HTTPException(status_code=400, detail="enabled must be a boolean")
        updated = await asyncio.to_thread(ext.set_enabled, package_id, enabled)
        if not updated:
            raise HTTPException(status_code=404, detail="extension not found")
        _audit_action(services, "extension", "enable" if enabled else "disable", subject=package_id)
        return {"ok": True, "id": package_id, "enabled": enabled}

    @app.delete("/v1/extensions/{package_id}")
    async def remove_extension(package_id: str) -> dict[str, Any]:
        ext = getattr(services, "extensions", None)
        if ext is None:
            raise HTTPException(status_code=503, detail="extensions unavailable")
        removed = await asyncio.to_thread(ext.remove, package_id)
        if not removed:
            raise HTTPException(status_code=404, detail="extension not found")
        _audit_action(services, "extension", "remove", subject=package_id)
        return {"ok": True, "id": package_id}

    @app.get("/v1/extensions/{package_id}/verify")
    async def verify_extension(package_id: str) -> dict[str, Any]:
        ext = getattr(services, "extensions", None)
        if ext is None:
            raise HTTPException(status_code=503, detail="extensions unavailable")
        result = await asyncio.to_thread(ext.verify, package_id)
        if result is None:
            raise HTTPException(status_code=404, detail="extension not found")
        return {"id": package_id, "verified": result}

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

    @app.patch("/v1/settings/failover")
    async def update_failover_enabled(
        request: Request,
    ) -> dict[str, Any]:
        body = await _read_bounded_object(
            request,
            limit=128,
            detail="invalid failover payload",
        )
        if set(body) != {"enabled"} or not isinstance(body.get("enabled"), bool):
            raise HTTPException(
                status_code=400,
                detail="invalid failover payload",
            )
        return services.settings.set_failover_enabled(body["enabled"])

    @app.patch("/v1/settings/stirling")
    async def update_stirling_url(request: Request) -> dict[str, Any]:
        body = await _read_bounded_object(
            request,
            limit=1024,
            detail="invalid Stirling URL",
        )
        if set(body) != {"url"} or not isinstance(body.get("url"), str):
            raise HTTPException(status_code=400, detail="invalid Stirling URL")
        result = services.settings.set_stirling_url(body["url"])
        if not result.get("ok"):
            raise HTTPException(
                status_code=400,
                detail=result.get("error", "invalid Stirling URL"),
            )
        return result

    @app.patch("/v1/settings/codex-security")
    async def update_codex_security_bin(request: Request) -> dict[str, Any]:
        body = await _read_bounded_object(request, limit=8192, detail="invalid Codex Security path")
        if set(body) != {"path"} or not isinstance(body.get("path"), str):
            raise HTTPException(status_code=400, detail="invalid Codex Security path")
        result = services.settings.set_codex_security_bin(body["path"])
        if not result.get("ok"):
            raise HTTPException(status_code=400, detail=result.get("error", "invalid Codex Security path"))
        return result

    @app.post("/v1/settings/stirling/health")
    async def check_configured_stirling_health() -> dict[str, Any]:
        stirling_url = services.settings.view().get("stirling_url")
        if not isinstance(stirling_url, str) or not stirling_url:
            raise HTTPException(
                status_code=400,
                detail="Local Stirling endpoint is not configured",
            )
        result = await asyncio.to_thread(check_stirling_health, stirling_url)
        if not result["ok"]:
            raise HTTPException(
                status_code=503,
                detail="Local Stirling endpoint is unavailable",
            )
        return result

    @app.post("/v1/settings/ollama/refresh")
    async def refresh_ollama_models() -> dict[str, Any]:
        """Discover models only from the fixed local Ollama service."""
        result = await asyncio.to_thread(discover_ollama_models)
        models = result["models"]
        if result["available"] and models:
            persisted = services.settings.add_models(models)
            if not persisted.get("ok"):
                raise HTTPException(
                    status_code=400,
                    detail=persisted.get("error", "invalid Ollama models"),
                )
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

    @app.get("/v1/sessions/{session_id}/workspace/files")
    async def workspace_files(
        session_id: str,
        limit: int = 1_000,
    ) -> dict[str, Any]:
        _validate_public_session_id(session_id)
        if not 1 <= limit <= 2_000:
            raise HTTPException(status_code=400, detail="invalid file index limit")
        result = await asyncio.to_thread(
            services.sessions.workspace_files,
            session_id,
            limit=limit,
        )
        if not result.get("ok"):
            raise HTTPException(
                status_code=404,
                detail=result.get("error", "workspace files unavailable"),
            )
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
        _audit_action(services, "session", "delete", subject=session_id)
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
        api_key, base_url = await _read_api_key(request)
        try:
            return services.secrets.set_api_key(provider, api_key, base_url=base_url)
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

    @app.get("/v1/providers/custom")
    async def custom_providers_list() -> list[dict[str, Any]]:
        return services.secrets.custom_providers()

    @app.post("/v1/providers/custom")
    async def custom_provider_create(
        request: Request,
    ) -> dict[str, Any]:
        _authorize_secret_sync(request, services.secrets)
        try:
            body = await request.json()
        except (json.JSONDecodeError, UnicodeDecodeError):
            raise HTTPException(status_code=400, detail="invalid payload") from None
        if not isinstance(body, dict) or set(body) - {"slug", "base_url", "api_key", "failover_eligible"}:
            raise HTTPException(status_code=400, detail="invalid payload")
        slug = body.get("slug")
        base_url = body.get("base_url")
        api_key = body.get("api_key")
        failover_eligible = bool(body.get("failover_eligible", False))
        if not (isinstance(slug, str) and isinstance(base_url, str) and isinstance(api_key, str)):
            raise HTTPException(status_code=400, detail="invalid payload")
        try:
            return services.secrets.set_custom_provider(
                slug,
                base_url=base_url,
                api_key=api_key,
                failover_eligible=failover_eligible,
            )
        except ValueError as error:
            raise HTTPException(status_code=400, detail=str(error)) from None

    @app.delete("/v1/providers/custom/{slug}")
    async def custom_provider_delete(
        slug: str, request: Request,
    ) -> dict[str, Any]:
        _authorize_secret_sync(request, services.secrets)
        try:
            return services.secrets.delete_custom_provider(slug)
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

    @app.post("/v1/sessions/{session_id}/terminal/run")
    async def run_terminal_command(
        session_id: str,
        request: Request,
    ) -> JSONResponse:
        _validate_public_session_id(session_id)
        if services.turns.is_active(session_id):
            raise HTTPException(
                status_code=409,
                detail="session already has an active turn",
            ) from None
        payload = await _read_terminal_command(request)
        command = payload["command"]
        timeout_seconds = payload["timeout_seconds"]
        try:
            engine = services.sessions.get_engine(session_id)
        except Exception as error:
            raise HTTPException(
                status_code=404,
                detail="session not found",
            ) from error
        if engine is None:
            raise HTTPException(
                status_code=404,
                detail="session not found",
            )
        shell = getattr(engine, "_terminal_shell", None)
        permissions = getattr(engine, "permissions", None)
        if shell is None or permissions is None:
            raise HTTPException(
                status_code=409,
                detail="terminal is unavailable for this session",
            )
        decision = permissions.evaluate(
            "run_shell",
            {"command": command},
        )
        if not decision.allowed:
            if not decision.needs_user:
                raise HTTPException(
                    status_code=403,
                    detail=decision.reason or "command blocked",
                )
            approvals = getattr(services, "approvals", None)
            if approvals is None:
                raise HTTPException(
                    status_code=403,
                    detail="session requires command approval",
                )
            approver = approvals.approver(session_id)
            tool_call_id = f"terminal-{uuid.uuid4().hex}"
            permission_request = PermissionRequest(
                tool_name="run_shell",
                arguments={"command": command},
                reason=decision.reason,
                risk="exec",
                command=command,
                tool_call_id=tool_call_id,
            )
            try:
                outcome = await approver(permission_request)
            except ApprovalPersistenceError:
                raise HTTPException(
                    status_code=503,
                    detail="approval decision could not be saved",
                ) from None
            if outcome is ApprovalOutcome.DENY:
                raise HTTPException(
                    status_code=409,
                    detail="command denied by user",
                )
            if outcome is ApprovalOutcome.ALWAYS_COMMAND:
                permissions.allow_command_for_session(command)
        try:
            result = await asyncio.to_thread(
                shell.run,
                command,
                timeout_seconds=timeout_seconds,
            )
        except (InvalidCommandError, ValueError):
            raise HTTPException(
                status_code=400,
                detail="invalid command",
            ) from None
        except SandboxUnavailableError:
            raise HTTPException(
                status_code=503,
                detail="sandbox execution unavailable",
            ) from None
        except (OSError, RuntimeError):
            raise HTTPException(
                status_code=502,
                detail="terminal execution failed",
            ) from None
        result_dict = (
            result.as_dict() if hasattr(result, "as_dict") else result
        )
        if not isinstance(result_dict, dict):
            raise HTTPException(
                status_code=502,
                detail="terminal execution failed",
            )
        # Enrich: scan stdout+stderr for localhost dev-server URLs so the UI
        # can surface clickable "Preview" links.
        combined_output = " ".join(
            str(result_dict.get(key, ""))
            for key in ("stdout", "stderr")
        )
        result_dict["devserver_urls"] = detect_devserver_urls(combined_output)
        _audit_action(services, "terminal", "run", subject=session_id, payload={"command": command[:100]})
        return JSONResponse(result_dict)


    @app.post("/v1/sessions/{session_id}/terminal/interrupt")
    async def interrupt_terminal(session_id: str) -> dict[str, Any]:
        _validate_public_session_id(session_id)
        try:
            engine = services.sessions.get_engine(session_id)
        except Exception as error:
            raise HTTPException(
                status_code=404,
                detail="session not found",
            ) from error
        if engine is None:
            raise HTTPException(
                status_code=404,
                detail="session not found",
            )
        shell = getattr(engine, "_terminal_shell", None)
        if shell is None:
            raise HTTPException(
                status_code=409,
                detail="terminal is unavailable for this session",
            )
        interrupt = getattr(shell, "interrupt", None)
        if not callable(interrupt):
            raise HTTPException(
                status_code=503,
                detail="terminal interrupt unavailable",
            )
        try:
            interrupted = bool(interrupt())
        except Exception as error:
            raise HTTPException(
                status_code=502,
                detail="terminal stop failed",
            ) from error
        _audit_action(services, "terminal", "interrupt", subject=session_id, payload={"ok": interrupted})
        return {
            "ok": interrupted,
            "session_id": session_id,
        }

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
        _audit_action(services, "worker", "create", subject=record.worker_id, payload={"task": body["task"][:100]})
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
        _audit_action(services, "worker", "steer", subject=worker_id)
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
        _audit_action(services, "worker", "cancel", subject=worker_id)
        return {"ok": ok, "worker_id": worker_id}

    @app.post("/v1/workers/{worker_id}/adopt")
    async def adopt_worker(worker_id: str) -> dict[str, object]:
        _validate_public_session_id(worker_id)
        workers = getattr(services, "workers", None)
        if workers is None:
            raise HTTPException(status_code=503, detail="workers are unavailable")
        try:
            result = await workers.adopt(worker_id)
        except KeyError:
            raise HTTPException(status_code=404, detail="worker not found") from None
        except (GitWorkspaceError, ValueError) as error:
            raise HTTPException(status_code=409, detail=str(error)) from None
        _audit_action(services, "worker", "adopt", subject=worker_id)
        return result

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
        _audit_action(services, "approval", "resolve", subject=approval_id, payload={"outcome": str(outcome)})
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

    @app.get("/v1/sessions/{session_id}/artifacts")
    async def list_artifacts(session_id: str) -> list[dict[str, Any]]:
        _validate_public_session_id(session_id)
        return await asyncio.to_thread(
            services.sessions.list_artifacts,
            session_id,
        )

    @app.get("/v1/sessions/{session_id}/artifacts/read")
    async def read_artifact(
        session_id: str,
        path: str,
    ) -> dict[str, Any]:
        _validate_public_session_id(session_id)
        _validate_artifact_path(path)
        result = await asyncio.to_thread(
            services.sessions.read_artifact,
            session_id,
            path,
        )
        if not result.get("ok"):
            error = result.get("error", "artifact unavailable")
            if error == "path escapes workspace":
                raise HTTPException(status_code=400, detail=error)
            if error == "file too large to preview":
                raise HTTPException(status_code=413, detail=error)
            raise HTTPException(
                status_code=404 if error == "not found" else 400,
                detail=error,
            )
        return result

    @app.post("/v1/sessions/{session_id}/inline-edit")
    async def inline_edit(
        session_id: str,
        request: Request,
    ) -> dict[str, Any]:
        """Phase 52: inline edit (Cmd-K). Replaces selected code per instruction.

        Sends the selected text + instruction to the session's model and
        returns the replacement. Best-effort — errors return empty.
        """
        _validate_public_session_id(session_id)
        body = await _read_bounded_object(
            request, limit=65536, detail="invalid inline-edit payload"
        )
        selected_text = str(body.get("selected_text", ""))[:32000]
        instruction = str(body.get("instruction", "")).strip()[:2000]
        language = str(body.get("language", "auto"))
        if not selected_text or not instruction:
            raise HTTPException(status_code=400, detail="selected_text and instruction are required")
        try:
            engine = services.sessions.get_engine(session_id)
        except Exception:
            return {"replacement": ""}
        if engine is None:
            return {"replacement": ""}
        try:
            provider = getattr(engine, "provider", None) or getattr(
                engine, "_provider", None
            )
            if provider is None:
                return {"replacement": ""}
            model = getattr(engine, "model", None) or "openai:gpt-5.6-sol"
            messages = [
                {
                    "role": "system",
                    "content": (
                        f"You are a code editor. The user selected code ({language}) "
                        "and wants you to modify it per their instruction. "
                        "Return ONLY the replacement code, no explanation, no markdown fences."
                    ),
                },
                {
                    "role": "user",
                    "content": f"Instruction: {instruction}\n\nSelected code:\n```\n{selected_text}\n```",
                },
            ]
            turn = await asyncio.to_thread(
                provider.complete, model=model, messages=messages,
            )
            text = (turn.text or "").strip() if hasattr(turn, "text") else ""
            if text.startswith("```"):
                lines = text.split("\n")
                text = "\n".join(lines[1:-1]) if lines[-1].strip() == "```" else "\n".join(lines[1:])
            return {"replacement": text}
        except Exception:
            return {"replacement": ""}

    @app.post("/v1/sessions/{session_id}/complete")
    async def inline_complete(
        session_id: str,
        request: Request,
    ) -> dict[str, Any]:
        """Phase 51: inline code completion (ghost text).

        Sends a minimal FIM (fill-in-the-middle) prompt to the session's
        configured model and returns a short suggestion. Best-effort —
        errors return an empty suggestion (the UI shows no ghost text).
        """
        _validate_public_session_id(session_id)
        body = await _read_bounded_object(
            request, limit=8192, detail="invalid completion payload"
        )
        prefix = str(body.get("prefix", ""))[-2000:]
        suffix = str(body.get("suffix", ""))[:500]
        if not prefix:
            return {"suggestion": ""}
        try:
            engine = services.sessions.get_engine(session_id)
        except Exception:
            return {"suggestion": ""}
        if engine is None:
            return {"suggestion": ""}
        try:
            # Build a FIM-style prompt. Model-agnostic: most OpenAI-compat
            # models handle this instruction well enough for short completions.
            messages = [
                {
                    "role": "system",
                    "content": (
                        "Complete the code at the cursor position. "
                        "Return ONLY the code to insert, no explanation. "
                        "Keep it short (1-3 lines)."
                    ),
                },
                {
                    "role": "user",
                    "content": f"Code before cursor:\n```\n{prefix}\n```\n\n"
                    f"Code after cursor:\n```\n{suffix}\n```\n\n"
                    "What should be inserted at the cursor?",
                },
            ]
            provider = getattr(engine, "provider", None) or getattr(
                engine, "_provider", None
            )
            if provider is None:
                return {"suggestion": ""}
            model = getattr(engine, "model", None) or "openai:gpt-5.6-sol"
            turn = await asyncio.to_thread(
                provider.complete,
                model=model,
                messages=messages,
            )
            text = (turn.text or "").strip() if hasattr(turn, "text") else ""
            # Strip markdown fences if the model wrapped the completion.
            if text.startswith("```"):
                lines = text.split("\n")
                text = "\n".join(lines[1:-1]) if lines[-1].strip() == "```" else "\n".join(lines[1:])
            return {"suggestion": text[:500]}
        except Exception:
            return {"suggestion": ""}

    @app.post("/v1/sessions/{session_id}/artifacts/write")
    async def write_artifact(
        session_id: str,
        request: Request,
    ) -> dict[str, Any]:
        """Write text content to a file within the session workspace.

        User-initiated save from the code editor (Phase 49). Workspace-scoped
        — no policy gate (same trust boundary as read_artifact). The path must
        resolve within the workspace root; parent dirs are created as needed.
        """
        _validate_public_session_id(session_id)
        body = await _read_bounded_object(
            request,
            limit=2 * 1024 * 1024,  # 2MB max content
            detail="invalid write payload",
        )
        if (
            set(body) != {"path", "content"}
            or not isinstance(body.get("path"), str)
            or not isinstance(body.get("content"), str)
        ):
            raise HTTPException(status_code=400, detail="invalid write payload")
        path = body["path"]
        content = body["content"]
        _validate_artifact_path(path)
        result = await asyncio.to_thread(
            services.sessions.write_artifact,
            session_id,
            path,
            content,
        )
        if not result.get("ok"):
            error = result.get("error", "write failed")
            if error == "path escapes workspace":
                raise HTTPException(status_code=400, detail=error)
            raise HTTPException(status_code=400, detail=error)
        _audit_action(
            services, "editor", "write", subject=session_id, payload={"path": path[:100]}
        )
        return result

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

    @app.post("/v1/sessions/{session_id}/artifacts/reveal")
    async def reveal_artifact(
        session_id: str,
        request: Request,
    ) -> dict[str, Any]:
        _validate_public_session_id(session_id)
        body = await _read_artifact_action(request)
        result = await asyncio.to_thread(
            services.sessions.reveal_artifact,
            session_id,
            body["path"],
            mode=body["mode"],
        )
        if not result.get("ok"):
            error = result.get("error", "artifact unavailable")
            if error == "artifact opener is not configured":
                raise HTTPException(
                    status_code=503,
                    detail=error,
                )
            if error == "path escapes workspace":
                raise HTTPException(status_code=400, detail=error)
            raise HTTPException(
                status_code=404 if error == "not found" else 400,
                detail=error,
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

    @app.get("/v1/sessions/{session_id}/mcp/servers")
    async def list_mcp_servers(session_id: str) -> list[dict[str, Any]]:
        _validate_public_session_id(session_id)
        if services.mcp is None:
            raise HTTPException(status_code=503, detail="MCP unavailable")
        try:
            return services.mcp.list_connected(session_id)
        except SessionNotFoundError:
            raise HTTPException(
                status_code=404,
                detail="session not found",
            ) from None

    @app.delete("/v1/sessions/{session_id}/mcp/servers/{server_name}")
    async def disconnect_mcp(
        session_id: str,
        server_name: str,
    ) -> dict[str, Any]:
        _validate_public_session_id(session_id)
        if not re.fullmatch(MCP_SERVER_NAME, server_name):
            raise HTTPException(
                status_code=400,
                detail="invalid MCP server name",
            )
        if services.mcp is None:
            raise HTTPException(status_code=503, detail="MCP unavailable")
        try:
            return await services.mcp.disconnect(session_id, server_name)
        except SessionNotFoundError:
            raise HTTPException(
                status_code=404,
                detail="session not found",
            ) from None
        except SessionBusyError:
            raise HTTPException(
                status_code=409,
                detail="session already has an active turn",
            ) from None
        except ValueError:
            raise HTTPException(
                status_code=404,
                detail="MCP server not connected",
            ) from None

    @app.patch("/v1/sessions/{session_id}/mcp/servers/{server_name}")
    async def set_mcp_server_enabled(
        session_id: str,
        server_name: str,
        request: Request,
    ) -> dict[str, Any]:
        _validate_public_session_id(session_id)
        if not re.fullmatch(MCP_SERVER_NAME, server_name):
            raise HTTPException(
                status_code=400,
                detail="invalid MCP server name",
            )
        if services.mcp is None:
            raise HTTPException(status_code=503, detail="MCP unavailable")
        body = await _read_mcp_enable(request)
        try:
            return await services.mcp.set_enabled(
                session_id,
                server_name,
                enabled=body["enabled"],
            )
        except SessionNotFoundError:
            raise HTTPException(
                status_code=404,
                detail="session not found",
            ) from None
        except SessionBusyError:
            raise HTTPException(
                status_code=409,
                detail="session already has an active turn",
            ) from None
        except ValueError:
            raise HTTPException(
                status_code=404,
                detail="MCP server not connected",
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

    @app.get("/v1/security/status")
    async def security_status() -> dict[str, object]:
        security = getattr(services, "security", None)
        if security is None:
            return {"available": False, "reason": "Security scanning is unavailable."}
        return await asyncio.to_thread(security.status)

    @app.post("/v1/sessions/{session_id}/security/scan")
    async def security_scan(session_id: str) -> dict[str, object]:
        """Run an explicitly requested, bounded working-tree security scan."""
        _validate_public_session_id(session_id)
        security = getattr(services, "security", None)
        if security is None:
            raise HTTPException(status_code=503, detail="security scanning unavailable")
        if services.git is None or services.git.load(session_id) is None:
            raise HTTPException(status_code=404, detail="Git session not found")
        record = services.git.load(session_id)
        try:
            result = await services.turns.mutate_when_idle(
                session_id,
                lambda: security.scan(session_id, record.source_root),
            )
        except SessionBusyError as error:
            raise HTTPException(status_code=409, detail=str(error)) from None
        except SecurityScanError as error:
            raise HTTPException(status_code=409, detail=str(error)) from None
        _audit_action(
            services,
            "security",
            "scan",
            subject=session_id,
            payload={
                "ok": bool(result.get("ok")),
                "finding_count": int(result.get("finding_count", 0)),
                "coverage": result.get("coverage", {}).get("status", "unknown"),
                "max_cost_usd": result.get("max_cost_usd", 0),
            },
        )
        return result

    @app.get("/v1/sessions/{session_id}/git/diff")
    async def git_diff(
        session_id: str,
        staged: bool = False,
        against_base: bool = False,
        path: str | None = None,
        commit: str | None = None,
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
                commit=commit,
            )
        except GitWorkspaceError:
            raise HTTPException(
                status_code=409,
                detail="Git diff unavailable",
            ) from None

    @app.post("/v1/sessions/{session_id}/git/stage")
    async def git_stage(session_id: str, request: Request) -> dict[str, object]:
        _validate_public_session_id(session_id)
        if services.git is None or services.git.load(session_id) is None:
            raise HTTPException(status_code=404, detail="Git session not found")
        path = await _read_git_stage(request)
        try:
            return await asyncio.to_thread(
                services.git.stage,
                session_id,
                path,
            )
        except GitWorkspaceError:
            raise HTTPException(
                status_code=409,
                detail="Git stage unavailable",
            ) from None

    @app.post("/v1/sessions/{session_id}/git/commit")
    async def git_commit(session_id: str, request: Request) -> dict[str, object]:
        _validate_public_session_id(session_id)
        if services.git is None or services.git.load(session_id) is None:
            raise HTTPException(status_code=404, detail="Git session not found")
        message = await _read_git_commit(request)
        try:
            return await asyncio.to_thread(
                services.git.commit,
                session_id,
                message,
            )
        except GitWorkspaceError:
            raise HTTPException(
                status_code=409,
                detail="Git commit unavailable",
            ) from None

    @app.get("/v1/sessions/{session_id}/git/log")
    async def git_log(
        session_id: str,
        limit: int = 50,
    ) -> dict[str, object]:
        _validate_public_session_id(session_id)
        if services.git is None or services.git.load(session_id) is None:
            raise HTTPException(status_code=404, detail="Git session not found")
        try:
            return await asyncio.to_thread(
                services.git.log,
                session_id,
                limit=limit,
            )
        except GitWorkspaceError:
            raise HTTPException(
                status_code=409,
                detail="Git log unavailable",
            ) from None

    @app.get("/v1/sessions/{session_id}/git/graph")
    async def git_graph(
        session_id: str,
        limit: int = 50,
    ) -> dict[str, object]:
        _validate_public_session_id(session_id)
        if services.git is None or services.git.load(session_id) is None:
            raise HTTPException(status_code=404, detail="Git session not found")
        try:
            return await asyncio.to_thread(
                services.git.graph,
                session_id,
                limit=limit,
            )
        except GitWorkspaceError:
            raise HTTPException(
                status_code=409,
                detail="Git graph unavailable",
            ) from None

    @app.post("/v1/sessions/{session_id}/git/push")
    async def git_push(session_id: str, request: Request) -> dict[str, object]:
        _validate_public_session_id(session_id)
        if services.git is None or services.git.load(session_id) is None:
            raise HTTPException(status_code=404, detail="Git session not found")
        body = await _read_git_push(request)
        try:
            result = await services.turns.mutate_when_idle(
                session_id,
                lambda: services.git.push(
                    session_id,
                    remote=body["remote"],
                    set_upstream=body["set_upstream"],
                ),
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
        audit = getattr(services, "audit", None)
        if audit is not None:
            audit.record(
                "git",
                "push",
                actor="host",
                subject=str(result.get("branch", "")),
                payload={
                    "remote": body["remote"],
                    "set_upstream": body["set_upstream"],
                    "ok": bool(result.get("ok")),
                },
            )
        return result

    @app.post("/v1/sessions/{session_id}/git/apply")
    async def git_apply(
        session_id: str,
        request: Request,
    ) -> JSONResponse:
        _validate_public_session_id(session_id)
        if services.git is None or services.git.load(session_id) is None:
            raise HTTPException(status_code=404, detail="Git session not found")
        selection = await _read_apply_selection(request)

        def _apply() -> dict[str, object]:
            if selection is None:
                return services.git.apply_back(session_id)
            if selection["kind"] == "hunks":
                return services.git.apply_selected_hunks(
                    session_id, selection["hunks"]
                )
            return services.git.apply_selected(session_id, selection["paths"])

        try:
            result = await services.turns.mutate_when_idle(session_id, _apply)
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

    @app.get("/v1/sessions/{session_id}/git/files")
    async def git_changed_files(session_id: str) -> dict[str, object]:
        _validate_public_session_id(session_id)
        if services.git is None or services.git.load(session_id) is None:
            raise HTTPException(status_code=404, detail="Git session not found")
        try:
            return await asyncio.to_thread(
                services.git.changed_files,
                session_id,
            )
        except GitWorkspaceError:
            raise HTTPException(
                status_code=409,
                detail="Git files unavailable",
            ) from None

    @app.post("/v1/sessions/{session_id}/github/pr")
    async def github_create_pr(
        session_id: str,
        request: Request,
    ) -> dict[str, Any]:
        _validate_public_session_id(session_id)
        if services.git is None or services.git.load(session_id) is None:
            raise HTTPException(status_code=404, detail="Git session not found")
        github = getattr(services, "github", None)
        if github is None:
            raise HTTPException(status_code=503, detail="GitHub unavailable")
        body = await _read_github_pr_request(request)
        record = services.git.load(session_id)

        def _create() -> dict[str, object]:
            return github.create_pr(
                record.source_root,
                record.session_branch,
                title=body["title"],
                body=body.get("body", ""),
                base=body.get("base", ""),
            )

        try:
            result = await services.turns.mutate_when_idle(session_id, _create)
        except SessionBusyError as error:
            raise HTTPException(status_code=409, detail=str(error)) from None
        return result

    @app.get("/v1/sessions/{session_id}/github/pr")
    async def github_get_pr(session_id: str) -> dict[str, Any]:
        _validate_public_session_id(session_id)
        if services.git is None or services.git.load(session_id) is None:
            raise HTTPException(status_code=404, detail="Git session not found")
        github = getattr(services, "github", None)
        if github is None:
            raise HTTPException(status_code=503, detail="GitHub unavailable")
        record = services.git.load(session_id)
        try:
            return await asyncio.to_thread(
                github.find_pr,
                record.source_root,
                record.session_branch,
            )
        except Exception as error:
            raise HTTPException(
                status_code=502,
                detail=str(error),
            ) from None

    @app.get("/v1/sessions/{session_id}/github/checks")
    async def github_checks(session_id: str) -> dict[str, Any]:
        _validate_public_session_id(session_id)
        if services.git is None or services.git.load(session_id) is None:
            raise HTTPException(status_code=404, detail="Git session not found")
        github = getattr(services, "github", None)
        if github is None:
            raise HTTPException(status_code=503, detail="GitHub unavailable")
        record = services.git.load(session_id)
        head = services.git.status(session_id).get("head_commit", "")
        try:
            return await asyncio.to_thread(
                github.list_checks,
                record.source_root,
                head,
            )
        except Exception as error:
            raise HTTPException(
                status_code=502,
                detail=str(error),
            ) from None

    @app.post("/v1/sessions/{session_id}/github/merge")
    async def github_merge_pr(
        session_id: str,
        request: Request,
    ) -> dict[str, Any]:
        _validate_public_session_id(session_id)
        if services.git is None or services.git.load(session_id) is None:
            raise HTTPException(status_code=404, detail="Git session not found")
        github = getattr(services, "github", None)
        if github is None:
            raise HTTPException(status_code=503, detail="GitHub unavailable")
        record = services.git.load(session_id)
        try:
            body = await request.json()
        except (json.JSONDecodeError, UnicodeDecodeError):
            body = {}
        method = body.get("method", "squash") if isinstance(body, dict) else "squash"
        if method not in ("squash", "merge", "rebase"):
            raise HTTPException(status_code=400, detail="method must be squash, merge, or rebase")

        def _merge() -> dict[str, object]:
            return github.merge_pr(
                record.source_root,
                record.session_branch,
                method=method,
            )

        try:
            result = await services.turns.mutate_when_idle(session_id, _merge)
        except SessionBusyError as error:
            raise HTTPException(status_code=409, detail=str(error)) from None
        _audit_action(services, "github", "merge", subject=record.session_branch)
        return result

    @app.post("/v1/sessions/{session_id}/github/comment")
    async def github_add_comment(
        session_id: str,
        request: Request,
    ) -> dict[str, Any]:
        _validate_public_session_id(session_id)
        if services.git is None or services.git.load(session_id) is None:
            raise HTTPException(status_code=404, detail="Git session not found")
        github = getattr(services, "github", None)
        if github is None:
            raise HTTPException(status_code=503, detail="GitHub unavailable")
        record = services.git.load(session_id)
        try:
            body = await request.json()
        except (json.JSONDecodeError, UnicodeDecodeError):
            raise HTTPException(status_code=400, detail="invalid request") from None
        comment_body = body.get("body") if isinstance(body, dict) else None
        if not isinstance(comment_body, str) or not comment_body.strip():
            raise HTTPException(status_code=400, detail="body is required")
        try:
            return await asyncio.to_thread(
                github.add_review_comment,
                record.source_root,
                record.session_branch,
                body=comment_body[:65_536],
            )
        except Exception as error:
            raise HTTPException(status_code=502, detail=str(error)) from None

    @app.post("/v1/sessions/{session_id}/github/cleanup")
    async def github_post_merge_cleanup(session_id: str) -> dict[str, Any]:
        _validate_public_session_id(session_id)
        if services.git is None or services.git.load(session_id) is None:
            raise HTTPException(status_code=404, detail="Git session not found")
        github = getattr(services, "github", None)
        if github is None:
            raise HTTPException(status_code=503, detail="GitHub unavailable")
        record = services.git.load(session_id)

        def _cleanup() -> dict[str, object]:
            return github.post_merge_cleanup(
                record.source_root,
                record.session_branch,
            )

        try:
            result = await services.turns.mutate_when_idle(session_id, _cleanup)
        except SessionBusyError as error:
            raise HTTPException(status_code=409, detail=str(error)) from None
        _audit_action(services, "github", "cleanup", subject=record.session_branch)
        return result

    @app.post("/v1/sessions/{session_id}/preview/evidence")
    async def add_preview_evidence(
        session_id: str,
        request: Request,
    ) -> dict[str, Any]:
        _validate_public_session_id(session_id)
        preview = getattr(services, "preview", None)
        if preview is None:
            raise HTTPException(status_code=503, detail="preview unavailable")
        body = await _read_preview_evidence(request)
        try:
            return await asyncio.to_thread(
                preview.add_evidence,
                session_id,
                body["kind"],
                body["content"],
            )
        except ValueError as error:
            raise HTTPException(
                status_code=400,
                detail=str(error),
            ) from None

    @app.get("/v1/sessions/{session_id}/preview/evidence")
    async def list_preview_evidence(session_id: str) -> list[dict[str, Any]]:
        _validate_public_session_id(session_id)
        preview = getattr(services, "preview", None)
        if preview is None:
            raise HTTPException(status_code=503, detail="preview unavailable")
        return await asyncio.to_thread(preview.list_evidence, session_id)

    @app.delete("/v1/sessions/{session_id}/preview/evidence")
    async def clear_preview_evidence(session_id: str) -> dict[str, Any]:
        _validate_public_session_id(session_id)
        preview = getattr(services, "preview", None)
        if preview is None:
            raise HTTPException(status_code=503, detail="preview unavailable")
        cleared = await asyncio.to_thread(preview.clear_evidence, session_id)
        return {"ok": True, "cleared": cleared}

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


def _runtime_version() -> str:
    return os.environ.get("CODINAL_VERSION", "dev")


def _audit_action(
    services: Any,
    domain: str,
    action: str,
    *,
    subject: str = "",
    payload: dict[str, Any] | None = None,
) -> None:
    """Record an audit event at the route layer (best-effort, no-op if no ledger)."""
    ledger = getattr(services, "audit", None)
    if ledger is None:
        return
    try:
        ledger.record(domain, action, actor="host", subject=subject, payload=payload or {})
    except Exception:
        pass


def _component_health(services: Any, *, started_at: float) -> dict[str, Any]:
    """Structured, secret-safe runtime health for /v1/status and support bundles.

    Never includes provider keys, message bodies, or file contents. Provider
    state is the configured flag only; audit chain is verified/tampered.
    """
    secrets = getattr(services, "secrets", None)
    providers_configured: list[dict[str, Any]] = []
    if secrets is not None and hasattr(secrets, "status"):
        try:
            providers_configured = [
                {"provider": entry["provider"], "configured": bool(entry.get("configured"))}
                for entry in secrets.status()
            ]
        except Exception:
            providers_configured = []

    audit = getattr(services, "audit", None)
    audit_chain = "unavailable"
    if audit is not None and hasattr(audit, "verify_chain"):
        try:
            audit_chain = "verified" if audit.verify_chain() else "tampered"
        except Exception:
            audit_chain = "degraded"

    sessions = getattr(services, "sessions", None)
    session_count = 0
    if sessions is not None and hasattr(sessions, "list_sessions"):
        try:
            session_count = len(sessions.list_sessions())
        except Exception:
            session_count = 0

    return {
        "version": _runtime_version(),
        "uptime_seconds": max(0.0, time.time() - started_at),
        "components": {
            "audit_chain": audit_chain,
            "providers": providers_configured,
            "session_count": session_count,
        },
    }


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


async def _read_terminal_command(request: Request) -> dict[str, Any]:
    body = await _read_bounded_object(
        request,
        limit=MAX_TERMINAL_COMMAND_BYTES,
        detail="invalid terminal payload",
    )
    timeout_seconds = body.get("timeout_seconds", None)
    command = body.get("command")
    if isinstance(command, str):
        command = command.strip()
    if (
        set(body) not in ({"command"}, {"command", "timeout_seconds"})
        or not _valid_utf8_text(
            command,
            minimum=1,
            maximum=MAX_TERMINAL_COMMAND_BYTES,
        )
        or (
            timeout_seconds is not None
            and (
                not isinstance(timeout_seconds, (int, float))
                or isinstance(timeout_seconds, bool)
                or not (
                    0 < timeout_seconds <= MAX_TERMINAL_TIMEOUT_SECONDS
                )
            )
        )
        or not command
    ):
        raise HTTPException(
            status_code=400,
            detail="invalid terminal payload",
        )
    return {
        "command": command,
        "timeout_seconds": float(timeout_seconds)
        if timeout_seconds is not None
        else None,
    }


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


def _validate_artifact_path(path: Any) -> str:
    if (
        not isinstance(path, str)
        or not _valid_utf8_text(path, minimum=1, maximum=MAX_ARTIFACT_PATH_BYTES)
        or "\x00" in path
        or "\\" in path
        or Path(path).is_absolute()
        or ".." in Path(path).parts
    ):
        raise HTTPException(status_code=400, detail="invalid artifact path")
    return path


async def _read_artifact_action(request: Request) -> dict[str, Any]:
    body = await _read_bounded_object(
        request,
        limit=MAX_ARTIFACT_BODY_BYTES,
        detail="invalid artifact payload",
    )
    path = body.get("path")
    mode = body.get("mode", "reveal")
    if (
        set(body) not in ({"path"}, {"path", "mode"})
        or path is None
        or mode not in {"open", "reveal"}
    ):
        raise HTTPException(status_code=400, detail="invalid artifact payload")
    return {"path": _validate_artifact_path(path), "mode": mode}


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


async def _read_mcp_enable(request: Request) -> dict[str, Any]:
    try:
        body = await request.json()
    except (json.JSONDecodeError, UnicodeDecodeError):
        raise HTTPException(
            status_code=400,
            detail="invalid MCP enable update",
        ) from None
    if (
        not isinstance(body, dict)
        or set(body) != {"enabled"}
        or not isinstance(body.get("enabled"), bool)
    ):
        raise HTTPException(
            status_code=400,
            detail="invalid MCP enable update",
        )
    return body


async def _read_git_stage(request: Request) -> str:
    try:
        body = await request.json()
    except (json.JSONDecodeError, UnicodeDecodeError):
        raise HTTPException(
            status_code=400,
            detail="invalid Git stage update",
        ) from None
    if (
        not isinstance(body, dict)
        or set(body) != {"path"}
        or not isinstance(body.get("path"), str)
        or not 1 <= len(body["path"]) <= 4096
    ):
        raise HTTPException(
            status_code=400,
            detail="invalid Git stage update",
        )
    return body["path"]


async def _read_git_commit(request: Request) -> str:
    try:
        body = await request.json()
    except (json.JSONDecodeError, UnicodeDecodeError):
        raise HTTPException(
            status_code=400,
            detail="invalid Git commit message",
        ) from None
    if (
        not isinstance(body, dict)
        or set(body) != {"message"}
        or not isinstance(body.get("message"), str)
        or not body["message"].strip()
        or len(body["message"].encode("utf-8")) > 10_000
    ):
        raise HTTPException(
            status_code=400,
            detail="invalid Git commit message",
        )
    return body["message"]


async def _read_apply_selection(request: Request) -> dict[str, Any] | None:
    """Read the optional selective-apply body.

    Accepts either:
      - ``{"paths": [...]}`` — file-level selection (Phase 33).
      - ``{"hunks": [{"path": ..., "hunk_index": ...}, ...]}`` — hunk-level
        selection (Phase 43).

    Returns ``{"kind": "paths", "paths": [...]}``,
    ``{"kind": "hunks", "hunks": [...]}``, or ``None`` when the body is
    absent/empty (meaning "apply all" — the legacy whole-branch behavior).
    """
    try:
        body = await request.json()
    except (json.JSONDecodeError, UnicodeDecodeError):
        # No body or invalid JSON → apply all (backward-compatible).
        return None
    if body is None or body == {}:
        return None
    if not isinstance(body, dict) or len(body) != 1:
        raise HTTPException(
            status_code=400,
            detail="invalid apply selection",
        )
    if "paths" in body:
        paths = body["paths"]
        if (
            not isinstance(paths, list)
            or not all(
                isinstance(p, str) and 1 <= len(p) <= 4096 and "\x00" not in p
                for p in paths
            )
            or not 1 <= len(paths) <= 1000
        ):
            raise HTTPException(
                status_code=400,
                detail="invalid apply selection",
            )
        return {"kind": "paths", "paths": list(paths)}
    if "hunks" in body:
        hunks = body["hunks"]
        if (
            not isinstance(hunks, list)
            or not 1 <= len(hunks) <= 1000
            or not all(
                isinstance(h, dict)
                and set(h) == {"path", "hunk_index"}
                and isinstance(h.get("path"), str)
                and 1 <= len(h["path"]) <= 4096
                and "\x00" not in h["path"]
                and isinstance(h.get("hunk_index"), int)
                and not isinstance(h.get("hunk_index"), bool)
                and 0 <= h["hunk_index"] < 10000
                for h in hunks
            )
        ):
            raise HTTPException(
                status_code=400,
                detail="invalid apply selection",
            )
        return {"kind": "hunks", "hunks": list(hunks)}
    raise HTTPException(
        status_code=400,
        detail="invalid apply selection",
    )


async def _read_preview_evidence(request: Request) -> dict[str, Any]:
    try:
        body = await request.json()
    except (json.JSONDecodeError, UnicodeDecodeError):
        raise HTTPException(
            status_code=400,
            detail="invalid preview evidence",
        ) from None
    kind = body.get("kind") if isinstance(body, dict) else None
    content = body.get("content") if isinstance(body, dict) else None
    if (
        not isinstance(body, dict)
        or kind not in ("console", "annotation")
        or not isinstance(content, (str, dict, list))
        or set(body) != {"kind", "content"}
    ):
        raise HTTPException(
            status_code=400,
            detail="invalid preview evidence",
        )
    return {"kind": kind, "content": content}


async def _read_github_pr_request(request: Request) -> dict[str, Any]:
    try:
        body = await request.json()
    except (json.JSONDecodeError, UnicodeDecodeError):
        raise HTTPException(
            status_code=400,
            detail="invalid GitHub PR request",
        ) from None
    title = body.get("title") if isinstance(body, dict) else None
    if (
        not isinstance(body, dict)
        or not isinstance(title, str)
        or not 1 <= len(title) <= 256
        or not set(body) <= {"title", "body", "base"}
        or (body.get("body") is not None and not isinstance(body.get("body"), str))
        or (body.get("base") is not None and not isinstance(body.get("base"), str))
    ):
        raise HTTPException(
            status_code=400,
            detail="invalid GitHub PR request",
        )
    result: dict[str, Any] = {"title": title}
    if "body" in body and body["body"] is not None:
        result["body"] = body["body"][:65_536]
    if "base" in body and body["base"] is not None:
        result["base"] = body["base"][:128]
    return result


async def _read_git_push(request: Request) -> dict[str, Any]:
    try:
        body = await request.json()
    except (json.JSONDecodeError, UnicodeDecodeError):
        raise HTTPException(
            status_code=400,
            detail="invalid Git push request",
        ) from None
    remote = body.get("remote") if isinstance(body, dict) else None
    set_upstream = body.get("set_upstream") if isinstance(body, dict) else None
    if (
        not isinstance(body, dict)
        or not isinstance(remote, str)
        or not 1 <= len(remote) <= 64
        or not re.fullmatch(r"[A-Za-z0-9._-]+", remote)
        or not isinstance(set_upstream, bool)
        or set(body) - {"remote", "set_upstream"}
    ):
        raise HTTPException(
            status_code=400,
            detail="invalid Git push request",
        )
    return {"remote": remote, "set_upstream": set_upstream}


async def _read_api_key(request: Request) -> tuple[str, str | None]:
    try:
        body = await request.json()
    except (json.JSONDecodeError, UnicodeDecodeError):
        raise HTTPException(status_code=400, detail="invalid secret payload") from None
    if (
        not isinstance(body, dict)
        or not isinstance(body.get("api_key"), str)
        or not 1 <= len(body["api_key"]) <= 16_384
    ):
        raise HTTPException(status_code=400, detail="invalid secret payload")
    base_url = body.get("base_url")
    allowed_keys = {"api_key"}
    if base_url is not None:
        if not isinstance(base_url, str) or len(base_url) > 512:
            raise HTTPException(status_code=400, detail="invalid secret payload")
        allowed_keys = {"api_key", "base_url"}
    if set(body) != allowed_keys:
        raise HTTPException(status_code=400, detail="invalid secret payload")
    return body["api_key"], base_url if isinstance(base_url, str) and base_url else None


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
