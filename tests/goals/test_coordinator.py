import asyncio
from dataclasses import replace

import pytest

from runtime.goals import (
    GoalCoordinator,
    GoalEvidence,
    GoalRecord,
    GoalRequirement,
    GoalState,
    GoalStore,
)


class FakeSessions:
    def __init__(self):
        self._messages = {"session-parent": []}

    def list_sessions(self):
        return [
            {
                "session_id": "session-parent",
                "workspace": "/tmp/workspace",
                "agent": "code",
                "model": "openai:test",
                "mode": "interactive",
            }
        ]

    def messages(self, session_id):
        return list(self._messages.get(session_id, []))


class FakeTurns:
    def __init__(self, sessions):
        self.sessions = sessions
        self.started = []
        self.active = set()
        self.waiters = {}
        self.outcomes = {}
        self.turn_ids = {}
        self.turn_sessions = {}
        self.receipts = {}
        self.next_turn = 0

    async def start(self, session_id, **options):
        self.next_turn += 1
        turn_id = f"turn-test-{self.next_turn}"
        self.started.append((session_id, options))
        self.active.add(session_id)
        self.turn_ids[session_id] = turn_id
        self.turn_sessions[turn_id] = session_id
        self.waiters[session_id] = asyncio.Event()
        return {"ok": True, "session_id": session_id}

    async def wait(self, session_id):
        await self.waiters[session_id].wait()
        return True

    def is_active(self, session_id):
        return session_id in self.active

    def outcome(self, session_id):
        return self.outcomes.get(session_id)

    def turn_id(self, session_id):
        return self.turn_ids.get(session_id)

    def receipt(self, turn_id):
        return self.receipts.get(turn_id)

    def latest_receipt(self, session_id):
        for receipt in reversed(tuple(self.receipts.values())):
            if receipt["session_id"] == session_id:
                return receipt
        return None

    async def wait_turn(self, turn_id):
        session_id = self.turn_sessions[turn_id]
        await self.wait(session_id)
        return True

    def finish(self, session_id, text, status="completed"):
        self.sessions._messages[session_id].append(
            {"role": "assistant", "content": text}
        )
        self.outcomes[session_id] = {
            "type": "turn_end",
            "status": status,
        }
        turn_id = self.turn_ids[session_id]
        self.receipts[turn_id] = {
            "turn_id": turn_id,
            "session_id": session_id,
            "outcome": dict(self.outcomes[session_id]),
            "message_count": len(self.sessions._messages[session_id]),
        }
        self.active.discard(session_id)
        self.turn_ids.pop(session_id, None)
        self.waiters[session_id].set()


class FakeEvents:
    def __init__(self):
        self.messages = []

    async def publish_session(self, session_id, message):
        self.messages.append((session_id, message))

    async def publish_global(self, message):
        self.messages.append(("global", message))


def build_coordinator(tmp_path, *, token_budget=100):
    sessions = FakeSessions()
    turns = FakeTurns(sessions)
    coordinator = GoalCoordinator(
        store=GoalStore(tmp_path / "state"),
        sessions=sessions,
        turns=turns,
        events=FakeEvents(),
    )
    return coordinator, sessions, turns


def test_goal_continuation_persists_usage_and_turn_evidence(tmp_path):
    async def scenario():
        coordinator, _sessions, turns = build_coordinator(
            tmp_path,
            token_budget=4,
        )
        created = await coordinator.create(
            "session-parent",
            objective="Ship the parser",
            requirements=(
                {"requirement_id": "parser", "text": "Parser passes"},
            ),
            token_budget=4,
            time_budget_seconds=3600,
            continuation_prompt="Continue the goal and verify it.",
        )
        await coordinator.continue_goal(created["goal_id"])
        turns.finish("session-parent", "completed parser safely")
        await coordinator.wait_idle()
        return coordinator, created["goal_id"]

    coordinator, goal_id = asyncio.run(scenario())
    loaded = coordinator.load(goal_id)

    assert loaded["state"] == "exhausted"
    assert loaded["continuation_count"] == 1
    assert loaded["tokens_used"] >= 4
    assert loaded["continuation_running"] is False
    assert loaded["evidence"][0]["kind"] == "turn"
    assert loaded["evidence"][0]["turn_index"] == 1

    coordinator.store.close()
    reopened = GoalStore(tmp_path / "state")
    persisted = reopened.load(goal_id)
    assert persisted is not None
    assert persisted.state is GoalState.EXHAUSTED
    assert persisted.continuation_count == 1


