"""Durable background-worker state."""

from __future__ import annotations

import re
from dataclasses import dataclass, field, replace
from enum import Enum

from .protocol import PROTOCOL_VERSION, REQUIRED_CAPABILITIES

_PUBLIC_ID = re.compile(r"[A-Za-z0-9][A-Za-z0-9_-]{0,127}")
_COMMIT = re.compile(r"[0-9a-f]{40}")


class WorkerState(str, Enum):
    QUEUED = "queued"
    BLOCKED = "blocked"
    RUNNING = "running"
    FINALIZING = "finalizing"
    SUCCEEDED = "succeeded"
    ADOPTING = "adopting"
    ADOPTED = "adopted"
    FAILED = "failed"
    CANCELLED = "cancelled"


TERMINAL_WORKER_STATES = frozenset(
    {
        WorkerState.SUCCEEDED,
        WorkerState.ADOPTED,
        WorkerState.FAILED,
        WorkerState.CANCELLED,
    }
)

ALLOWED_WORKER_TRANSITIONS = {
    WorkerState.QUEUED: frozenset(
        {
            WorkerState.BLOCKED,
            WorkerState.RUNNING,
            WorkerState.FAILED,
            WorkerState.CANCELLED,
        }
    ),
    WorkerState.BLOCKED: frozenset(
        {
            WorkerState.QUEUED,
            WorkerState.CANCELLED,
            WorkerState.FAILED,
        }
    ),
    WorkerState.RUNNING: frozenset(
        {
            WorkerState.FINALIZING,
            WorkerState.FAILED,
            WorkerState.CANCELLED,
        }
    ),
    WorkerState.FINALIZING: frozenset(
        {
            WorkerState.SUCCEEDED,
            WorkerState.FAILED,
            WorkerState.CANCELLED,
        }
    ),
    WorkerState.SUCCEEDED: frozenset({WorkerState.ADOPTING}),
    WorkerState.ADOPTING: frozenset(
        {
            WorkerState.ADOPTED,
            WorkerState.SUCCEEDED,
        }
    ),
    WorkerState.ADOPTED: frozenset(),
    WorkerState.FAILED: frozenset(),
    WorkerState.CANCELLED: frozenset(),
}


@dataclass(frozen=True)
class WorkerRecord:
    worker_id: str
    parent_session_id: str
    child_session_id: str
    task: str
    ownership: tuple[str, ...]
    dependencies: tuple[str, ...]
    model: str
    state: WorkerState = WorkerState.QUEUED
    worker_kind: str = "local"
    protocol_version: str = PROTOCOL_VERSION
    capabilities: frozenset[str] = field(
        default_factory=lambda: REQUIRED_CAPABILITIES
    )
    summary: str = ""
    error: str = ""
    commit: str = ""
    created_at: str | None = field(default=None, compare=False)
    updated_at: str | None = field(default=None, compare=False)

    def __post_init__(self) -> None:
        if (
            not _valid_id(self.worker_id, "worker-")
            or not _valid_id(self.parent_session_id)
            or not _valid_id(self.child_session_id)
            or not _valid_text(self.task, minimum=1, maximum=32 * 1024)
            or not _valid_text(self.model, minimum=1, maximum=256)
            or not isinstance(self.state, WorkerState)
            or self.worker_kind not in {"local", "remote"}
            or self.protocol_version != PROTOCOL_VERSION
            or not isinstance(self.capabilities, frozenset)
            or not REQUIRED_CAPABILITIES <= self.capabilities
            or not _valid_paths(self.ownership)
            or not _valid_dependencies(self.worker_id, self.dependencies)
            or not _valid_text(self.summary, minimum=0, maximum=64 * 1024)
            or not _valid_text(self.error, minimum=0, maximum=2048)
            or not isinstance(self.commit, str)
            or bool(self.commit)
            and _COMMIT.fullmatch(self.commit) is None
        ):
            raise ValueError("invalid worker record")

    def with_timestamps(
        self,
        *,
        created_at: str,
        updated_at: str,
    ) -> "WorkerRecord":
        return replace(
            self,
            created_at=created_at,
            updated_at=updated_at,
        )


def _valid_id(value: object, prefix: str = "") -> bool:
    return (
        isinstance(value, str)
        and _PUBLIC_ID.fullmatch(value) is not None
        and (not prefix or value.startswith(prefix))
        and not value.startswith("__")
    )


def _valid_text(value: object, *, minimum: int, maximum: int) -> bool:
    if not isinstance(value, str):
        return False
    try:
        size = len(value.encode("utf-8"))
    except UnicodeEncodeError:
        return False
    return minimum <= size <= maximum


def _valid_paths(paths: object) -> bool:
    if (
        not isinstance(paths, tuple)
        or not 1 <= len(paths) <= 32
        or len(set(paths)) != len(paths)
    ):
        return False
    for path in paths:
        if (
            not isinstance(path, str)
            or not _valid_text(path, minimum=1, maximum=4096)
            or path.startswith("/")
            or "\\" in path
        ):
            return False
        parts = path.split("/")
        if any(part in {"", ".", ".."} for part in parts):
            return False
    return True


def _valid_dependencies(worker_id: str, dependencies: object) -> bool:
    return (
        isinstance(dependencies, tuple)
        and len(dependencies) <= 32
        and len(set(dependencies)) == len(dependencies)
        and worker_id not in dependencies
        and all(_valid_id(dependency, "worker-") for dependency in dependencies)
    )
