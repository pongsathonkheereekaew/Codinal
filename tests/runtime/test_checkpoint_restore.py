from dataclasses import replace

import pytest

from runtime.checkpoint_restore import CheckpointRestoreCoordinator
from runtime.git import (
    CheckpointRestoreRecord,
    CheckpointRestoreScope,
    CheckpointRestoreState,
)


class FakeGit:
    def __init__(self):
        self.operation = None
        self.checkpoint_exists = True
        self.actions = []

    def begin_restore(self, session_id, checkpoint_id, scope):
        self.operation = CheckpointRestoreRecord(
            operation_id="a" * 32,
            checkpoint_id=checkpoint_id,
            session_id=session_id,
            scope=scope,
            state=CheckpointRestoreState.PREPARED,
            message_count=2,
            code_before_tree="b" * 40 if scope.value != "conversation" else "",
            code_after_tree="c" * 40 if scope.value != "conversation" else "",
            discard_checkpoint_ids=(
                (checkpoint_id,)
                if scope.value != "code"
                else ()
            ),
        )
        self.actions.append("begin")
        return self.operation

    def pending_restores(self):
        return [self.operation] if self.operation is not None else []

    def resume_restore_code(self, _operation_id):
        self.actions.append("code")
        return {"ok": True}

    def advance_restore(self, _operation_id, state):
        self.operation = replace(self.operation, state=state)
        self.actions.append(state.value)
        return self.operation

    def load_checkpoint(self, _checkpoint_id):
        return object() if self.checkpoint_exists else None

    def discard_restore_history(self, _operation_id):
        return self.discard_checkpoint_history(
            "session-1",
            "d" * 32,
        )

    def discard_checkpoint_history(self, _session_id, _checkpoint_id):
        self.actions.append("discard")
        self.checkpoint_exists = False
        return 1

    def finish_restore(self, _operation_id):
        self.actions.append("finish")
        self.operation = None
        return True


class FakeSessions:
    def __init__(self, *, fail=False):
        self.fail = fail
        self.actions = []

    def restore_conversation(self, _session_id, *, message_count):
        self.actions.append(message_count)
        if self.fail:
            raise OSError("disk unavailable")
        return True


def test_combined_restore_journals_each_durable_boundary():
    git = FakeGit()
    sessions = FakeSessions()
    coordinator = CheckpointRestoreCoordinator(
        git=git,
        sessions=sessions,
    )

    result = coordinator.restore(
        "session-1",
        "d" * 32,
        CheckpointRestoreScope.BOTH,
    )

    assert result["scope"] == "both"
    assert git.actions == [
        "begin",
        "code",
        "code_restored",
        "conversation_restored",
        "discard",
        "finish",
    ]
    assert sessions.actions == [2]


def test_reconcile_completes_after_conversation_failure():
    git = FakeGit()
    sessions = FakeSessions(fail=True)
    coordinator = CheckpointRestoreCoordinator(
        git=git,
        sessions=sessions,
    )

    with pytest.raises(OSError, match="disk unavailable"):
        coordinator.restore(
            "session-1",
            "d" * 32,
            CheckpointRestoreScope.BOTH,
        )

    assert git.operation.state is CheckpointRestoreState.CODE_RESTORED
    sessions.fail = False
    assert coordinator.reconcile() == 1
    assert git.operation is None
    assert git.actions[-3:] == [
        "conversation_restored",
        "discard",
        "finish",
    ]


def test_reconcile_finishes_if_history_was_already_discarded():
    git = FakeGit()
    sessions = FakeSessions()
    git.operation = CheckpointRestoreRecord(
        operation_id="a" * 32,
        checkpoint_id="d" * 32,
        session_id="session-1",
        scope=CheckpointRestoreScope.BOTH,
        state=CheckpointRestoreState.CONVERSATION_RESTORED,
        message_count=2,
        code_before_tree="b" * 40,
        code_after_tree="c" * 40,
        discard_checkpoint_ids=("d" * 32,),
    )
    git.checkpoint_exists = False
    coordinator = CheckpointRestoreCoordinator(
        git=git,
        sessions=sessions,
    )

    assert coordinator.reconcile() == 1

    assert git.actions == ["discard", "finish"]
    assert sessions.actions == []
