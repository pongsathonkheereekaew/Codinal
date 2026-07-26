"""Persistent goal orchestration with bounded continuation and strict audits."""

from __future__ import annotations

import asyncio
import json
from dataclasses import replace
from datetime import datetime, timezone
from typing import Any
from uuid import uuid4

from .models import (
    TERMINAL_GOAL_STATES,
    GoalEvidence,
    GoalRecord,
    GoalRequirement,
    GoalState,
)
from .store import GoalStore


class GoalCoordinator:
    def __init__(
        self,
        *,
        store: GoalStore,
        sessions: Any,
        turns: Any,
        events: Any,
    ) -> None:
        self.store = store
        self._sessions = sessions
        self._turns = turns
        self._events = events
        self._monitors: dict[str, asyncio.Task[None]] = {}
        self._lock = asyncio.Lock()

    async def create(
        self,
        session_id: str,
        *,
        objective: str,
        requirements: tuple[dict[str, Any], ...],
        continuation_prompt: str,
        token_budget: int | None = None,
        time_budget_seconds: int | None = None,
    ) -> dict[str, Any]:
        if self._session(session_id) is None:
            raise KeyError(session_id)
        record = GoalRecord(
            goal_id=f"goal-{uuid4()}",
            session_id=session_id,
            objective=objective,
            requirements=tuple(
                GoalRequirement(
                    requirement_id=item["requirement_id"],
                    text=item["text"],
                )
                for item in requirements
            ),
            continuation_prompt=continuation_prompt,
            token_budget=token_budget,
            time_budget_seconds=time_budget_seconds,
        )
        created = self.store.create(record)
        await self._publish(created)
        return self._to_dict(created)

    def list(self, session_id: str) -> list[dict[str, Any]]:
        return [
            self._to_dict(self._refresh_budget(record))
            for record in self.store.list(session_id)
        ]

    def load(self, goal_id: str) -> dict[str, Any]:
        record = self._require(goal_id)
        refreshed = self._refresh_budget(record)
        return self._to_dict(refreshed)

    async def continue_goal(self, goal_id: str) -> dict[str, Any]:
        async with self._lock:
            record = self._refresh_budget(self._require(goal_id))
            if record.state is GoalState.EXHAUSTED:
                raise ValueError("goal budget is exhausted")
            if record.state is not GoalState.ACTIVE:
                raise ValueError("goal is not active")
            if record.continuation_running:
                raise ValueError("goal continuation is already running")
            session = self._session(record.session_id)
            if session is None:
                raise ValueError("goal session is unavailable")
            if self._turns.is_active(record.session_id):
                raise ValueError("goal session already has an active turn")
            baseline = len(self._sessions.messages(record.session_id))
            started = replace(
                record,
                continuation_count=record.continuation_count + 1,
                continuation_running=True,
                baseline_message_count=baseline,
                turn_started_at=_now(),
            )
            saved = self.store.save(
                started,
                expected_version=record.version,
            )
            if saved is None:
                raise ValueError("goal state changed")
            try:
                await self._turns.start(
                    record.session_id,
                    user_input=record.continuation_prompt,
                    workspace=session["workspace"],
                    agent=session["agent"],
                    mode=session["mode"],
                    model=session["model"],
                    source={
                        "kind": "goal_continuation",
                        "goal_id": record.goal_id,
                        "continuation_index": saved.continuation_count,
                    },
                )
            except Exception:
                rolled_back = self.store.save(
                    replace(
                        saved,
                        continuation_count=record.continuation_count,
                        continuation_running=False,
                        baseline_message_count=0,
                        continuation_turn_id="",
                        turn_started_at="",
                    ),
                    expected_version=saved.version,
                )
                if rolled_back is not None:
                    await self._publish(rolled_back)
                raise
            turn_id = str(
                self._turns.turn_id(record.session_id) or ""
            )
            bound = replace(saved, continuation_turn_id=turn_id)
            persisted = self.store.save(
                bound,
                expected_version=saved.version,
            )
            if persisted is None:
                persisted = bound
            self._attach_monitor(persisted)
            await self._publish(persisted)
            return self._to_dict(persisted)

    async def add_evidence(
        self,
        goal_id: str,
        *,
        requirement_id: str,
        kind: str,
        summary: str,
        result: str,
        passed: bool,
    ) -> dict[str, Any]:
        async with self._lock:
            record = self._require(goal_id)
            if record.state in TERMINAL_GOAL_STATES:
                raise ValueError("goal is already audited")
            if record.continuation_running:
                raise ValueError("goal continuation is still running")
            evidence = GoalEvidence(
                evidence_id=f"evidence-{uuid4()}",
                requirement_id=requirement_id,
                kind=kind,
                summary=summary,
                result=result,
                passed=passed,
                turn_index=record.continuation_count,
                observed_at=_now(),
            )
            if kind == "blocker" and any(
                item.kind == "blocker"
                and item.turn_index == evidence.turn_index
                for item in record.evidence
            ):
                raise ValueError("blocker evidence already recorded for turn")
            saved = self.store.save(
                replace(record, evidence=(*record.evidence, evidence)),
                expected_version=record.version,
            )
            if saved is None:
                raise ValueError("goal state changed")
            await self._publish(saved)
            return evidence.__dict__.copy()

    async def audit(
        self,
        goal_id: str,
        *,
        status: str,
        summary: str,
        requirement_evidence: dict[str, tuple[str, ...]],
    ) -> dict[str, Any]:
        async with self._lock:
            record = self._require(goal_id)
            if record.state in TERMINAL_GOAL_STATES:
                return self._to_dict(record)
            if record.continuation_running or self._turns.is_active(
                record.session_id
            ):
                raise ValueError("goal continuation is still running")
            if status == "complete":
                mapping = self._validate_completion(
                    record,
                    requirement_evidence,
                )
                target = GoalState.COMPLETED
            elif status == "blocked":
                self._validate_blocked(record, summary)
                mapping = ()
                target = GoalState.BLOCKED
            else:
                raise ValueError("invalid goal audit status")
            saved = self.store.save(
                replace(
                    record,
                    state=target,
                    audit_summary=summary,
                    requirement_evidence=mapping,
                ),
                expected_version=record.version,
            )
            if saved is None:
                raise ValueError("goal state changed")
            await self._publish(saved)
            return self._to_dict(saved)

    async def recover(self) -> int:
        recovered = 0
        for record in self.store.list_running():
            if self._turns.is_active(record.session_id):
                turn_id = self._turns.turn_id(record.session_id) or ""
                rebound = record
                if turn_id and turn_id != record.continuation_turn_id:
                    candidate = replace(
                        record,
                        continuation_turn_id=turn_id,
                    )
                    rebound = (
                        self.store.save(
                            candidate,
                            expected_version=record.version,
                        )
                        or candidate
                    )
                self._attach_monitor(rebound)
            else:
                exact = (
                    self._turns.receipt(record.continuation_turn_id)
                    if record.continuation_turn_id
                    else None
                )
                latest = (
                    self._turns.latest_receipt(record.session_id)
                    if not record.continuation_turn_id
                    else None
                )
                turn_id = (
                    str(exact["turn_id"])
                    if exact is not None
                    else (
                        str(latest["turn_id"])
                        if latest is not None
                        and int(latest["message_count"])
                        > record.baseline_message_count
                        else ""
                    )
                )
                await self._finalize(record.goal_id, turn_id)
            recovered += 1
        return recovered

    async def shutdown(self) -> None:
        monitors = tuple(self._monitors.values())
        for monitor in monitors:
            monitor.cancel()
        if monitors:
            await asyncio.gather(*monitors, return_exceptions=True)
        self._monitors.clear()

    async def wait_idle(self) -> None:
        while self._monitors:
            await asyncio.gather(
                *tuple(self._monitors.values()),
                return_exceptions=True,
            )

    def _attach_monitor(self, record: GoalRecord) -> None:
        if record.goal_id in self._monitors:
            return
        monitor = asyncio.create_task(self._monitor(record))
        self._monitors[record.goal_id] = monitor
        monitor.add_done_callback(
            lambda _task, goal_id=record.goal_id: self._monitors.pop(
                goal_id,
                None,
            )
        )

    async def _monitor(self, record: GoalRecord) -> None:
        try:
            await self._turns.wait_turn(record.continuation_turn_id)
        except asyncio.CancelledError:
            raise
        await self._finalize(
            record.goal_id,
            record.continuation_turn_id,
        )

    async def _finalize(self, goal_id: str, turn_id: str) -> None:
        async with self._lock:
            record = self._require(goal_id)
            if not record.continuation_running:
                return
            messages = self._sessions.messages(record.session_id)
            receipt = self._turns.receipt(turn_id) if turn_id else None
            message_end = (
                min(len(messages), int(receipt["message_count"]))
                if receipt is not None
                else min(
                    len(messages),
                    record.baseline_message_count,
                )
            )
            new_messages = messages[
                record.baseline_message_count : message_end
            ]
            used = _estimated_tokens(new_messages)
            outcome = (
                dict(receipt["outcome"])
                if receipt is not None
                else {
                "type": "interrupted",
                "status": "interrupted",
                }
            )
            result = str(outcome.get("status") or outcome.get("type") or "")
            evidence = GoalEvidence(
                evidence_id=f"evidence-{uuid4()}",
                requirement_id="",
                kind="turn",
                summary=_last_assistant_text(new_messages),
                result=result,
                passed=result == "completed",
                turn_index=record.continuation_count,
                observed_at=_now(),
            )
            candidate = replace(
                record,
                tokens_used=record.tokens_used + used,
                continuation_running=False,
                baseline_message_count=0,
                continuation_turn_id="",
                turn_started_at="",
                evidence=(*record.evidence, evidence),
            )
            candidate = replace(
                candidate,
                state=(
                    GoalState.EXHAUSTED
                    if _budget_exhausted(candidate)
                    else GoalState.ACTIVE
                ),
            )
            saved = self.store.save(
                candidate,
                expected_version=record.version,
            )
            if saved is None:
                raise ValueError("goal state changed")
            await self._publish(saved)

    def _validate_completion(
        self,
        record: GoalRecord,
        requirement_evidence: dict[str, tuple[str, ...]],
    ) -> tuple[tuple[str, tuple[str, ...]], ...]:
        required = {
            requirement.requirement_id
            for requirement in record.requirements
        }
        if set(requirement_evidence) != required:
            raise ValueError("completion requires every requirement")
        evidence = {item.evidence_id: item for item in record.evidence}
        for requirement_id, evidence_ids in requirement_evidence.items():
            if not evidence_ids or any(
                evidence_id not in evidence
                or evidence[evidence_id].requirement_id != requirement_id
                or evidence[evidence_id].kind != "verification"
                or not evidence[evidence_id].passed
                for evidence_id in evidence_ids
            ):
                raise ValueError(
                    "completion requires passing evidence for every requirement"
                )
        return tuple(
            (requirement_id, tuple(evidence_ids))
            for requirement_id, evidence_ids in sorted(
                requirement_evidence.items()
            )
        )

    @staticmethod
    def _validate_blocked(record: GoalRecord, summary: str) -> None:
        target = summary.strip().casefold()
        expected_turns = list(
            range(
                record.continuation_count - 2,
                record.continuation_count + 1,
            )
        )
        blockers = {
            item.turn_index: item
            for item in record.evidence
            if item.kind == "blocker"
            and item.summary.strip().casefold() == target
        }
        if (
            record.continuation_count < 3
            or any(index not in blockers for index in expected_turns)
        ):
            raise ValueError(
                "blocked audit requires the same blocker for three consecutive turns"
            )

    def _refresh_budget(self, record: GoalRecord) -> GoalRecord:
        if (
            record.state is GoalState.ACTIVE
            and not record.continuation_running
            and _budget_exhausted(record)
        ):
            saved = self.store.save(
                replace(record, state=GoalState.EXHAUSTED),
                expected_version=record.version,
            )
            return saved or record
        return record

    def _session(self, session_id: str) -> dict[str, Any] | None:
        return next(
            (
                session
                for session in self._sessions.list_sessions()
                if session["session_id"] == session_id
            ),
            None,
        )

    def _require(self, goal_id: str) -> GoalRecord:
        record = self.store.load(goal_id)
        if record is None:
            raise KeyError(goal_id)
        return record

    async def _publish(self, record: GoalRecord) -> None:
        message = {
            "type": "goal_status",
            "goal": self._to_dict(record),
        }
        await self._events.publish_session(record.session_id, message)
        await self._events.publish_global(message)

    def _to_dict(self, record: GoalRecord) -> dict[str, Any]:
        elapsed = _elapsed_seconds(record)
        return {
            "goal_id": record.goal_id,
            "session_id": record.session_id,
            "objective": record.objective,
            "requirements": [
                requirement.__dict__.copy()
                for requirement in record.requirements
            ],
            "continuation_prompt": record.continuation_prompt,
            "token_budget": record.token_budget,
            "time_budget_seconds": record.time_budget_seconds,
            "state": record.state.value,
            "tokens_used": record.tokens_used,
            "elapsed_seconds": elapsed,
            "continuation_count": record.continuation_count,
            "continuation_running": record.continuation_running,
            "evidence": [
                evidence.__dict__.copy()
                for evidence in record.evidence
            ],
            "audit_summary": record.audit_summary,
            "requirement_evidence": {
                requirement_id: list(evidence)
                for requirement_id, evidence in record.requirement_evidence
            },
            "created_at": record.created_at,
            "updated_at": record.updated_at,
        }