def test_complete_audit_requires_passing_evidence_for_every_requirement(
    tmp_path,
):
    async def scenario():
        coordinator, _sessions, _turns = build_coordinator(tmp_path)
        created = await coordinator.create(
            "session-parent",
            objective="Ship safely",
            requirements=(
                {"requirement_id": "tests", "text": "Tests pass"},
                {"requirement_id": "build", "text": "Build passes"},
            ),
            continuation_prompt="Continue and verify.",
        )
        first = await coordinator.add_evidence(
            created["goal_id"],
            requirement_id="tests",
            kind="verification",
            summary="Focused tests",
            result="12 passed",
            passed=True,
        )
        with pytest.raises(ValueError, match="every requirement"):
            await coordinator.audit(
                created["goal_id"],
                status="complete",
                summary="Done",
                requirement_evidence={
                    "tests": (first["evidence_id"],),
                },
            )
        second = await coordinator.add_evidence(
            created["goal_id"],
            requirement_id="build",
            kind="verification",
            summary="Release build",
            result="PASS",
            passed=True,
        )
        completed = await coordinator.audit(
            created["goal_id"],
            status="complete",
            summary="All requirements verified",
            requirement_evidence={
                "tests": (first["evidence_id"],),
                "build": (second["evidence_id"],),
            },
        )
        return completed

    completed = asyncio.run(scenario())
    assert completed["state"] == "completed"
    assert completed["audit_summary"] == "All requirements verified"


def test_blocked_audit_requires_same_blocker_for_three_consecutive_turns(
    tmp_path,
):
    async def scenario():
        coordinator, _sessions, turns = build_coordinator(
            tmp_path,
            token_budget=10_000,
        )
        created = await coordinator.create(
            "session-parent",
            objective="Integrate unavailable API",
            requirements=(
                {"requirement_id": "api", "text": "API responds"},
            ),
            continuation_prompt="Retry the integration.",
        )
        for index in range(3):
            await coordinator.continue_goal(created["goal_id"])
            turns.finish("session-parent", f"attempt {index + 1}")
            await coordinator.wait_idle()
            await coordinator.add_evidence(
                created["goal_id"],
                requirement_id="api",
                kind="blocker",
                summary="Vendor API unavailable",
                result="HTTP 503",
                passed=False,
            )
            if index < 2:
                with pytest.raises(ValueError, match="three consecutive"):
                    await coordinator.audit(
                        created["goal_id"],
                        status="blocked",
                        summary="Vendor API unavailable",
                        requirement_evidence={},
                    )
        return await coordinator.audit(
            created["goal_id"],
            status="blocked",
            summary="Vendor API unavailable",
            requirement_evidence={},
        )

    blocked = asyncio.run(scenario())
    assert blocked["state"] == "blocked"
    assert blocked["audit_summary"] == "Vendor API unavailable"


