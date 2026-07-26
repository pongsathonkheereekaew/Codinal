import threading
import time

import runtime.search.coordinator as coordinator_module
from runtime.search import RepositorySearchCoordinator


def _result(query, mode, *, cancelled=False):
    return {
        "ok": True,
        "query": query,
        "mode": mode,
        "count": 0,
        "matches": [],
        "files_scanned": 0,
        "duration_ms": 0,
        "truncated": cancelled,
        "cancelled": cancelled,
    }


def test_latest_search_cancels_prior_search_for_same_session():
    first_started = threading.Event()
    first_cancelled = threading.Event()

    def searcher(_roots, *, query, mode, cancelled, **_options):
        if query == "first":
            first_started.set()
            while not cancelled():
                time.sleep(0.005)
            first_cancelled.set()
            return _result(query, mode, cancelled=True)
        return _result(query, mode)

    coordinator = RepositorySearchCoordinator(searcher=searcher)
    first_result = {}

    def run_first():
        first_result.update(
            coordinator.search(
                "session-1",
                [{"path": "/tmp/repo"}],
                query="first",
                mode="text",
                limit=10,
            )
        )

    thread = threading.Thread(target=run_first)
    thread.start()
    assert first_started.wait(timeout=1)
    second = coordinator.search(
        "session-1",
        [{"path": "/tmp/repo"}],
        query="second",
        mode="text",
        limit=10,
    )
    thread.join(timeout=1)

    assert first_cancelled.is_set()
    assert first_result["cancelled"] is True
    assert second["cancelled"] is False


def test_search_coordinator_enforces_global_concurrency_bound():
    lock = threading.Lock()
    release = threading.Event()
    running = 0
    maximum = 0

    def searcher(_roots, *, query, mode, cancelled, **_options):
        nonlocal maximum, running
        with lock:
            running += 1
            maximum = max(maximum, running)
        release.wait(timeout=1)
        with lock:
            running -= 1
        return _result(query, mode, cancelled=cancelled())

    coordinator = RepositorySearchCoordinator(
        max_concurrent=2,
        searcher=searcher,
    )
    threads = [
        threading.Thread(
            target=coordinator.search,
            args=(f"session-{index}", [{"path": "/tmp/repo"}]),
            kwargs={"query": str(index), "mode": "text", "limit": 10},
        )
        for index in range(4)
    ]
    for thread in threads:
        thread.start()
    time.sleep(0.1)
    release.set()
    for thread in threads:
        thread.join(timeout=1)

    assert maximum == 2


def test_search_coordinator_bounds_slot_wait_within_request_deadline(
    monkeypatch,
):
    monkeypatch.setattr(coordinator_module, "_MAX_SECONDS", 0.1)
    first_started = threading.Event()
    release = threading.Event()

    def searcher(_roots, *, query, mode, cancelled, **_options):
        first_started.set()
        release.wait(timeout=1)
        return _result(query, mode, cancelled=cancelled())

    coordinator = RepositorySearchCoordinator(
        max_concurrent=1,
        searcher=searcher,
    )
    first = threading.Thread(
        target=coordinator.search,
        args=("first", [{"path": "/tmp/repo"}]),
        kwargs={"query": "first", "mode": "text", "limit": 10},
    )
    first.start()
    assert first_started.wait(timeout=1)

    started = time.monotonic()
    queued = coordinator.search(
        "queued",
        [{"path": "/tmp/repo"}],
        query="queued",
        mode="text",
        limit=10,
    )
    elapsed = time.monotonic() - started
    release.set()
    first.join(timeout=1)

    assert elapsed < 0.3
    assert queued["truncated"] is True
    assert queued["cancelled"] is False
