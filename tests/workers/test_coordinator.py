from __future__ import annotations

import asyncio
from pathlib import Path

import pytest

from runtime.workers import (
    WorkerCoordinator,
    WorkerRecord,
    WorkerState,
    WorkerStore,
)


class FakeSessions:
    def __init__(self, workspace: Path) -> None:
        self.workspace = workspace
        self.created: list[dict[str, str]] = []

    def create_worker_session(self, parent, **options):
        self.created.append({"parent": parent, **options})
        return {
            "ok": True,
            "session_id": options["child_session_id"],
            "workspace": str(self.workspace),
        }

    def messages(self, _session_id):
        return [{"role": "assistant", "content": "Implemented safely"}]


class FakeTurns:
    def __init__(self) -> None:
        self.started: list[tuple[str, dict[str, object]]] = []
        self.waiters: dict[str, asyncio.Event] = {}
        self.steered: list[tuple[str, str]] = []
        self.interrupted: list[str] = []
        self.outcomes: dict[str, dict[str, object]] = {}
        self.mutations: list[str] = []

    async def start(self, session_id, **options):
        self.started.append((session_id, options))
        self.waiters[session_id] = asyncio.Event()
        return {"ok": True}

    async def wait(self, session_id):
        await self.waiters[session_id].wait()
        return True

    def is_active(self, session_id):
        return (
            session_id in self.waiters
            and not self.waiters[session_id].is_set()
        )

    def steer(self, session_id, text):
        self.steered.append((session_id, text))
        return True

    def interrupt(self, session_id):
        self.interrupted.append(session_id)
        return True

    async def mutate_when_idle(self, session_id, mutation):
        self.mutations.append(session_id)
        if self.is_active(session_id):
            raise RuntimeError("session already has an active turn")
        return mutation()

    def outcome(self, session_id):
        return self.outcomes.get(
            session_id,
            {"type": "turn_end", "status": "completed"},
        )


class FakeGit:
    def __init__(self) -> None:
        self.staged: list[tuple[str, str]] = []
        self.adopted: list[str] = []
        self.clean: set[str] = set()

    def load(self, _session_id):
        return object()

    def prepare(self, _session_id, _workspace):
        return object()

    def status(self, session_id):
        parent_clean = session_id == "session-parent"
        return {
            "ok": True,
            "clean": parent_clean or session_id in self.clean,
            "base_commit": "b" * 40,
            "head_commit": (
                "a" * 40
                if session_id in self.clean
                else "b" * 40
            ),
        }

    def stage(self, session_id, path):
        self.staged.append((session_id, path))
        return {"ok": True}

    def commit(self, session_id, _message):
        self.clean.add(session_id)
        return {"ok": True, "commit": "a" * 40}

    def apply_back(self, session_id):
        self.adopted.append(session_id)
        return {"ok": True, "strategy": "cherry-pick", "commit": "a" * 40}


class FakeEvents:
    def __init__(self) -> None:
        self.messages = []

    async def publish_session(self, session_id, message):
        self.messages.append((session_id, message))

    async def publish_global(self, message):
        self.messages.append(("global", message))


def test_three_workers_run_in_parallel_and_commit_only_owned_paths(
    tmp_path,
):
    async def scenario():
        turns = FakeTurns()
        git = FakeGit()
        events = FakeEvents()
        coordinator = WorkerCoordinator(
            store=WorkerStore(tmp_path / "state"),
            sessions=FakeSessions(tmp_path),
            turns=turns,
            git=git,
            events=events,
        )
        for index, owned in enumerate(("runtime/a", "runtime/b", "tests/c")):
            result = await coordinator.create(
                "session-parent",
                task=f"Task {index}",
                ownership=(owned,),
                model="openai:test",
            )
            assert result.state is WorkerState.RUNNING
        assert len(turns.started) == 3
        for event in turns.waiters.values():
            event.set()
        await coordinator.wait_idle()
        return coordinator, git, turns

    coordinator, git, turns = asyncio.run(scenario())
    records = coordinator.list("session-parent")
    assert all(record.state is WorkerState.SUCCEEDED for record in records)
    assert {path for _, path in git.staged} == {
        "runtime/a",
        "runtime/b",
        "tests/c",
    }
    mutations_before_adopt = len(turns.mutations)
    adopted = asyncio.run(coordinator.adopt(records[1].worker_id))
    repeated = asyncio.run(coordinator.adopt(records[1].worker_id))
    assert adopted["ok"] is True
    assert repeated["strategy"] == "already-applied"
    assert git.adopted == [records[1].child_session_id]
    assert coordinator.load(records[1].worker_id).state is WorkerState.ADOPTED
    assert len(turns.mutations) == mutations_before_adopt + 1


