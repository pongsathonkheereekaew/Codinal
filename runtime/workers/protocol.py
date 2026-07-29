"""Versioned, host-neutral contract shared by local and remote subagents."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Final

PROTOCOL_VERSION: Final = "harness.subagent.v1"
LEGACY_PROTOCOL_VERSIONS: Final = frozenset({"codinal.worker.v1"})
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


def normalize_persisted_version(version: str) -> str:
    """Upgrade stored v1 records without accepting legacy handshakes."""
    if version in LEGACY_PROTOCOL_VERSIONS:
        return PROTOCOL_VERSION
    return version


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
