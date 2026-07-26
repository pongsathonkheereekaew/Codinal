from __future__ import annotations

import platform
import subprocess
import threading
import time
from pathlib import Path

import pytest

import runtime.git.transactional_shell as transactional_shell_module
from runtime.git import (
    CheckpointCaptureMode,
    GitWorkspaceError,
    GitWorktreeService,
    TransactionalShell,
)

requires_seatbelt = pytest.mark.skipif(
    platform.system() != "Darwin",
    reason="transactional shell requires macOS Seatbelt",
)

from conftest import skip_on_ci


def _git(repo: Path, *arguments: str) -> None:
    subprocess.run(
        ["git", "-C", str(repo), *arguments],
        check=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )


def _workspace(tmp_path: Path) -> tuple[Path, Path]:
    source = tmp_path / "source"
    worktree = tmp_path / "worktree"
    source.mkdir()
    _git(source, "init", "-b", "main")
    _git(source, "config", "user.name", "Codinal Test")
    _git(source, "config", "user.email", "codinal@example.invalid")
    (source / "tracked.txt").write_text("base\n", encoding="utf-8")
    _git(source, "add", "tracked.txt")
    _git(source, "commit", "-m", "base")
    _git(source, "worktree", "add", "-b", "session", str(worktree))
    common = Path(
        subprocess.run(
            ["git", "-C", str(worktree), "rev-parse", "--git-common-dir"],
            check=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        ).stdout.strip()
    )
    if not common.is_absolute():
        common = (worktree / common).resolve()
    return worktree, common


def _shell(
    tmp_path: Path,
    recorder,
) -> tuple[TransactionalShell, Path]:
    workspace, common = _workspace(tmp_path)

    def apply_attributed(paths, apply_delta):
        for path in paths:
            recorder(path)
        return apply_delta()

    return (
        TransactionalShell(
            workspace=workspace,
            temp_dir=tmp_path / "transactions",
            git_executable=Path("/usr/bin/git"),
            git_read_root=common,
            apply_attributed_delta=apply_attributed,
        ),
        workspace,
    )


@requires_seatbelt
def test_transactional_shell_applies_only_shell_delta(
    tmp_path: Path,
) -> None:
    recorded = []
    shell, workspace = _shell(tmp_path, recorded.append)
    result_box = []

    worker = threading.Thread(
        target=lambda: result_box.append(
            shell.run(
                (
                    "/usr/bin/perl -e "
                    "\"select(undef,undef,undef,0.3); "
                    "open(F,'>agent.txt'); print F qq(agent\\\\n); close(F)\""
                )
            )
        )
    )
    worker.start()
    time.sleep(0.1)
    (workspace / "manual.txt").write_text(
        "manual\n",
        encoding="utf-8",
    )
    worker.join(timeout=10)

    assert not worker.is_alive()
    assert result_box[0].exit_code == 0
    assert (workspace / "agent.txt").read_text(
        encoding="utf-8"
    ) == "agent\n"
    assert (workspace / "manual.txt").read_text(
        encoding="utf-8"
    ) == "manual\n"
    assert recorded == [workspace / "agent.txt"]
    assert list((tmp_path / "transactions").iterdir()) == []


@requires_seatbelt
def test_transactional_shell_rejects_same_path_manual_conflict(
    tmp_path: Path,
) -> None:
    recorded = []
    shell, workspace = _shell(tmp_path, recorded.append)
    result_box = []
    worker = threading.Thread(
        target=lambda: result_box.append(
            shell.run(
                (
                    "/usr/bin/perl -e "
                    "\"select(undef,undef,undef,0.3); "
                    "open(F,'>tracked.txt'); print F qq(agent\\\\n); close(F)\""
                )
            )
        )
    )
    worker.start()
    time.sleep(0.1)
    (workspace / "tracked.txt").write_text(
        "manual\n",
        encoding="utf-8",
    )
    worker.join(timeout=10)

    assert result_box[0].exit_code == 1
    assert "conflicts with a concurrent edit" in result_box[0].stderr
    assert (workspace / "tracked.txt").read_text(
        encoding="utf-8"
    ) == "manual\n"
    assert recorded == []


@requires_seatbelt
def test_transactional_shell_never_applies_protected_git_changes(
    tmp_path: Path,
) -> None:
    recorded = []
    shell, workspace = _shell(tmp_path, recorded.append)

    result = shell.run("/bin/rm .git")

    assert result.exit_code == 1
    assert "protected Git metadata" in result.stderr
    assert (workspace / ".git").exists()
    assert recorded == []


@requires_seatbelt
def test_transactional_shell_rejects_nested_git_metadata(
    tmp_path: Path,
) -> None:
    recorded = []
    shell, workspace = _shell(tmp_path, recorded.append)

    result = shell.run(
        (
            "/usr/bin/perl -e "
            "\"mkdir 'nested'; mkdir 'nested/.git'; "
            "open(F,'>nested/.git/config'); "
            "print F qq(secret); close(F)\""
        )
    )

    assert result.exit_code == 1
    assert "protected Git metadata" in result.stderr
    assert not (workspace / "nested").exists()
    assert recorded == []


