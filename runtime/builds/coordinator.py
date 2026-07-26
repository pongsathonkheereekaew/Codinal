"""Plan-to-parallel-build and explicit best-of-N adoption."""

from __future__ import annotations

from dataclasses import replace
from typing import Any
from uuid import uuid4

from runtime.workers import WorkerState

from .models import (
    PlanBuildCandidate,
    PlanBuildRecord,
    PlanBuildState,
    PlanBuildTask,
)
from .store import PlanBuildStore

_CANDIDATE_TERMINAL_STATES = {
    WorkerState.SUCCEEDED,
    WorkerState.ADOPTED,
    WorkerState.FAILED,
    WorkerState.CANCELLED,
}
class PlanBuildCoordinator:
    def __init__(
        self,
        *,
        store: PlanBuildStore,
        plans: Any,
        workers: Any,
        events: Any,
    ) -> None:
        self.store = store
        self._plans = plans
        self._workers = workers
        self._events = events

    async def create(
        self,
        parent_session_id: str,
        *,
        plan_id: str,
        tasks: tuple[dict[str, Any], ...],
    ) -> dict[str, Any]:
        artifact = self._plans.load_plan_artifact(
            parent_session_id,
            plan_id,
        )
        if (
            artifact is None
            or artifact.get("status") != "approved"
        ):
            raise ValueError("build requires a selected approved plan")
        selected_ids = set(artifact.get("selected_task_ids", []))
        artifact_tasks = {
            task["id"]: task
            for task in artifact.get("tasks", [])
            if isinstance(task, dict) and isinstance(task.get("id"), str)
        }
        requested_ids = {task.get("task_id") for task in tasks}
        if (
            not tasks
            or not requested_ids <= selected_ids
            or any(task_id not in artifact_tasks for task_id in requested_ids)
        ):
            raise ValueError("build requires a selected approved plan task")
        build_tasks = tuple(
            self._build_task(request, artifact_tasks[request["task_id"]])
            for request in tasks
        )
        self._workers.validate_plan_build(
            parent_session_id,
            build_tasks,
        )
        record = self.store.create(
            PlanBuildRecord(
                build_id=f"build-{uuid4()}",
                parent_session_id=parent_session_id,
                plan_id=plan_id,
                tasks=build_tasks,
            )
        )
        started: list[str] = []
        try:
            for task in record.tasks:
                for index, candidate in enumerate(task.candidates):
                    worker = await self._workers.create(
                        parent_session_id,
                        task=_candidate_prompt(task, candidate),
                        ownership=task.ownership,
                        model=candidate.model,
                        build_id=record.build_id,
                        plan_task_id=task.task_id,
                        candidate_index=index,
                    )
                    started.append(worker.worker_id)
                    record = self.store.attach_candidate(
                        record.build_id,
                        task.task_id,
                        index,
                        worker.worker_id,
                    )
            running = self.store.transition(
                record.build_id,
                expected={PlanBuildState.DISPATCHING},
                target=PlanBuildState.RUNNING,
            )
            if running is None:
                raise ValueError("plan build dispatch state changed")
            await self._publish(running)
            return self._to_dict(running)
        except Exception:
            failed = self.store.transition(
                record.build_id,
                expected={PlanBuildState.DISPATCHING},
                target=PlanBuildState.FAILED,
                error="plan build candidate dispatch failed",
            )
            for worker_id in started:
                try:
                    await self._workers.cancel(worker_id)
                except Exception:
                    pass
            if failed is not None:
                await self._publish(failed)
            raise

    def load(self, build_id: str) -> dict[str, Any]:
        record = self.store.load(build_id)
        if record is None:
            raise KeyError(build_id)
        record = self._refresh(record)
        return self._to_dict(record)

    def list(self, parent_session_id: str) -> list[dict[str, Any]]:
        return [
            self._to_dict(self._refresh(record))
            for record in self.store.list(parent_session_id)
        ]

    def candidate_diff(
        self,
        build_id: str,
        worker_id: str,
    ) -> dict[str, Any]:
        record = self.store.load(build_id)
        if record is None:
            raise KeyError(build_id)
        for task in record.tasks:
            candidate = next(
                (
                    item
                    for item in task.candidates
                    if item.worker_id == worker_id
                ),
                None,
            )
            if candidate is None:
                continue
            result = self._workers.comparison_diff(worker_id)
            return {
                **result,
                "build_id": build_id,
                "task_id": task.task_id,
                "title": task.title,
                "verification": task.verification,
                "model": candidate.model,
            }
        raise ValueError("worker is not a candidate in this plan build")

    async def select(
        self,
        build_id: str,
        worker_id: str,
    ) -> dict[str, Any]:
        current = self.store.load(build_id)
        if current is None:
            raise KeyError(build_id)
        current = self._refresh(current)
        if current.state not in {
            PlanBuildState.READY,
            PlanBuildState.SELECTED,
        }:
            raise ValueError("plan build is not ready for selection")
        worker = self._workers.load(worker_id)
        if (
            worker is None
            or worker.state is not WorkerState.SUCCEEDED
            or not worker.commit
            or worker.build_id != build_id
        ):
            raise ValueError("selected candidate has not succeeded")
        selected = self.store.select(build_id, worker_id)
        if all(task.selected_worker_id for task in selected.tasks):
            if selected.state is PlanBuildState.READY:
                transitioned = self.store.transition(
                    build_id,
                    expected={PlanBuildState.READY},
                    target=PlanBuildState.SELECTED,
                )
                if transitioned is None:
                    raise ValueError("plan build selection state changed")
                selected = transitioned
        await self._publish(selected)
        return self._to_dict(selected)

    async def adopt(self, build_id: str) -> dict[str, Any]:
        current = self.store.load(build_id)
        if current is None:
            raise KeyError(build_id)
        if current.state is PlanBuildState.ADOPTED:
            return {
                "ok": True,
                "state": "adopted",
                **self._to_dict(current),
            }
        if current.state is not PlanBuildState.SELECTED:
            raise ValueError("all plan tasks require an explicit selection")
        adopting = self.store.transition(
            build_id,
            expected={PlanBuildState.SELECTED},
            target=PlanBuildState.ADOPTING,
        )
        if adopting is None:
            raise ValueError("plan build adoption is already in progress")
        await self._publish(adopting)
        return await self._continue_adoption(adopting)

    async def recover(self) -> int:
        recovered = 0
        for record in self.store.list_non_terminal():
            if record.state is PlanBuildState.DISPATCHING:
                for task in record.tasks:
                    for candidate in task.candidates:
                        if not candidate.worker_id:
                            continue
                        try:
                            await self._workers.cancel(candidate.worker_id)
                        except Exception:
                            pass
                failed = self.store.transition(
                    record.build_id,
                    expected={PlanBuildState.DISPATCHING},
                    target=PlanBuildState.FAILED,
                    error="plan build dispatch interrupted",
                )
                if failed is not None:
                    await self._publish(failed)
                recovered += 1
            elif record.state is PlanBuildState.ADOPTING:
                try:
                    await self._continue_adoption(record)
                except Exception:
                    pass
                recovered += 1
            else:
                self._refresh(record)
                recovered += 1
        return recovered

    async def shutdown(self) -> None:
        return None

    def is_selected(self, build_id: str, worker_id: str) -> bool:
        record = self.store.load(build_id)
        return bool(
            record is not None
            and record.state
            in {
                PlanBuildState.SELECTED,
                PlanBuildState.ADOPTING,
                PlanBuildState.ADOPTED,
            }
            and any(
                task.selected_worker_id == worker_id
                for task in record.tasks
            )
        )

    async def _continue_adoption(
        self,
        record: PlanBuildRecord,
    ) -> dict[str, Any]:
        try:
            result = await self._workers.adopt_plan_build(
                record.build_id,
                tuple(
                    task.selected_worker_id
                    for task in record.tasks
                ),
            )
        except Exception:
            selected_workers = tuple(
                self._workers.load(task.selected_worker_id)
                for task in record.tasks
            )
            if all(
                worker is not None
                and worker.state is WorkerState.SUCCEEDED
                for worker in selected_workers
            ):
                restored = self.store.transition(
                    record.build_id,
                    expected={PlanBuildState.ADOPTING},
                    target=PlanBuildState.SELECTED,
                )
                if restored is not None:
                    await self._publish(restored)
            raise
        adopted = self.store.transition(
            record.build_id,
            expected={PlanBuildState.ADOPTING},
            target=PlanBuildState.ADOPTED,
        )
        if adopted is None:
            raise ValueError("plan build adoption state changed")
        await self._publish(adopted)
        return {
            "ok": True,
            "state": "adopted",
            "result": result,
            **self._to_dict(adopted),
        }

    def _refresh(self, record: PlanBuildRecord) -> PlanBuildRecord:
        if record.state is not PlanBuildState.RUNNING:
            return record
        workers = [
            self._workers.load(candidate.worker_id)
            for task in record.tasks
            for candidate in task.candidates
        ]
        if any(worker is None for worker in workers):
            return record
        if not all(
            worker.state in _CANDIDATE_TERMINAL_STATES
            for worker in workers
        ):
            return record
        for task in record.tasks:
            task_workers = [
                self._workers.load(candidate.worker_id)
                for candidate in task.candidates
            ]
            if not any(
                worker is not None
                and _is_adoptable(worker)
                for worker in task_workers
            ):
                failed = self.store.transition(
                    record.build_id,
                    expected={PlanBuildState.RUNNING},
                    target=PlanBuildState.FAILED,
                    error=(
                        "no adoptable candidate completed for task "
                        f"{task.task_id}"
                    ),
                )
                return failed or record
        ready = self.store.transition(
            record.build_id,
            expected={PlanBuildState.RUNNING},
            target=PlanBuildState.READY,
        )
        return ready or record

    def _to_dict(self, record: PlanBuildRecord) -> dict[str, Any]:
        return {
            "build_id": record.build_id,
            "parent_session_id": record.parent_session_id,
            "plan_id": record.plan_id,
            "state": record.state.value,
            "error": record.error,
            "tasks": [
                {
                    "task_id": task.task_id,
                    "title": task.title,
                    "description": task.description,
                    "verification": task.verification,
                    "ownership": list(task.ownership),
                    "selected_worker_id": task.selected_worker_id,
                    "candidates": [
                        self._candidate_dict(
                            candidate,
                            candidate.worker_id
                            == task.selected_worker_id,
                        )
                        for candidate in task.candidates
                    ],
                }
                for task in record.tasks
            ],
            "created_at": record.created_at,
            "updated_at": record.updated_at,
        }

    def _candidate_dict(
        self,
        candidate: PlanBuildCandidate,
        selected: bool,
    ) -> dict[str, Any]:
        worker = (
            self._workers.load(candidate.worker_id)
            if candidate.worker_id
            else None
        )
        return {
            "model": candidate.model,
            "instruction": candidate.instruction,
            "worker_id": candidate.worker_id,
            "selected": selected,
            "selectable": bool(
                worker is not None
                and worker.state is WorkerState.SUCCEEDED
                and worker.commit
            ),
            "state": worker.state.value if worker is not None else "dispatching",
            "summary": worker.summary if worker is not None else "",
            "commit": worker.commit if worker is not None else "",
            "error": worker.error if worker is not None else "",
        }

    def _build_task(
        self,
        request: dict[str, Any],
        artifact_task: dict[str, Any],
    ) -> PlanBuildTask:
        return PlanBuildTask(
            task_id=request["task_id"],
            title=artifact_task["title"],
            description=artifact_task.get("description", ""),
            verification=artifact_task["verification"],
            ownership=tuple(request["ownership"]),
            candidates=tuple(
                PlanBuildCandidate(
                    model=candidate["model"],
                    instruction=candidate.get("instruction", ""),
                )
                for candidate in request["candidates"]
            ),
        )

    async def _publish(self, record: PlanBuildRecord) -> None:
        message = {
            "type": "plan_build_status",
            "build": self._to_dict(record),
        }
        await self._events.publish_session(record.parent_session_id, message)
        await self._events.publish_global(message)


def _candidate_prompt(
    task: PlanBuildTask,
    candidate: PlanBuildCandidate,
) -> str:
    parts = [
        task.title,
        task.description,
        f"Verification: {task.verification}",
    ]
    if candidate.instruction:
        parts.append(f"Candidate instruction: {candidate.instruction}")
    return "\n\n".join(part for part in parts if part)


def _is_adoptable(worker: Any) -> bool:
    return bool(
        worker.state in {WorkerState.SUCCEEDED, WorkerState.ADOPTED}
        and worker.commit
    )
