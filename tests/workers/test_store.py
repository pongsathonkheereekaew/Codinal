from runtime.workers import (
    WorkerRecord,
    WorkerState,
    WorkerStore,
)


def record(**changes):
    values = {
        "worker_id": "worker-a",
        "parent_session_id": "session-parent",
        "child_session_id": "session-worker-a",
        "task": "Implement the parser",
        "ownership": ("runtime/parser",),
        "dependencies": (),
        "model": "openai:gpt-test",
        "state": WorkerState.QUEUED,
    }
    values.update(changes)
    return WorkerRecord(**values)


def test_worker_store_survives_restart_and_lists_parent_in_creation_order(
    tmp_path,
):
    first = WorkerStore(tmp_path)
    first.create(record(worker_id="worker-a"))
    first.create(
        record(
            worker_id="worker-b",
            child_session_id="session-worker-b",
            dependencies=("worker-a",),
            ownership=("tests/parser",),
        )
    )
    first.close()

    restarted = WorkerStore(tmp_path)

    assert [item.worker_id for item in restarted.list("session-parent")] == [
        "worker-a",
        "worker-b",
    ]
    assert restarted.load("worker-b") == record(
        worker_id="worker-b",
        child_session_id="session-worker-b",
        dependencies=("worker-a",),
        ownership=("tests/parser",),
    )


def test_worker_store_enforces_monotonic_compare_and_set_transitions(tmp_path):
    store = WorkerStore(tmp_path)
    store.create(record())

    running = store.transition(
        "worker-a",
        expected={WorkerState.QUEUED},
        target=WorkerState.RUNNING,
    )
    stale = store.transition(
        "worker-a",
        expected={WorkerState.QUEUED},
        target=WorkerState.CANCELLED,
    )
    finalizing = store.transition(
        "worker-a",
        expected={WorkerState.RUNNING},
        target=WorkerState.FINALIZING,
    )
    succeeded = store.transition(
        "worker-a",
        expected={WorkerState.FINALIZING},
        target=WorkerState.SUCCEEDED,
        summary="Parser tests pass",
        commit="a" * 40,
    )

    assert running is not None and running.state is WorkerState.RUNNING
    assert stale is None
    assert finalizing is not None
    assert succeeded is not None
    assert succeeded.summary == "Parser tests pass"
    assert succeeded.commit == "a" * 40


def test_worker_store_rejects_cross_parent_dependencies(tmp_path):
    store = WorkerStore(tmp_path)
    store.create(record(worker_id="worker-a"))

    try:
        store.create(
            record(
                worker_id="worker-b",
                parent_session_id="session-other",
                child_session_id="session-worker-b",
                dependencies=("worker-a",),
            )
        )
    except ValueError as error:
        assert str(error) == "worker dependency belongs to another parent"
    else:
        raise AssertionError("cross-parent dependency was accepted")


def test_worker_store_finds_child_session_and_non_terminal_records(tmp_path):
    store = WorkerStore(tmp_path)
    store.create(record(worker_id="worker-a"))
    store.create(
        record(
            worker_id="worker-b",
            child_session_id="session-worker-b",
        )
    )
    store.transition(
        "worker-a",
        expected={WorkerState.QUEUED},
        target=WorkerState.CANCELLED,
    )

    found = store.load_by_child_session("session-worker-b")

    assert found is not None
    assert found.worker_id == "worker-b"
    assert [item.worker_id for item in store.list_non_terminal()] == [
        "worker-b"
    ]
