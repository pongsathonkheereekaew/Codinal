"""Latest-wins, concurrency-bounded repository search coordination."""

from __future__ import annotations

import threading
import time
from typing import Any, Callable

from .service import _MAX_SECONDS, search_repository_roots


class RepositorySearchCoordinator:
    def __init__(
        self,
        *,
        max_concurrent: int = 2,
        searcher: Callable[..., dict[str, Any]] = search_repository_roots,
    ) -> None:
        if not 1 <= max_concurrent <= 16:
            raise ValueError("invalid search concurrency")
        self._slots = threading.BoundedSemaphore(max_concurrent)
        self._searcher = searcher
        self._lock = threading.Lock()
        self._active: dict[str, threading.Event] = {}

    def search(
        self,
        session_id: str,
        roots: list[dict[str, Any]],
        *,
        query: str,
        mode: str,
        limit: int,
    ) -> dict[str, Any]:
        started = time.monotonic()
        deadline = started + _MAX_SECONDS
        cancellation = threading.Event()
        with self._lock:
            previous = self._active.get(session_id)
            if previous is not None:
                previous.set()
            self._active[session_id] = cancellation
        acquired = False
        try:
            while (
                not cancellation.is_set()
                and time.monotonic() < deadline
            ):
                if self._slots.acquire(
                    timeout=min(0.05, max(0.0, deadline - time.monotonic()))
                ):
                    acquired = True
                    break
            if not acquired:
                return _cancelled(
                    query,
                    mode,
                    cancelled=cancellation.is_set(),
                    duration_ms=max(
                        0,
                        int((time.monotonic() - started) * 1000),
                    ),
                )
            return self._searcher(
                roots,
                query=query,
                mode=mode,
                limit=limit,
                cancelled=cancellation.is_set,
                deadline=deadline,
            )
        finally:
            if acquired:
                self._slots.release()
            with self._lock:
                if self._active.get(session_id) is cancellation:
                    self._active.pop(session_id, None)

    def cancel(self, session_id: str) -> bool:
        with self._lock:
            active = self._active.get(session_id)
            if active is None:
                return False
            active.set()
            return True


def _cancelled(
    query: str,
    mode: str,
    *,
    cancelled: bool = True,
    duration_ms: int = 0,
) -> dict[str, Any]:
    return {
        "ok": True,
        "query": query,
        "mode": mode,
        "count": 0,
        "matches": [],
        "files_scanned": 0,
        "duration_ms": duration_ms,
        "truncated": True,
        "cancelled": cancelled,
    }