def test_worker_supports_steering_cancellation_and_explicit_adoption(
    tmp_path,
):
    async def scenario():
        turns = FakeTurns()
        git = FakeGit()
        events = FakeEvents()
        coordinator = WorkerCoordinator(
            store=WorkerStore(tmp_path / "state"),
            sessions=FakeSessions(tmp_path),
            turns=turns,
            git=git,
            events=events,
        )
        worker = await coordinator.create(
            "session-parent",
            task="Implement parser",
            ownership=("runtime/parser",),
            model="openai:test",
        )
        return coordinator, turns, git, events, worker

    coordinator, turns, git, events, worker = asyncio.run(scenario())

    assert coordinator.steer(worker.worker_id, "Also cover empty input")
    assert turns.steered == [
        (worker.child_session_id, "Also cover empty input")
    ]
    assert asyncio.run(coordinator.cancel(worker.worker_id))
    assert turns.interrupted == [worker.child_session_id]
    assert coordinator.load(worker.worker_id).state is WorkerState.CANCELLED
    assert events.messages[-1][1]["worker"]["state"] == "cancelled"
    with pytest.raises(ValueError, match="succeeded"):
        asyncio.run(coordinator.adopt(worker.worker_id))

    with pytest.raises(ValueError, match="invalid worker state"):
        coordinator.store.transition(
            worker.worker_id,
            expected={WorkerState.CANCELLED},
            target=WorkerState.SUCCEEDED,
        )


def test_non_completed_turn_fails_and_publishes_terminal_status(tmp_path):
    async def scenario():
        turns = FakeTurns()
        events = FakeEvents()
        coordinator = WorkerCoordinator(
            store=WorkerStore(tmp_path / "state"),
            sessions=FakeSessions(tmp_path),
            turns=turns,
            git=FakeGit(),
            events=events,
        )
        worker = await coordinator.create(
            "session-parent",
            task="Loop forever",
            ownership=("runtime/loop",),
            model="openai:test",
        )
        turns.outcomes[worker.child_session_id] = {
            "type": "turn_end",
            "status": "max_iterations_exceeded",
        }
        turns.waiters[worker.child_session_id].set()
        await coordinator.wait_idle()
        return coordinator, worker, events

    coordinator, worker, events = asyncio.run(scenario())

    failed = coordinator.load(worker.worker_id)
    assert failed.state is WorkerState.FAILED
    assert failed.error == "worker turn did not complete"
    assert any(
        message["worker"]["state"] == "failed"
        for _, message in events.messages
    )


def test_dependency_graph_unblocks_only_after_predecessor_succeeds(tmp_path):
    async def scenario():
        turns = FakeTurns()
        sessions = FakeSessions(tmp_path)
        coordinator = WorkerCoordinator(
            store=WorkerStore(tmp_path / "state"),
            sessions=sessions,
            turns=turns,
            git=FakeGit(),
            events=FakeEvents(),
        )
        first = await coordinator.create(
            "session-parent",
            task="Implement parser",
            ownership=("runtime/parser",),
            model="openai:test",
        )
        second = await coordinator.create(
            "session-parent",
            task="Add parser tests",
            ownership=("runtime/parser",),
            dependencies=(first.worker_id,),
            model="openai:test",
        )
        assert second.state is WorkerState.BLOCKED
        assert len(turns.started) == 1
        assert len(sessions.created) == 1
        turns.waiters[first.child_session_id].set()
        while (
            coordinator.load(first.worker_id).state
            is not WorkerState.SUCCEEDED
        ):
            await asyncio.sleep(0)
        await coordinator.adopt(first.worker_id)
        assert len(sessions.created) == 2
        while second.child_session_id not in turns.waiters:
            await asyncio.sleep(0)
        turns.waiters[second.child_session_id].set()
        await coordinator.wait_idle()
        return coordinator, second

    coordinator, second = asyncio.run(scenario())

    assert coordinator.load(second.worker_id).state is WorkerState.SUCCEEDED


