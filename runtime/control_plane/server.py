"""Standalone sidecar configuration and startup."""

from __future__ import annotations

import hashlib
import os
import shutil
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any, TextIO

import uvicorn

from runtime import RuntimeServices, compose_runtime
from runtime.git import (
    GitWorkspaceError,
    GitWorktreeService,
    NotGitRepositoryError,
)
from runtime.mcp import MCPManager
from runtime.oauth import OAuthCoordinator
from runtime.policy import Approver, deny_all
from runtime.providers import ProviderClient, ProviderRouter
from runtime.secrets import ProviderSecretService, load_secret_bootstrap
from runtime.sandbox import SandboxedShell
from runtime.sessions import SessionCleanupError, SessionRecord
from runtime.storage import ConversationStore
from runtime.tools import (
    build_core_registry,
    register_git_tools,
    register_mutation_tools,
)
from runtime.turn_engine import TurnEngine

from .app import create_control_plane_app
from .auth import validate_session_token


@dataclass(frozen=True)
class ServerConfig:
    token: str
    port: int
    data_dir: Path
    default_model: str
    host: str = "127.0.0.1"


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
    return ServerConfig(
        token=token,
        port=port,
        data_dir=data_dir,
        default_model=default_model,
    )


def build_services(
    config: ServerConfig,
    secrets: ProviderSecretService | None = None,
    oauth: OAuthCoordinator | None = None,
    provider: ProviderClient | None = None,
    mcp_manager: MCPManager | None = None,
    approver: Approver = deny_all,
) -> RuntimeServices:
    secret_service = secrets or ProviderSecretService()
    store = ConversationStore(config.data_dir)
    provider_client = provider or ProviderRouter(secret_service)
    git_service = GitWorktreeService(config.data_dir)
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
        shell = SandboxedShell(
            workspace=context.roots[0].path,
            temp_dir=sandbox_directory(context.request.session_id),
        )
        registry = build_core_registry(context.roots)
        register_mutation_tools(
            registry,
            roots=context.roots,
            shell=shell,
        )
        if git_service.load(context.request.session_id) is not None:
            register_git_tools(
                registry,
                service=git_service,
                session_id=context.request.session_id,
            )
        engine = TurnEngine(
            provider=provider_client,
            registry=registry,
            permissions=context.permissions,
            model=context.request.model,
            instructions=_coding_instructions(),
            approver=context.approver,
            messages=context.request.messages,
            interrupt_hooks=[
                shell.interrupt,
                lambda: git_service.interrupt(
                    context.request.session_id
                ),
            ],
        )
        engine.agent = context.request.agent
        engine.source_workspace = context.request.workspace
        return engine

    def prepare_workspace(request) -> Path:
        try:
            return git_service.prepare(
                request.session_id,
                request.workspace,
            ).worktree_path
        except NotGitRepositoryError:
            return request.workspace

    def snapshot(session_id: str, engine: Any) -> SessionRecord:
        existing = store.load(session_id)
        roots = list(engine.roots)
        permissions = engine.permissions
        return SessionRecord(
            session_id=session_id,
            workspace=str(roots[0].path),
            source_workspace=str(
                getattr(engine, "source_workspace", roots[0].path)
            ),
            model=engine.model,
            mode=permissions.mode.value,
            messages=list(engine.messages),
            title=existing.title if existing else None,
            agent=str(getattr(engine, "agent", "code")),
            message_count=len(engine.messages),
            extra_roots=[
                {
                    "path": str(root.path),
                    "writable": bool(root.writable),
                    "label": root.label,
                }
                for root in roots[1:]
            ],
            grants={
                "tools": sorted(permissions.session_allow_tools),
                "commands": sorted(permissions.session_allow_commands),
            },
            pinned=existing.pinned if existing else False,
            archived=existing.archived if existing else False,
            origin=existing.origin if existing else "desktop",
            origin_label=existing.origin_label if existing else "Codinal",
        )

    return compose_runtime(
        data_dir=config.data_dir,
        session_store=store,
        engine_builder=build_engine,
        snapshotter=snapshot,
        default_model=config.default_model,
        approver=approver,
        delete_callbacks=(delete_git_workspace, delete_sandbox),
        provider_secrets=secret_service,
        oauth=oauth or OAuthCoordinator(),
        mcp_manager=mcp_manager or MCPManager(),
        workspace_preparer=prepare_workspace,
        git_service=git_service,
    )


def _coding_instructions() -> str:
    return (
        "You are Codinal, a local coding agent. Inspect the workspace with "
        "the provided tools, make requested changes with the mutation tools, "
        "and cite concrete file paths and line numbers. Shell commands run as "
        "direct argv in a network-denied workspace sandbox and do not support "
        "shell operators. Never claim a file changed unless a tool result "
        "proves it."
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
