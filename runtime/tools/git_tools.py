"""Session-bound Git read and mutation tool adapters."""

from __future__ import annotations

from typing import Any, Protocol

from runtime.git import GitWorkspaceError

from .registry import ToolRegistry


class GitToolService(Protocol):
    def status(self, session_id: str) -> dict[str, object]: ...

    def diff(
        self,
        session_id: str,
        *,
        staged: bool = False,
        against_base: bool = False,
        path: str | None = None,
    ) -> dict[str, object]: ...

    def stage(
        self,
        session_id: str,
        path: str = ".",
    ) -> dict[str, object]: ...

    def commit(
        self,
        session_id: str,
        message: str,
    ) -> dict[str, object]: ...


def register_git_tools(
    registry: ToolRegistry,
    *,
    service: GitToolService,
    session_id: str,
) -> ToolRegistry:
    def git_status() -> dict[str, object]:
        try:
            return service.status(session_id)
        except GitWorkspaceError:
            return {"ok": False, "error": "git operation failed"}

    def git_diff(
        staged: bool = False,
        against_base: bool = False,
        path: str | None = None,
    ) -> dict[str, object]:
        try:
            return service.diff(
                session_id,
                staged=staged,
                against_base=against_base,
                path=path,
            )
        except GitWorkspaceError:
            return {"ok": False, "error": "git operation failed"}

    def git_stage(path: str = ".") -> dict[str, object]:
        try:
            return service.stage(session_id, path)
        except GitWorkspaceError:
            return {"ok": False, "error": "git operation failed"}

    def git_commit(message: str) -> dict[str, object]:
        try:
            return service.commit(session_id, message)
        except GitWorkspaceError:
            return {"ok": False, "error": "git operation failed"}

    registry.register(git_status, schema=_schema("git_status", {}, []))
    registry.register(
        git_diff,
        schema=_schema(
            "git_diff",
            {
                "staged": {"type": "boolean"},
                "against_base": {"type": "boolean"},
                "path": {"type": "string", "maxLength": 4096},
            },
            [],
        ),
    )
    registry.register(
        git_stage,
        schema=_schema(
            "git_stage",
            {"path": {"type": "string", "maxLength": 4096}},
            [],
        ),
    )
    registry.register(
        git_commit,
        schema=_schema(
            "git_commit",
            {"message": {"type": "string", "maxLength": 10000}},
            ["message"],
        ),
    )
    return registry


def _schema(
    name: str,
    properties: dict[str, Any],
    required: list[str],
) -> dict[str, Any]:
    descriptions = {
        "git_status": "Show the isolated session worktree status.",
        "git_diff": "Show an unstaged or staged isolated worktree diff.",
        "git_stage": "Stage a literal path in the isolated worktree.",
        "git_commit": "Commit staged changes on the isolated session branch.",
    }
    return {
        "type": "function",
        "function": {
            "name": name,
            "description": descriptions[name],
            "parameters": {
                "type": "object",
                "properties": properties,
                "required": required,
                "additionalProperties": False,
            },
        },
    }