def test_running_goal_continuation_recovers_once_after_restart(tmp_path):
    async def scenario():
        sessions = FakeSessions()
        turns = FakeTurns(sessions)
        store = GoalStore(tmp_path / "state")
        first = GoalCoordinator(
            store=store,
            sessions=sessions,
            turns=turns,
            events=FakeEvents(),
        )
        created = await first.create(
            "session-parent",
            objective="Recover this goal",
            requirements=(
                {"requirement_id": "restart", "text": "Resume once"},
            ),
            continuation_prompt="Continue after restart.",
        )
        await first.continue_goal(created["goal_id"])
        await asyncio.sleep(0)
        await first.shutdown()
        interrupted = store.load(created["goal_id"])
        assert interrupted is not None
        assert interrupted.continuation_running is True

        recovered = GoalCoordinator(
            store=store,
            sessions=sessions,
            turns=turns,
            events=FakeEvents(),
        )
        assert await recovered.recover() == 1
        turns.finish("session-parent", "recovered exactly once")
        await recovered.wait_idle()
        return recovered.load(created["goal_id"])

    goal = asyncio.run(scenario())
    assert goal["continuation_count"] == 1
    assert len(goal["evidence"]) == 1
    assert goal["evidence"][0]["summary"] == "recovered exactly once"


def test_recovery_does_not_reuse_receipt_before_turn_start(tmp_path):
    async def scenario():
        coordinator, sessions, turns = build_coordinator(tmp_path)
        sessions._messages["session-parent"].append(
            {"role": "assistant", "content": "previous turn"}
        )
        turns.receipts["turn-previous"] = {
            "turn_id": "turn-previous",
            "session_id": "session-parent",
            "outcome": {"type": "turn_end", "status": "completed"},
            "message_count": 1,
        }
        created = await coordinator.create(
            "session-parent",
            objective="Do not reuse prior receipts",
            requirements=(
                {"requirement_id": "fresh", "text": "Fresh turn starts"},
            ),
            continuation_prompt="Start a fresh turn.",
        )
        record = coordinator.store.load(created["goal_id"])
        assert record is not None
        marker = coordinator.store.save(
            replace(
                record,
                continuation_count=1,
                continuation_running=True,
                baseline_message_count=1,
                turn_started_at="2026-07-26T00:00:00Z",
            ),
            expected_version=record.version,
        )
        assert marker is not None

        assert await coordinator.recover() == 1
        return coordinator.load(created["goal_id"])

    goal = asyncio.run(scenario())

    assert goal["continuation_running"] is False
    assert goal["tokens_used"] == 0
    assert len(goal["evidence"]) == 1
    assert goal["evidence"][0]["result"] == "interrupted"
    assert goal["evidence"][0]["summary"] != "previous turn"


def test_recovery_does_not_replace_missing_bound_receipt(tmp_path):
    async def scenario():
        coordinator, sessions, turns = build_coordinator(tmp_path)
        created = await coordinator.create(
            "session-parent",
            objective="Fail closed on a missing bound receipt",
            requirements=(
                {"requirement_id": "bound", "text": "Use the bound turn"},
            ),
            continuation_prompt="Run the bound turn.",
        )
        await coordinator.continue_goal(created["goal_id"])
        marker = coordinator.store.load(created["goal_id"])
        assert marker is not None
        bound_turn_id = marker.continuation_turn_id
        await coordinator.shutdown()
        turns.finish("session-parent", "unpersisted goal result")
        turns.receipts.pop(bound_turn_id)
        sessions._messages["session-parent"].append(
            {"role": "assistant", "content": "later ordinary turn"}
        )
        turns.receipts["turn-later"] = {
            "turn_id": "turn-later",
            "session_id": "session-parent",
            "outcome": {"type": "turn_end", "status": "completed"},
            "message_count": 2,
        }

        restarted = GoalCoordinator(
            store=coordinator.store,
            sessions=sessions,
            turns=turns,
            events=FakeEvents(),
        )
        assert await restarted.recover() == 1
        return restarted.load(created["goal_id"])

    goal = asyncio.run(scenario())

    assert goal["tokens_used"] == 0
    assert goal["evidence"][0]["result"] == "interrupted"
    assert goal["evidence"][0]["summary"] != "later ordinary turn"


