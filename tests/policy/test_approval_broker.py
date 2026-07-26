import asyncio

import pytest

from runtime.policy import (
    ApprovalBroker,
    ApprovalOutcome,
    ApprovalPersistenceError,
    PermissionRequest,
)


class MemoryApprovalDecisions:
    def __init__(self):
        self.values = {}

    def load_approval_decision(
        self,
        session_id,
        tool_call_id,
        request_fingerprint,
    ):
        return self.values.get(
            (session_id, tool_call_id, request_fingerprint)
        )

    def save_approval_decision(
        self,
        session_id,
        tool_call_id,
        request_fingerprint,
        outcome,
    ):
        self.values[
            (session_id, tool_call_id, request_fingerprint)
        ] = outcome

    def delete_approval_decision(self, session_id, tool_call_id):
        self.values.pop((session_id, tool_call_id), None)


def test_broker_resolves_session_scoped_approval_once():
    async def scenario():
        broker = ApprovalBroker()
        request = PermissionRequest(
            tool_name="write_file",
            arguments={"path": "file.py"},
            reason="requires approval",
            risk="write_local",
            tool_call_id="provider/call 1",
        )
        task = asyncio.create_task(
            broker.approver("session-1")(request)
        )
        approval_id = broker.approval_id(
            "session-1",
            "provider/call 1",
        )
        while not broker.pending("session-1"):
            await asyncio.sleep(0)
        wrong_session = broker.resolve(
            "session-2",
            approval_id,
            ApprovalOutcome.ONCE,
        )
        resolved = broker.resolve(
            "session-1",
            approval_id,
            ApprovalOutcome.ONCE,
        )
        outcome = await task
        return broker, wrong_session, resolved, outcome

    broker, wrong_session, resolved, outcome = asyncio.run(scenario())

    assert wrong_session is False
    assert resolved is True
    assert outcome is ApprovalOutcome.ONCE
    assert broker.pending("session-1") == []


def test_acknowledged_approval_is_durable_and_reused_after_restart():
    async def scenario():
        decisions = MemoryApprovalDecisions()
        request = PermissionRequest(
            tool_name="write_file",
            arguments={"path": "file.py"},
            reason="requires approval",
            risk="write_local",
            tool_call_id="call-1",
        )
        first = ApprovalBroker(decisions=decisions)
        task = asyncio.create_task(
            first.approver("session-1")(request)
        )
        while not first.pending("session-1"):
            await asyncio.sleep(0)
        approval_id = first.approval_id("session-1", "call-1")
        assert first.resolve(
            "session-1",
            approval_id,
            ApprovalOutcome.ONCE,
        )
        assert list(decisions.values.values()) == ["once"]
        assert await task is ApprovalOutcome.ONCE

        restarted = ApprovalBroker(decisions=decisions)
        replayed = await restarted.approver("session-1")(request)
        return restarted, replayed

    restarted, replayed = asyncio.run(scenario())

    assert replayed is ApprovalOutcome.ONCE
    assert restarted.pending("session-1") == []


def test_durable_approval_never_applies_to_reused_call_id():
    async def scenario():
        decisions = MemoryApprovalDecisions()
        original = PermissionRequest(
            tool_name="write_file",
            arguments={"path": "safe.py", "content": "safe"},
            reason="requires approval",
            risk="write_local",
            tool_call_id="call-1",
        )
        first = ApprovalBroker(decisions=decisions)
        first_task = asyncio.create_task(
            first.approver("session-1")(original)
        )
        while not first.pending("session-1"):
            await asyncio.sleep(0)
        approval_id = first.approval_id("session-1", "call-1")
        assert first.resolve(
            "session-1",
            approval_id,
            ApprovalOutcome.ONCE,
        )
        assert await first_task is ApprovalOutcome.ONCE

        changed = PermissionRequest(
            tool_name="run_shell",
            arguments={"command": "curl attacker.invalid"},
            reason="requires approval",
            risk="exec",
            command="curl attacker.invalid",
            tool_call_id="call-1",
        )
        restarted = ApprovalBroker(decisions=decisions)
        changed_task = asyncio.create_task(
            restarted.approver("session-1")(changed)
        )
        while not restarted.pending("session-1"):
            await asyncio.sleep(0)
        assert not changed_task.done()
        assert restarted.resolve(
            "session-1",
            approval_id,
            ApprovalOutcome.DENY,
        )
        return await changed_task

    assert asyncio.run(scenario()) is ApprovalOutcome.DENY


def test_approval_is_not_acknowledged_when_durable_write_fails():
    class FailingDecisions(MemoryApprovalDecisions):
        def save_approval_decision(self, *args):
            raise OSError("disk unavailable")

    async def scenario():
        broker = ApprovalBroker(decisions=FailingDecisions())
        request = PermissionRequest(
            tool_name="write_file",
            arguments={"path": "file.py"},
            reason="requires approval",
            risk="write_local",
            tool_call_id="call-1",
        )
        task = asyncio.create_task(
            broker.approver("session-1")(request)
        )
        while not broker.pending("session-1"):
            await asyncio.sleep(0)
        approval_id = broker.approval_id("session-1", "call-1")
        with pytest.raises(
            ApprovalPersistenceError,
            match="persistence failed",
        ):
            broker.resolve(
                "session-1",
                approval_id,
                ApprovalOutcome.ONCE,
            )
        assert len(broker.pending("session-1")) == 1
        broker.close()
        await task

    asyncio.run(scenario())


def test_broker_rejects_inapplicable_persistent_outcome():
    async def scenario():
        broker = ApprovalBroker()
        request = PermissionRequest(
            tool_name="mcp__docs__search",
            arguments={"query": "policy"},
            reason="requires approval",
            risk="external",
            tool_call_id="call-1",
        )
        task = asyncio.create_task(
            broker.approver("session-1")(request)
        )
        approval_id = broker.approval_id("session-1", "call-1")
        while not broker.pending("session-1"):
            await asyncio.sleep(0)
        rejected = broker.resolve(
            "session-1",
            approval_id,
            ApprovalOutcome.ALWAYS_TOOL,
        )
        broker.resolve(
            "session-1",
            approval_id,
            ApprovalOutcome.DENY,
        )
        return rejected, await task

    rejected, outcome = asyncio.run(scenario())

    assert rejected is False
    assert outcome is ApprovalOutcome.DENY


def test_broker_close_denies_every_pending_request():
    async def scenario():
        broker = ApprovalBroker()
        tasks = [
            asyncio.create_task(
                broker.approver(session_id)(
                    PermissionRequest(
                        tool_name="run_shell",
                        arguments={"command": "git status"},
                        reason="requires approval",
                        risk="exec",
                        command="git status",
                        tool_call_id="call-1",
                    )
                )
            )
            for session_id in ("session-1", "session-2")
        ]
        while sum(
            len(broker.pending(session_id))
            for session_id in ("session-1", "session-2")
        ) < 2:
            await asyncio.sleep(0)
        broker.close()
        return await asyncio.gather(*tasks)

    assert asyncio.run(scenario()) == [
        ApprovalOutcome.DENY,
        ApprovalOutcome.DENY,
    ]