def test_worker_creation_rejects_plain_directory_and_remote_dispatch(
    tmp_path,
):
    class PlainGit(FakeGit):
        def load(self, _session_id):
            return None

    class DirtyGit(FakeGit):
        def status(self, session_id):
            status = super().status(session_id)
            return {**status, "clean": False}

    coordinator = WorkerCoordinator(
        store=WorkerStore(tmp_path / "state"),
        sessions=FakeSessions(tmp_path),
        turns=FakeTurns(),
        git=PlainGit(),
        events=FakeEvents(),
    )

    async def create(worker_kind):
        return await coordinator.create(
            "session-parent",
            task="Unsafe task",
            ownership=("runtime",),
            model="openai:test",
            worker_kind=worker_kind,
        )

    with pytest.raises(ValueError, match="Git workspace"):
        asyncio.run(create("local"))
    with pytest.raises(ValueError, match="remote worker transport"):
        asyncio.run(create("remote"))

    dirty = WorkerCoordinator(
        store=WorkerStore(tmp_path / "dirty-state"),
        sessions=FakeSessions(tmp_path),
        turns=FakeTurns(),
        git=DirtyGit(),
        events=FakeEvents(),
    )
    with pytest.raises(ValueError, match="parent worktree must be clean"):
        asyncio.run(
            dirty.create(
                "session-parent",
                task="Dirty baseline",
                ownership=("runtime",),
                model="openai:test",
            )
        )

    busy_turns = FakeTurns()

    async def busy_create():
        busy_turns.waiters["session-parent"] = asyncio.Event()
        busy = WorkerCoordinator(
            store=WorkerStore(tmp_path / "busy-state"),
            sessions=FakeSessions(tmp_path),
            turns=busy_turns,
            git=FakeGit(),
            events=FakeEvents(),
        )
        await busy.create(
            "session-parent",
            task="Racing baseline",
            ownership=("runtime",),
            model="openai:test",
        )

    with pytest.raises(RuntimeError, match="active turn"):
        asyncio.run(busy_create())


def test_running_worker_recovers_from_reopened_store_after_restart(tmp_path):
    state_dir = tmp_path / "state"
    first_store = WorkerStore(state_dir)
    first_store.create(
        WorkerRecord(
            worker_id="worker-restart",
            parent_session_id="session-parent",
            child_session_id="session-worker-restart",
            task="Resume durable task",
            ownership=("runtime/restart",),
            dependencies=(),
            model="openai:test",
            state=WorkerState.RUNNING,
        )
    )
    first_store.close()

    async def scenario():
        turns = FakeTurns()
        turns.waiters["session-worker-restart"] = asyncio.Event()
        coordinator = WorkerCoordinator(
            store=WorkerStore(state_dir),
            sessions=FakeSessions(tmp_path),
            turns=turns,
            git=FakeGit(),
            events=FakeEvents(),
        )
        assert await coordinator.recover() == 1
        turns.waiters["session-worker-restart"].set()
        await coordinator.wait_idle()
        return coordinator

    restarted = asyncio.run(scenario())

    assert restarted.load("worker-restart").state is WorkerState.SUCCEEDED


def test_restart_fails_closed_without_active_turn_or_durable_outcome(tmp_path):
    store = WorkerStore(tmp_path / "state")
    store.create(
        WorkerRecord(
            worker_id="worker-unknown",
            parent_session_id="session-parent",
            child_session_id="session-worker-unknown",
            task="Unknown crash window",
            ownership=("runtime/unknown",),
            dependencies=(),
            model="openai:test",
            state=WorkerState.RUNNING,
        )
    )
    coordinator = WorkerCoordinator(
        store=store,
        sessions=FakeSessions(tmp_path),
        turns=FakeTurns(),
        git=FakeGit(),
        events=FakeEvents(),
    )

    asyncio.run(coordinator.recover())

    record = coordinator.load("worker-unknown")
    assert record.state is WorkerState.FAILED
    assert record.error == "worker outcome unavailable after restart"


def test_restart_completes_durable_finalizing_worker(tmp_path):
    store = WorkerStore(tmp_path / "state")
    store.create(
        WorkerRecord(
            worker_id="worker-finalizing",
            parent_session_id="session-parent",
            child_session_id="session-worker-finalizing",
            task="Finalize durable task",
            ownership=("runtime/finalizing",),
            dependencies=(),
            model="openai:test",
            state=WorkerState.FINALIZING,
        )
    )
    git = FakeGit()
    git.clean.add("session-worker-finalizing")
    coordinator = WorkerCoordinator(
        store=store,
        sessions=FakeSessions(tmp_path),
        turns=FakeTurns(),
        git=git,
        events=FakeEvents(),
    )

    asyncio.run(coordinator.recover())

    recovered = coordinator.load("worker-finalizing")
    assert recovered.state is WorkerState.SUCCEEDED
    assert recovered.commit == "a" * 40


def test_restart_completes_durable_adoption_once(tmp_path):
    state_dir = tmp_path / "state"
    store = WorkerStore(state_dir)
    store.create(
        WorkerRecord(
            worker_id="worker-adopting",
            parent_session_id="session-parent",
            child_session_id="session-worker-adopting",
            task="Adopt durable task",
            ownership=("runtime/adopting",),
            dependencies=(),
            model="openai:test",
            state=WorkerState.ADOPTING,
            commit="a" * 40,
        )
    )
    git = FakeGit()
    git.clean.add("session-worker-adopting")
    coordinator = WorkerCoordinator(
        store=store,
        sessions=FakeSessions(tmp_path),
        turns=FakeTurns(),
        git=git,
        events=FakeEvents(),
    )

    asyncio.run(coordinator.recover())

    assert coordinator.load("worker-adopting").state is WorkerState.ADOPTED
    assert git.adopted == ["session-worker-adopting"]
