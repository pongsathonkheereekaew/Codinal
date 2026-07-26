"""Versioned protocol contract shared by local and future remote workers."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Final

PROTOCOL_VERSION: Final = "codinal.worker.v1"
REQUIRED_CAPABILITIES: Final = frozenset(
    {
        "artifact.git-worktree",
        "task.cancel",
        "task.execute",
        "task.status",
        "task.steer",
    }
)


class WorkerProtocolError(ValueError):
    pass


@dataclass(frozen=True)
class WorkerHello:
    version: str
    worker_kind: str
    capabilities: frozenset[str]


def negotiate(hello: WorkerHello) -> frozenset[str]:
    if hello.version != PROTOCOL_VERSION:
        raise WorkerProtocolError("unsupported worker protocol")
    if hello.worker_kind not in {"local", "remote"}:
        raise WorkerProtocolError("unsupported worker kind")
    if not REQUIRED_CAPABILITIES <= hello.capabilities:
        raise WorkerProtocolError("worker capabilities are incomplete")
    if any(
        not capability
        or len(capability) > 80
        or not all(
            character.islower()
            or character.isdigit()
            or character in {".", "-", "_"}
            for character in capability
        )
        for capability in hello.capabilities
    ):
        raise WorkerProtocolError("invalid worker capability")
    return frozenset(hello.capabilities)
