"""Codinal runtime composition root.

Provider and MCP mechanics remain injected through ``EngineBuilder``. This
module owns the harness-controlled policy chokepoint for every constructed
engine.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Awaitable, Callable, Iterable, Optional, Protocol

from .events import EventHub
from .mcp import MCPManager, MCPService
from .oauth import OAuthCoordinator
from .policy import Approver, Mode, PermissionEngine, deny_all
from .secrets import ProviderSecretService
from .sessions import EngineRequest, RootDir, SessionService
from .sessions.service import (
    ArtifactOpener,
    DeleteCallback,
    SessionEngine,
    SessionSnapshotter,
    SessionStore,
)
from .settings import JsonPreferenceStore, SettingsService
from .turns import TurnCoordinator

EventEmitter = Callable[[dict[str, Any]], Awaitable[None]]


@dataclass(frozen=True)
class EngineBuildContext:
    request: EngineRequest
    permissions: PermissionEngine
    approver: Approver
    roots: list[RootDir]
    emit: EventEmitter
    secrets: ProviderSecretService


class EngineBuilder(Protocol):
    def __call__(self, context: EngineBuildContext) -> SessionEngine: ...


@dataclass(frozen=True)
class RuntimeServices:
    sessions: SessionService
    turns: TurnCoordinator
    events: EventHub
    settings: SettingsService
    secrets: ProviderSecretService
    oauth: OAuthCoordinator
    mcp: MCPService | None = None


def compose_runtime(
    *,
    data_dir: str | Path,
    session_store: SessionStore,
    engine_builder: EngineBuilder,
    snapshotter: SessionSnapshotter,
    default_model: str,
    approver: Approver = deny_all,
    curated_models: Iterable[str] = (),
    delete_callbacks: Iterable[DeleteCallback] = (),
    artifact_opener: Optional[ArtifactOpener] = None,
    provider_secrets: ProviderSecretService | None = None,
    oauth: OAuthCoordinator | None = None,
    mcp_manager: MCPManager | None = None,
) -> RuntimeServices:
    """Build runtime services while forcing all engines through policy."""
    base = Path(data_dir).expanduser().resolve()
    base.mkdir(parents=True, exist_ok=True)
    events = EventHub()
    settings = SettingsService(
        JsonPreferenceStore(base / "prefs.json"),
        default_model=default_model,
        curated_models=curated_models,
    )
    secrets = provider_secrets or ProviderSecretService()
    oauth_service = oauth or OAuthCoordinator()

    def build_engine(request: EngineRequest) -> SessionEngine:
        roots = [
            RootDir(
                path=request.workspace,
                writable=True,
                label=request.workspace.name,
            ),
            *[
                RootDir(
                    path=root["path"],
                    writable=bool(root.get("writable", False)),
                    label=str(root.get("label", "")),
                )
                for root in request.extra_roots
            ],
        ]
        permissions = PermissionEngine(
            workspace_root=request.workspace,
            mode=Mode(request.mode),
            roots=roots,
        )
        for tool in request.grants.get("tools") or []:
            permissions.allow_tool_for_session(str(tool))
        for command in request.grants.get("commands") or []:
            permissions.allow_command_for_session(str(command))

        async def emit(message: dict[str, Any]) -> None:
            await events.publish_session(request.session_id, message)

        return engine_builder(
            EngineBuildContext(
                request=request,
                permissions=permissions,
                approver=approver,
                roots=roots,
                emit=emit,
                secrets=secrets,
            )
        )

    sessions = SessionService(
        session_store,
        scratch_base=base / "scratch",
        engine_factory=build_engine,
        snapshotter=snapshotter,
        delete_callbacks=delete_callbacks,
        artifact_opener=artifact_opener,
        default_model=default_model,
        default_model_provider=lambda: str(settings.view()["model"]),
    )
    turns = TurnCoordinator(sessions=sessions, events=events)
    mcp = (
        MCPService(
            manager=mcp_manager,
            sessions=sessions,
            turns=turns,
        )
        if mcp_manager is not None
        else None
    )
    return RuntimeServices(
        sessions=sessions,
        turns=turns,
        events=events,
        settings=settings,
        secrets=secrets,
        oauth=oauth_service,
        mcp=mcp,
    )