@requires_seatbelt
def test_transactional_shell_allows_read_only_git_status(
    tmp_path: Path,
) -> None:
    recorded = []
    shell, workspace = _shell(tmp_path, recorded.append)

    result = shell.run("git status --short")

    assert result.exit_code == 0
    assert result.stdout == ""
    assert result.stderr == ""
    assert recorded == []
    assert (workspace / ".git").is_file()


@requires_seatbelt
def test_transactional_shell_applies_file_under_new_directory(
    tmp_path: Path,
) -> None:
    recorded = []
    shell, workspace = _shell(tmp_path, recorded.append)

    result = shell.run(
        (
            "/usr/bin/perl -e "
            "\"mkdir 'new'; mkdir 'new/nested'; "
            "open(F,'>new/nested/file.txt'); "
            "print F qq(agent\\\\n); close(F)\""
        )
    )

    assert result.exit_code == 0
    assert (workspace / "new/nested/file.txt").read_text(
        encoding="utf-8"
    ) == "agent\n"
    assert recorded == [workspace / "new/nested/file.txt"]


@requires_seatbelt
def test_interrupt_during_delta_preparation_prevents_apply(
    tmp_path: Path,
    monkeypatch,
) -> None:
    recorded = []
    shell, workspace = _shell(tmp_path, recorded.append)
    scanning = threading.Event()
    release = threading.Event()
    original = transactional_shell_module._changed_paths

    def blocked_scan(*args, **kwargs):
        scanning.set()
        assert release.wait(timeout=5)
        return original(*args, **kwargs)

    monkeypatch.setattr(
        transactional_shell_module,
        "_changed_paths",
        blocked_scan,
    )
    result_box = []
    worker = threading.Thread(
        target=lambda: result_box.append(
            shell.run(
                (
                    "/usr/bin/perl -e "
                    "\"open(F,'>cancelled.txt'); "
                    "print F qq(agent\\\\n); close(F)\""
                )
            )
        )
    )
    worker.start()
    assert scanning.wait(timeout=5)
    shell.interrupt()
    release.set()
    worker.join(timeout=10)

    assert not worker.is_alive()
    assert result_box[0].interrupted
    assert not (workspace / "cancelled.txt").exists()
    assert recorded == []


@requires_seatbelt
def test_interrupt_during_stale_cleanup_is_not_cleared(
    tmp_path: Path,
    monkeypatch,
) -> None:
    recorded = []
    shell, workspace = _shell(tmp_path, recorded.append)
    cleaning = threading.Event()
    release = threading.Event()

    def blocked_cleanup():
        cleaning.set()
        assert release.wait(timeout=5)

    monkeypatch.setattr(
        shell,
        "_retry_stale_transactions",
        blocked_cleanup,
    )
    result_box = []
    worker = threading.Thread(
        target=lambda: result_box.append(
            shell.run(
                (
                    "/usr/bin/perl -e "
                    "\"open(F,'>must-not-run.txt'); "
                    "print F qq(agent\\\\n); close(F)\""
                )
            )
        )
    )
    worker.start()
    assert cleaning.wait(timeout=5)
    shell.interrupt()
    release.set()
    worker.join(timeout=10)

    assert not worker.is_alive()
    assert result_box[0].interrupted
    assert not (workspace / "must-not-run.txt").exists()
    assert recorded == []


@requires_seatbelt
def test_interrupt_before_worker_entry_cancels_shell_call(
    tmp_path: Path,
) -> None:
    recorded = []
    shell, workspace = _shell(tmp_path, recorded.append)
    shell.interrupt()

    result = shell.run(
        (
            "/usr/bin/perl -e "
            "\"open(F,'>must-not-run.txt'); "
            "print F qq(agent\\\\n); close(F)\""
        )
    )

    assert result.exit_code == 130
    assert result.interrupted
    assert not (workspace / "must-not-run.txt").exists()
    assert recorded == []

    shell.begin_turn()
    resumed = shell.run(
        (
            "/usr/bin/perl -e "
            "\"open(F,'>next-turn.txt'); "
            "print F qq(next\\\\n); close(F)\""
        )
    )

    assert resumed.exit_code == 0
    assert (workspace / "next-turn.txt").read_text(
        encoding="utf-8"
    ) == "next\n"
    assert recorded == [workspace / "next-turn.txt"]


@requires_seatbelt
def test_cleanup_failure_is_reported_and_retried(
    tmp_path: Path,
    monkeypatch,
) -> None:
    recorded = []
    shell, _workspace_path = _shell(tmp_path, recorded.append)
    original = transactional_shell_module.shutil.rmtree
    calls = 0

    def fail_once(path):
        nonlocal calls
        calls += 1
        if calls == 1:
            raise OSError("simulated cleanup failure")
        return original(path)

    monkeypatch.setattr(
        transactional_shell_module.shutil,
        "rmtree",
        fail_once,
    )

    first = shell.run("/bin/pwd")
    retained = list((tmp_path / "transactions").iterdir())
    second = shell.run("/bin/pwd")

    assert first.exit_code == 0
    assert "cleanup pending" in first.stderr
    assert len(retained) == 1
    assert retained[0].name.startswith("cleanup-")
    assert second.exit_code == 0
    assert second.stderr == ""
    assert list((tmp_path / "transactions").iterdir()) == []


