"""Sandboxed one-session/one-branch/one-worktree lifecycle."""

from __future__ import annotations

import hashlib
import os
import re
import secrets
import signal
import shlex
import shutil
import stat
import subprocess
import tempfile
import threading
from dataclasses import dataclass, replace
from pathlib import Path
from typing import Callable, Optional

from runtime.sandbox import SandboxedShell

from .models import (
    CheckpointCaptureMode,
    CheckpointFileRecord,
    CheckpointRestoreRecord,
    CheckpointRestoreScope,
    CheckpointRestoreState,
    CheckpointState,
    CodeCheckpointRecord,
    GitWorkspaceRecord,
    WorktreeState,
)
from .store import GitWorktreeStore

_PROBE_TIMEOUT_SECONDS = 10
_PROBE_OUTPUT_LIMIT = 1024 * 1024
_PREIMAGE_UNSET = object()
_MAX_CHECKPOINT_PATCH_BYTES = 32 * 1024 * 1024
_MAX_CHECKPOINT_FILE_BYTES = 32 * 1024 * 1024


class _BoundedOutput:
    def __init__(self, maximum: int) -> None:
        self.remaining = maximum
        self.buffers = [bytearray(), bytearray()]
        self.truncated = False
        self.lock = threading.Lock()

    def drain(self, index: int, stream) -> None:
        try:
            while chunk := stream.read(16 * 1024):
                with self.lock:
                    accepted = min(len(chunk), self.remaining)
                    if accepted:
                        self.buffers[index].extend(chunk[:accepted])
                        self.remaining -= accepted
                    if accepted < len(chunk):
                        self.truncated = True
        finally:
            stream.close()


@dataclass(frozen=True)
class _ProbeResult:
    returncode: int
    stdout: str
    stderr: str
    output_truncated: bool = False


@dataclass(frozen=True)
class _MutationRecorder:
    service: "GitWorktreeService"
    session_id: str

    def record_file_preimage(
        self,
        path: Path,
        *,
        content: bytes | None | object = _PREIMAGE_UNSET,
        mode: int = 0,
    ) -> None:
        self.service.record_file_preimage(
            self.session_id,
            path,
            content=content,
            mode=mode,
        )

    def record_shell_fallback(self) -> None:
        self.service.record_shell_fallback(self.session_id)


@dataclass(frozen=True)
class _ComposedCheckpointPatch:
    path: Path
    before_tree: str
    after_tree: str


class GitWorkspaceError(RuntimeError):
    """A stable, user-displayable Git workspace lifecycle failure."""


class DetachedHeadError(GitWorkspaceError):
    """The selected source worktree has no named branch to apply back to."""


class NotGitRepositoryError(GitWorkspaceError):
    """The selected folder is not inside a non-bare Git worktree."""


