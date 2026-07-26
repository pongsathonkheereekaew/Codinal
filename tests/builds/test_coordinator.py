import asyncio
from dataclasses import replace

import pytest

from runtime.builds import PlanBuildCoordinator, PlanBuildState, PlanBuildStore
from runtime.workers import WorkerRecord, WorkerState

PLAN_ID = "a" * 32


class FakePlans:
    def load_plan_artifact(self, session_id, plan_id):
        if session_id != "session-parent" or plan_id != PLAN_ID:
            return None
        return {
            "plan_id": PLAN_ID,
            "session_id": session_id,
            "status": "approved",
            "selected_task_ids": ["parser", "tests"],
            "tasks": [
                {
                    "id": "parser",
                    "title": "Implement parser",
                    "description": "Parse the new syntax.",
                    "verification": "Parser unit tests pass.",
                },
                {
                    "id": "tests",
                    "title": "Add integration tests",
                    "verification": "Integration suite passes.",
                },
            ],
        }


class FakeWorkers:
    def __init__(self):
        self.records = {}
        self.adopted = []
        self.cancelled = []
        self.validation_error = ""

    def validate_plan_build(self, _parent_session_id, _tasks):
        if self.validation_error:
            raise ValueError(self.validation_error)

    async def create(self, parent_session_id, **options):
        index = len(self.records)
        worker_id = f"worker-candidate-{index}"
        record = WorkerRecord(
            worker_id=worker_id,
            parent_session_id=parent_session_id,
            child_session_id=f"session-{worker_id}",
            task=options["task"],
            ownership=options["ownership"],
            dependencies=(),
            model=options["model"],
            state=WorkerState.RUNNING,
            build_id=options["build_id"],
            plan_task_id=options["plan_task_id"],
            candidate_index=options["candidate_index"],
        )
        self.records[worker_id] = record
        return record

    def load(self, worker_id):
        return self.records.get(worker_id)

    def comparison_diff(self, worker_id):
        record = self.records[worker_id]
        return {
            "worker_id": worker_id,
            "commit": record.commit,
            "summary": record.summary,
            "diff": f"+{record.model}",
            "output_truncated": False,
        }

    async def adopt_plan_build(self, build_id, worker_ids):
        for worker_id in worker_ids:
            assert build_id == self.records[worker_id].build_id
            self.adopted.append(worker_id)
            record = self.records[worker_id]
            self.records[worker_id] = replace(
                record,
                state=WorkerState.ADOPTED,
            )
        return {"ok": True, "strategy": "octopus"}

    async def cancel(self, worker_id):
        self.cancelled.append(worker_id)
        return True


class FakeEvents:
    def __init__(self):
        self.messages = []

    async def publish_session(self, session_id, message):
        self.messages.append((session_id, message))

    async def publish_global(self, message):
        self.messages.append(("global", message))


def request_tasks():
    return (
        {
            "task_id": "parser",
            "ownership": ["runtime/parser"],
            "candidates": [
                {"model": "openai:a"},
                {"model": "anthropic:b", "instruction": "Prefer clarity."},
            ],
        },
        {
            "task_id": "tests",
            "ownership": ["tests/parser"],
            "candidates": [
                {"model": "openai:a"},
                {"model": "google:c"},
            ],
        },
    )


def test_plan_build_dispatches_parallel_candidates_and_adopts_only_selections(
    tmp_path,
):
    async def scenario():
        workers = FakeWorkers()
        events = FakeEvents()
        coordinator = PlanBuildCoordinator(
            store=PlanBuildStore(tmp_path / "state"),
            plans=FakePlans(),
            workers=workers,
            events=events,
        )
        created = await coordinator.create(
            "session-parent",
            plan_id=PLAN_ID,
            tasks=request_tasks(),
        )
        assert created["state"] == "running"
        assert len(workers.records) == 4
        assert {
            record.plan_task_id for record in workers.records.values()
        } == {"parser", "tests"}

        for worker_id, record in tuple(workers.records.items()):
            workers.records[worker_id] = replace(
                record,
                state=WorkerState.SUCCEEDED,
                commit=str(record.candidate_index + 1) * 40,
                summary=f"Candidate {record.candidate_index}",
            )

        ready = coordinator.load(created["build_id"])
        assert ready["state"] == "ready"
        parser = ready["tasks"][0]["candidates"][1]["worker_id"]
        tests = ready["tasks"][1]["candidates"][0]["worker_id"]
        reviewed = coordinator.candidate_diff(
            created["build_id"],
            parser,
        )
        assert reviewed["verification"] == "Parser unit tests pass."
        assert reviewed["diff"] == "+anthropic:b"

        partially_selected = await coordinator.select(
            created["build_id"],
            parser,
        )
        assert partially_selected["state"] == "ready"
        selected = await coordinator.select(created["build_id"], tests)
        assert selected["state"] == "selected"
        adopted = await coordinator.adopt(created["build_id"])

        assert adopted["ok"] is True
        assert adopted["state"] == "adopted"
        assert workers.adopted == [parser, tests]
        assert {
            candidate["worker_id"]
            for task in adopted["tasks"]
            for candidate in task["candidates"]
            if candidate["selected"]
        } == {parser, tests}
        return coordinator, workers

    coordinator, workers = asyncio.run(scenario())
    assert len(coordinator.list("session-parent")) == 1
    assert len(workers.records) == 4


