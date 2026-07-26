"""Bounded direct-argv execution inside a macOS Seatbelt profile."""

from __future__ import annotations

import os
import platform
import signal
import subprocess
import threading
from dataclasses import dataclass
from pathlib import Path
from typing import BinaryIO, Iterable, Mapping, Optional

from runtime.policy.permissions import parse_command_argv

_DEFAULT_SANDBOX_EXECUTABLE = Path("/usr/bin/sandbox-exec")
_DEFAULT_TIMEOUT_SECONDS = 120.0
_DEFAULT_MAX_OUTPUT_BYTES = 1024 * 1024
_MAX_DECLARED_ROOTS = 32
_PROFILE_PREFIX = """
(version 1)
(deny default)
(import "system.sb")
(allow process*)
(allow file-read-metadata file-test-existence
    {read_ancestors}
    (path-ancestors "/Applications/Xcode.app")
    (path-ancestors "/opt/homebrew")
    (path-ancestors "/System/Volumes/Data/opt/homebrew"))
(allow file-read*
    {read_roots}
    (subpath "/Applications/Xcode.app")
    (subpath "/Library/Apple")
    (subpath "/Library/Developer")
    (subpath "/Library/Frameworks")
    (subpath "/System")
    (subpath "/System/Volumes/Data/opt/homebrew")
    (subpath "/bin")
    (subpath "/dev")
    (subpath "/opt/homebrew")
    (literal "/private/etc/gitconfig")
    (subpath "/private/var/select")
    (subpath "/sbin")
    (subpath "/usr"))
(allow file-map-executable
    {read_roots}
    (subpath "/Applications/Xcode.app")
    (subpath "/Library/Apple")
    (subpath "/Library/Developer")
    (subpath "/Library/Frameworks")
    (subpath "/System")
    (subpath "/System/Volumes/Data/opt/homebrew")
    (subpath "/opt/homebrew")
    (subpath "/usr"))
(allow sysctl-read)
(allow file-write*
    {write_roots}
    (literal "/dev/null"))
(deny network*)
"""
_SAFE_ENV_KEYS = ("PATH", "LANG", "LC_ALL", "LC_CTYPE", "TERM")


def _sandbox_profile(read_count: int, write_count: int) -> str:
    read_roots = "\n    ".join(
        f'(subpath (param "READ_ROOT_{index}"))'
        for index in range(read_count)
    )
    read_ancestors = "\n    ".join(
        f'(path-ancestors (param "READ_ROOT_{index}"))'
        for index in range(read_count)
    )
    write_roots = "\n    ".join(
        f'(subpath (param "WRITE_ROOT_{index}"))'
        for index in range(write_count)
    )
    return _PROFILE_PREFIX.format(
        read_roots=read_roots,
        read_ancestors=read_ancestors,
        write_roots=write_roots,
    ).strip()


class InvalidCommandError(ValueError):
    """The command is empty, malformed, or asks for shell evaluation."""


class SandboxUnavailableError(RuntimeError):
    """The mandatory sandbox backend is missing or not executable."""


@dataclass(frozen=True)
class SandboxResult:
    exit_code: Optional[int]
    stdout: str
    stderr: str
    timed_out: bool = False
    interrupted: bool = False
    output_truncated: bool = False

    def as_dict(self) -> dict[str, object]:
        return {
            "exit_code": self.exit_code,
            "stdout": self.stdout,
            "stderr": self.stderr,
            "timed_out": self.timed_out,
            "interrupted": self.interrupted,
            "output_truncated": self.output_truncated,
        }


