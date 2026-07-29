"""Bounded adapter for an already-installed Codex Security CLI.

The adapter never installs the CLI, never starts a scan by itself, and writes
reports outside the scanned repository.  A scan is started only by an explicit
Codinal UI action.
"""

from __future__ import annotations

import json
import os
import shutil
import signal
import stat
import subprocess
import time
import uuid
import re
from pathlib import Path
from typing import Any, Callable, Mapping

from runtime.storage.migrations import secure_directory

MAX_COST_USD = 5
SCAN_TIMEOUT_SECONDS = 15 * 60
MAX_RESULT_BYTES = 2 * 1024 * 1024
MAX_OUTPUT_BYTES = 20 * 1024 * 1024
SESSION_ID_RE = re.compile(r"[A-Za-z0-9][A-Za-z0-9_-]{0,127}")


class SecurityScanError(RuntimeError):
    """A safe, user-facing failure from the external scanner."""


ProcessFactory = Callable[..., Any]


class CodexSecurityScanner:
    def __init__(
        self,
        data_dir: str | Path,
        *,
        process_factory: ProcessFactory = subprocess.Popen,
        environment: Mapping[str, str] | None = None,
        executable_provider: Callable[[], str | None] | None = None,
    ) -> None:
        self.base = Path(data_dir).expanduser().resolve() / "security-scans"
        secure_directory(self.base)
        self._process_factory = process_factory
        self._environment = environment if environment is not None else os.environ
        self._executable_provider = executable_provider

    def status(self) -> dict[str, object]:
        executable, reason = self._configured_executable()
        if executable is None:
            return {
                "available": False,
                "reason": reason,
                "max_cost_usd": MAX_COST_USD,
            }
        return {
            "available": True,
            "executable": str(executable),
            "reason": "Configured executable runs only after you confirm a scan. Codinal never installs it.",
            "max_cost_usd": MAX_COST_USD,
        }

    def scan(self, session_id: str, workspace: str | Path) -> dict[str, object]:
        if not SESSION_ID_RE.fullmatch(session_id):
            raise SecurityScanError("Invalid security scan session.")
        root = Path(workspace).expanduser().resolve()
        if not root.is_dir() or not (root / ".git").exists():
            raise SecurityScanError("Codex Security requires a Git workspace.")
        output = self.base / session_id / f"scan-{int(time.time())}-{uuid.uuid4().hex[:8]}"
        secure_directory(output.parent)
        secure_directory(output)
        # Validate immediately before execution, after all filesystem setup.
        executable, reason = self._configured_executable()
        if executable is None:
            shutil.rmtree(output, ignore_errors=True)
            raise SecurityScanError(reason)
        command = [
            str(executable),
            "scan",
            str(root),
            "--working-tree",
            "--base",
            "HEAD",
            "--output-dir",
            str(output),
            "--max-cost",
            str(MAX_COST_USD),
        ]
        try:
            try:
                process = self._process_factory(
                    command,
                    cwd=root,
                    stdin=subprocess.DEVNULL,
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                    text=True,
                    start_new_session=True,
                )
            except OSError as error:
                raise SecurityScanError("Could not start Codex Security.") from error
            deadline = time.monotonic() + SCAN_TIMEOUT_SECONDS
            while process.poll() is None:
                if _tree_size(output) > MAX_OUTPUT_BYTES:
                    _stop_process(process)
                    raise SecurityScanError("Security scan output exceeded the 20 MiB safety limit.")
                if time.monotonic() >= deadline:
                    _stop_process(process)
                    raise SecurityScanError("Security scan timed out after 15 minutes.")
                time.sleep(0.1)
            if _tree_size(output) > MAX_OUTPUT_BYTES:
                raise SecurityScanError("Security scan output exceeded the 20 MiB safety limit.")
            result = self._read_result(output)
            result.update(
                {
                    "ok": process.returncode == 0,
                    "exit_code": process.returncode,
                    "summary": "Security scan completed." if process.returncode == 0 else "Security scan exited with an error.",
                    "max_cost_usd": MAX_COST_USD,
                }
            )
            return result
        finally:
            # Findings may contain source excerpts. Keep only the bounded,
            # presentation-safe summary returned above; never retain raw reports.
            if output.is_dir() and not output.is_symlink():
                shutil.rmtree(output, ignore_errors=True)

    def _read_result(self, output: Path) -> dict[str, object]:
        findings = _read_json(output / "findings.json", default=[])
        coverage = _read_json(output / "coverage.json", default={})
        if not isinstance(findings, list):
            findings = []
        normalized = [_finding(item) for item in findings if isinstance(item, dict)]
        return {
            "findings": normalized[:100],
            "finding_count": len(normalized),
            "coverage": _coverage(coverage),
        }

    def _configured_executable(self) -> tuple[Path | None, str]:
        configured = self._executable_provider() if self._executable_provider else None
        raw = (configured or self._environment.get("CODINAL_CODEX_SECURITY_BIN", "")).strip()
        if not raw:
            return None, (
                "Configure CODINAL_CODEX_SECURITY_BIN to the absolute Codex Security executable installed from @openai/codex-security."
            )
        candidate = Path(raw).expanduser()
        if not candidate.is_absolute():
            return None, "CODINAL_CODEX_SECURITY_BIN must be an absolute path."
        try:
            executable = candidate.resolve(strict=True)
            mode = stat.S_IMODE(executable.stat().st_mode)
        except OSError:
            return None, "Configured Codex Security executable is unavailable."
        if not executable.is_file() or not os.access(executable, os.X_OK):
            return None, "Configured Codex Security executable is not executable."
        if not _is_trusted_executable_path(executable, mode):
            return None, (
                "Configured Codex Security path and its parent directories must be owned by you or root and not group- or world-writable."
            )
        return executable, ""