def _estimated_tokens(messages: list[dict[str, Any]]) -> int:
    if not messages:
        return 0
    payload = json.dumps(
        messages,
        allow_nan=False,
        ensure_ascii=False,
        separators=(",", ":"),
        default=str,
    ).encode("utf-8")
    return (len(payload) + 3) // 4


def _last_assistant_text(messages: list[dict[str, Any]]) -> str:
    for message in reversed(messages):
        if message.get("role") != "assistant":
            continue
        content = message.get("content")
        if isinstance(content, str) and content.strip():
            return _truncate_utf8(content.strip(), 8192)
    return "Goal continuation produced no assistant summary."


def _elapsed_seconds(record: GoalRecord) -> int:
    if not record.created_at:
        return 0
    try:
        created = datetime.fromisoformat(
            record.created_at.replace("Z", "+00:00")
        )
    except ValueError:
        return 0
    return max(
        0,
        int((datetime.now(timezone.utc) - created).total_seconds()),
    )


def _budget_exhausted(record: GoalRecord) -> bool:
    return bool(
        record.token_budget is not None
        and record.tokens_used >= record.token_budget
        or record.time_budget_seconds is not None
        and _elapsed_seconds(record) >= record.time_budget_seconds
    )


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(
        timespec="milliseconds"
    ).replace("+00:00", "Z")


def _truncate_utf8(value: str, maximum: int) -> str:
    encoded = value.encode("utf-8")
    if len(encoded) <= maximum:
        return value
    return encoded[:maximum].decode("utf-8", errors="ignore")
