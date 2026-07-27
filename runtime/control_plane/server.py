"""Standalone sidecar configuration and startup."""

from __future__ import annotations

import hashlib
import os
import shutil
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any, TextIO

import uvicorn

from runtime import RuntimeServices, compose_runtime
from runtime.audit import AuditLedger
from runtime.policy.managed import ManagedPolicy
from runtime.git import (
    GitWorkspaceError,
    GitWorktreeService,
    NotGitRepositoryError,
    TransactionalShell,
)
from runtime.interactions import InteractionBroker
from runtime.mcp import MCPManager, MCPStore
from runtime.github import GitHubService
from runtime.preview import PreviewEvidenceStore
from runtime.oauth import OAuthCoordinator
from runtime.policy import ApprovalBroker, Approver, deny_all
from runtime.providers import ProviderClient, ProviderRouter
from runtime.sandbox import SandboxedShell
from runtime.secrets import (
    ProviderSecretService,
    SecretRedactor,
    load_secret_bootstrap,
)
from runtime.sessions import (
    RootDir,
    SessionCleanupError,
    SessionRecord,
    TurnCheckpoint,
)
from runtime.storage import ConversationStore
from runtime.tools import (
    build_core_registry,
    register_git_tools,
    register_interaction_tools,
    register_mutation_tools,
)
from runtime.turn_engine import TurnEngine
from runtime.path_scope import owns_path
from runtime.workers import WorkerStore
from runtime.builds import PlanBuildStore
from runtime.goals import GoalStore

from .app import create_control_plane_app
from .auth import validate_session_token


@dataclass(frozen=True)
class ServerConfig:
    token: str
    port: int
    data_dir: Path
    default_model: str
    host: str = "127.0.0.1"
    managed_policy_path: Path | None = None


def load_server_config() -> ServerConfig:
    token = os.environ.pop("CODINAL_SESSION_TOKEN", "")
    if not token:
        raise ValueError("CODINAL_SESSION_TOKEN is required")
    validate_session_token(token)

    port_value = os.environ.get("CODINAL_PORT")
    if port_value is None:
        raise ValueError("CODINAL_PORT is required")
    try:
        port = int(port_value)
    except ValueError as error:
        raise ValueError("CODINAL_PORT must be an integer") from error
    if not 1 <= port <= 65535:
        raise ValueError("CODINAL_PORT must be between 1 and 65535")

    data_dir = Path(
        os.environ.get(
            "CODINAL_DATA_DIR",
            "~/Library/Application Support/Codinal",
        )
    ).expanduser()
    default_model = (
        os.environ.get("CODINAL_DEFAULT_MODEL", "openai:gpt-5").strip()
        or "openai:gpt-5"
    )
    policy_path = os.environ.get("CODINAL_MANAGED_POLICY", "")
    managed_policy_path = Path(policy_path).expanduser() if policy_path else None
    return ServerConfig(
        token=token,
        port=port,
        data_dir=data_dir,
        default_model=default_model,
        managed_policy_path=managed_policy_path,
    )


