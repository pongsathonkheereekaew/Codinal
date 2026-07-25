"""One-time, process-local OAuth state lifecycle."""

from __future__ import annotations

import secrets
import threading
import time
from copy import deepcopy
from dataclasses import dataclass
from typing import Any, Callable


@dataclass(frozen=True)
class OAuthAttempt:
    state: str
    expires_in: int


@dataclass
class _PendingAttempt:
    flow: str
    metadata: dict[str, Any]
    expires_at: float


class OAuthStateService:
    def __init__(
        self,
        *,
        ttl_seconds: int = 600,
        max_pending: int = 64,
        token_factory: Callable[[], str] | None = None,
        clock: Callable[[], float] | None = None,
    ) -> None:
        if not 1 <= ttl_seconds <= 600:
            raise ValueError("ttl_seconds must be between 1 and 600")
        if not 1 <= max_pending <= 1024:
            raise ValueError("max_pending must be between 1 and 1024")
        self._ttl_seconds = ttl_seconds
        self._max_pending = max_pending
        self._token_factory = token_factory or (
            lambda: secrets.token_urlsafe(32)
        )
        self._clock = clock or time.monotonic
        self._pending: dict[str, _PendingAttempt] = {}
        self._lock = threading.Lock()

    def begin(
        self, flow: str, metadata: dict[str, Any] | None = None
    ) -> OAuthAttempt:
        if (
            not isinstance(flow, str)
            or not 1 <= len(flow) <= 128
            or not all(
                character.isascii()
                and (character.isalnum() or character in "._:-")
                for character in flow
            )
        ):
            raise ValueError("invalid OAuth flow")
        if metadata is not None and not isinstance(metadata, dict):
            raise ValueError("OAuth metadata must be an object")
        now = self._clock()
        with self._lock:
            self._prune_expired(now)
            while len(self._pending) >= self._max_pending:
                self._pending.pop(next(iter(self._pending)))
            for _ in range(4):
                state = self._token_factory()
                if self._valid_state(state) and state not in self._pending:
                    break
            else:
                raise RuntimeError("unable to mint unique OAuth state")
            self._pending[state] = _PendingAttempt(
                flow=flow,
                metadata=deepcopy(metadata or {}),
                expires_at=now + self._ttl_seconds,
            )
        return OAuthAttempt(state=state, expires_in=self._ttl_seconds)

    def consume(self, state: str, flow: str) -> dict[str, Any] | None:
        now = self._clock()
        with self._lock:
            pending = self._pending.get(state)
            if (
                pending is None
                or pending.flow != flow
                or pending.expires_at <= now
            ):
                if pending is not None and pending.expires_at <= now:
                    self._pending.pop(state, None)
                return None
            self._pending.pop(state)
            return deepcopy(pending.metadata)

    @staticmethod
    def _valid_state(state: str) -> bool:
        return (
            isinstance(state, str)
            and 32 <= len(state) <= 256
            and all(
                character.isascii()
                and (character.isalnum() or character in "-_")
                for character in state
            )
        )

    def _prune_expired(self, now: float) -> None:
        for state, pending in tuple(self._pending.items()):
            if pending.expires_at <= now:
                self._pending.pop(state, None)
