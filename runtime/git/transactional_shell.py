"""Execute shell commands in a private mirror and apply only their delta."""

from __future__ import annotations

import hashlib
import os
import shutil
import signal
import stat
import subprocess
import tempfile
import threading
from dataclasses import dataclass, replace
from pathlib import Path, PurePosixPath
from typing import Callable, Optional

from runtime.sandbox import SandboxResult, SandboxedShell

_MAX_CHANGED_FILES = 10_000
_MAX_FILE_BYTES = 32 * 1024 * 1024
_MAX_PATCH_BYTES = 32 * 1024 * 1024


@dataclass(frozen=True)
class _FileState:
    digest: str = ""
    mode: int = 0


class _TransactionInterrupted(Exception):
    pass


class TransactionalShell:
    """Run a command against a COW mirror before conflict-checked apply."""

    transactional_mutations = True

    def __init__(
        self,
        *,
        workspace: Path,
        temp_dir: Path,
        git_executable: Path,
        apply_attributed_delta: Callable[
            [tuple[Path, ...], Callable[[], bool]],
            bool,
        ],
        git_read_root: Path | None = None,
    ) -> None:
        self.workspace = workspace.expanduser().resolve()
        self.temp_dir = temp_dir.expanduser().resolve()
        self.git_executable = git_executable.expanduser().resolve()
        self.apply_attributed_delta = apply_attributed_delta
        self.git_read_root = (
            git_read_root.expanduser().resolve()
            if git_read_root is not None
            else None
        )
        if not self.workspace.is_dir():
            raise ValueError("workspace must be an existing directory")
        self.temp_dir.mkdir(mode=0o700, parents=True, exist_ok=True)
        os.chmod(self.temp_dir, 0o700)
        self._run_lock = threading.Lock()
        self._commit_lock = threading.Lock()
        self._lock = threading.Lock()
        self._active: SandboxedShell | None = None
        self._active_process: subprocess.Popen[bytes] | None = None
        self._cancelled = threading.Event()

    def run(
        self,
        command: str,
        *,
        timeout_seconds: Optional[float] = None,
    ) -> SandboxResult:
        with self._run_lock:
            self._retry_stale_transactions()
            if self._cancelled.is_set():
                return _interrupted(None)
            transaction = Path(
                tempfile.mkdtemp(
                    prefix="shell-",
                    dir=self.temp_dir,
                )
            )
            result = self._run_transaction(
                command,
                timeout_seconds=timeout_seconds,
                transaction=transaction,
            )
            if not self._cleanup_transaction(transaction):
                return _with_warning(
                    result,
                    "shell transaction cleanup pending",
                )
            return result

    def _run_transaction(
        self,
        command: str,
        *,
        timeout_seconds: Optional[float],
        transaction: Path,
    ) -> SandboxResult:
        before = transaction / "before"
        after = transaction / "after"
        command_temp = transaction / "tmp"
        patch_path = transaction / "changes.patch"
        result: SandboxResult | None = None
        try:
            _clone_tree(
                self.workspace,
                before,
                runner=self._run_helper,
            )
            _clone_tree(
                before,
                after,
                runner=self._run_helper,
            )
            if self._cancelled.is_set():
                raise _TransactionInterrupted
            shell = SandboxedShell(
                workspace=after,
                temp_dir=command_temp,
                additional_read_roots=(
                    [self.git_read_root]
                    if self.git_read_root is not None
                    else []
                ),
            )
            with self._lock:
                self._active = shell
            try:
                result = shell.run(
                    command,
                    timeout_seconds=timeout_seconds,
                )
            finally:
                with self._lock:
                    self._active = None
            if (
                result.interrupted
                or result.timed_out
                or self._cancelled.is_set()
            ):
                return _interrupted(result)
            if _protected_git_state(
                before,
                cancelled=self._cancelled.is_set,
            ) != _protected_git_state(
                after,
                cancelled=self._cancelled.is_set,
            ):
                return _failed(
                    result,
                    "shell transaction changed protected Git metadata",
                )
            changed = _changed_paths(
                self.git_executable,
                transaction,
                runner=self._run_helper,
            )
            if self._cancelled.is_set():
                return _interrupted(result)
            if not changed:
                return result
            if any(
                ".git"
                in (part.casefold() for part in PurePosixPath(path).parts)
                for path in changed
            ):
                return _failed(
                    result,
                    "shell transaction changed protected Git metadata",
                )
            if len(changed) > _MAX_CHANGED_FILES:
                return _failed(
                    result,
                    "shell transaction changed too many files",
                )
            for relative in changed:
                baseline = _file_state(
                    before / relative,
                    cancelled=self._cancelled.is_set,
                )
                proposed = _file_state(
                    after / relative,
                    cancelled=self._cancelled.is_set,
                )
                current = _file_state(
                    self.workspace / relative,
                    cancelled=self._cancelled.is_set,
                )
                if current != baseline:
                    return _failed(
                        result,
                        (
                            "shell transaction conflicts with a "
                            f"concurrent edit: {relative}"
                        ),
                    )
                if proposed.mode not in {0, 0o100644, 0o100755}:
                    return _failed(
                        result,
                        f"shell transaction changed unsupported path: {relative}",
                    )
            if not _write_patch(
                self.git_executable,
                transaction,
                patch_path,
                runner=self._run_helper,
            ):
                return _failed(
                    result,
                    "shell transaction could not prepare changes",
                )
            if patch_path.stat().st_size > _MAX_PATCH_BYTES:
                return _failed(
                    result,
                    "shell transaction exceeds change limit",
                )
            if self._cancelled.is_set():
                return _interrupted(result)
            paths = tuple(
                self.workspace / relative
                for relative in changed
            )
            if not self.apply_attributed_delta(
                paths,
                lambda: self._apply_if_active(
                    patch_path,
                ),
            ):
                if self._cancelled.is_set():
                    return _interrupted(result)
                return _failed(
                    result,
                    "shell transaction conflicts with current files",
                )
            return replace(result, changed_paths=tuple(changed))
        except _TransactionInterrupted:
            return _interrupted(result)
        except Exception:
            return SandboxResult(
                exit_code=1,
                stdout="",
                stderr="shell transaction unavailable",
                profile="build",
            )

    def interrupt(self) -> None:
        with self._commit_lock:
            self._cancelled.set()
        with self._lock:
            shell = self._active
            process = self._active_process
        if shell is not None:
            shell.interrupt()
        if process is not None:
            self._terminate_helper(process)

    def begin_turn(self) -> None:
        with self._lock:
            if self._active is not None or self._active_process is not None:
                raise RuntimeError("shell transaction is still active")
        with self._commit_lock:
            self._cancelled.clear()

    def _apply_if_active(self, patch_path: Path) -> bool:
        with self._commit_lock:
            if self._cancelled.is_set():
                return False
            return _apply_patch(
                self.git_executable,
                self.workspace,
                patch_path,
            )

    def _run_helper(
        self,
        arguments,
        *,
        cwd=None,
        env=None,
        stdin=None,
        stdout=None,
        stderr=None,
        timeout=120,
    ) -> subprocess.CompletedProcess[bytes]:
        if self._cancelled.is_set():
            raise _TransactionInterrupted
        process = subprocess.Popen(
            arguments,
            cwd=cwd,
            env=env,
            stdin=stdin,
            stdout=stdout,
            stderr=stderr,
            start_new_session=True,
        )
        with self._lock:
            self._active_process = process
            cancelled = self._cancelled.is_set()
        if cancelled:
            self._terminate_helper(process)
        try:
            output, errors = process.communicate(timeout=timeout)
        except subprocess.TimeoutExpired:
            self._terminate_helper(process)
            output, errors = process.communicate()
            raise
        finally:
            with self._lock:
                if self._active_process is process:
                    self._active_process = None
        if self._cancelled.is_set():
            raise _TransactionInterrupted
        return subprocess.CompletedProcess(
            arguments,
            process.returncode,
            output,
            errors,
        )

    @staticmethod
    def _terminate_helper(process: subprocess.Popen[bytes]) -> None:
        if process.poll() is not None:
            return
        try:
            os.killpg(process.pid, signal.SIGKILL)
        except (OSError, ProcessLookupError):
            pass

    def _retry_stale_transactions(self) -> None:
        for candidate in self.temp_dir.iterdir():
            if (
                candidate.is_dir()
                and candidate.name.startswith(
                    ("shell-", "cleanup-")
                )
            ):
                try:
                    shutil.rmtree(candidate)
                except OSError:
                    pass

    def _cleanup_transaction(self, transaction: Path) -> bool:
        try:
            shutil.rmtree(transaction)
            return True
        except OSError:
            quarantine = (
                self.temp_dir
                / f"cleanup-{transaction.name.removeprefix('shell-')}"
            )
            try:
                transaction.replace(quarantine)
            except OSError:
                pass
            return False