class _BoundedCapture:
    def __init__(self, maximum: int) -> None:
        self._remaining = maximum
        self._lock = threading.Lock()
        self._buffers: dict[str, bytearray] = {
            "stdout": bytearray(),
            "stderr": bytearray(),
        }
        self.truncated = False

    def drain(self, name: str, stream: BinaryIO) -> None:
        try:
            while chunk := stream.read(16 * 1024):
                with self._lock:
                    accepted = min(len(chunk), self._remaining)
                    if accepted:
                        self._buffers[name].extend(chunk[:accepted])
                        self._remaining -= accepted
                    if accepted < len(chunk):
                        self.truncated = True
        finally:
            stream.close()

    def text(self, name: str) -> str:
        return self._buffers[name].decode("utf-8", errors="replace")


class SandboxedShell:
    """Execute one direct argv at a time with writes and network constrained."""

    def __init__(
        self,
        *,
        workspace: str | Path,
        temp_dir: str | Path,
        timeout_seconds: float = _DEFAULT_TIMEOUT_SECONDS,
        max_output_bytes: int = _DEFAULT_MAX_OUTPUT_BYTES,
        sandbox_executable: str | Path = _DEFAULT_SANDBOX_EXECUTABLE,
        environment: Optional[Mapping[str, str]] = None,
        workspace_writable: bool = True,
        additional_read_roots: Iterable[str | Path] = (),
        additional_write_roots: Iterable[str | Path] = (),
    ) -> None:
        self.workspace = Path(workspace).expanduser().resolve()
        self.temp_dir = Path(temp_dir).expanduser().resolve()
        if not self.workspace.is_dir():
            raise ValueError("workspace must be an existing directory")
        if self.temp_dir == Path(self.temp_dir.anchor):
            raise ValueError("temp directory cannot be a filesystem root")
        if timeout_seconds <= 0:
            raise ValueError("timeout must be positive")
        if max_output_bytes <= 0:
            raise ValueError("output limit must be positive")
        self.temp_dir.mkdir(mode=0o700, parents=True, exist_ok=True)
        os.chmod(self.temp_dir, 0o700)
        extra_reads = _existing_roots(
            additional_read_roots,
            label="read root",
        )
        extra_writes = _existing_roots(
            additional_write_roots,
            label="write root",
        )
        self.read_roots = _deduplicate_paths(
            [self.workspace, self.temp_dir, *extra_reads, *extra_writes]
        )
        self.write_roots = _deduplicate_paths(
            [
                self.temp_dir,
                *([self.workspace] if workspace_writable else []),
                *extra_writes,
            ]
        )
        if (
            len(self.read_roots) > _MAX_DECLARED_ROOTS
            or len(self.write_roots) > _MAX_DECLARED_ROOTS
        ):
            raise ValueError("too many sandbox roots")
        self.timeout_seconds = float(timeout_seconds)
        self.max_output_bytes = int(max_output_bytes)
        self.sandbox_executable = Path(sandbox_executable).expanduser().resolve()
        self._source_environment = dict(
            os.environ if environment is None else environment
        )
        self._active_lock = threading.Lock()
        self._active: Optional[subprocess.Popen[bytes]] = None
        self._interrupted = False

    def run(
        self,
        command: str,
        *,
        timeout_seconds: Optional[float] = None,
    ) -> SandboxResult:
        try:
            command_argv = parse_command_argv(command)
        except ValueError as exc:
            raise InvalidCommandError(str(exc)) from None
        if (
            platform.system() != "Darwin"
            or not self.sandbox_executable.is_file()
            or not os.access(self.sandbox_executable, os.X_OK)
        ):
            raise SandboxUnavailableError("sandbox backend is unavailable")
        timeout = (
            self.timeout_seconds
            if timeout_seconds is None
            else float(timeout_seconds)
        )
        if timeout <= 0:
            raise ValueError("timeout must be positive")

        definitions: list[str] = []
        for index, root in enumerate(self.read_roots):
            definitions.extend(["-D", f"READ_ROOT_{index}={root}"])
        for index, root in enumerate(self.write_roots):
            definitions.extend(["-D", f"WRITE_ROOT_{index}={root}"])
        argv = [
            str(self.sandbox_executable),
            *definitions,
            "-p",
            _sandbox_profile(
                len(self.read_roots),
                len(self.write_roots),
            ),
            *command_argv,
        ]
        with self._active_lock:
            if self._active is not None:
                raise RuntimeError("sandbox executor is already active")
            if self._interrupted:
                self._interrupted = False
                return SandboxResult(
                    exit_code=130,
                    stdout="",
                    stderr="",
                    interrupted=True,
                )
            process = subprocess.Popen(
                argv,
                cwd=self.workspace,
                env=self._safe_environment(),
                stdin=subprocess.DEVNULL,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                start_new_session=True,
            )
            self._active = process

        capture = _BoundedCapture(self.max_output_bytes)
        assert process.stdout is not None
        assert process.stderr is not None
        readers = [
            threading.Thread(
                target=capture.drain,
                args=("stdout", process.stdout),
                daemon=True,
            ),
            threading.Thread(
                target=capture.drain,
                args=("stderr", process.stderr),
                daemon=True,
            ),
        ]
        for reader in readers:
            reader.start()

        timed_out = False
        try:
            process.wait(timeout=timeout)
        except subprocess.TimeoutExpired:
            timed_out = True
            self._terminate(process)
            process.wait()
        finally:
            for reader in readers:
                reader.join()
            with self._active_lock:
                interrupted = self._interrupted
                self._interrupted = False
                if self._active is process:
                    self._active = None

        return SandboxResult(
            exit_code=process.returncode,
            stdout=capture.text("stdout"),
            stderr=capture.text("stderr"),
            timed_out=timed_out,
            interrupted=interrupted,
            output_truncated=capture.truncated,
        )

    def interrupt(self) -> bool:
        """Kill the active command and all descendants, if any."""
        with self._active_lock:
            process = self._active
            self._interrupted = True
            if process is None:
                return False
            self._terminate(process)
            return True

    def begin_turn(self) -> None:
        with self._active_lock:
            if self._active is not None:
                raise RuntimeError("sandbox executor is still active")
            self._interrupted = False

    def _safe_environment(self) -> dict[str, str]:
        safe = {
            key: self._source_environment[key]
            for key in _SAFE_ENV_KEYS
            if self._source_environment.get(key)
        }
        developer_bins = [
            path
            for path in (
                "/Applications/Xcode.app/Contents/Developer/usr/bin",
                "/Library/Developer/CommandLineTools/usr/bin",
            )
            if Path(path).is_dir()
        ]
        source_path = safe.get("PATH", "/usr/bin:/bin:/usr/sbin:/sbin")
        safe["PATH"] = os.pathsep.join([*developer_bins, source_path])
        safe.update(
            {
                "GIT_OPTIONAL_LOCKS": "0",
                "HOME": str(self.temp_dir),
                "TMPDIR": str(self.temp_dir),
                "XDG_CACHE_HOME": str(self.temp_dir / "cache"),
                "XDG_CONFIG_HOME": str(self.temp_dir / "config"),
            }
        )
        return safe

    @staticmethod
    def _terminate(process: subprocess.Popen[bytes]) -> None:
        if process.poll() is not None:
            return
        try:
            os.killpg(process.pid, signal.SIGKILL)
        except ProcessLookupError:
            return
        except PermissionError:
            try:
                process.kill()
            except (ProcessLookupError, PermissionError):
                return


def _existing_roots(
    values: Iterable[str | Path],
    *,
    label: str,
) -> list[Path]:
    roots: list[Path] = []
    for value in values:
        path = Path(value).expanduser().resolve()
        if path == Path(path.anchor):
            raise ValueError(f"{label} cannot be a filesystem root")
        if not path.is_dir():
            raise ValueError(f"{label} must be an existing directory")
        roots.append(path)
    return roots


def _deduplicate_paths(paths: Iterable[Path]) -> list[Path]:
    unique: list[Path] = []
    seen: set[Path] = set()
    for path in paths:
        if path in seen:
            continue
        seen.add(path)
        unique.append(path)
    return unique
