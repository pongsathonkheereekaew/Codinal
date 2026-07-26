import sqlite3

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


def test_worker_store_transitions_selected_workers_atomically(tmp_path):
    store = WorkerStore(tmp_path)
    for suffix in ("a", "b"):
        store.create(
            record(
                worker_id=f"worker-{suffix}",
                child_session_id=f"session-worker-{suffix}",
            )
        )
        store.transition(
            f"worker-{suffix}",
            expected={WorkerState.QUEUED},
            target=WorkerState.RUNNING,
        )
        store.transition(
            f"worker-{suffix}",
            expected={WorkerState.RUNNING},
            target=WorkerState.FINALIZING,
        )
        store.transition(
            f"worker-{suffix}",
            expected={WorkerState.FINALIZING},
            target=WorkerState.SUCCEEDED,
            commit="a" * 40,
        )

    adopting = store.transition_many(
        ("worker-a", "worker-b"),
        expected={WorkerState.SUCCEEDED},
        target=WorkerState.ADOPTING,
    )
    stale = store.transition_many(
        ("worker-a", "worker-b"),
        expected={WorkerState.SUCCEEDED},
        target=WorkerState.ADOPTING,
    )

    assert adopting is not None
    assert {item.state for item in adopting} == {WorkerState.ADOPTING}
    assert stale is None
    assert {
        item.state for item in store.list("session-parent")
    } == {WorkerState.ADOPTING}


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


def test_worker_store_migrates_v1_records_to_comparison_metadata(tmp_path):
    initial = WorkerStore(tmp_path)
    initial.create(record())
    initial.close()
    connection = sqlite3.connect(tmp_path / "workers.db")
    with connection:
        connection.execute("DROP INDEX workers_build")
        connection.execute(
            "ALTER TABLE workers DROP COLUMN candidate_index"
        )
        connection.execute("ALTER TABLE workers DROP COLUMN plan_task_id")
        connection.execute("ALTER TABLE workers DROP COLUMN build_id")
        connection.execute("PRAGMA user_version = 1")
    connection.close()

    migrated = WorkerStore(tmp_path)
    loaded = migrated.load("worker-a")
    with sqlite3.connect(tmp_path / "workers.db") as connection:
        version = connection.execute("PRAGMA user_version").fetchone()[0]

    assert loaded is not None
    assert loaded.build_id == ""
    assert loaded.plan_task_id == ""
    assert loaded.candidate_index == -1
    assert version == 2
    assert len(list((tmp_path / "backups").glob("*.pre-v1-to-v2-*.bak"))) == 1
