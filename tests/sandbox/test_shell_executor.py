from __future__ import annotations

import os
import platform
import socket
import sys
import threading
import time
from pathlib import Path

import pytest

from runtime.sandbox import (
    InvalidCommandError,
    SandboxedShell,
    SandboxUnavailableError,
)

PYTHON_EXECUTABLE = Path(sys.executable).resolve()

requires_seatbelt = pytest.mark.skipif(
    platform.system() != "Darwin"
    or not Path("/usr/bin/sandbox-exec").is_file(),
    reason="Seatbelt is a macOS release boundary",
)


@pytest.fixture
def shell(tmp_path: Path) -> SandboxedShell:
    workspace = tmp_path / "workspace"
    scratch = tmp_path / "scratch"
    workspace.mkdir()
    return SandboxedShell(
        workspace=workspace,
        temp_dir=scratch,
        timeout_seconds=2,
        max_output_bytes=1_024,
    )


@pytest.mark.parametrize(
    "command",
    [
        "",
        "git status && whoami",
        "git status; whoami",
        "printf x > escaped",
        "echo $(whoami)",
        "echo `whoami`",
        "echo unterminated'",
    ],
)
def test_rejects_empty_malformed_and_shell_operator_commands(
    shell: SandboxedShell,
    command: str,
) -> None:
    with pytest.raises(InvalidCommandError):
        shell.run(command)