def build_services(
    config: ServerConfig,
    secrets: ProviderSecretService | None = None,
    oauth: OAuthCoordinator | None = None,
    provider: ProviderClient | None = None,
    mcp_manager: MCPManager | None = None,
    approver: Approver = deny_all,
) -> RuntimeServices:
    managed_policy = ManagedPolicy.from_file(config.managed_policy_path)
    secret_service = secrets or ProviderSecretService(managed_policy=managed_policy)
    store = ConversationStore(config.data_dir)
    provider_client = provider or ProviderRouter(secret_service)
    git_service = GitWorktreeService(config.data_dir)
    approval_broker = ApprovalBroker(decisions=store)
    interaction_broker = InteractionBroker(store)
    worker_store = WorkerStore(config.data_dir)
    plan_build_store = PlanBuildStore(config.data_dir)
    goal_store = GoalStore(config.data_dir)
    mcp_store = MCPStore(config.data_dir)
    secret_redactor = SecretRedactor(secret_service)
    audit_ledger = AuditLedger(config.data_dir, redactor=secret_redactor)
    github_service = GitHubService(secret_service)
    preview_store = PreviewEvidenceStore(config.data_dir)
    sandbox_base = (config.data_dir / "sandbox").expanduser().resolve()

    def sandbox_directory(session_id: str) -> Path:
        return sandbox_base / hashlib.sha256(
            session_id.encode("utf-8")
        ).hexdigest()

    def delete_sandbox(session_id: str) -> None:
        target = sandbox_directory(session_id)
        if target.parent != sandbox_base or target == sandbox_base:
            raise ValueError("invalid sandbox cleanup target")
        if target.is_symlink():
            target.unlink()
        elif target.is_dir():
            shutil.rmtree(target)

    def delete_git_workspace(session_id: str) -> None:
        try:
            git_service.cleanup(session_id)
        except GitWorkspaceError as error:
            raise SessionCleanupError(str(error)) from None

    def build_engine(context):
        worker = worker_store.load_by_child_session(
            context.request.session_id
        )
        write_scope = worker.ownership if worker is not None else ()
        git_record = git_service.load(context.request.session_id)
        checkpoint_enabled = git_service.has_checkpoint_session(
            context.request.session_id
        )
        if worker is not None and not checkpoint_enabled:
            raise RuntimeError("worker Git worktree is unavailable")
        shell = (
            TransactionalShell(
                workspace=context.roots[0].path,
                temp_dir=(
                    sandbox_directory(context.request.session_id)
                    / "shell-transactions"
                ),
                git_executable=git_service.git_executable,
                git_read_root=(
                    git_record.git_common_dir
                    if git_record is not None
                    else None
                ),
                apply_attributed_delta=lambda paths, apply_delta: (
                    False
                    if write_scope
                    and any(
                        not owns_path(
                            context.roots[0].path,
                            write_scope,
                            path,
                        )
                        for path in paths
                    )
                    else git_service.apply_file_delta(
                        context.request.session_id,
                        paths,
                        apply_delta,
                    )
                ),
            )
            if checkpoint_enabled
            else SandboxedShell(
                workspace=context.roots[0].path,
                temp_dir=sandbox_directory(
                    context.request.session_id
                ),
            )
        )
        registry = build_core_registry(context.roots)
        if worker is None:
            register_interaction_tools(registry)
        register_mutation_tools(
            registry,
            roots=context.roots,
            shell=shell,
            mutation_recorder=(
                git_service.mutation_recorder(
                    context.request.session_id
                )
                if checkpoint_enabled
                else None
            ),
            write_scope=write_scope,
        )
        if git_record is not None and worker is None:
            register_git_tools(
                registry,
                service=git_service,
                session_id=context.request.session_id,
            )

        def bind_directory_response(
            response: dict[str, Any],
            replay: bool,
        ) -> dict[str, Any]:
            if not response.get("granted"):
                return response
            candidate = Path(
                str(response.get("path", ""))
            ).expanduser()
            if not candidate.is_absolute():
                raise ValueError("directory path is not absolute")
            resolved = candidate.resolve(strict=True)
            metadata = resolved.stat()
            if not resolved.is_dir():
                raise ValueError("directory is unavailable")
            if replay:
                if (
                    candidate != resolved
                    or response.get("_device") != metadata.st_dev
                    or response.get("_inode") != metadata.st_ino
                ):
                    raise ValueError("approved directory changed")
            return {
                "granted": True,
                "path": str(resolved),
                "writable": bool(response.get("writable", False)),
                "_device": metadata.st_dev,
                "_inode": metadata.st_ino,
            }

        def request_directory(
            arguments: dict[str, Any],
            tool_call_id: str,
        ):
            response_awaitable = interaction_broker.requester(
                context.request.session_id,
                "directory",
                response_normalizer=bind_directory_response,
            )(arguments, tool_call_id)

            async def apply_response() -> dict[str, Any]:
                response = await response_awaitable
                if not response.get("granted"):
                    return response
                try:
                    bound = bind_directory_response(
                        response,
                        True,
                    )
                except (OSError, ValueError):
                    return {
                        "granted": False,
                        "error": "selected directory changed",
                    }
                resolved = Path(str(bound["path"]))
                writable = bool(response.get("writable", False))
                matching = next(
                    (
                        root
                        for root in context.roots
                        if root.path == resolved
                    ),
                    None,
                )
                if matching is None:
                    context.roots.append(
                        RootDir(
                            path=resolved,
                            writable=writable,
                            label=resolved.name,
                            device=int(bound["_device"]),
                            inode=int(bound["_inode"]),
                        )
                    )
                elif matching is not context.roots[0]:
                    matching.writable = writable
                    matching.device = int(bound["_device"])
                    matching.inode = int(bound["_inode"])
                return {
                    "granted": True,
                    "path": str(resolved),
                    "writable": writable,
                }

            return apply_response()

        engine = TurnEngine(
            provider=provider_client,
            registry=registry,
            permissions=context.permissions,
            model=context.request.model,
            instructions=_coding_instructions(),
            approver=context.approver,
            approval_id_factory=lambda call: approval_broker.approval_id(
                context.request.session_id,
                call.id,
            ),
            directory_requester=(
                request_directory if worker is None else None
            ),
            plan_approver=(
                interaction_broker.requester(
                    context.request.session_id,
                    "plan",
                )
                if worker is None
                else None
            ),
            question_asker=(
                interaction_broker.requester(
                    context.request.session_id,
                    "question",
                )
                if worker is None
                else None
            ),
            interaction_id_factory=lambda call, kind: (
                interaction_broker.interaction_id(
                    context.request.session_id,
                    call.id,
                    kind,
                )
            ),
            messages=context.request.messages,
            interrupt_hooks=[
                shell.interrupt,
                lambda: git_service.interrupt(
                    context.request.session_id
                ),
            ],
            turn_start_hooks=[shell.begin_turn],
            redactor=secret_redactor,
        )
        engine._terminal_shell = shell
        engine.agent = context.request.agent
        engine.source_workspace = context.request.workspace
        return engine

    def prepare_workspace(request) -> Path:
        if git_service.is_plain_session(request.session_id):
            return git_service.prepare_plain(
                request.session_id,
                request.workspace,
            )
        try:
            return git_service.prepare(
                request.session_id,
                request.workspace,
            ).worktree_path
        except NotGitRepositoryError:
            return git_service.prepare_plain(
                request.session_id,
                request.workspace,
            )

    def snapshot(session_id: str, engine: Any) -> SessionRecord:
        existing = store.load(session_id)
        roots = list(engine.roots)
        permissions = engine.permissions
        active_extra_roots = {
            str(root.path): {
                "path": str(root.path),
                "writable": bool(root.writable),
                "label": root.label,
                "_device": root.device,
                "_inode": root.inode,
            }
            for root in roots[1:]
        }
        extra_roots = []
        for root in getattr(engine, "durable_extra_roots", []):
            path = str(root.get("path", ""))
            extra_roots.append(active_extra_roots.pop(path, root))
        extra_roots.extend(active_extra_roots.values())
        return SessionRecord(
            session_id=session_id,
            workspace=str(roots[0].path),
            workspace_device=roots[0].device,
            workspace_inode=roots[0].inode,
            source_workspace=str(
                getattr(engine, "source_workspace", roots[0].path)
            ),
            model=engine.model,
            mode=permissions.mode.value,
            messages=list(engine.messages),
            title=existing.title if existing else None,
            agent=str(getattr(engine, "agent", "code")),
            message_count=len(engine.messages),
            extra_roots=extra_roots,
            grants={
                "tools": sorted(permissions.session_allow_tools),
                "commands": sorted(permissions.session_allow_commands),
            },
            pinned=existing.pinned if existing else False,
            archived=existing.archived if existing else False,
            origin=existing.origin if existing else "desktop",
            origin_label=existing.origin_label if existing else "Codinal",
            turn_checkpoint=(
                existing.turn_checkpoint
                if existing
                else TurnCheckpoint()
            ),
        )

    return compose_runtime(
        data_dir=config.data_dir,
        session_store=store,
        engine_builder=build_engine,
        snapshotter=snapshot,
        default_model=config.default_model,
        curated_models=(
            "openai:gpt-5.6-sol",
            "anthropic:claude-sonnet-4-6",
            "gemini:gemini-2.5-flash",
        ),
        approver=approver,
        approver_factory=(
            approval_broker.approver if approver is deny_all else None
        ),
        delete_callbacks=(delete_git_workspace, delete_sandbox),
        artifact_opener=_open_project_item,
        provider_secrets=secret_service,
        oauth=oauth or OAuthCoordinator(),
        mcp_manager=mcp_manager or MCPManager(),
        workspace_preparer=prepare_workspace,
        git_service=git_service,
        approval_broker=approval_broker,
        interaction_broker=interaction_broker,
        plan_store=store,
        worker_store=worker_store,
        plan_build_store=plan_build_store,
        goal_store=goal_store,
        mcp_store=mcp_store,
        audit=audit_ledger,
        github=github_service,
        preview=preview_store,
        managed_policy=managed_policy,
    )