def _clone_tree(
    source: Path,
    destination: Path,
    *,
    runner: Callable[..., subprocess.CompletedProcess[bytes]],
) -> None:
    completed = runner(
        ["/bin/cp", "-cR", f"{source}/.", destination],
        stdin=subprocess.DEVNULL,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.PIPE,
        timeout=120,
    )
    if completed.returncode != 0:
        raise OSError("unable to clone shell workspace")
    os.chmod(destination, 0o700)


def _git_environment() -> dict[str, str]:
    environment = {
        key: os.environ[key]
        for key in ("LANG", "LC_ALL", "LC_CTYPE", "PATH")
        if os.environ.get(key)
    }
    environment.update(
        {
            "GIT_ATTR_NOSYSTEM": "1",
            "GIT_CONFIG_GLOBAL": "/dev/null",
            "GIT_CONFIG_SYSTEM": "/dev/null",
            "GIT_OPTIONAL_LOCKS": "0",
            "GIT_TERMINAL_PROMPT": "0",
        }
    )
    return environment


def _changed_paths(
    git_executable: Path,
    transaction: Path,
    *,
    runner: Callable[..., subprocess.CompletedProcess[bytes]],
) -> list[str]:
    completed = runner(
        [
            git_executable,
            "-c",
            "core.quotepath=false",
            "diff",
            "--no-index",
            "--name-status",
            "-z",
            "--no-renames",
            "--",
            "before",
            "after",
        ],
        cwd=transaction,
        env=_git_environment(),
        stdin=subprocess.DEVNULL,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        timeout=120,
    )
    if completed.returncode not in {0, 1}:
        raise OSError("unable to inspect shell changes")
    if completed.returncode == 0:
        return []
    fields = completed.stdout.split(b"\0")
    if fields and not fields[-1]:
        fields.pop()
    if len(fields) % 2:
        raise ValueError("invalid shell change list")
    changed: list[str] = []
    for index in range(0, len(fields), 2):
        status_value = os.fsdecode(fields[index])
        if status_value not in {"A", "D", "M"}:
            raise ValueError("unsupported shell change")
        raw_path = os.fsdecode(fields[index + 1])
        prefix = "after/" if status_value == "A" else "before/"
        if not raw_path.startswith(prefix):
            raise ValueError("invalid shell change path")
        relative = raw_path[len(prefix) :]
        parsed = PurePosixPath(relative)
        if (
            not relative
            or parsed.is_absolute()
            or ".." in parsed.parts
            or str(parsed) != relative
            or len(os.fsencode(relative)) > 4096
        ):
            raise ValueError("invalid shell change path")
        changed.append(relative)
    return sorted(set(changed))