@requires_seatbelt
def test_does_not_inherit_provider_secrets(
    shell: SandboxedShell,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("OPENAI_API_KEY", "must-not-leak")

    result = shell.run("/usr/bin/env")

    assert result.exit_code == 0
    assert "OPENAI_API_KEY" not in result.stdout
    assert result.stderr == ""


@requires_seatbelt
def test_caps_captured_output(shell: SandboxedShell) -> None:
    result = shell.run(
        f"{PYTHON_EXECUTABLE} -c \"import sys; "
        "sys.stdout.write('o' * 5000); sys.stderr.write('e' * 5000)\""
    )

    assert result.exit_code == 0
    assert len(result.stdout.encode()) + len(result.stderr.encode()) <= 1_024
    assert result.output_truncated is True


@requires_seatbelt
def test_timeout_kills_the_command(shell: SandboxedShell) -> None:
    result = shell.run(
        f"{PYTHON_EXECUTABLE} -c \"import time; time.sleep(10)\"",
        timeout_seconds=0.05,
    )

    assert result.timed_out is True
    assert result.exit_code is not None


@requires_seatbelt
def test_interrupt_kills_the_active_command(shell: SandboxedShell) -> None:
    outcome: list[object] = []
    thread = threading.Thread(
        target=lambda: outcome.append(
            shell.run(
                f"{PYTHON_EXECUTABLE} -c "
                "\"import time; time.sleep(10)\""
            )
        )
    )
    thread.start()
    deadline = time.monotonic() + 1
    while thread.is_alive() and time.monotonic() < deadline:
        shell.interrupt()
        time.sleep(0.01)
    thread.join(timeout=1)

    assert not thread.is_alive()
    assert len(outcome) == 1
    result = outcome[0]
    assert result.interrupted is True
    assert result.exit_code is not None


@requires_seatbelt
def test_interrupt_before_start_cancels_next_command(
    shell: SandboxedShell,
) -> None:
    shell.interrupt()

    result = shell.run("/bin/echo must-not-run")

    assert result.exit_code == 130
    assert result.stdout == ""
    assert result.interrupted is True

    shell.begin_turn()
    resumed = shell.run("/bin/echo next-turn")

    assert resumed.exit_code == 0
    assert resumed.stdout == "next-turn\n"


@requires_seatbelt
def test_seatbelt_allows_workspace_and_temp_writes_only(
    shell: SandboxedShell,
    tmp_path: Path,
) -> None:
    workspace_file = shell.workspace / "inside"
    temp_file = shell.temp_dir / "temporary"
    outside_file = tmp_path / "outside"

    assert shell.run(f"/usr/bin/touch {workspace_file}").exit_code == 0
    assert shell.run(f"/usr/bin/touch {temp_file}").exit_code == 0
    outside = shell.run(f"/usr/bin/touch {outside_file}")

    assert workspace_file.exists()
    assert temp_file.exists()
    assert outside.exit_code != 0
    assert not outside_file.exists()


@requires_seatbelt
def test_seatbelt_denies_read_outside_declared_roots(
    shell: SandboxedShell,
    tmp_path: Path,
) -> None:
    outside_file = tmp_path / "outside-secret"
    outside_file.write_text("must-not-reach-model", encoding="utf-8")

    result = shell.run(f"/bin/cat {outside_file}")

    assert result.exit_code != 0
    assert "must-not-reach-model" not in result.stdout


@requires_seatbelt
def test_seatbelt_supports_dedicated_read_and_write_roots(
    tmp_path: Path,
) -> None:
    source = tmp_path / "source"
    scratch = tmp_path / "scratch"
    metadata = tmp_path / "git-metadata"
    source.mkdir()
    metadata.mkdir()
    (source / "readable").write_text("source data", encoding="utf-8")
    shell = SandboxedShell(
        workspace=source,
        temp_dir=scratch,
        workspace_writable=False,
        additional_write_roots=[metadata],
    )

    read = shell.run(f"/bin/cat {source / 'readable'}")
    source_write = shell.run(f"/usr/bin/touch {source / 'blocked'}")
    metadata_write = shell.run(f"/usr/bin/touch {metadata / 'allowed'}")

    assert read.stdout == "source data"
    assert source_write.exit_code != 0
    assert not (source / "blocked").exists()
    assert metadata_write.exit_code == 0
    assert (metadata / "allowed").exists()


@requires_seatbelt
def test_seatbelt_can_run_workspace_git(shell: SandboxedShell) -> None:
    result = shell.run("git init")

    assert result.exit_code == 0
    assert (shell.workspace / ".git").is_dir()


@requires_seatbelt
def test_seatbelt_blocks_write_through_symlink(
    shell: SandboxedShell,
    tmp_path: Path,
) -> None:
    outside_file = tmp_path / "outside"
    link = shell.workspace / "escape"
    link.symlink_to(outside_file)

    result = shell.run(f"/usr/bin/touch {link}")

    assert result.exit_code != 0
    assert not outside_file.exists()


@requires_seatbelt
def test_seatbelt_denies_network(shell: SandboxedShell) -> None:
    listener = socket.socket()
    listener.bind(("127.0.0.1", 0))
    listener.listen()
    port = listener.getsockname()[1]
    command = (
        f"{PYTHON_EXECUTABLE} -c \"import socket; "
        f"socket.create_connection(('127.0.0.1', {port}), timeout=0.2)\""
    )
    try:
        result = shell.run(command)
    finally:
        listener.close()

    assert result.exit_code != 0
    assert "Operation not permitted" in result.stderr


def test_reports_missing_seatbelt_backend(
    tmp_path: Path,
) -> None:
    shell = SandboxedShell(
        workspace=tmp_path,
        temp_dir=tmp_path / "scratch",
        sandbox_executable=tmp_path / "missing-sandbox-exec",
    )

    with pytest.raises(SandboxUnavailableError):
        shell.run("/usr/bin/true")


def test_rejects_filesystem_root_as_temp_directory(
    tmp_path: Path,
) -> None:
    workspace = tmp_path / "workspace"
    workspace.mkdir()

    with pytest.raises(ValueError):
        SandboxedShell(
            workspace=workspace,
            temp_dir=Path(os.sep),
        )


def test_rejects_filesystem_root_as_additional_write_root(
    tmp_path: Path,
) -> None:
    with pytest.raises(ValueError):
        SandboxedShell(
            workspace=tmp_path,
            temp_dir=tmp_path / "scratch",
            additional_write_roots=[Path(os.sep)],
        )