def _open_project_item(_path: Path, mode: str, descriptor: int) -> None:
    helper = os.environ.get("CODINAL_HOST_HELPER", "")
    if not helper or not Path(helper).is_absolute() or not os.access(helper, os.X_OK):
        raise OSError("native project opener is unavailable")
    command = [helper, "--codinal-open-fd", mode, str(descriptor)]
    try:
        result = subprocess.run(
            command,
            stdin=subprocess.DEVNULL,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            pass_fds=(descriptor,),
            check=False,
            timeout=10,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise OSError("could not open project item") from exc
    if result.returncode != 0:
        raise OSError("could not open project item")


def _coding_instructions() -> str:
    return (
        "You are Codinal, a local coding agent. Inspect the workspace with "
        "the provided tools, make requested changes with the mutation tools, "
        "and cite concrete file paths and line numbers. Shell commands run as "
        "direct argv in a network-denied transactional workspace mirror; only "
        "their conflict-checked file delta is applied, and shell operators are "
        "not supported. Never claim a file changed unless a tool result proves "
        "it."
    )


def load_runtime_secrets(stream: TextIO) -> ProviderSecretService:
    channel = os.environ.pop("CODINAL_SECRET_BOOTSTRAP", "")
    if not channel:
        return ProviderSecretService()
    if channel != "stdin-v1":
        raise ValueError("unsupported secret bootstrap channel")
    return load_secret_bootstrap(stream)


def run() -> None:
    config = load_server_config()
    app = create_control_plane_app(
        token=config.token,
        services=build_services(config, load_runtime_secrets(sys.stdin)),
    )
    uvicorn.run(
        app,
        host=config.host,
        port=config.port,
        access_log=False,
        server_header=False,
    )
