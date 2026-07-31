"""Versioned, host-neutral contract shared by local and remote subagents."""

from __future__ import annotations

import hashlib
import hmac
import json
import secrets
import time
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


@dataclass(frozen=True)
class RemoteLease:
    token: str
    worker_id: str
    revision: str
    capabilities: frozenset[str]
    expires_at: int


class RemoteLeaseAuthority:
    """Issues opaque, connection-scoped leases for an opted-in remote runner."""

    def __init__(self, secret: bytes, *, now=None) -> None:
        if not isinstance(secret, bytes) or len(secret) < 32:
            raise ValueError("remote lease secret is invalid")
        self._secret = secret
        self._now = now
        self._leases: dict[str, RemoteLease] = {}

    def issue(
        self,
        *,
        worker_id: str,
        revision: str,
        capabilities: frozenset[str],
        ttl_seconds: int,
    ) -> RemoteLease:
        if not 1 <= ttl_seconds <= 3600 or len(revision) != 40:
            raise WorkerProtocolError("invalid remote lease")
        negotiate(WorkerHello(PROTOCOL_VERSION, "remote", capabilities))
        now = int(self._now() if self._now else time.time())
        nonce = secrets.token_urlsafe(24)
        payload = f"{worker_id}\0{revision}\0{now + ttl_seconds}\0{nonce}".encode()
        signature = hmac.new(self._secret, payload, hashlib.sha256).hexdigest()
        lease = RemoteLease(
            token=f"{nonce}.{signature}", worker_id=worker_id, revision=revision,
            capabilities=capabilities, expires_at=now + ttl_seconds,
        )
        self._leases[lease.token] = lease
        return lease

    def attest(
        self, token: str, *, worker_id: str, revision: str,
        capabilities: frozenset[str], now: int | None = None,
    ) -> RemoteLease:
        lease = self._leases.get(token)
        current = int(now if now is not None else (self._now() if self._now else time.time()))
        if (lease is None or not hmac.compare_digest(lease.token, token)
                or lease.expires_at < current or lease.worker_id != worker_id
                or lease.revision != revision or lease.capabilities != capabilities):
            raise WorkerProtocolError("remote lease attestation failed")
        return lease


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