class GitWorktreeService:
    def __init__(
        self,
        data_dir: str | Path,
        *,
        store: Optional[GitWorktreeStore] = None,
        git_executable: Optional[str | Path] = None,
    ) -> None:
        self.data_dir = Path(data_dir).expanduser().resolve()
        self.data_dir.mkdir(mode=0o700, parents=True, exist_ok=True)
        self.worktree_base = self.data_dir / "worktrees"
        self.worktree_base.mkdir(mode=0o700, parents=True, exist_ok=True)
        self.sandbox_base = self.data_dir / "git-sandbox"
        self.sandbox_base.mkdir(mode=0o700, parents=True, exist_ok=True)
        self.checkpoint_base = self.data_dir / "checkpoints"
        self.checkpoint_base.mkdir(
            mode=0o700,
            parents=True,
            exist_ok=True,
        )
        for directory in (
            self.data_dir,
            self.worktree_base,
            self.sandbox_base,
            self.checkpoint_base,
        ):
            try:
                os.chmod(directory, 0o700)
            except OSError:
                pass
        self.store = store or GitWorktreeStore(self.data_dir)
        self.git_executable = Path(
            git_executable or _discover_git()
        ).expanduser().resolve()
        self._lock = threading.RLock()
        self._process_lock = threading.Lock()
        self._active_shells: dict[str, set[SandboxedShell]] = {}

    def close(self) -> None:
        self.store.close()

    def load(self, session_id: str) -> Optional[GitWorkspaceRecord]:
        if self.store.is_plain_workspace(session_id):
            return None
        return self.store.load(session_id)

    def prepare_plain(
        self,
        session_id: str,
        workspace: str | Path,
    ) -> Path:
        root = Path(workspace).expanduser().resolve()
        with self._lock:
            existing = self.store.load_plain_workspace(session_id)
            if existing is not None:
                if existing != root:
                    raise GitWorkspaceError(
                        "session workspace does not match state"
                    )
                return existing
            if self.store.load(session_id) is not None:
                raise GitWorkspaceError(
                    "session already has a Git workspace"
                )
            return self.store.save_plain_workspace(
                session_id,
                root,
            )

    def has_checkpoint_session(self, session_id: str) -> bool:
        return self.store.load(session_id) is not None

    def is_plain_session(self, session_id: str) -> bool:
        return self.store.is_plain_workspace(session_id)

    def status(self, session_id: str) -> dict[str, object]:
        record = self._usable_record(session_id)
        result = self._execute_worktree(
            record,
            "status",
            "--porcelain=v1",
            "--branch",
            "--untracked-files=all",
        )
        if result.exit_code != 0:
            return {"ok": False, "error": "git status failed"}
        lines = result.stdout.splitlines()
        changes = [
            line
            for line in lines
            if not line.startswith("## ")
        ]
        return {
            "ok": True,
            "branch": record.session_branch,
            "base_commit": record.base_commit,
            "clean": not changes,
            "porcelain": result.stdout,
            "output_truncated": result.output_truncated,
        }

    def begin_checkpoint(
        self,
        session_id: str,
        *,
        message_count: int,
        attributed: bool = False,
    ) -> CodeCheckpointRecord | None:
        if self.store.load(session_id) is None:
            return None
        if (
            not isinstance(message_count, int)
            or message_count < 0
        ):
            raise ValueError("invalid checkpoint message count")
        with self._lock:
            pending = self.store.pending_checkpoint(session_id)
            if pending is not None:
                if (
                    pending.after_tree
                    and pending.after_message_count == message_count
                ):
                    self._finalize_checkpoint_locked(
                        session_id,
                        pending.checkpoint_id,
                    )
                else:
                    raise GitWorkspaceError(
                        "session already has a pending checkpoint"
                    )
            record = self._checkpoint_record(session_id)
            if (
                self.store.is_plain_workspace(session_id)
                and not attributed
            ):
                raise GitWorkspaceError(
                    "plain workspace checkpoints require attribution"
                )
            checkpoint_id = secrets.token_hex(16)
            capture_mode = (
                CheckpointCaptureMode.ATTRIBUTED
                if attributed
                else CheckpointCaptureMode.WHOLE_TREE
            )
            before_tree = (
                ""
                if attributed
                else self._snapshot_tree(
                    record,
                    checkpoint_id,
                )
            )
            checkpoint = CodeCheckpointRecord(
                checkpoint_id=checkpoint_id,
                session_id=session_id,
                before_tree=before_tree,
                before_message_count=message_count,
                capture_mode=capture_mode,
            )
            try:
                return self.store.save_checkpoint(checkpoint)
            except Exception:
                self._delete_checkpoint_ref(
                    record,
                    checkpoint_id,
                    "before",
                )
                raise

    def mutation_recorder(self, session_id: str) -> _MutationRecorder:
        return _MutationRecorder(self, session_id)

    def record_file_preimage(
        self,
        session_id: str,
        path: Path,
        *,
        content: bytes | None | object = _PREIMAGE_UNSET,
        mode: int = 0,
    ) -> None:
        with self._lock:
            record = self._checkpoint_record(session_id)
            checkpoint = self.store.pending_checkpoint(session_id)
            if checkpoint is None:
                raise GitWorkspaceError(
                    "pending checkpoint not found"
                )
            candidate = Path(path)
            if (
                candidate.is_absolute()
                and not candidate.is_relative_to(
                    record.worktree_path
                )
            ):
                return
            relative = self._checkpoint_relative_path(
                record,
                candidate,
            )
            existing = {
                item.path
                for item in self.store.list_checkpoint_files(
                    checkpoint.checkpoint_id
                )
            }
            if relative in existing:
                return
            try:
                if content is _PREIMAGE_UNSET:
                    blob, captured_mode = self._capture_file_blob(
                        record,
                        path,
                    )
                else:
                    blob, captured_mode = self._capture_preimage_bytes(
                        record,
                        content,
                        mode,
                    )
                self.store.save_checkpoint_file(
                    CheckpointFileRecord(
                        checkpoint_id=checkpoint.checkpoint_id,
                        path=relative,
                        before_blob=blob,
                        before_mode=captured_mode,
                    )
                )
                self._refresh_attributed_before_tree(
                    record,
                    checkpoint.checkpoint_id,
                )
            except Exception:
                self.store.delete_checkpoint_files(
                    checkpoint.checkpoint_id,
                    (relative,),
                )
                self._refresh_attributed_before_tree(
                    record,
                    checkpoint.checkpoint_id,
                )
                self._prune_checkpoint_repository(record)
                raise

    def apply_file_delta(
        self,
        session_id: str,
        paths: tuple[Path, ...],
        apply_delta: Callable[[], bool],
    ) -> bool:
        with self._lock:
            checkpoint = self.store.pending_checkpoint(session_id)
            if checkpoint is None:
                raise GitWorkspaceError(
                    "pending checkpoint not found"
                )
            before = {
                item.path
                for item in self.store.list_checkpoint_files(
                    checkpoint.checkpoint_id
                )
            }
            added: tuple[str, ...] = ()
            applied = False
            try:
                for path in paths:
                    self.record_file_preimage(session_id, path)
                after = {
                    item.path
                    for item in self.store.list_checkpoint_files(
                        checkpoint.checkpoint_id
                    )
                }
                added = tuple(sorted(after - before))
                applied = bool(apply_delta())
                return applied
            finally:
                if not applied:
                    current = {
                        item.path
                        for item in self.store.list_checkpoint_files(
                            checkpoint.checkpoint_id
                        )
                    }
                    added = tuple(sorted(current - before))
                    self.store.delete_checkpoint_files(
                        checkpoint.checkpoint_id,
                        added,
                    )
                    if added:
                        record = self._checkpoint_record(session_id)
                        self._refresh_attributed_before_tree(
                            record,
                            checkpoint.checkpoint_id,
                        )
                        self._prune_checkpoint_repository(record)

    def record_shell_fallback(self, session_id: str) -> None:
        with self._lock:
            if self.store.is_plain_workspace(session_id):
                raise GitWorkspaceError(
                    "plain workspace shell requires a transaction"
                )
            record = self._checkpoint_record(session_id)
            checkpoint = self.store.pending_checkpoint(session_id)
            if checkpoint is None:
                raise GitWorkspaceError(
                    "pending checkpoint not found"
                )
            if (
                checkpoint.capture_mode
                is CheckpointCaptureMode.WHOLE_TREE
            ):
                return
            before_tree = self._snapshot_tree(
                record,
                checkpoint.checkpoint_id,
            )
            self.store.save_checkpoint(
                replace(
                    checkpoint,
                    before_tree=before_tree,
                    capture_mode=CheckpointCaptureMode.WHOLE_TREE,
                )
            )

    def complete_checkpoint(
        self,
        session_id: str,
        checkpoint_id: str,
        *,
        message_count: int,
    ) -> CodeCheckpointRecord:
        self.capture_checkpoint(
            session_id,
            checkpoint_id,
            message_count=message_count,
        )
        return self.finalize_checkpoint(
            session_id,
            checkpoint_id,
        )

    def capture_checkpoint(
        self,
        session_id: str,
        checkpoint_id: str,
        *,
        message_count: int,
    ) -> CodeCheckpointRecord:
        with self._lock:
            record = self._checkpoint_record(session_id)
            checkpoint = self.store.load_checkpoint(checkpoint_id)
            if (
                checkpoint is None
                or checkpoint.session_id != session_id
                or checkpoint.state is not CheckpointState.PENDING
            ):
                raise GitWorkspaceError(
                    "pending checkpoint not found"
                )
            if (
                not isinstance(message_count, int)
                or message_count < checkpoint.before_message_count
            ):
                raise ValueError("invalid checkpoint message count")
            files = self.store.list_checkpoint_files(checkpoint_id)
            captured_files = [
                replace(
                    item,
                    after_blob=blob,
                    after_mode=mode,
                )
                for item in files
                for blob, mode in [
                    self._capture_file_blob(
                        record,
                        record.worktree_path / item.path,
                    )
                ]
            ]
            for item in captured_files:
                self.store.save_checkpoint_file(item)
            if (
                checkpoint.capture_mode
                is CheckpointCaptureMode.ATTRIBUTED
            ):
                before_tree = self._checkpoint_file_tree(
                    record,
                    checkpoint_id,
                    captured_files,
                    phase="before",
                )
                after_tree = self._checkpoint_file_tree(
                    record,
                    checkpoint_id,
                    captured_files,
                    phase="after",
                )
            else:
                before_tree = (
                    self._checkpoint_file_tree(
                        record,
                        checkpoint_id,
                        captured_files,
                        phase="before",
                        base_tree=checkpoint.before_tree,
                    )
                    if captured_files
                    else checkpoint.before_tree
                )
                whole_after_tree = self._snapshot_tree(
                    record,
                    checkpoint_id,
                    phase="after",
                )
                after_tree = (
                    self._checkpoint_file_tree(
                        record,
                        checkpoint_id,
                        captured_files,
                        phase="after",
                        base_tree=whole_after_tree,
                    )
                    if captured_files
                    else whole_after_tree
                )
            captured = replace(
                checkpoint,
                before_tree=before_tree,
                after_tree=after_tree,
                after_message_count=message_count,
            )
            try:
                return self.store.save_checkpoint(captured)
            except Exception:
                if checkpoint.after_tree:
                    restored = self._set_checkpoint_ref(
                        record,
                        checkpoint_id,
                        "after",
                        checkpoint.after_tree,
                    )
                    if not restored:
                        raise GitWorkspaceError(
                            "unable to preserve pending checkpoint"
                        ) from None
                else:
                    self._delete_checkpoint_ref(
                        record,
                        checkpoint_id,
                        "after",
                    )
                raise

    def finalize_checkpoint(
        self,
        session_id: str,
        checkpoint_id: str,
    ) -> CodeCheckpointRecord:
        with self._lock:
            return self._finalize_checkpoint_locked(
                session_id,
                checkpoint_id,
            )

    def _finalize_checkpoint_locked(
        self,
        session_id: str,
        checkpoint_id: str,
    ) -> CodeCheckpointRecord:
        checkpoint = self.store.load_checkpoint(checkpoint_id)
        if (
            checkpoint is None
            or checkpoint.session_id != session_id
            or checkpoint.state is not CheckpointState.PENDING
            or not checkpoint.after_tree
        ):
            raise GitWorkspaceError(
                "captured checkpoint not found"
            )
        return self.store.save_checkpoint(
            replace(
                checkpoint,
                state=CheckpointState.COMPLETED,
            )
        )

    def pending_checkpoint(
        self,
        session_id: str,
    ) -> CodeCheckpointRecord | None:
        return self.store.pending_checkpoint(session_id)

    def pending_checkpoints(self) -> list[CodeCheckpointRecord]:
        return self.store.pending_checkpoints()

    def list_checkpoints(
        self,
        session_id: str,
    ) -> list[CodeCheckpointRecord]:
        self._checkpoint_record(session_id)
        return self.store.list_checkpoints(session_id)

    def load_checkpoint(
        self,
        checkpoint_id: str,
    ) -> CodeCheckpointRecord | None:
        return self.store.load_checkpoint(checkpoint_id)

    def begin_restore(
        self,
        session_id: str,
        checkpoint_id: str,
        scope: CheckpointRestoreScope,
    ) -> CheckpointRestoreRecord:
        with self._lock:
            existing = self.store.pending_restore(session_id)
            if existing is not None:
                if (
                    existing.checkpoint_id == checkpoint_id
                    and existing.scope is scope
                ):
                    return existing
                raise GitWorkspaceError(
                    "session already has a pending checkpoint restore"
                )
            record = self._checkpoint_record(session_id)
            checkpoint, history = self._restore_checkpoint_history(
                session_id,
                checkpoint_id,
            )
            operation_id = secrets.token_hex(16)
            before_tree = ""
            after_tree = ""
            if scope in {
                CheckpointRestoreScope.CODE,
                CheckpointRestoreScope.BOTH,
            }:
                composed = self._composed_checkpoint_patch(
                    record,
                    history,
                    reverse=False,
                )
                try:
                    before_tree = composed.before_tree
                    after_tree = composed.after_tree
                finally:
                    composed.path.unlink(missing_ok=True)
            restore = CheckpointRestoreRecord(
                operation_id=operation_id,
                checkpoint_id=checkpoint_id,
                session_id=session_id,
                scope=scope,
                state=CheckpointRestoreState.PREPARED,
                message_count=checkpoint.before_message_count,
                code_before_tree=before_tree,
                code_after_tree=after_tree,
                discard_checkpoint_ids=(
                    tuple(
                        item.checkpoint_id
                        for item in history
                    )
                    if scope
                    in {
                        CheckpointRestoreScope.CONVERSATION,
                        CheckpointRestoreScope.BOTH,
                    }
                    else ()
                ),
            )
            saved = self.store.save_restore(restore)
            if (
                scope
                in {
                    CheckpointRestoreScope.CODE,
                    CheckpointRestoreScope.BOTH,
                }
                and not self._ensure_restore_refs(record, saved)
            ):
                raise GitWorkspaceError(
                    "unable to retain checkpoint restore"
                )
            return saved

    def pending_restores(self) -> list[CheckpointRestoreRecord]:
        return self.store.pending_restores()

    def has_pending_restore(self, session_id: str) -> bool:
        return self.store.pending_restore(session_id) is not None

    def advance_restore(
        self,
        operation_id: str,
        state: CheckpointRestoreState,
    ) -> CheckpointRestoreRecord:
        with self._lock:
            restore = self.store.load_restore(operation_id)
            if restore is None:
                raise GitWorkspaceError(
                    "checkpoint restore not found"
                )
            allowed = {
                CheckpointRestoreScope.CODE: {
                    CheckpointRestoreState.CODE_RESTORED,
                },
                CheckpointRestoreScope.CONVERSATION: {
                    CheckpointRestoreState.CONVERSATION_RESTORED,
                },
                CheckpointRestoreScope.BOTH: {
                    CheckpointRestoreState.CODE_RESTORED,
                },
            }
            if state is restore.state:
                return restore
            valid = (
                restore.state is CheckpointRestoreState.PREPARED
                and state in allowed[restore.scope]
            ) or (
                restore.scope is CheckpointRestoreScope.BOTH
                and restore.state
                is CheckpointRestoreState.CODE_RESTORED
                and state
                is CheckpointRestoreState.CONVERSATION_RESTORED
            )
            if not valid:
                raise GitWorkspaceError(
                    "invalid checkpoint restore transition"
                )
            return self.store.save_restore(
                replace(restore, state=state)
            )

    def resume_restore_code(
        self,
        operation_id: str,
    ) -> dict[str, object]:
        with self._lock:
            restore = self.store.load_restore(operation_id)
            if (
                restore is None
                or restore.scope
                not in {
                    CheckpointRestoreScope.CODE,
                    CheckpointRestoreScope.BOTH,
                }
            ):
                raise GitWorkspaceError(
                    "checkpoint restore not found"
                )
            record = self._checkpoint_record(restore.session_id)
            if not self._ensure_restore_refs(record, restore):
                raise GitWorkspaceError(
                    "unable to retain checkpoint restore"
                )
            _checkpoint, history = self._restore_checkpoint_history(
                restore.session_id,
                restore.checkpoint_id,
            )
            current_tree = self._effective_current_tree(
                record,
                history,
                f"resume-{operation_id}",
            )
            if current_tree == restore.code_after_tree:
                return {
                    "ok": True,
                    "checkpoint_id": restore.checkpoint_id,
                    "scope": "code",
                }
            if current_tree != restore.code_before_tree:
                raise GitWorkspaceError(
                    "checkpoint restore state diverged"
                )
            patch_path = self._tree_patch(
                record,
                restore.code_before_tree,
                restore.code_after_tree,
                f"journal-{operation_id}",
            )
            self._apply_restore_patch(record, patch_path)
            verified_tree = self._effective_current_tree(
                record,
                history,
                f"verify-{operation_id}",
            )
            if verified_tree != restore.code_after_tree:
                raise GitWorkspaceError(
                    "checkpoint restore verification failed"
                )
            return {
                "ok": True,
                "checkpoint_id": restore.checkpoint_id,
                "scope": "code",
            }

    def discard_restore_history(self, operation_id: str) -> int:
        with self._lock:
            restore = self.store.load_restore(operation_id)
            if restore is None:
                raise GitWorkspaceError(
                    "checkpoint restore not found"
                )
            record = self._checkpoint_record(restore.session_id)
            for checkpoint_id in restore.discard_checkpoint_ids:
                before_deleted = self._delete_checkpoint_ref(
                    record,
                    checkpoint_id,
                    "before",
                )
                after_deleted = self._delete_checkpoint_ref(
                    record,
                    checkpoint_id,
                    "after",
                )
                if not before_deleted or not after_deleted:
                    raise GitWorkspaceError(
                        "unable to release checkpoint history"
                    )
            return self.store.delete_checkpoints(
                restore.session_id,
                restore.discard_checkpoint_ids,
            )

    def finish_restore(self, operation_id: str) -> bool:
        with self._lock:
            restore = self.store.load_restore(operation_id)
            if restore is None:
                return False
            record = self._checkpoint_record(restore.session_id)
            if not self._delete_restore_refs(
                record,
                operation_id,
            ):
                raise GitWorkspaceError(
                    "unable to release checkpoint restore"
                )
            return self.store.delete_restore(operation_id)

    def discard_checkpoint_history(
        self,
        session_id: str,
        checkpoint_id: str,
    ) -> int:
        with self._lock:
            record = self._checkpoint_record(session_id)
            try:
                discarded = self.store.discard_checkpoint_history(
                    session_id,
                    checkpoint_id,
                )
            except ValueError as error:
                raise GitWorkspaceError(str(error)) from None
            for checkpoint in discarded:
                self._delete_checkpoint_ref(
                    record,
                    checkpoint.checkpoint_id,
                    "before",
                )
                self._delete_checkpoint_ref(
                    record,
                    checkpoint.checkpoint_id,
                    "after",
                )
            return len(discarded)

    def _restore_checkpoint_history(
        self,
        session_id: str,
        checkpoint_id: str,
    ) -> tuple[CodeCheckpointRecord, list[CodeCheckpointRecord]]:
        checkpoint = self.store.load_checkpoint(checkpoint_id)
        if (
            checkpoint is None
            or checkpoint.session_id != session_id
            or checkpoint.state is not CheckpointState.COMPLETED
        ):
            raise GitWorkspaceError("checkpoint not found")
        history = self.store.list_checkpoints(session_id)
        try:
            target_index = next(
                index
                for index, candidate in enumerate(history)
                if candidate.checkpoint_id == checkpoint_id
            )
        except StopIteration:
            raise GitWorkspaceError("checkpoint not found") from None
        return checkpoint, history[: target_index + 1]

    def restore_checkpoint_code(
        self,
        session_id: str,
        checkpoint_id: str,
    ) -> dict[str, object]:
        return self._apply_checkpoint_code(
            session_id,
            checkpoint_id,
            reverse=False,
        )

    def reapply_checkpoint_code(
        self,
        session_id: str,
        checkpoint_id: str,
    ) -> dict[str, object]:
        return self._apply_checkpoint_code(
            session_id,
            checkpoint_id,
            reverse=True,
        )

    def _apply_checkpoint_code(
        self,
        session_id: str,
        checkpoint_id: str,
        *,
        reverse: bool,
    ) -> dict[str, object]:
        with self._lock:
            record = self._checkpoint_record(session_id)
            checkpoint = self.store.load_checkpoint(checkpoint_id)
            if (
                checkpoint is None
                or checkpoint.session_id != session_id
                or checkpoint.state is not CheckpointState.COMPLETED
            ):
                raise GitWorkspaceError("checkpoint not found")
            history = self.store.list_checkpoints(session_id)
            try:
                target_index = next(
                    index
                    for index, candidate in enumerate(history)
                    if candidate.checkpoint_id == checkpoint_id
                )
            except StopIteration:
                raise GitWorkspaceError("checkpoint not found") from None
            composed = self._composed_checkpoint_patch(
                record,
                history[: target_index + 1],
                reverse=reverse,
            )
            patch_path = composed.path
            try:
                if patch_path.stat().st_size == 0:
                    return {
                        "ok": True,
                        "checkpoint_id": checkpoint_id,
                        "scope": "code",
                    }
                if (
                    patch_path.stat().st_size
                    > _MAX_CHECKPOINT_PATCH_BYTES
                ):
                    raise GitWorkspaceError(
                        "checkpoint patch exceeds safety limit"
                    )
                checked = self._execute_worktree(
                    record,
                    "apply",
                    "--check",
                    "--unidiff-zero",
                    "--whitespace=nowarn",
                    patch_path,
                )
                if checked.exit_code != 0:
                    raise GitWorkspaceError(
                        "checkpoint conflicts with current edits"
                    )
                applied = self._execute_worktree(
                    record,
                    "apply",
                    "--unidiff-zero",
                    "--whitespace=nowarn",
                    patch_path,
                )
                if applied.exit_code != 0:
                    raise GitWorkspaceError(
                        "checkpoint restore failed"
                    )
            finally:
                patch_path.unlink(missing_ok=True)
            return {
                "ok": True,
                "checkpoint_id": checkpoint_id,
                "scope": "code",
            }

    def diff(
        self,
        session_id: str,
        *,
        staged: bool = False,
        against_base: bool = False,
        path: Optional[str] = None,
    ) -> dict[str, object]:
        record = self._usable_record(session_id)
        pathspec, error = _pathspec(record.worktree_path, path)
        if error:
            return {"ok": False, "error": error}
        if staged and against_base:
            return {
                "ok": False,
                "error": "staged and against_base are mutually exclusive",
            }
        arguments = [
            "diff",
            "--no-ext-diff",
            "--no-textconv",
            "--no-color",
        ]
        if staged:
            arguments.append("--cached")
        elif against_base:
            arguments.append(f"{record.base_commit}...HEAD")
        if pathspec is not None:
            arguments.extend(["--", pathspec])
        result = self._execute_worktree(record, *arguments)
        if result.exit_code != 0:
            return {"ok": False, "error": "git diff failed"}
        return {
            "ok": True,
            "staged": staged,
            "against_base": against_base,
            "diff": result.stdout,
            "output_truncated": result.output_truncated,
        }

    def stage(
        self,
        session_id: str,
        path: str = ".",
    ) -> dict[str, object]:
        record = self._usable_record(session_id)
        pathspec, error = _pathspec(record.worktree_path, path)
        if error:
            return {"ok": False, "error": error}
        assert pathspec is not None
        result = self._execute_worktree(
            record,
            "add",
            "--all",
            "--",
            pathspec,
        )
        if result.exit_code != 0:
            return {"ok": False, "error": "git stage failed"}
        return {"ok": True, "path": pathspec}

    def commit(
        self,
        session_id: str,
        message: str,
    ) -> dict[str, object]:
        record = self._usable_record(session_id)
        try:
            encoded_message = (
                message.encode("utf-8")
                if isinstance(message, str)
                else b""
            )
        except UnicodeEncodeError:
            encoded_message = b""
        if (
            not isinstance(message, str)
            or not message.strip()
            or "\x00" in message
            or not encoded_message
            or len(encoded_message) > 10_000
        ):
            return {"ok": False, "error": "invalid commit message"}
        staged = self._execute_worktree(
            record,
            "diff",
            "--cached",
            "--quiet",
            "--exit-code",
        )
        if staged.exit_code == 0:
            return {"ok": False, "error": "nothing staged to commit"}
        if staged.exit_code != 1:
            return {"ok": False, "error": "unable to inspect staged changes"}
        name = self._config_value(record.source_root, "user.name") or "Codinal"
        email = (
            self._config_value(record.source_root, "user.email")
            or "codinal@localhost"
        )
        result = self._execute_worktree(
            record,
            "-c",
            f"user.name={name}",
            "-c",
            f"user.email={email}",
            "commit",
            "--no-verify",
            "--no-gpg-sign",
            "-m",
            message,
        )
        if result.exit_code != 0:
            return {"ok": False, "error": "git commit failed"}
        commit = self._probe(
            record.worktree_path,
            "rev-parse",
            "--verify",
            "HEAD^{commit}",
        )
        return {
            "ok": True,
            "commit": commit,
            "branch": record.session_branch,
        }

    def apply_back(self, session_id: str) -> dict[str, object]:
        record = self._usable_record(session_id)
        if not self._is_clean(record.worktree_path):
            raise GitWorkspaceError(
                "session worktree must be clean before apply"
            )
        if self._source_branch(record.source_root) != record.source_branch:
            raise GitWorkspaceError("source branch changed since session start")
        if not self._is_clean(record.source_root):
            raise GitWorkspaceError(
                "source worktree must be clean before apply"
            )
        session_head = self._probe(
            record.worktree_path,
            "rev-parse",
            "--verify",
            "HEAD^{commit}",
        )
        source_head = self._probe(
            record.source_root,
            "rev-parse",
            "--verify",
            "HEAD^{commit}",
        )
        if self._is_ancestor(
            record.source_root,
            session_head,
            source_head,
        ):
            self.store.save(
                replace(record, state=WorktreeState.APPLIED)
            )
            return {
                "ok": True,
                "strategy": "already-applied",
                "commit": source_head,
            }

        shell = self._apply_shell(record)
        fast_forward = self._run_registered(
            session_id,
            shell,
            _git_command(
                self.git_executable,
                "-c",
                "core.hooksPath=/dev/null",
                "-c",
                "commit.gpgsign=false",
                "-C",
                record.source_root,
                "merge",
                "--ff-only",
                record.session_branch,
            ),
        )
        if fast_forward.exit_code == 0:
            commit = self._probe(record.source_root, "rev-parse", "HEAD")
            self.store.save(replace(record, state=WorktreeState.APPLIED))
            return {
                "ok": True,
                "strategy": "fast-forward",
                "commit": commit,
            }

        name = self._config_value(record.source_root, "user.name") or "Codinal"
        email = (
            self._config_value(record.source_root, "user.email")
            or "codinal@localhost"
        )
        merged = self._run_registered(
            session_id,
            shell,
            _git_command(
                self.git_executable,
                "-c",
                "core.hooksPath=/dev/null",
                "-c",
                "commit.gpgsign=false",
                "-c",
                f"user.name={name}",
                "-c",
                f"user.email={email}",
                "-C",
                record.source_root,
                "merge",
                "--no-ff",
                "--no-edit",
                "--no-gpg-sign",
                record.session_branch,
            ),
        )
        if merged.exit_code == 0:
            commit = self._probe(record.source_root, "rev-parse", "HEAD")
            self.store.save(replace(record, state=WorktreeState.APPLIED))
            return {
                "ok": True,
                "strategy": "merge",
                "commit": commit,
            }

        if not self._merge_in_progress(record.source_root):
            raise GitWorkspaceError("apply failed before merge started")
        aborted = self._run_registered(
            session_id,
            shell,
            _git_command(
                self.git_executable,
                "-c",
                "core.hooksPath=/dev/null",
                "-C",
                record.source_root,
                "merge",
                "--abort",
            ),
        )
        restored_head = self._probe(
            record.source_root,
            "rev-parse",
            "HEAD",
        )
        if (
            aborted.exit_code != 0
            or restored_head != source_head
            or not self._is_clean(record.source_root)
        ):
            raise GitWorkspaceError("apply rollback failed")
        self.store.save(replace(record, state=WorktreeState.CONFLICT))
        return {
            "ok": False,
            "conflict": True,
            "error": "apply conflict; source was restored",
        }

    def interrupt(self, session_id: str) -> None:
        with self._process_lock:
            shells = list(self._active_shells.get(session_id, ()))
        for shell in shells:
            shell.interrupt()

    def cleanup(self, session_id: str) -> None:
        """Remove only a clean worktree whose commits are retained in source."""
        with self._lock:
            if self.store.is_plain_workspace(session_id):
                record = self.store.load(session_id)
                if record is None:
                    return
                self.interrupt(session_id)
                self._remove_checkpoint_repository(record)
                self._remove_session_sandbox(session_id)
                self.store.delete(session_id)
                return
            record = self.store.load(session_id)
            if record is None:
                return
            self.interrupt(session_id)
            if record.worktree_path.is_dir():
                if not self._is_clean(record.worktree_path):
                    raise GitWorkspaceError(
                        "isolated worktree has uncommitted changes"
                    )
                session_head = self._probe(
                    record.worktree_path,
                    "rev-parse",
                    "HEAD",
                )
                source_tip = self._probe(
                    record.source_root,
                    "rev-parse",
                    f"refs/heads/{record.source_branch}",
                )
                if not self._is_ancestor(
                    record.source_root,
                    session_head,
                    source_tip,
                ):
                    raise GitWorkspaceError(
                        "isolated worktree has unapplied commits"
                    )
            shell = self._creation_shell(record)
            if record.worktree_path.exists():
                removed = shell.run(
                    _git_command(
                        self.git_executable,
                        "-c",
                        "core.hooksPath=/dev/null",
                        "-C",
                        record.source_root,
                        "worktree",
                        "remove",
                        "--force",
                        record.worktree_path,
                    )
                )
                if removed.exit_code != 0:
                    raise GitWorkspaceError(
                        "failed to remove isolated worktree"
                    )
            if self._branch_exists(
                record.source_root,
                record.session_branch,
            ):
                deleted = shell.run(
                    _git_command(
                        self.git_executable,
                        "-C",
                        record.source_root,
                        "branch",
                        "-D",
                        record.session_branch,
                    )
                )
                if deleted.exit_code != 0:
                    raise GitWorkspaceError(
                        "failed to remove isolated branch"
                    )
            self._remove_checkpoint_repository(record)
            self.store.delete(session_id)
            self._remove_session_sandbox(record.session_id)

    def prepare(
        self,
        session_id: str,
        workspace: str | Path,
    ) -> GitWorkspaceRecord:
        with self._lock:
            existing = self.store.load(session_id)
            requested = Path(workspace).expanduser().resolve()
            if existing is not None:
                if not _inside(
                    requested,
                    existing.source_root,
                    existing.worktree_path,
                ):
                    raise GitWorkspaceError(
                        "session is already bound to another Git workspace"
                    )
                if existing.state not in {
                    WorktreeState.CREATING,
                    WorktreeState.FAILED,
                }:
                    self._validate_active(existing)
                    return existing
                raise GitWorkspaceError(
                    "Git workspace requires recovery before it can resume"
                )

            source_root = self._source_root(requested)
            source_branch = self._source_branch(source_root)
            base_commit = self._probe(
                source_root,
                "rev-parse",
                "--verify",
                "HEAD^{commit}",
            )
            git_common_dir = self._common_dir(source_root)
            source_dirty = bool(
                self._probe(
                    source_root,
                    "status",
                    "--porcelain=v1",
                    "-z",
                )
            )
            identity = hashlib.sha256(
                f"{git_common_dir}\0{session_id}".encode("utf-8")
            ).hexdigest()
            repo_identity = hashlib.sha256(
                str(git_common_dir).encode("utf-8")
            ).hexdigest()
            session_branch = f"codinal/session-{identity[:16]}"
            worktree_path = (
                self.worktree_base
                / f"{repo_identity[:12]}-{identity[:16]}"
            )
            if worktree_path.exists():
                raise GitWorkspaceError("isolated worktree path already exists")
            if self._branch_exists(source_root, session_branch):
                raise GitWorkspaceError("isolated session branch already exists")

            creating = self.store.save(
                GitWorkspaceRecord(
                    session_id=session_id,
                    source_root=source_root,
                    git_common_dir=git_common_dir,
                    source_branch=source_branch,
                    base_commit=base_commit,
                    worktree_path=worktree_path,
                    session_branch=session_branch,
                    source_dirty=source_dirty,
                    state=WorktreeState.CREATING,
                )
            )
            shell = self._creation_shell(creating)
            result = shell.run(
                _git_command(
                    self.git_executable,
                    "-c",
                    "core.hooksPath=/dev/null",
                    "-c",
                    "commit.gpgsign=false",
                    "-C",
                    source_root,
                    "worktree",
                    "add",
                    "-b",
                    session_branch,
                    worktree_path,
                    base_commit,
                )
            )
            if result.exit_code != 0:
                failed = self.store.save(
                    GitWorkspaceRecord(
                        **{
                            **creating.__dict__,
                            "state": WorktreeState.FAILED,
                        }
                    )
                )
                self._cleanup_failed(failed, shell)
                raise GitWorkspaceError(
                    "failed to create isolated Git worktree"
                )

            active = self.store.save(
                GitWorkspaceRecord(
                    **{
                        **creating.__dict__,
                        "state": WorktreeState.ACTIVE,
                    }
                )
            )
            self._validate_active(active)
            return active

    def _source_root(self, workspace: Path) -> Path:
        if not workspace.is_dir():
            raise GitWorkspaceError("workspace is not an existing directory")
        try:
            value = self._probe(
                workspace,
                "rev-parse",
                "--show-toplevel",
            )
        except GitWorkspaceError:
            raise NotGitRepositoryError(
                "workspace is not a Git worktree"
            ) from None
        root = Path(value).expanduser().resolve()
        if not root.is_dir():
            raise NotGitRepositoryError("workspace is not a Git worktree")
        return root

    def _source_branch(self, source_root: Path) -> str:
        try:
            branch = self._probe(
                source_root,
                "symbolic-ref",
                "--quiet",
                "--short",
                "HEAD",
            )
        except GitWorkspaceError:
            raise DetachedHeadError(
                "source worktree must be on a named branch"
            ) from None
        if not branch or len(branch) > 255:
            raise DetachedHeadError(
                "source worktree must be on a named branch"
            )
        return branch

    def _common_dir(self, source_root: Path) -> Path:
        value = Path(
            self._probe(
                source_root,
                "rev-parse",
                "--git-common-dir",
            )
        )
        if not value.is_absolute():
            value = source_root / value
        common = value.expanduser().resolve()
        if not common.is_dir() or common == Path(common.anchor):
            raise GitWorkspaceError("invalid Git metadata directory")
        return common

    def _branch_exists(self, source_root: Path, branch: str) -> bool:
        result = self._probe_result(
            source_root,
            "show-ref",
            "--verify",
            "--quiet",
            f"refs/heads/{branch}",
        )
        return result.returncode == 0

    def _validate_active(self, record: GitWorkspaceRecord) -> None:
        if not record.worktree_path.is_dir():
            raise GitWorkspaceError("isolated Git worktree is missing")
        branch = self._probe(
            record.worktree_path,
            "symbolic-ref",
            "--quiet",
            "--short",
            "HEAD",
        )
        if branch != record.session_branch:
            raise GitWorkspaceError("isolated Git branch does not match state")
        common = self._common_dir(record.worktree_path)
        if common != record.git_common_dir:
            raise GitWorkspaceError("isolated Git repository does not match state")

    def _git_shell(self, record: GitWorkspaceRecord) -> SandboxedShell:
        if not record.worktree_path.is_dir():
            raise GitWorkspaceError("isolated Git worktree is missing")
        identity = hashlib.sha256(
            record.session_id.encode("utf-8")
        ).hexdigest()
        return SandboxedShell(
            workspace=record.source_root,
            temp_dir=self.sandbox_base / identity,
            workspace_writable=False,
            additional_write_roots=[
                record.worktree_path,
                record.git_common_dir,
                self.checkpoint_base,
            ],
        )

    def _creation_shell(
        self,
        record: GitWorkspaceRecord,
    ) -> SandboxedShell:
        identity = hashlib.sha256(
            record.session_id.encode("utf-8")
        ).hexdigest()
        return SandboxedShell(
            workspace=record.source_root,
            temp_dir=self.sandbox_base / identity,
            workspace_writable=False,
            additional_write_roots=[
                self.worktree_base,
                record.git_common_dir,
            ],
        )

    def _apply_shell(self, record: GitWorkspaceRecord) -> SandboxedShell:
        identity = hashlib.sha256(
            f"apply\0{record.session_id}".encode("utf-8")
        ).hexdigest()
        return SandboxedShell(
            workspace=record.source_root,
            temp_dir=self.sandbox_base / identity,
            workspace_writable=True,
            additional_read_roots=[record.worktree_path],
            additional_write_roots=[record.git_common_dir],
        )

    def _snapshot_tree(
        self,
        record: GitWorkspaceRecord,
        checkpoint_id: str,
        *,
        phase: str = "before",
    ) -> str:
        tree = self._capture_tree(
            record,
            f"{checkpoint_id}-{phase}",
        )
        updated = self._checkpoint_git(
            record,
            "update-ref",
            self._checkpoint_ref(
                record.session_id,
                checkpoint_id,
                phase,
            ),
            tree,
        )
        if updated.exit_code != 0:
            raise GitWorkspaceError(
                "unable to retain checkpoint"
            )
        return tree

    def _checkpoint_relative_path(
        self,
        record: GitWorkspaceRecord,
        path: Path,
    ) -> str:
        candidate = Path(path)
        if not candidate.is_absolute() or candidate.is_symlink():
            raise GitWorkspaceError(
                "checkpoint path is unavailable"
            )
        try:
            relative = candidate.relative_to(record.worktree_path)
            if (
                ".." in relative.parts
                or ".git" in (part.casefold() for part in relative.parts)
            ):
                raise ValueError
            ancestor = candidate.parent
            while True:
                try:
                    metadata = ancestor.lstat()
                    break
                except FileNotFoundError:
                    if ancestor == record.worktree_path:
                        raise
                    ancestor = ancestor.parent
            if (
                not stat.S_ISDIR(metadata.st_mode)
                or ancestor.resolve(strict=True) != ancestor
                or not ancestor.is_relative_to(record.worktree_path)
            ):
                raise ValueError
        except (FileNotFoundError, OSError, ValueError):
            raise GitWorkspaceError(
                "checkpoint path is outside the worktree"
            ) from None
        value = relative.as_posix()
        if not value or len(value.encode("utf-8")) > 4096:
            raise GitWorkspaceError("invalid checkpoint path")
        return value

    def _refresh_attributed_before_tree(
        self,
        record: GitWorkspaceRecord,
        checkpoint_id: str,
    ) -> None:
        checkpoint = self.store.load_checkpoint(checkpoint_id)
        if (
            checkpoint is None
            or checkpoint.capture_mode
            is not CheckpointCaptureMode.ATTRIBUTED
            or checkpoint.state is not CheckpointState.PENDING
        ):
            raise GitWorkspaceError(
                "pending attributed checkpoint not found"
            )
        files = self.store.list_checkpoint_files(checkpoint_id)
        if files:
            before_tree = self._checkpoint_file_tree(
                record,
                checkpoint_id,
                files,
                phase="before",
            )
        else:
            if not self._delete_checkpoint_ref(
                record,
                checkpoint_id,
                "before",
            ):
                raise GitWorkspaceError(
                    "unable to release checkpoint files"
                )
            before_tree = ""
        self.store.save_checkpoint(
            replace(checkpoint, before_tree=before_tree)
        )

    def _prune_checkpoint_repository(
        self,
        record: GitWorkspaceRecord,
    ) -> None:
        result = self._checkpoint_git(
            record,
            "prune",
            "--expire=now",
        )
        if result.exit_code != 0:
            raise GitWorkspaceError(
                "unable to remove discarded checkpoint data"
            )

    def _capture_file_blob(
        self,
        record: GitWorkspaceRecord,
        path: Path,
    ) -> tuple[str, int]:
        self._checkpoint_relative_path(record, path)
        try:
            metadata = path.lstat()
        except FileNotFoundError:
            return "", 0
        except OSError:
            raise GitWorkspaceError(
                "checkpoint file is unavailable"
            ) from None
        if (
            not stat.S_ISREG(metadata.st_mode)
            or metadata.st_size > _MAX_CHECKPOINT_FILE_BYTES
        ):
            raise GitWorkspaceError(
                "checkpoint file is unsupported"
            )
        result = self._checkpoint_git(
            record,
            "hash-object",
            "-w",
            "--no-filters",
            path,
        )
        blob = result.stdout.strip()
        if (
            result.exit_code != 0
            or re.fullmatch(r"[0-9a-f]{40,64}", blob) is None
        ):
            raise GitWorkspaceError(
                "unable to capture checkpoint file"
            )
        mode = (
            0o100755
            if metadata.st_mode & stat.S_IXUSR
            else 0o100644
        )
        return blob, mode

    def _capture_preimage_bytes(
        self,
        record: GitWorkspaceRecord,
        content: bytes | None | object,
        mode: int,
    ) -> tuple[str, int]:
        if content is None:
            return "", 0
        if (
            not isinstance(content, bytes)
            or len(content) > _MAX_CHECKPOINT_FILE_BYTES
            or isinstance(mode, bool)
            or not isinstance(mode, int)
        ):
            raise GitWorkspaceError("checkpoint file is unsupported")
        repository = self._checkpoint_repository(record)
        self._ensure_checkpoint_repository(record)
        descriptor, temporary_name = tempfile.mkstemp(
            prefix="preimage-",
            dir=repository,
        )
        temporary = Path(temporary_name)
        try:
            view = memoryview(content)
            while view:
                written = os.write(descriptor, view)
                if written <= 0:
                    raise OSError("short write")
                view = view[written:]
            os.fsync(descriptor)
            os.close(descriptor)
            descriptor = -1
            result = self._checkpoint_git(
                record,
                "hash-object",
                "-w",
                "--no-filters",
                temporary,
            )
            blob = result.stdout.strip()
            if (
                result.exit_code != 0
                or re.fullmatch(r"[0-9a-f]{40,64}", blob) is None
            ):
                raise GitWorkspaceError(
                    "unable to capture checkpoint file"
                )
        except OSError:
            raise GitWorkspaceError(
                "checkpoint file is unavailable"
            ) from None
        finally:
            if descriptor >= 0:
                os.close(descriptor)
            temporary.unlink(missing_ok=True)
        captured_mode = 0o100755 if mode & stat.S_IXUSR else 0o100644
        return blob, captured_mode

    def _checkpoint_file_tree(
        self,
        record: GitWorkspaceRecord,
        checkpoint_id: str,
        files: list[CheckpointFileRecord],
        *,
        phase: str,
        base_tree: str = "",
    ) -> str:
        identity = hashlib.sha256(
            record.session_id.encode("utf-8")
        ).hexdigest()
        index_path = (
            self.sandbox_base
            / identity
            / f"files-{checkpoint_id}-{phase}.index"
        )
        index_path.unlink(missing_ok=True)
        try:
            initialized = self._index_git(
                record,
                index_path,
                "read-tree",
                *(base_tree,) if base_tree else ("--empty",),
            )
            if initialized.exit_code != 0:
                raise GitWorkspaceError(
                    "unable to initialize checkpoint files"
                )
            for item in files:
                blob = (
                    item.before_blob
                    if phase == "before"
                    else item.after_blob
                )
                mode = (
                    item.before_mode
                    if phase == "before"
                    else item.after_mode
                )
                if blob:
                    changed = self._index_git(
                        record,
                        index_path,
                        "update-index",
                        "--add",
                        "--cacheinfo",
                        format(mode, "o"),
                        blob,
                        item.path,
                    )
                else:
                    changed = self._index_git(
                        record,
                        index_path,
                        "update-index",
                        "--force-remove",
                        "--",
                        item.path,
                    )
                if changed.exit_code != 0:
                    raise GitWorkspaceError(
                        "unable to capture checkpoint files"
                    )
            written = self._index_git(
                record,
                index_path,
                "write-tree",
            )
            tree = written.stdout.strip()
            if (
                written.exit_code != 0
                or re.fullmatch(r"[0-9a-f]{40,64}", tree) is None
                or not self._set_checkpoint_ref(
                    record,
                    checkpoint_id,
                    phase,
                    tree,
                )
            ):
                raise GitWorkspaceError(
                    "unable to retain checkpoint files"
                )
            return tree
        finally:
            index_path.unlink(missing_ok=True)

    def _capture_tree(
        self,
        record: GitWorkspaceRecord,
        operation_id: str,
    ) -> str:
        identity = hashlib.sha256(
            record.session_id.encode("utf-8")
        ).hexdigest()
        index_path = (
            self.sandbox_base
            / identity
            / f"checkpoint-{operation_id}.index"
        )
        index_path.unlink(missing_ok=True)
        self._ensure_checkpoint_repository(record)
        head = self._execute_worktree(
            record,
            "rev-parse",
            "HEAD^{tree}",
        )
        head_tree = head.stdout.strip()
        if (
            head.exit_code != 0
            or re.fullmatch(r"[0-9a-f]{40,64}", head_tree) is None
        ):
            raise GitWorkspaceError(
                "unable to initialize checkpoint"
            )
        try:
            if self._index_git(
                record,
                index_path,
                "read-tree",
                head_tree,
            ).exit_code != 0:
                raise GitWorkspaceError(
                    "unable to initialize checkpoint"
                )
            if self._index_git(
                record,
                index_path,
                "add",
                "--all",
            ).exit_code != 0:
                raise GitWorkspaceError(
                    "unable to capture checkpoint"
                )
            written = self._index_git(
                record,
                index_path,
                "write-tree",
            )
            tree = written.stdout.strip()
            if (
                written.exit_code != 0
                or re.fullmatch(
                    r"[0-9a-f]{40,64}",
                    tree,
                )
                is None
            ):
                raise GitWorkspaceError(
                    "unable to finalize checkpoint"
                )
            return tree
        finally:
            index_path.unlink(missing_ok=True)

    def _index_git(
        self,
        record: GitWorkspaceRecord,
        index_path: Path,
        *arguments: object,
    ):
        return self._checkpoint_git(
            record,
            *arguments,
            index_path=index_path,
            work_tree=True,
        )

    def _checkpoint_git(
        self,
        record: GitWorkspaceRecord,
        *arguments: object,
        index_path: Path | None = None,
        work_tree: bool = False,
    ):
        self._ensure_checkpoint_repository(record)
        environment = [
            "GIT_CONFIG_NOSYSTEM=1",
            "GIT_CONFIG_GLOBAL=/dev/null",
            f"GIT_DIR={self._checkpoint_repository(record)}",
        ]
        if work_tree:
            environment.append(
                f"GIT_WORK_TREE={record.worktree_path}"
            )
        if index_path is not None:
            environment.append(f"GIT_INDEX_FILE={index_path}")
        return self._run_registered(
            record.session_id,
            self._git_shell(record),
            _git_command(
                Path("/usr/bin/env"),
                *environment,
                self.git_executable,
                "-c",
                "core.hooksPath=/dev/null",
                "-c",
                "core.fsmonitor=false",
                "--literal-pathspecs",
                *arguments,
            ),
        )

    def _ensure_checkpoint_repository(
        self,
        record: GitWorkspaceRecord,
    ) -> Path:
        repository = self._checkpoint_repository(record)
        if repository.is_symlink():
            raise GitWorkspaceError(
                "invalid checkpoint storage"
            )
        alternates = repository / "objects" / "info" / "alternates"
        if not (repository / "HEAD").is_file():
            initialized = self._run_registered(
                record.session_id,
                self._git_shell(record),
                _git_command(
                    Path("/usr/bin/env"),
                    "GIT_CONFIG_NOSYSTEM=1",
                    "GIT_CONFIG_GLOBAL=/dev/null",
                    self.git_executable,
                    "init",
                    "--bare",
                    "--quiet",
                    repository,
                ),
            )
            if initialized.exit_code != 0:
                raise GitWorkspaceError(
                    "unable to initialize checkpoint storage"
                )
        if self.store.is_plain_workspace(record.session_id):
            try:
                os.chmod(repository, 0o700)
            except OSError:
                raise GitWorkspaceError(
                    "unable to secure checkpoint storage"
                ) from None
            return repository
        source_objects = record.git_common_dir / "objects"
        if (
            "\n" in str(source_objects)
            or not source_objects.is_dir()
            or alternates.is_symlink()
        ):
            raise GitWorkspaceError(
                "invalid Git object directory"
            )
        try:
            os.chmod(repository, 0o700)
            alternates.parent.mkdir(
                mode=0o700,
                parents=True,
                exist_ok=True,
            )
            alternates.write_text(
                f"{source_objects}\n",
                encoding="utf-8",
            )
            os.chmod(alternates, 0o600)
        except OSError:
            raise GitWorkspaceError(
                "unable to secure checkpoint storage"
            ) from None
        return repository

    def _checkpoint_repository(
        self,
        record: GitWorkspaceRecord,
    ) -> Path:
        identity = hashlib.sha256(
            record.session_id.encode("utf-8")
        ).hexdigest()
        return self.checkpoint_base / identity

    def _composed_checkpoint_patch(
        self,
        record: GitWorkspaceRecord,
        checkpoints: list[CodeCheckpointRecord],
        *,
        reverse: bool,
    ) -> _ComposedCheckpointPatch:
        target = checkpoints[-1]
        identity = hashlib.sha256(
            record.session_id.encode("utf-8")
        ).hexdigest()
        index_path = (
            self.sandbox_base
            / identity
            / f"compose-{target.checkpoint_id}.index"
        )
        index_path.unlink(missing_ok=True)
        effective_current_tree = self._effective_current_tree(
            record,
            checkpoints,
            f"current-{target.checkpoint_id}",
        )
        ordered = (
            list(reversed(checkpoints))
            if reverse
            else checkpoints
        )
        try:
            initialized = self._index_git(
                record,
                index_path,
                "read-tree",
                effective_current_tree,
            )
            if initialized.exit_code != 0:
                raise GitWorkspaceError(
                    "unable to initialize checkpoint restore"
                )
            for checkpoint in ordered:
                patch_path = self._checkpoint_patch(
                    record,
                    checkpoint,
                )
                try:
                    if patch_path.stat().st_size == 0:
                        continue
                    if (
                        patch_path.stat().st_size
                        > _MAX_CHECKPOINT_PATCH_BYTES
                    ):
                        raise GitWorkspaceError(
                            "checkpoint patch exceeds safety limit"
                        )
                    applied = self._index_git(
                        record,
                        index_path,
                        "apply",
                        "--cached",
                        *(("--reverse",) if reverse else ()),
                        "--unidiff-zero",
                        "--whitespace=nowarn",
                        patch_path,
                    )
                finally:
                    patch_path.unlink(missing_ok=True)
                if applied.exit_code != 0:
                    raise GitWorkspaceError(
                        "checkpoint conflicts with current edits"
                    )
            written = self._index_git(
                record,
                index_path,
                "write-tree",
            )
            restored_tree = written.stdout.strip()
            if (
                written.exit_code != 0
                or re.fullmatch(
                    r"[0-9a-f]{40,64}",
                    restored_tree,
                )
                is None
            ):
                raise GitWorkspaceError(
                    "unable to finalize checkpoint restore"
                )
            return _ComposedCheckpointPatch(
                path=self._tree_patch(
                    record,
                    effective_current_tree,
                    restored_tree,
                    f"composed-{target.checkpoint_id}",
                ),
                before_tree=effective_current_tree,
                after_tree=restored_tree,
            )
        finally:
            index_path.unlink(missing_ok=True)

    def _effective_current_tree(
        self,
        record: GitWorkspaceRecord,
        checkpoints: list[CodeCheckpointRecord],
        operation_id: str,
    ) -> str:
        plain = self.store.is_plain_workspace(record.session_id)
        current_tree = (
            ""
            if plain
            else self._capture_tree(record, operation_id)
        )
        identity = hashlib.sha256(
            record.session_id.encode("utf-8")
        ).hexdigest()
        index_path = (
            self.sandbox_base
            / identity
            / f"effective-{operation_id}.index"
        )
        index_path.unlink(missing_ok=True)
        try:
            initialized = self._index_git(
                record,
                index_path,
                "read-tree",
                *(("--empty",) if plain else (current_tree,)),
            )
            if initialized.exit_code != 0:
                raise GitWorkspaceError(
                    "unable to initialize checkpoint restore"
                )
            attributed_paths = {
                item.path
                for checkpoint in checkpoints
                for item in self.store.list_checkpoint_files(
                    checkpoint.checkpoint_id
                )
            }
            for path in sorted(attributed_paths):
                blob, mode = self._capture_file_blob(
                    record,
                    record.worktree_path / path,
                )
                if blob:
                    updated = self._index_git(
                        record,
                        index_path,
                        "update-index",
                        "--add",
                        "--cacheinfo",
                        format(mode, "o"),
                        blob,
                        path,
                    )
                else:
                    updated = self._index_git(
                        record,
                        index_path,
                        "update-index",
                        "--force-remove",
                        "--",
                        path,
                    )
                if updated.exit_code != 0:
                    raise GitWorkspaceError(
                        "unable to capture attributed files"
                    )
            written = self._index_git(
                record,
                index_path,
                "write-tree",
            )
            tree = written.stdout.strip()
            if (
                written.exit_code != 0
                or re.fullmatch(r"[0-9a-f]{40,64}", tree) is None
            ):
                raise GitWorkspaceError(
                    "unable to capture checkpoint restore state"
                )
            return tree
        finally:
            index_path.unlink(missing_ok=True)

    def _checkpoint_patch(
        self,
        record: GitWorkspaceRecord,
        checkpoint: CodeCheckpointRecord,
    ) -> Path:
        return self._tree_patch(
            record,
            checkpoint.after_tree,
            checkpoint.before_tree,
            checkpoint.checkpoint_id,
        )

    def _tree_patch(
        self,
        record: GitWorkspaceRecord,
        before_tree: str,
        after_tree: str,
        label: str,
    ) -> Path:
        identity = hashlib.sha256(
            record.session_id.encode("utf-8")
        ).hexdigest()
        patch_path = (
            self.sandbox_base
            / identity
            / f"restore-{label}.patch"
        )
        patch_path.unlink(missing_ok=True)
        result = self._checkpoint_git(
            record,
            "diff",
            "--binary",
            "--full-index",
            "--unified=0",
            "--no-ext-diff",
            "--no-textconv",
            f"--output={patch_path}",
            before_tree,
            after_tree,
        )
        if result.exit_code != 0 or not patch_path.is_file():
            patch_path.unlink(missing_ok=True)
            raise GitWorkspaceError(
                "unable to prepare checkpoint restore"
            )
        try:
            os.chmod(patch_path, 0o600)
        except OSError:
            patch_path.unlink(missing_ok=True)
            raise GitWorkspaceError(
                "unable to secure checkpoint restore"
            ) from None
        return patch_path

    def _apply_restore_patch(
        self,
        record: GitWorkspaceRecord,
        patch_path: Path,
    ) -> None:
        try:
            if patch_path.stat().st_size == 0:
                return
            if (
                patch_path.stat().st_size
                > _MAX_CHECKPOINT_PATCH_BYTES
            ):
                raise GitWorkspaceError(
                    "checkpoint patch exceeds safety limit"
                )
            checked = self._execute_worktree(
                record,
                "apply",
                "--check",
                "--unidiff-zero",
                "--whitespace=nowarn",
                patch_path,
            )
            if checked.exit_code != 0:
                raise GitWorkspaceError(
                    "checkpoint conflicts with current edits"
                )
            applied = self._execute_worktree(
                record,
                "apply",
                "--unidiff-zero",
                "--whitespace=nowarn",
                patch_path,
            )
            if applied.exit_code != 0:
                raise GitWorkspaceError(
                    "checkpoint restore failed"
                )
        finally:
            patch_path.unlink(missing_ok=True)

    def _delete_restore_refs(
        self,
        record: GitWorkspaceRecord,
        operation_id: str,
    ) -> bool:
        before_deleted = self._delete_checkpoint_ref(
            record,
            operation_id,
            "restore-before",
        )
        after_deleted = self._delete_checkpoint_ref(
            record,
            operation_id,
            "restore-after",
        )
        return before_deleted and after_deleted

    def _ensure_restore_refs(
        self,
        record: GitWorkspaceRecord,
        restore: CheckpointRestoreRecord,
    ) -> bool:
        if restore.scope is CheckpointRestoreScope.CONVERSATION:
            return True
        return self._set_checkpoint_ref(
            record,
            restore.operation_id,
            "restore-before",
            restore.code_before_tree,
        ) and self._set_checkpoint_ref(
            record,
            restore.operation_id,
            "restore-after",
            restore.code_after_tree,
        )

    def _delete_checkpoint_ref(
        self,
        record: GitWorkspaceRecord,
        checkpoint_id: str,
        phase: str,
    ) -> bool:
        try:
            result = self._checkpoint_git(
                record,
                "update-ref",
                "-d",
                self._checkpoint_ref(
                    record.session_id,
                    checkpoint_id,
                    phase,
                ),
            )
        except Exception:
            return False
        return result.exit_code == 0

    def _set_checkpoint_ref(
        self,
        record: GitWorkspaceRecord,
        checkpoint_id: str,
        phase: str,
        tree: str,
    ) -> bool:
        try:
            result = self._checkpoint_git(
                record,
                "update-ref",
                self._checkpoint_ref(
                    record.session_id,
                    checkpoint_id,
                    phase,
                ),
                tree,
            )
        except Exception:
            return False
        return result.exit_code == 0

    def _remove_checkpoint_repository(
        self,
        record: GitWorkspaceRecord,
    ) -> None:
        target = self._checkpoint_repository(record)
        if (
            target.parent != self.checkpoint_base
            or target == self.checkpoint_base
        ):
            raise GitWorkspaceError(
                "invalid checkpoint cleanup target"
            )
        if target.is_symlink():
            target.unlink()
        elif target.is_dir():
            shutil.rmtree(target)

    @staticmethod
    def _checkpoint_ref(
        session_id: str,
        checkpoint_id: str,
        phase: str,
    ) -> str:
        return (
            "refs/codinal/checkpoints/"
            f"{session_id}/{checkpoint_id}/{phase}"
        )

    def _usable_record(self, session_id: str) -> GitWorkspaceRecord:
        record = self.store.load(session_id)
        if record is None:
            raise GitWorkspaceError("Git session workspace not found")
        if record.state in {
            WorktreeState.CREATING,
            WorktreeState.FAILED,
        }:
            raise GitWorkspaceError("Git session workspace is unavailable")
        self._validate_active(record)
        return record

    def _checkpoint_record(
        self,
        session_id: str,
    ) -> GitWorkspaceRecord:
        plain = self.store.load_plain_workspace(session_id)
        if plain is None:
            return self._usable_record(session_id)
        if not plain.is_dir():
            raise GitWorkspaceError(
                "plain session workspace is unavailable"
            )
        return GitWorkspaceRecord(
            session_id=session_id,
            source_root=plain,
            git_common_dir=self.checkpoint_base,
            source_branch="codinal-plain",
            base_commit="0" * 40,
            worktree_path=plain,
            session_branch="codinal-plain",
            source_dirty=False,
            state=WorktreeState.ACTIVE,
        )

    def _execute_worktree(
        self,
        record: GitWorkspaceRecord,
        *arguments: object,
    ):
        shell = self._git_shell(record)
        return self._run_registered(
            record.session_id,
            shell,
            _git_command(
                self.git_executable,
                "-c",
                "core.hooksPath=/dev/null",
                "-c",
                "commit.gpgsign=false",
                "--literal-pathspecs",
                "-C",
                record.worktree_path,
                *arguments,
            ),
        )

    def _run_registered(
        self,
        session_id: str,
        shell: SandboxedShell,
        command: str,
    ):
        with self._process_lock:
            self._active_shells.setdefault(session_id, set()).add(shell)
        try:
            return shell.run(command)
        finally:
            with self._process_lock:
                active = self._active_shells.get(session_id)
                if active is not None:
                    active.discard(shell)
                    if not active:
                        self._active_shells.pop(session_id, None)

    def _config_value(self, root: Path, key: str) -> str:
        result = self._probe_result(
            root,
            "config",
            "--get",
            key,
        )
        if result.returncode != 0:
            return ""
        value = result.stdout.strip()
        if (
            not value
            or len(value) > 320
            or any(character in value for character in "\x00\n\r")
        ):
            return ""
        return value

    def _is_clean(self, root: Path) -> bool:
        return not self._probe(
            root,
            "status",
            "--porcelain=v1",
            "-z",
            "--untracked-files=all",
        )

    def _is_ancestor(
        self,
        root: Path,
        ancestor: str,
        descendant: str,
    ) -> bool:
        result = self._probe_result(
            root,
            "merge-base",
            "--is-ancestor",
            ancestor,
            descendant,
        )
        if result.returncode not in {0, 1}:
            raise GitWorkspaceError("unable to compare Git history")
        return result.returncode == 0

    def _merge_in_progress(self, root: Path) -> bool:
        return (
            self._probe_result(
                root,
                "rev-parse",
                "--verify",
                "--quiet",
                "MERGE_HEAD",
            ).returncode
            == 0
        )

    def _cleanup_failed(
        self,
        record: GitWorkspaceRecord,
        shell: SandboxedShell,
    ) -> None:
        shell.run(
            _git_command(
                self.git_executable,
                "-c",
                "core.hooksPath=/dev/null",
                "-C",
                record.source_root,
                "worktree",
                "remove",
                "--force",
                record.worktree_path,
            )
        )
        shell.run(
            _git_command(
                self.git_executable,
                "-C",
                record.source_root,
                "branch",
                "-D",
                record.session_branch,
            )
        )

    def _remove_session_sandbox(self, session_id: str) -> None:
        identities = (
            hashlib.sha256(session_id.encode("utf-8")).hexdigest(),
            hashlib.sha256(
                f"apply\0{session_id}".encode("utf-8")
            ).hexdigest(),
        )
        for identity in identities:
            target = self.sandbox_base / identity
            if target.parent != self.sandbox_base or target == self.sandbox_base:
                raise GitWorkspaceError("invalid sandbox cleanup target")
            if target.is_symlink():
                target.unlink()
            elif target.is_dir():
                shutil.rmtree(target)
    def _probe(self, cwd: Path, *arguments: str) -> str:
        result = self._probe_result(cwd, *arguments)
        if result.returncode != 0:
            raise GitWorkspaceError("Git repository inspection failed")
        return result.stdout.rstrip("\n")

    def _probe_result(
        self,
        cwd: Path,
        *arguments: str,
    ) -> _ProbeResult:
        environment = {
            key: os.environ[key]
            for key in ("HOME", "LANG", "LC_ALL", "LC_CTYPE", "PATH")
            if os.environ.get(key)
        }
        environment["GIT_OPTIONAL_LOCKS"] = "0"
        try:
            result = _run_bounded(
                [
                    str(self.git_executable),
                    "-c",
                    "core.hooksPath=/dev/null",
                    "-C",
                    str(cwd),
                    *arguments,
                ],
                cwd=cwd,
                env=environment,
                timeout=_PROBE_TIMEOUT_SECONDS,
                output_limit=_PROBE_OUTPUT_LIMIT,
            )
        except (OSError, subprocess.TimeoutExpired, UnicodeError):
            raise GitWorkspaceError("Git repository inspection failed") from None
        if result.output_truncated:
            raise GitWorkspaceError("Git repository inspection exceeded limit")
        return result