def _protected_git_state(
    root: Path,
    *,
    cancelled: Callable[[], bool],
) -> dict[str, tuple[str, int, str]]:
    protected: dict[str, tuple[str, int, str]] = {}
    for directory, names, files in os.walk(
        root,
        topdown=True,
        followlinks=False,
    ):
        if cancelled():
            raise _TransactionInterrupted
        base = Path(directory)
        for name in (*names, *files):
            path = base / name
            relative = path.relative_to(root)
            if ".git" not in relative.parts:
                continue
            metadata = path.lstat()
            mode = stat.S_IMODE(metadata.st_mode)
            if stat.S_ISREG(metadata.st_mode):
                digest = _file_state(
                    path,
                    cancelled=cancelled,
                ).digest
                kind = "file"
            elif stat.S_ISDIR(metadata.st_mode):
                digest = ""
                kind = "directory"
            elif stat.S_ISLNK(metadata.st_mode):
                digest = os.readlink(path)
                kind = "symlink"
            else:
                digest = ""
                kind = "other"
            protected[relative.as_posix()] = (kind, mode, digest)
    return protected


def _file_state(
    path: Path,
    *,
    cancelled: Callable[[], bool],
) -> _FileState:
    if cancelled():
        raise _TransactionInterrupted
    try:
        metadata = path.lstat()
    except FileNotFoundError:
        return _FileState()
    if (
        not stat.S_ISREG(metadata.st_mode)
        or metadata.st_size > _MAX_FILE_BYTES
    ):
        raise ValueError("unsupported shell transaction file")
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        while chunk := stream.read(1024 * 1024):
            if cancelled():
                raise _TransactionInterrupted
            digest.update(chunk)
    mode = (
        0o100755
        if metadata.st_mode & stat.S_IXUSR
        else 0o100644
    )
    return _FileState(digest.hexdigest(), mode)


