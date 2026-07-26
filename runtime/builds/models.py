"""Validated durable state for plan builds and candidate comparisons."""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from enum import Enum

from runtime.path_scope import scopes_overlap

_PUBLIC_ID = re.compile(r"[A-Za-z0-9][A-Za-z0-9_-]{0,127}")
_PLAN_ID = re.compile(r"[a-f0-9]{32}")
_TASK_ID = re.compile(r"[A-Za-z0-9][A-Za-z0-9_-]{0,63}")
MAX_PLAN_BUILD_CANDIDATES = 8


class PlanBuildState(str, Enum):
    DISPATCHING = "dispatching"
    RUNNING = "running"
    READY = "ready"
    SELECTED = "selected"
    ADOPTING = "adopting"
    ADOPTED = "adopted"
    FAILED = "failed"


TERMINAL_PLAN_BUILD_STATES = frozenset(
    {PlanBuildState.ADOPTED, PlanBuildState.FAILED}
)

ALLOWED_PLAN_BUILD_TRANSITIONS = {
    PlanBuildState.DISPATCHING: frozenset(
        {PlanBuildState.RUNNING, PlanBuildState.FAILED}
    ),
    PlanBuildState.RUNNING: frozenset(
        {PlanBuildState.READY, PlanBuildState.FAILED}
    ),
    PlanBuildState.READY: frozenset({PlanBuildState.SELECTED}),
    PlanBuildState.SELECTED: frozenset({PlanBuildState.ADOPTING}),
    PlanBuildState.ADOPTING: frozenset(
        {PlanBuildState.ADOPTED, PlanBuildState.SELECTED}
    ),
    PlanBuildState.ADOPTED: frozenset(),
    PlanBuildState.FAILED: frozenset(),
}


@dataclass(frozen=True)
class PlanBuildCandidate:
    model: str
    instruction: str = ""
    worker_id: str = ""

    def __post_init__(self) -> None:
        if (
            not _valid_text(self.model, 1, 256)
            or not _valid_text(self.instruction, 0, 32 * 1024)
            or self.worker_id
            and not _valid_id(self.worker_id, "worker-")
        ):
            raise ValueError("invalid plan build candidate")


@dataclass(frozen=True)
class PlanBuildTask:
    task_id: str
    title: str
    description: str
    verification: str
    ownership: tuple[str, ...]
    candidates: tuple[PlanBuildCandidate, ...]
    selected_worker_id: str = ""

    def __post_init__(self) -> None:
        worker_ids = [
            candidate.worker_id
            for candidate in self.candidates
            if candidate.worker_id
        ]
        if (
            _TASK_ID.fullmatch(self.task_id) is None
            or not _valid_text(self.title, 1, 512)
            or not _valid_text(self.description, 0, 4096)
            or not _valid_text(self.verification, 1, 2048)
            or not _valid_paths(self.ownership)
            or not 2 <= len(self.candidates) <= 4
            or len(worker_ids) != len(set(worker_ids))
            or self.selected_worker_id
            and self.selected_worker_id not in worker_ids
        ):
            raise ValueError("invalid plan build task")


@dataclass(frozen=True)
class PlanBuildRecord:
    build_id: str
    parent_session_id: str
    plan_id: str
    tasks: tuple[PlanBuildTask, ...]
    state: PlanBuildState = PlanBuildState.DISPATCHING
    error: str = ""
    created_at: str | None = field(default=None, compare=False)
    updated_at: str | None = field(default=None, compare=False)

    def __post_init__(self) -> None:
        task_ids = [task.task_id for task in self.tasks]
        candidate_count = sum(
            len(task.candidates) for task in self.tasks
        )
        if (
            not _valid_id(self.build_id, "build-")
            or not _valid_id(self.parent_session_id)
            or _PLAN_ID.fullmatch(self.plan_id) is None
            or not 1 <= len(self.tasks) <= 20
            or candidate_count > MAX_PLAN_BUILD_CANDIDATES
            or len(task_ids) != len(set(task_ids))
            or not isinstance(self.state, PlanBuildState)
            or not _valid_text(self.error, 0, 2048)
            or any(
                scopes_overlap(left.ownership, right.ownership)
                for index, left in enumerate(self.tasks)
                for right in self.tasks[index + 1 :]
            )
        ):
            raise ValueError("invalid plan build")


def _valid_id(value: object, prefix: str = "") -> bool:
    return (
        isinstance(value, str)
        and _PUBLIC_ID.fullmatch(value) is not None
        and (not prefix or value.startswith(prefix))
        and not value.startswith("__")
    )


def _valid_text(value: object, minimum: int, maximum: int) -> bool:
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
        or len(paths) != len(set(paths))
    ):
        return False
    for path in paths:
        if (
            not isinstance(path, str)
            or not _valid_text(path, 1, 4096)
            or path.startswith("/")
            or "\\" in path
            or any(part in {"", ".", ".."} for part in path.split("/"))
        ):
            return False
    return True