def _discover_git() -> str:
    candidates = (
        "/Applications/Xcode.app/Contents/Developer/usr/bin/git",
        "/Library/Developer/CommandLineTools/usr/bin/git",
        shutil.which("git"),
    )
    for candidate in candidates:
        if candidate and os.access(candidate, os.X_OK):
            return candidate
    raise GitWorkspaceError("Git executable is unavailable")


def _git_command(executable: Path, *arguments: object) -> str:
    return shlex.join([str(executable), *(str(value) for value in arguments)])


def _inside(candidate: Path, *roots: Path) -> bool:
    for root in roots:
        try:
            candidate.relative_to(root)
            return True
        except ValueError:
            continue
    return False


def _pathspec(
    worktree: Path,
    value: Optional[str],
) -> tuple[Optional[str], str]:
    if value is None:
        return None, ""
    if (
        not isinstance(value, str)
        or not 1 <= len(value) <= 4096
        or any(character in value for character in "\x00\n\r")
    ):
        return None, "invalid path"
    try:
        value.encode("utf-8")
    except UnicodeEncodeError:
        return None, "invalid path"
    candidate = Path(value)
    if candidate.is_absolute():
        try:
            relative = candidate.relative_to(worktree)
        except ValueError:
            return None, "path escapes worktree"
    else:
        relative = Path(os.path.normpath(value))
        if relative.is_absolute() or relative == Path(".."):
            return None, "path escapes worktree"
        if relative.parts and relative.parts[0] == "..":
            return None, "path escapes worktree"
    return str(relative), ""


