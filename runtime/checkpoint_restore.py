"""Crash-consistent orchestration for code and conversation restores."""

from __future__ import annotations

from typing import Protocol

from runtime.git import (
    CheckpointRestoreRecord,
    CheckpointRestoreScope,
    CheckpointRestoreState,
)


class RestoreGitControl(Protocol):
    def begin_restore(
        self,
        session_id: str,
        checkpoint_id: str,
        scope: CheckpointRestoreScope,
    ) -> CheckpointRestoreRecord: ...

    def pending_restores(self) -> list[CheckpointRestoreRecord]: ...

    def resume_restore_code(
        self,
        operation_id: str,
    ) -> dict[str, object]: ...

    def advance_restore(
        self,
        operation_id: str,
        state: CheckpointRestoreState,
    ) -> CheckpointRestoreRecord: ...

    def discard_restore_history(self, operation_id: str) -> int: ...

    def finish_restore(self, operation_id: str) -> bool: ...


class RestoreSessionControl(Protocol):
    def restore_conversation(
        self,
        session_id: str,
        *,
        message_count: int,
    ) -> bool: ...


class CheckpointRestoreCoordinator:
    def __init__(
        self,
        *,
        git: RestoreGitControl,
        sessions: RestoreSessionControl,
    ) -> None:
        self._git = git
        self._sessions = sessions

    def restore(
        self,
        session_id: str,
        checkpoint_id: str,
        scope: CheckpointRestoreScope,
    ) -> dict[str, object]:
        operation = self._git.begin_restore(
            session_id,
            checkpoint_id,
            scope,
        )
        return self._resume(operation)

    def reconcile(self) -> int:
        recovered = 0
        for operation in self._git.pending_restores():
            self._resume(operation)
            recovered += 1
        return recovered

    def _resume(
        self,
        operation: CheckpointRestoreRecord,
    ) -> dict[str, object]:
        if (
            operation.scope
            in {
                CheckpointRestoreScope.CODE,
                CheckpointRestoreScope.BOTH,
            }
            and operation.state is CheckpointRestoreState.PREPARED
        ):
            self._git.resume_restore_code(operation.operation_id)
            operation = self._git.advance_restore(
                operation.operation_id,
                CheckpointRestoreState.CODE_RESTORED,
            )

        if operation.scope in {
            CheckpointRestoreScope.CONVERSATION,
            CheckpointRestoreScope.BOTH,
        } and operation.state in {
            CheckpointRestoreState.PREPARED,
            CheckpointRestoreState.CODE_RESTORED,
        }:
            restored = self._sessions.restore_conversation(
                operation.session_id,
                message_count=operation.message_count,
            )
            if not restored:
                raise RuntimeError(
                    "checkpoint conversation not found"
                )
            operation = self._git.advance_restore(
                operation.operation_id,
                CheckpointRestoreState.CONVERSATION_RESTORED,
            )

        if operation.scope in {
            CheckpointRestoreScope.CONVERSATION,
            CheckpointRestoreScope.BOTH,
        }:
            self._git.discard_restore_history(
                operation.operation_id
            )

        if not self._git.finish_restore(operation.operation_id):
            raise RuntimeError("checkpoint restore journal was lost")
        return {
            "ok": True,
            "checkpoint_id": operation.checkpoint_id,
            "scope": operation.scope.value,
        }
