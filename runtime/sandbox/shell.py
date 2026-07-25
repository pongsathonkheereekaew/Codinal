"""Bounded direct-argv execution inside a macOS Seatbelt profile."""

from __future__ import annotations

import os
import platform
import signal
import subprocess
import threading
from dataclasses import dataclass
from pathlib import Path
from typing import BinaryIO, Mapping, Optional

from runtime.policy.permissions import parse_command_argv

_DEFAULT_SANDBOX_EXECUTABLE = Path("/usr/bin/sandbox-exec")
_DEFAULT_TIMEOUT_SECONDS = 120.0
_DEFAULT_MAX_OUTPUT_BYTES = 1024 * 1024
_PROFILE = """
(version 1)
(deny default)
(allow process*)
(allow file-read*)
(allow sysctl-read)
(allow file-write*
    (subpath (param "WORKSPACE"))
    (subpath (param "SESSION_TMP"))
    (literal "/dev/null"))
(deny network*)
""".strip()
_SAFE_ENV_KEYS = ("PATH", "LANG", "LC_ALL", "LC_CTYPE", "TERM")


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

        argv = [
            str(self.sandbox_executable),
            "-D",
            f"WORKSPACE={self.workspace}",
            "-D",
            f"SESSION_TMP={self.temp_dir}",
            "-p",
            _PROFILE,
            *command_argv,
        ]
        with self._active_lock:
            if self._active is not None:
                raise RuntimeError("sandbox executor is already active")
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
            self._interrupted = False

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

    def interrupt(self) -> None:
        """Kill the active command and all descendants, if any."""
        with self._active_lock:
            process = self._active
            if process is None:
                return
            self._interrupted = True
            self._terminate(process)

    def _safe_environment(self) -> dict[str, str]:
        safe = {
            key: self._source_environment[key]
            for key in _SAFE_ENV_KEYS
            if self._source_environment.get(key)
        }
        safe.update(
            {
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