def _read_json(path: Path, *, default: object) -> object:
    try:
        if not path.is_file() or path.stat().st_size > MAX_RESULT_BYTES:
            return default
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError):
        return default


def _finding(value: dict[str, Any]) -> dict[str, str]:
    location = value.get("location")
    if isinstance(location, dict):
        path = str(location.get("path", ""))[:512]
        line = str(location.get("line", ""))[:16]
    else:
        path = str(value.get("path", ""))[:512]
        line = str(value.get("line", ""))[:16]
    return {
        "id": str(value.get("id", ""))[:128],
        "severity": str(value.get("severity", "unknown"))[:32],
        "title": str(value.get("title", value.get("summary", "Finding")))[:512],
        "path": path,
        "line": line,
    }


def _coverage(value: object) -> dict[str, str]:
    if not isinstance(value, dict):
        return {"status": "unknown"}
    return {
        "status": str(value.get("status", value.get("coverage", "unknown")))[:32],
        "summary": str(value.get("summary", ""))[:512],
    }


def _tree_size(root: Path) -> int:
    total = 0
    try:
        for item in root.rglob("*"):
            if item.is_symlink() or not item.is_file():
                continue
            total += item.stat().st_size
            if total > MAX_OUTPUT_BYTES:
                return total
    except OSError:
        return MAX_OUTPUT_BYTES + 1
    return total


def _is_trusted_executable_path(executable: Path, file_mode: int) -> bool:
    """Reject replacement through a writable parent before execution."""
    allowed_owners = {os.getuid(), 0}
    current = executable
    while True:
        try:
            metadata = current.stat()
        except OSError:
            return False
        mode = file_mode if current == executable else stat.S_IMODE(metadata.st_mode)
        if metadata.st_uid not in allowed_owners or mode & 0o022:
            return False
        if current.parent == current:
            return True
        current = current.parent


def _stop_process(process: Any) -> None:
    """Stop the CLI process group before its temporary output is removed."""
    pid = getattr(process, "pid", None)
    try:
        if isinstance(pid, int):
            os.killpg(pid, signal.SIGTERM)
        else:
            process.terminate()
        process.wait(timeout=10)
        return
    except (OSError, subprocess.TimeoutExpired):
        pass
    try:
        if isinstance(pid, int):
            os.killpg(pid, signal.SIGKILL)
        else:
            process.kill()
        process.wait(timeout=10)
    except (OSError, subprocess.TimeoutExpired):
        # The process is already best-effort terminated; never retain reports.
        return