def test_plan_build_selection_survives_store_restart(tmp_path):
    async def create_and_select(store):
        workers = FakeWorkers()
        coordinator = PlanBuildCoordinator(
            store=store,
            plans=FakePlans(),
            workers=workers,
            events=FakeEvents(),
        )
        created = await coordinator.create(
            "session-parent",
            plan_id=PLAN_ID,
            tasks=(request_tasks()[0],),
        )
        for worker_id, record in tuple(workers.records.items()):
            workers.records[worker_id] = replace(
                record,
                state=WorkerState.SUCCEEDED,
                commit="a" * 40,
            )
        ready = coordinator.load(created["build_id"])
        winner = ready["tasks"][0]["candidates"][0]["worker_id"]
        await coordinator.select(created["build_id"], winner)
        return created["build_id"], winner, workers

    store = PlanBuildStore(tmp_path / "state")
    build_id, winner, workers = asyncio.run(create_and_select(store))
    store.close()

    reopened = PlanBuildStore(tmp_path / "state")
    coordinator = PlanBuildCoordinator(
        store=reopened,
        plans=FakePlans(),
        workers=workers,
        events=FakeEvents(),
    )
    loaded = coordinator.load(build_id)

    assert loaded["state"] == "selected"
    assert loaded["tasks"][0]["selected_worker_id"] == winner
    reopened.close()


def test_plan_build_only_reopens_selection_after_proven_no_apply(tmp_path):
    class FailingWorkers(FakeWorkers):
        def __init__(self, *, applied_before_failure):
            super().__init__()
            self.applied_before_failure = applied_before_failure

        async def adopt_plan_build(self, build_id, worker_ids):
            if self.applied_before_failure:
                for worker_id in worker_ids:
                    self.records[worker_id] = replace(
                        self.records[worker_id],
                        state=WorkerState.ADOPTED,
                    )
            raise RuntimeError("simulated adoption interruption")

    async def scenario(applied_before_failure, state_dir):
        workers = FailingWorkers(
            applied_before_failure=applied_before_failure,
        )
        coordinator = PlanBuildCoordinator(
            store=PlanBuildStore(state_dir),
            plans=FakePlans(),
            workers=workers,
            events=FakeEvents(),
        )
        created = await coordinator.create(
            "session-parent",
            plan_id=PLAN_ID,
            tasks=(request_tasks()[0],),
        )
        for worker_id, record in tuple(workers.records.items()):
            workers.records[worker_id] = replace(
                record,
                state=WorkerState.SUCCEEDED,
                commit="a" * 40,
            )
        ready = coordinator.load(created["build_id"])
        winner = ready["tasks"][0]["candidates"][0]["worker_id"]
        await coordinator.select(created["build_id"], winner)
        with pytest.raises(
            RuntimeError,
            match="simulated adoption interruption",
        ):
            await coordinator.adopt(created["build_id"])
        return coordinator.load(created["build_id"])["state"]

    safe_state = asyncio.run(
        scenario(False, tmp_path / "safe")
    )
    uncertain_state = asyncio.run(
        scenario(True, tmp_path / "uncertain")
    )

    assert safe_state == "selected"
    assert uncertain_state == "adopting"


def test_plan_build_rejects_unapproved_or_unselected_plan_task(tmp_path):
    coordinator = PlanBuildCoordinator(
        store=PlanBuildStore(tmp_path / "state"),
        plans=FakePlans(),
        workers=FakeWorkers(),
        events=FakeEvents(),
    )
    invalid = {
        **request_tasks()[0],
        "task_id": "not-selected",
    }

    with pytest.raises(ValueError, match="selected approved plan"):
        asyncio.run(
            coordinator.create(
                "session-parent",
                plan_id=PLAN_ID,
                tasks=(invalid,),
            )
        )
    assert coordinator.list("session-parent") == []


def test_plan_build_requires_a_committed_candidate_for_each_task(tmp_path):
    async def scenario():
        workers = FakeWorkers()
        coordinator = PlanBuildCoordinator(
            store=PlanBuildStore(tmp_path / "state"),
            plans=FakePlans(),
            workers=workers,
            events=FakeEvents(),
        )
        created = await coordinator.create(
            "session-parent",
            plan_id=PLAN_ID,
            tasks=(request_tasks()[0],),
        )
        for worker_id, record in tuple(workers.records.items()):
            workers.records[worker_id] = replace(
                record,
                state=WorkerState.SUCCEEDED,
                commit="",
                summary="No changes",
            )
        return coordinator.load(created["build_id"])

    failed = asyncio.run(scenario())

    assert failed["state"] == "failed"
    assert "no adoptable candidate" in failed["error"]


def test_plan_build_validates_capacity_before_persisting_or_dispatching(
    tmp_path,
):
    workers = FakeWorkers()
    workers.validation_error = "worker parallelism limit reached"
    coordinator = PlanBuildCoordinator(
        store=PlanBuildStore(tmp_path / "state"),
        plans=FakePlans(),
        workers=workers,
        events=FakeEvents(),
    )

    with pytest.raises(ValueError, match="parallelism limit"):
        asyncio.run(
            coordinator.create(
                "session-parent",
                plan_id=PLAN_ID,
                tasks=(request_tasks()[0],),
            )
        )

    assert workers.records == {}
    assert coordinator.list("session-parent") == []
