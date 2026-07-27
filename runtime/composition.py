"""Codinal runtime composition root.

Provider and MCP mechanics remain injected through ``EngineBuilder``. This
module owns the harness-controlled policy chokepoint for every constructed
engine.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Awaitable, Callable, Iterable, Optional, Protocol

from .audit import AuditLedger
from .checkpoint_restore import CheckpointRestoreCoordinator
from .events import EventHub
from .goals import GoalCoordinator, GoalStore
from .mcp import MCPManager, MCPService, MCPStore
from .oauth import OAuthCoordinator
from .policy import ApprovalBroker, Approver, Mode, PermissionEngine, deny_all
from .routing import ModelRoutingService
from .secrets import ProviderSecretService, SecretRedactor
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
from .workers import WorkerCoordinator, WorkerStore
from .builds import PlanBuildCoordinator, PlanBuildStore

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


class WorkspacePreparer(Protocol):
    def __call__(self, request: EngineRequest) -> str | Path: ...


@dataclass(frozen=True)
class RuntimeServices:
    sessions: SessionService
    turns: TurnCoordinator
    events: EventHub
    settings: SettingsService
    routing: ModelRoutingService
    secrets: ProviderSecretService
    oauth: OAuthCoordinator
    mcp: MCPService | None = None
    git: Any | None = None
    restores: CheckpointRestoreCoordinator | None = None
    approvals: ApprovalBroker | None = None
    interactions: Any | None = None
    plans: Any | None = None
    workers: WorkerCoordinator | None = None
    builds: PlanBuildCoordinator | None = None
    goals: GoalCoordinator | None = None
    audit: AuditLedger | None = None
    github: Any = None
    preview: Any = None
    managed_policy: Any = None
    extensions: Any = None


def compose_runtime(
    *,
    data_dir: str | Path,
    session_store: SessionStore,
    engine_builder: EngineBuilder,
    snapshotter: SessionSnapshotter,
    default_model: str,
    approver: Approver = deny_all,
    approver_factory: Callable[[str], Approver] | None = None,
    curated_models: Iterable[str] = (),
    delete_callbacks: Iterable[DeleteCallback] = (),
    artifact_opener: Optional[ArtifactOpener] = None,
    provider_secrets: ProviderSecretService | None = None,
    oauth: OAuthCoordinator | None = None,
    mcp_manager: MCPManager | None = None,
    workspace_preparer: WorkspacePreparer | None = None,
    git_service: Any | None = None,
    approval_broker: ApprovalBroker | None = None,
    interaction_broker: Any | None = None,
    plan_store: Any | None = None,
    worker_store: WorkerStore | None = None,
    plan_build_store: PlanBuildStore | None = None,
    goal_store: GoalStore | None = None,
    mcp_store: MCPStore | None = None,
    audit: AuditLedger | None = None,
    github: Any = None,
    preview: Any = None,
    managed_policy: Any = None,
    extensions: Any = None,
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
    redactor = SecretRedactor(secrets)
    routing = ModelRoutingService(
        lambda: list(settings.view()["models"]),
        secrets,
    )
    oauth_service = oauth or OAuthCoordinator()

    def build_engine(request: EngineRequest) -> SessionEngine:
        primary_workspace = (
            Path(workspace_preparer(request)).expanduser().resolve()
            if workspace_preparer is not None
            else request.workspace
        )
        if not primary_workspace.is_dir():
            raise RuntimeError("prepared workspace is unavailable")
        roots = [
            RootDir(
                path=primary_workspace,
                writable=True,
                label=primary_workspace.name,
            ),
            *[
                RootDir(
                    path=root["path"],
                    writable=bool(root.get("writable", False)),
                    label=str(root.get("label", "")),
                    device=root.get("_device"),
                    inode=root.get("_inode"),
                )
                for root in request.extra_roots
            ],
        ]
        worker = (
            worker_store.load_by_child_session(request.session_id)
            if worker_store is not None
            else None
        )
        permissions = PermissionEngine(
            workspace_root=primary_workspace,
            mode=Mode(request.mode),
            roots=roots,
            write_scope=worker.ownership if worker is not None else (),
            managed_policy=managed_policy,
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
                approver=(
                    approver_factory(request.session_id)
                    if approver_factory is not None
                    else approver
                ),
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
    turns = TurnCoordinator(
        sessions=sessions,
        events=events,
        code_checkpoints=git_service,
    )
    restores = (
        CheckpointRestoreCoordinator(
            git=git_service,
            sessions=sessions,
        )
        if git_service is not None
        else None
    )
    mcp = (
        MCPService(
            manager=mcp_manager,
            sessions=sessions,
            turns=turns,
            store=mcp_store,
            audit=audit,
            redactor=redactor,
        )
        if mcp_manager is not None
        else None
    )
    workers = (
        WorkerCoordinator(
            store=worker_store,
            sessions=sessions,
            turns=turns,
            git=git_service,
            events=events,
        )
        if worker_store is not None and git_service is not None
        else None
    )
    builds = (
        PlanBuildCoordinator(
            store=plan_build_store,
            plans=plan_store,
            workers=workers,
            events=events,
        )
        if (
            plan_build_store is not None
            and plan_store is not None
            and workers is not None
        )
        else None
    )
    if workers is not None and builds is not None:
        workers.bind_plan_builds(builds)
    goals = (
        GoalCoordinator(
            store=goal_store,
            sessions=sessions,
            turns=turns,
            events=events,
        )
        if goal_store is not None
        else None
    )
    return RuntimeServices(
        sessions=sessions,
        turns=turns,
        events=events,
        settings=settings,
        routing=routing,
        secrets=secrets,
        oauth=oauth_service,
        mcp=mcp,
        git=git_service,
        restores=restores,
        approvals=approval_broker,
        interactions=interaction_broker,
        plans=plan_store,
        workers=workers,
        builds=builds,
        goals=goals,
        audit=audit,
        github=github,
        preview=preview,
        managed_policy=managed_policy,
        extensions=extensions,
    )
