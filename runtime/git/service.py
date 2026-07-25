"""Sandboxed one-session/one-branch/one-worktree lifecycle."""

from __future__ import annotations

import hashlib
import os
import signal
import shlex
import shutil
import subprocess
import threading
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


class GitWorkspaceError(RuntimeError):
    """A stable, user-displayable Git workspace lifecycle failure."""


class DetachedHeadError(GitWorkspaceError):
    """The selected source worktree has no named branch to apply back to."""


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

    def close(self) -> None:
        self.store.close()

    def load(self, session_id: str) -> Optional[GitWorkspaceRecord]:
        return self.store.load(session_id)

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
                if existing.state is WorktreeState.ACTIVE:
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
            shell = self._git_shell(creating)
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
            raise GitWorkspaceError("workspace is not a Git worktree") from None
        root = Path(value).expanduser().resolve()
        if not root.is_dir():
            raise GitWorkspaceError("workspace is not a Git worktree")
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

    def _probe(self, cwd: Path, *arguments: str) -> str:
        result = self._probe_result(cwd, *arguments)
        if result.returncode != 0:
            raise GitWorkspaceError("Git repository inspection failed")
        return result.stdout.rstrip("\n")

    def _probe_result(
        self,
        cwd: Path,
        *arguments: str,
    ) -> subprocess.CompletedProcess[str]:
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
        if getattr(result, "output_truncated", False):
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


def _run_bounded(
    argv: list[str],
    *,
    cwd: Path,
    env: dict[str, str],
    timeout: float,
    output_limit: int,
) -> subprocess.CompletedProcess[str]:
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
            process.kill()
        process.wait()
        raise
    finally:
        for reader in readers:
            reader.join()
    result = subprocess.CompletedProcess(
        argv,
        process.returncode,
        stdout=captured.buffers[0].decode("utf-8"),
        stderr=captured.buffers[1].decode("utf-8"),
    )
    result.output_truncated = captured.truncated
    return result