def _write_patch(
    git_executable: Path,
    transaction: Path,
    patch_path: Path,
    *,
    runner: Callable[..., subprocess.CompletedProcess[bytes]],
) -> bool:
    completed = runner(
        [
            git_executable,
            "diff",
            "--no-index",
            "--binary",
            "--full-index",
            "--no-renames",
            "--no-ext-diff",
            "--no-textconv",
            f"--output={patch_path}",
            "--",
            "before",
            "after",
        ],
        cwd=transaction,
        env=_git_environment(),
        stdin=subprocess.DEVNULL,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.PIPE,
        timeout=120,
    )
    return completed.returncode == 1 and patch_path.is_file()


def _apply_patch(
    git_executable: Path,
    workspace: Path,
    patch_path: Path,
) -> bool:
    base = [
        git_executable,
        "-C",
        workspace,
        "-c",
        "core.hooksPath=/dev/null",
        "apply",
        "-p2",
        "--binary",
        "--whitespace=nowarn",
    ]
    environment = _git_environment()
    checked = subprocess.run(
        [*base, "--check", patch_path],
        env=environment,
        stdin=subprocess.DEVNULL,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.PIPE,
        timeout=120,
    )
    if checked.returncode != 0:
        return False
    applied = subprocess.run(
        [*base, patch_path],
        env=environment,
        stdin=subprocess.DEVNULL,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.PIPE,
        timeout=120,
    )
    return applied.returncode == 0


def _failed(result: SandboxResult, message: str) -> SandboxResult:
    stderr = result.stderr
    if stderr and not stderr.endswith("\n"):
        stderr += "\n"
    return replace(
        result,
        exit_code=1,
        stderr=f"{stderr}{message}",
        timed_out=False,
        interrupted=False,
    )


def _interrupted(result: SandboxResult | None) -> SandboxResult:
    if result is None:
        return SandboxResult(
            exit_code=130,
            stdout="",
            stderr="",
            interrupted=True,
            profile="build",
        )
    return replace(result, interrupted=True)


def _with_warning(
    result: SandboxResult,
    message: str,
) -> SandboxResult:
    stderr = result.stderr
    if stderr and not stderr.endswith("\n"):
        stderr += "\n"
    return replace(result, stderr=f"{stderr}{message}")
