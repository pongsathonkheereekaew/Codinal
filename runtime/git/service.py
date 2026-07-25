"""Sandboxed one-session/one-branch/one-worktree lifecycle."""

from __future__ import annotations

import hashlib
import os
import signal
import shlex
import shutil
import subprocess
import threading
from dataclasses import dataclass, replace
from pathlib import Path
from typing import Optional

from runtime.sandbox import SandboxedShell

from .models import GitWorkspaceRecord, WorktreeState
from .store import GitWorktreeStore

_PROBE_TIMEOUT_SECONDS = 10
_PROBE_OUTPUT_LIMIT = 1024 * 1024


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
        for directory in (
            self.data_dir,
            self.worktree_base,
            self.sandbox_base,
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
        return self.store.load(session_id)

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
