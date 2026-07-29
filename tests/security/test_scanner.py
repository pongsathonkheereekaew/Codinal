from __future__ import annotations

import json
import subprocess
from pathlib import Path

import pytest

from runtime.security import CodexSecurityScanner, SecurityScanError
from runtime.security import scanner as scanner_module


class _FinishedProcess:
    returncode = 0

    def poll(self):
        return self.returncode

    def terminate(self):
        self.returncode = -15

    def wait(self, timeout=None):
        return self.returncode


def _environment(tmp_path: Path) -> dict[str, str]:
    executable = tmp_path / "codex-security"
    executable.write_text("#!/bin/sh\n", encoding="utf-8")
    executable.chmod(0o700)
    return {"CODINAL_CODEX_SECURITY_BIN": str(executable)}


def _process_factory(command, **kwargs):
    output = Path(command[command.index("--output-dir") + 1])
    (output / "findings.json").write_text(
        json.dumps([{
            "id": "finding-1", "severity": "high", "title": "Unsafe input",
            "location": {"path": "src/app.py", "line": 14},
            "evidence": "must not leak",
        }]),
        encoding="utf-8",
    )
    (output / "coverage.json").write_text(
        json.dumps({"status": "complete", "summary": "all surfaces reviewed"}),
        encoding="utf-8",
    )
    return _FinishedProcess()


def test_scan_is_bounded_and_keeps_results_outside_workspace(tmp_path: Path) -> None:
    workspace = tmp_path / "repo"
    workspace.mkdir()
    (workspace / ".git").mkdir()
    scanner = CodexSecurityScanner(
        tmp_path / "data", process_factory=_process_factory, environment=_environment(tmp_path)
    )

    result = scanner.scan("session-1", workspace)

    assert result["ok"] is True
    assert result["max_cost_usd"] == 5
    assert not list((tmp_path / "data" / "security-scans" / "session-1").iterdir())
    assert result["coverage"] == {"status": "complete", "summary": "all surfaces reviewed"}
    assert result["findings"] == [{
        "id": "finding-1", "severity": "high", "title": "Unsafe input",
        "path": "src/app.py", "line": "14",
    }]


def test_scan_rejects_non_git_workspace(tmp_path: Path) -> None:
    scanner = CodexSecurityScanner(
        tmp_path / "data", process_factory=_process_factory, environment=_environment(tmp_path)
    )

    with pytest.raises(SecurityScanError, match="Git workspace"):
        scanner.scan("session-1", tmp_path)


def test_status_never_executes_or_installs_cli(tmp_path: Path) -> None:
    calls = []

    def factory(command, **kwargs):
        calls.append(command)
        return _FinishedProcess()

    scanner = CodexSecurityScanner(
        tmp_path / "data", process_factory=factory, environment=_environment(tmp_path)
    )

    assert scanner.status()["available"] is True
    assert calls == []


def test_status_rejects_untrusted_relative_executable(tmp_path: Path) -> None:
    scanner = CodexSecurityScanner(
        tmp_path / "data", environment={"CODINAL_CODEX_SECURITY_BIN": "./codex-security"}
    )

    status = scanner.status()

    assert status["available"] is False
    assert "absolute path" in status["reason"]


def test_status_rejects_executable_below_writable_parent(tmp_path: Path) -> None:
    unsafe = tmp_path / "unsafe"
    unsafe.mkdir()
    unsafe.chmod(0o777)
    executable = unsafe / "codex-security"
    executable.write_text("#!/bin/sh\n", encoding="utf-8")
    executable.chmod(0o700)
    scanner = CodexSecurityScanner(
        tmp_path / "data", environment={"CODINAL_CODEX_SECURITY_BIN": str(executable)}
    )

    status = scanner.status()

    assert status["available"] is False
    assert "parent directories" in status["reason"]


def test_scan_terminates_when_output_crosses_quota(tmp_path: Path, monkeypatch) -> None:
    workspace = tmp_path / "repo"
    workspace.mkdir()
    (workspace / ".git").mkdir()
    monkeypatch.setattr(scanner_module, "MAX_OUTPUT_BYTES", 1)
    process = _FinishedProcess()
    process.returncode = None

    def quota_factory(command, **kwargs):
        output = Path(command[command.index("--output-dir") + 1])
        (output / "partial.txt").write_text("too large", encoding="utf-8")
        return process

    scanner = CodexSecurityScanner(
        tmp_path / "data", process_factory=quota_factory, environment=_environment(tmp_path)
    )

    with pytest.raises(SecurityScanError, match="exceeded"):
        scanner.scan("session-1", workspace)
    assert process.returncode == -15
    assert not list((tmp_path / "data" / "security-scans" / "session-1").iterdir())


def test_scan_kills_stubborn_process_before_removing_output(tmp_path: Path, monkeypatch) -> None:
    workspace = tmp_path / "repo"
    workspace.mkdir()
    (workspace / ".git").mkdir()
    monkeypatch.setattr(scanner_module, "MAX_OUTPUT_BYTES", 1)

    class StubbornProcess:
        returncode = None
        killed = False

        def poll(self):
            return self.returncode

        def terminate(self):
            return None

        def kill(self):
            self.killed = True
            self.returncode = -9

        def wait(self, timeout=None):
            if not self.killed:
                raise subprocess.TimeoutExpired("codex-security", timeout or 0)
            return self.returncode

    process = StubbornProcess()

    def quota_factory(command, **kwargs):
        output = Path(command[command.index("--output-dir") + 1])
        (output / "partial.txt").write_text("too large", encoding="utf-8")
        return process

    scanner = CodexSecurityScanner(
        tmp_path / "data", process_factory=quota_factory, environment=_environment(tmp_path)
    )

    with pytest.raises(SecurityScanError, match="exceeded"):
        scanner.scan("session-1", workspace)
    assert process.killed is True
    assert not list((tmp_path / "data" / "security-scans" / "session-1").iterdir())