def _run_bounded(
    argv: list[str],
    *,
    cwd: Path,
    env: dict[str, str],
    timeout: float,
    output_limit: int,
) -> _ProbeResult:
    process = subprocess.Popen(
        argv,
        cwd=cwd,
        env=env,
        stdin=subprocess.DEVNULL,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        start_new_session=True,
    )
    assert process.stdout is not None
    assert process.stderr is not None
    captured = _BoundedOutput(output_limit)
    readers = [
        threading.Thread(
            target=captured.drain,
            args=(0, process.stdout),
            daemon=True,
        ),
        threading.Thread(
            target=captured.drain,
            args=(1, process.stderr),
            daemon=True,
        ),
    ]
    for reader in readers:
        reader.start()
    try:
        process.wait(timeout=timeout)
    except subprocess.TimeoutExpired:
        try:
            os.killpg(process.pid, signal.SIGKILL)
        except (ProcessLookupError, PermissionError):
            try:
                process.kill()
            except (ProcessLookupError, PermissionError):
                pass
        process.wait()
        raise
    finally:
        for reader in readers:
            reader.join()
    return _ProbeResult(
        returncode=process.returncode,
        stdout=captured.buffers[0].decode("utf-8"),
        stderr=captured.buffers[1].decode("utf-8"),
        output_truncated=captured.truncated,
    )