def test_goal_finalization_uses_bound_turn_receipt_not_later_messages(
    tmp_path,
):
    async def scenario():
        coordinator, sessions, turns = build_coordinator(tmp_path)
        created = await coordinator.create(
            "session-parent",
            objective="Keep turn accounting isolated",
            requirements=(
                {"requirement_id": "race", "text": "No later turn leakage"},
            ),
            continuation_prompt="Run the bound continuation.",
        )
        await coordinator.continue_goal(created["goal_id"])
        turns.finish("session-parent", "bound goal result")
        sessions._messages["session-parent"].append(
            {"role": "assistant", "content": "unrelated later turn"}
        )
        turns.outcomes["session-parent"] = {
            "type": "error",
            "status": "failed",
        }
        await coordinator.wait_idle()
        return coordinator.load(created["goal_id"])

    goal = asyncio.run(scenario())
    assert len(goal["evidence"]) == 1
    assert goal["evidence"][0]["summary"] == "bound goal result"
    assert goal["evidence"][0]["result"] == "completed"


def test_goal_does_not_claim_unpersisted_terminal_messages(tmp_path):
    async def scenario():
        coordinator, _sessions, turns = build_coordinator(tmp_path)
        created = await coordinator.create(
            "session-parent",
            objective="Require durable terminal evidence",
            requirements=(
                {"requirement_id": "durable", "text": "Receipt persists"},
            ),
            continuation_prompt="Persist before completion.",
        )
        await coordinator.continue_goal(created["goal_id"])
        turn_id = turns.turn_id("session-parent")
        turns.finish("session-parent", "not durably persisted")
        turns.receipts.pop(turn_id)
        await coordinator.wait_idle()
        return coordinator.load(created["goal_id"])

    goal = asyncio.run(scenario())

    assert goal["tokens_used"] == 0
    assert goal["evidence"][0]["result"] == "interrupted"
    assert goal["evidence"][0]["summary"] != "not durably persisted"


def test_goal_summary_truncates_multibyte_text_by_utf8_bytes(tmp_path):
    async def scenario():
        coordinator, _sessions, turns = build_coordinator(tmp_path)
        created = await coordinator.create(
            "session-parent",
            objective="Preserve Thai evidence",
            requirements=(
                {"requirement_id": "thai", "text": "Thai summary persists"},
            ),
            continuation_prompt="Continue in Thai.",
        )
        await coordinator.continue_goal(created["goal_id"])
        turns.finish("session-parent", "ก" * 3000)
        await coordinator.wait_idle()
        return coordinator.load(created["goal_id"])

    goal = asyncio.run(scenario())
    summary = goal["evidence"][0]["summary"]
    assert goal["continuation_running"] is False
    assert 0 < len(summary.encode("utf-8")) <= 8192


def test_goal_rejects_contradictory_passing_blocker(tmp_path):
    async def scenario():
        coordinator, _sessions, _turns = build_coordinator(tmp_path)
        created = await coordinator.create(
            "session-parent",
            objective="Reject contradictory evidence",
            requirements=(
                {"requirement_id": "api", "text": "API responds"},
            ),
            continuation_prompt="Retry API.",
        )
        with pytest.raises(ValueError, match="invalid goal evidence"):
            await coordinator.add_evidence(
                created["goal_id"],
                requirement_id="api",
                kind="blocker",
                summary="API unavailable",
                result="503",
                passed=True,
            )

    asyncio.run(scenario())


def test_goal_model_rejects_duplicate_audit_evidence_ids():
    evidence = GoalEvidence(
        evidence_id="evidence-pass",
        requirement_id="release",
        kind="verification",
        summary="Release suite",
        result="PASS",
        passed=True,
        turn_index=0,
        observed_at="2026-07-26T00:00:00Z",
    )

    with pytest.raises(ValueError, match="invalid goal audit mapping"):
        GoalRecord(
            goal_id="goal-bounded-audit",
            session_id="session-parent",
            objective="Bound audit mappings",
            requirements=(
                GoalRequirement(
                    requirement_id="release",
                    text="Release passes",
                ),
            ),
            continuation_prompt="Verify release.",
            evidence=(evidence,),
            requirement_evidence=(
                ("release", ("evidence-pass", "evidence-pass")),
            ),
        )
