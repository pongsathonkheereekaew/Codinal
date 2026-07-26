"""Durable background-worker lifecycle orchestration."""

from __future__ import annotations

import asyncio
from pathlib import Path
from typing import Any
from uuid import uuid4

from .models import TERMINAL_WORKER_STATES, WorkerRecord, WorkerState
from .protocol import (
    PROTOCOL_VERSION,
    REQUIRED_CAPABILITIES,
    WorkerHello,
    negotiate,
)
from .store import WorkerStore


class WorkerCoordinator:
    def __init__(
        self,
        *,
        store: WorkerStore,
        sessions: Any,
        turns: Any,
        git: Any,
        events: Any,
        max_parallel: int = 8,
    ) -> None:
        self.store = store
        self._sessions = sessions
        self._turns = turns
        self._git = git
        self._events = events
        self._max_parallel = max_parallel
        self._monitors: dict[str, asyncio.Task[None]] = {}
        self._shutting_down = False

    async def create(
        self,
        parent_session_id: str,
        *,
        task: str,
        ownership: tuple[str, ...],
        model: str,
        dependencies: tuple[str, ...] = (),
        worker_kind: str = "local",
    ) -> WorkerRecord:
        if self._shutting_down:
            raise ValueError("worker coordinator is shutting down")
        if worker_kind != "local":
            raise ValueError("remote worker transport is unavailable")
        hello = WorkerHello(
            version=PROTOCOL_VERSION,
            worker_kind="local",
            capabilities=REQUIRED_CAPABILITIES,
        )
        capabilities = negotiate(hello)
        worker_id = f"worker-{uuid4()}"
        child_session_id = f"session-{worker_id}"
        candidate = WorkerRecord(
            worker_id=worker_id,
            parent_session_id=parent_session_id,
            child_session_id=child_session_id,
            task=task,
            ownership=tuple(ownership),
            dependencies=tuple(dependencies),
            model=model,
            worker_kind=hello.worker_kind,
            protocol_version=hello.version,
            capabilities=capabilities,
        )

        def prepare_if_ready() -> dict[str, Any]:
            self._validate_creation(candidate)
            if self._dependency_state(candidate) == "ready":
                return self._prepare_child(candidate)
            return {"ok": True, "prepared": False}

        created = await self._turns.mutate_when_idle(
            parent_session_id,
            prepare_if_ready,
        )
        if not created.get("ok"):
            raise ValueError(
                str(created.get("error", "worker session failed"))
            )
        record = self.store.create(candidate)
        dependency_state = self._dependency_state(record)
        if dependency_state == "failed":
            failed = self.store.transition(
                worker_id,
                expected={WorkerState.QUEUED},
                target=WorkerState.FAILED,
                error="worker dependency did not succeed",
            )
            assert failed is not None
            await self._publish(failed)
            return failed
        if dependency_state == "blocked":
            blocked = self.store.transition(
                worker_id,
                expected={WorkerState.QUEUED},
                target=WorkerState.BLOCKED,
            )
            assert blocked is not None
            await self._publish(blocked)
            return blocked
        if not created.get("prepared", True):
            return await self._prepare_and_launch(record)
        return await self._launch(record)

    def _validate_creation(self, candidate: WorkerRecord) -> None:
        self._validate_parent_workspace(candidate.parent_session_id)
        siblings = self.store.list(candidate.parent_session_id)
        active = [
            item
            for item in siblings
            if item.state not in TERMINAL_WORKER_STATES
        ]
        if len(active) >= self._max_parallel:
            raise ValueError("worker parallelism limit reached")
        if any(
            _scopes_overlap(candidate.ownership, item.ownership)
            and item.worker_id not in candidate.dependencies
            for item in active
        ):
            raise ValueError("worker ownership overlaps active work")
        for dependency_id in candidate.dependencies:
            dependency = self.store.load(dependency_id)
            if (
                dependency is None
                or dependency.parent_session_id
                != candidate.parent_session_id
            ):
                raise ValueError("invalid worker dependency")

    def _validate_parent_workspace(self, parent_session_id: str) -> None:
        git_loader = getattr(self._git, "load", None)
        if (
            callable(git_loader)
            and git_loader(parent_session_id) is None
        ):
            raise ValueError("workers require a Git workspace")
        parent_status = self._git.status(parent_session_id)
        if not parent_status.get("ok") or not parent_status.get("clean"):
            raise ValueError(
                "parent worktree must be clean before delegation"
            )

    def _prepare_child(self, record: WorkerRecord) -> dict[str, Any]:
        created = self._sessions.create_worker_session(
            record.parent_session_id,
            worker_id=record.worker_id,
            child_session_id=record.child_session_id,
            model=record.model,
        )
        if created.get("ok"):
            self._git.prepare(
                record.child_session_id,
                str(created["workspace"]),
            )
            return {**created, "prepared": True}
        return created

    async def _prepare_and_launch(
        self,
        record: WorkerRecord,
    ) -> WorkerRecord:
        try:
            def prepare() -> dict[str, Any]:
                self._validate_parent_workspace(
                    record.parent_session_id
                )
                return self._prepare_child(record)

            created = await self._turns.mutate_when_idle(
                record.parent_session_id,
                prepare,
            )
            if not created.get("ok"):
                raise ValueError(
                    str(created.get("error", "worker session failed"))
                )
        except Exception:
            failed = self.store.transition(
                record.worker_id,
                expected={record.state},
                target=WorkerState.FAILED,
                error="worker worktree could not be prepared",
            )
            if failed is not None:
                await self._publish(failed)
                return failed
            raise
        return await self._launch(record)

    def load(self, worker_id: str) -> WorkerRecord | None:
        return self.store.load(worker_id)

    def list(self, parent_session_id: str) -> list[WorkerRecord]:
        return self.store.list(parent_session_id)

    def steer(self, worker_id: str, text: str) -> bool:
        record = self._require(worker_id)
        if record.state is not WorkerState.RUNNING:
            return False
        return bool(self._turns.steer(record.child_session_id, text))

    async def cancel(self, worker_id: str) -> bool:
        record = self._require(worker_id)
        if (
            record.state in TERMINAL_WORKER_STATES
            or record.state is WorkerState.ADOPTING
        ):
            return False
        if record.state is WorkerState.RUNNING:
            self._turns.interrupt(record.child_session_id)
        cancelled = self.store.transition(
            worker_id,
            expected={record.state},
            target=WorkerState.CANCELLED,
        )
        monitor = self._monitors.pop(worker_id, None)
        if monitor is not None:
            monitor.cancel()
        if cancelled is not None:
            await self._publish(cancelled)
            return True
        return False

    async def adopt(self, worker_id: str) -> dict[str, object]:
        record = self._require(worker_id)
        if record.state is WorkerState.ADOPTED:
            return {
                "ok": True,
                "strategy": "already-applied",
                "commit": record.commit,
            }
        if record.state is not WorkerState.SUCCEEDED:
            raise ValueError("worker must have succeeded before adoption")
        if not record.commit:
            raise ValueError("worker has no committed changes to adopt")
        if self._turns.is_active(record.parent_session_id):
            raise ValueError("parent turn must be idle before adoption")
        adopting = self.store.transition(
            worker_id,
            expected={WorkerState.SUCCEEDED},
            target=WorkerState.ADOPTING,
        )
        if adopting is None:
            raise ValueError("worker adoption is already in progress")
        await self._publish(adopting)
        return await self._continue_adoption(adopting)

    async def recover(self) -> int:
        recovered = 0
        for record in self.store.list_non_terminal():
            if record.state is WorkerState.RUNNING:
                if self._turns.is_active(record.child_session_id):
                    self._attach_monitor(record)
                else:
                    failed = self.store.transition(
                        record.worker_id,
                        expected={record.state},
                        target=WorkerState.FAILED,
                        error="worker outcome unavailable after restart",
                    )
                    if failed is not None:
                        await self._publish(failed)
                recovered += 1
            elif record.state is WorkerState.FINALIZING:
                await self._finish(record)
                recovered += 1
            elif record.state is WorkerState.ADOPTING:
                try:
                    await self._continue_adoption(record)
                except Exception:
                    pass
                recovered += 1
            elif record.state in {WorkerState.QUEUED, WorkerState.BLOCKED}:
                await self._schedule_dependents(record.parent_session_id)
                recovered += 1
        return recovered

    async def wait_idle(self) -> None:
        while self._monitors:
            tasks = tuple(self._monitors.values())
            await asyncio.gather(*tasks, return_exceptions=True)

    async def shutdown(self) -> None:
        self._shutting_down = True
        tasks = tuple(self._monitors.values())
        self._monitors.clear()
        for task in tasks:
            task.cancel()
        if tasks:
            await asyncio.gather(*tasks, return_exceptions=True)

    async def _launch(self, record: WorkerRecord) -> WorkerRecord:
        running = self.store.transition(
            record.worker_id,
            expected={WorkerState.QUEUED},
            target=WorkerState.RUNNING,
        )
        if running is None:
            return self._require(record.worker_id)
        try:
            await self._turns.start(
                running.child_session_id,
                user_input=running.task,
                agent="worker",
                mode="auto",
                model=running.model,
                source={"kind": "worker", "worker_id": running.worker_id},
            )
        except Exception:
            failed = self.store.transition(
                running.worker_id,
                expected={WorkerState.RUNNING},
                target=WorkerState.FAILED,
                error="worker turn could not start",
            )
            assert failed is not None
            await self._publish(failed)
            return failed
        self._attach_monitor(running)
        await self._publish(running)
        return running

    def _attach_monitor(self, record: WorkerRecord) -> None:
        if record.worker_id in self._monitors:
            return
        self._monitors[record.worker_id] = asyncio.create_task(
            self._monitor(record)
        )

    async def _monitor(self, record: WorkerRecord) -> None:
        try:
            await self._turns.wait(record.child_session_id)
            current = self.store.load(record.worker_id)
            if (
                current is not None
                and current.state
                is WorkerState.RUNNING
            ):
                outcome = self._turns.outcome(record.child_session_id)
                if (
                    outcome is None
                    or outcome.get("type") != "turn_end"
                    or outcome.get("status") != "completed"
                ):
                    failed = self.store.transition(
                        record.worker_id,
                        expected={current.state},
                        target=WorkerState.FAILED,
                        error="worker turn did not complete",
                    )
                    if failed is not None:
                        await self._publish(failed)
                else:
                    finalizing = self.store.transition(
                        record.worker_id,
                        expected={current.state},
                        target=WorkerState.FINALIZING,
                    )
                    if finalizing is not None:
                        await self._publish(finalizing)
                        await self._finish(finalizing)
        except asyncio.CancelledError:
            raise
        except Exception:
            failed = self.store.transition(
                record.worker_id,
                expected={
                    WorkerState.RUNNING,
                    WorkerState.FINALIZING,
                },
                target=WorkerState.FAILED,
                error="worker completion failed",
            )
            if failed is not None:
                await self._publish(failed)
        finally:
            self._monitors.pop(record.worker_id, None)
            if not self._shutting_down:
                await self._schedule_dependents(record.parent_session_id)

    async def _finish(self, record: WorkerRecord) -> None:
        try:
            status = self._git.status(record.child_session_id)
            if not status.get("ok"):
                raise RuntimeError("worker Git status failed")
            commit = ""
            if status.get("clean", True):
                head_commit = str(status.get("head_commit", ""))
                base_commit = str(status.get("base_commit", ""))
                if head_commit and head_commit != base_commit:
                    commit = head_commit
            else:
                for path in record.ownership:
                    staged = self._git.stage(record.child_session_id, path)
                    if not staged.get("ok"):
                        raise RuntimeError("worker Git stage failed")
                committed = self._git.commit(
                    record.child_session_id,
                    f"Codinal worker: {record.task[:72]}",
                )
                if not committed.get("ok"):
                    raise RuntimeError("worker Git commit failed")
                commit = str(committed.get("commit", ""))
                final_status = self._git.status(record.child_session_id)
                if (
                    not final_status.get("ok")
                    or not final_status.get("clean")
                ):
                    raise RuntimeError("worker worktree is not clean")
            completed = self.store.transition(
                record.worker_id,
                expected={WorkerState.FINALIZING},
                target=WorkerState.SUCCEEDED,
                summary=_last_assistant_text(
                    self._sessions.messages(record.child_session_id)
                ),
                commit=commit,
            )
        except Exception:
            completed = self.store.transition(
                record.worker_id,
                expected={WorkerState.FINALIZING},
                target=WorkerState.FAILED,
                error="worker result could not be finalized",
            )
        if completed is not None:
            await self._publish(completed)

    async def _continue_adoption(
        self,
        record: WorkerRecord,
    ) -> dict[str, object]:
        def apply_to_parent() -> dict[str, object]:
            status = self._git.status(record.child_session_id)
            if not status.get("ok") or not status.get("clean"):
                raise ValueError("worker worktree is not clean")
            result = self._git.apply_back(record.child_session_id)
            if not result.get("ok"):
                raise ValueError("worker adoption failed")
            return result

        try:
            result = await self._turns.mutate_when_idle(
                record.parent_session_id,
                apply_to_parent,
            )
        except Exception:
            restored = self.store.transition(
                record.worker_id,
                expected={WorkerState.ADOPTING},
                target=WorkerState.SUCCEEDED,
            )
            if restored is not None:
                await self._publish(restored)
            raise
        adopted = self.store.transition(
            record.worker_id,
            expected={WorkerState.ADOPTING},
            target=WorkerState.ADOPTED,
        )
        if adopted is None:
            raise ValueError("worker adoption state changed")
        await self._publish(adopted)
        await self._schedule_dependents(adopted.parent_session_id)
        return result

    async def _schedule_dependents(self, parent_session_id: str) -> None:
        for record in self.store.list(parent_session_id):
            if record.state not in {WorkerState.QUEUED, WorkerState.BLOCKED}:
                continue
            state = self._dependency_state(record)
            if state == "failed":
                failed = self.store.transition(
                    record.worker_id,
                    expected={record.state},
                    target=WorkerState.FAILED,
                    error="worker dependency did not succeed",
                )
                if failed is not None:
                    await self._publish(failed)
            elif state == "ready":
                queued = record
                if record.state is WorkerState.BLOCKED:
                    queued = self.store.transition(
                        record.worker_id,
                        expected={WorkerState.BLOCKED},
                        target=WorkerState.QUEUED,
                    )
                if queued is not None:
                    await self._prepare_and_launch(queued)

    def _dependency_state(self, record: WorkerRecord) -> str:
        dependencies = [self.store.load(item) for item in record.dependencies]
        if any(
            item is None
            or item.state in {WorkerState.FAILED, WorkerState.CANCELLED}
            or (
                item.state is WorkerState.SUCCEEDED
                and not item.commit
            )
            for item in dependencies
        ):
            return "failed"
        if all(
            item is not None
            and item.state is WorkerState.ADOPTED
            for item in dependencies
        ):
            return "ready"
        return "blocked"

    def _require(self, worker_id: str) -> WorkerRecord:
        record = self.store.load(worker_id)
        if record is None:
            raise KeyError(worker_id)
        return record

    async def _publish(self, record: WorkerRecord) -> None:
        message = {
            "type": "worker_status",
            "worker": worker_to_dict(record),
        }
        await self._events.publish_session(record.parent_session_id, message)
        await self._events.publish_global(message)


def worker_to_dict(record: WorkerRecord) -> dict[str, object]:
    return {
        "worker_id": record.worker_id,
        "parent_session_id": record.parent_session_id,
        "child_session_id": record.child_session_id,
        "task": record.task,
        "ownership": list(record.ownership),
        "dependencies": list(record.dependencies),
        "model": record.model,
        "state": record.state.value,
        "worker_kind": record.worker_kind,
        "protocol_version": record.protocol_version,
        "capabilities": sorted(record.capabilities),
        "summary": record.summary,
        "error": record.error,
        "commit": record.commit,
        "created_at": record.created_at,
        "updated_at": record.updated_at,
    }


def _scopes_overlap(left: tuple[str, ...], right: tuple[str, ...]) -> bool:
    for first in left:
        first_path = Path(first)
        for second in right:
            second_path = Path(second)
            if (
                first_path == second_path
                or first_path in second_path.parents
                or second_path in first_path.parents
            ):
                return True
    return False


def _last_assistant_text(messages: list[dict[str, Any]]) -> str:
    for message in reversed(messages):
        if message.get("role") != "assistant":
            continue
        content = message.get("content", "")
        if isinstance(content, str):
            return content[: 64 * 1024]
    return ""