@requires_seatbelt
def test_transactional_shell_checkpoint_restores_only_shell_paths(
    tmp_path: Path,
) -> None:
    source = tmp_path / "checkpoint-source"
    source.mkdir()
    _git(source, "init", "-b", "main")
    _git(source, "config", "user.name", "Codinal Test")
    _git(source, "config", "user.email", "codinal@example.invalid")
    (source / "tracked.txt").write_text("base\n", encoding="utf-8")
    (source / ".gitignore").write_text(
        ".agent-cache\n",
        encoding="utf-8",
    )
    _git(source, "add", "tracked.txt", ".gitignore")
    _git(source, "commit", "-m", "base")
    service = GitWorktreeService(tmp_path / "data")
    record = service.prepare("transaction-checkpoint", source)
    checkpoint = service.begin_checkpoint(
        "transaction-checkpoint",
        message_count=0,
        attributed=True,
    )
    assert checkpoint is not None
    shell = TransactionalShell(
        workspace=record.worktree_path,
        temp_dir=tmp_path / "shell-transactions",
        git_executable=service.git_executable,
        git_read_root=record.git_common_dir,
        apply_attributed_delta=lambda paths, apply_delta: (
            service.apply_file_delta(
                "transaction-checkpoint",
                paths,
                apply_delta,
            )
        ),
    )
    result_box = []
    worker = threading.Thread(
        target=lambda: result_box.append(
            shell.run(
                (
                    "/usr/bin/perl -e "
                    "\"select(undef,undef,undef,0.3); "
                    "open(F,'>.agent-cache'); "
                    "print F qq(agent\\\\n); close(F); "
                    "mkdir 'new'; mkdir 'new/nested'; "
                    "open(N,'>new/nested/file.txt'); "
                    "print N qq(nested\\\\n); close(N)\""
                )
            )
        )
    )
    worker.start()
    time.sleep(0.1)
    manual = record.worktree_path / "manual.txt"
    manual.write_text("manual\n", encoding="utf-8")
    worker.join(timeout=10)
    completed = service.complete_checkpoint(
        "transaction-checkpoint",
        checkpoint.checkpoint_id,
        message_count=2,
    )

    service.restore_checkpoint_code(
        "transaction-checkpoint",
        checkpoint.checkpoint_id,
    )

    assert result_box[0].exit_code == 0
    assert completed.capture_mode is CheckpointCaptureMode.ATTRIBUTED
    assert [
        item.path
        for item in service.store.list_checkpoint_files(
            checkpoint.checkpoint_id
        )
    ] == [".agent-cache", "new/nested/file.txt"]
    assert not (record.worktree_path / ".agent-cache").exists()
    assert not (record.worktree_path / "new/nested/file.txt").exists()
    assert manual.read_text(encoding="utf-8") == "manual\n"


@skip_on_ci
def test_failed_delta_discards_only_new_checkpoint_attribution(
    tmp_path: Path,
    monkeypatch,
) -> None:
    source = tmp_path / "rollback-source"
    source.mkdir()
    _git(source, "init", "-b", "main")
    _git(source, "config", "user.name", "Codinal Test")
    _git(source, "config", "user.email", "codinal@example.invalid")
    (source / "tracked.txt").write_text("base\n", encoding="utf-8")
    _git(source, "add", "tracked.txt")
    _git(source, "commit", "-m", "base")
    service = GitWorktreeService(tmp_path / "rollback-data")
    record = service.prepare("rollback-checkpoint", source)
    checkpoint = service.begin_checkpoint(
        "rollback-checkpoint",
        message_count=0,
        attributed=True,
    )
    assert checkpoint is not None
    tracked = record.worktree_path / "tracked.txt"
    service.record_file_preimage("rollback-checkpoint", tracked)
    original = service.record_file_preimage
    attempts = 0

    def fail_second(session_id, path):
        nonlocal attempts
        attempts += 1
        if attempts == 2:
            raise GitWorkspaceError("simulated capture failure")
        return original(session_id, path)

    monkeypatch.setattr(service, "record_file_preimage", fail_second)

    with pytest.raises(GitWorkspaceError):
        service.apply_file_delta(
            "rollback-checkpoint",
            (
                record.worktree_path / "first.txt",
                record.worktree_path / "second.txt",
            ),
            lambda: True,
        )
    applied = service.apply_file_delta(
        "rollback-checkpoint",
        (record.worktree_path / "failed.txt",),
        lambda: False,
    )

    assert not applied
    assert [
        item.path
        for item in service.store.list_checkpoint_files(
            checkpoint.checkpoint_id
        )
    ] == ["tracked.txt"]
