from __future__ import annotations

import hashlib
import platform
import shutil
import subprocess
from pathlib import Path

import pytest

from runtime.git import (
    GitWorkspaceError,
    GitWorktreeService,
    TransactionalShell,
)

from conftest import skip_on_ci


requires_seatbelt = pytest.mark.skipif(
    platform.system() != "Darwin",
    reason="transactional shell requires macOS Seatbelt",
)


@skip_on_ci
def test_direct_mutation_recorder_uses_supplied_preimage_bytes(
    tmp_path: Path,
) -> None:
    workspace = tmp_path / "secure-preimage"
    workspace.mkdir()
    target = workspace / "target.txt"
    target.write_text("outside secret\n", encoding="utf-8")
    service = GitWorktreeService(tmp_path / "secure-preimage-data")
    service.prepare_plain("secure-preimage", workspace)
    checkpoint = service.begin_checkpoint(
        "secure-preimage",
        message_count=0,
        attributed=True,
    )
    assert checkpoint is not None

    service.mutation_recorder("secure-preimage").record_file_preimage(
        target,
        content=b"approved preimage\n",
        mode=0o640,
    )

    stored = service.store.list_checkpoint_files(
        checkpoint.checkpoint_id
    )
    assert len(stored) == 1
    repository = service.checkpoint_base / hashlib.sha256(
        b"secure-preimage"
    ).hexdigest()
    captured = subprocess.run(
        [
            service.git_executable,
            f"--git-dir={repository}",
            "cat-file",
            "blob",
            stored[0].before_blob,
        ],
        check=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    ).stdout
    assert captured == b"approved preimage\n"
    assert b"outside secret" not in captured


@requires_seatbelt
def test_plain_workspace_checkpoint_restores_only_agent_paths(
    tmp_path: Path,
) -> None:
    workspace = tmp_path / "plain"
    workspace.mkdir()
    tracked = workspace / "tracked.txt"
    tracked.write_text("before\n", encoding="utf-8")
    secret = workspace / "manual-secret.txt"
    secret.write_text("never captured\n", encoding="utf-8")
    service = GitWorktreeService(tmp_path / "data")
    service.prepare_plain("plain-session", workspace)
    checkpoint = service.begin_checkpoint(
        "plain-session",
        message_count=0,
        attributed=True,
    )
    assert checkpoint is not None
    service.record_file_preimage("plain-session", tracked)
    tracked.write_text("after\n", encoding="utf-8")
    shell = TransactionalShell(
        workspace=workspace,
        temp_dir=tmp_path / "transactions",
        git_executable=service.git_executable,
        apply_attributed_delta=lambda paths, apply_delta: (
            service.apply_file_delta(
                "plain-session",
                paths,
                apply_delta,
            )
        ),
    )

    shell_result = shell.run(
        (
            "/usr/bin/perl -e "
            "\"mkdir 'generated'; "
            "open(F,'>generated/output.txt'); "
            "print F qq(shell\\\\n); close(F)\""
        )
    )
    completed = service.complete_checkpoint(
        "plain-session",
        checkpoint.checkpoint_id,
        message_count=2,
    )
    manual = workspace / "manual.txt"
    manual.write_text("manual\n", encoding="utf-8")

    restored = service.restore_checkpoint_code(
        "plain-session",
        checkpoint.checkpoint_id,
    )

    assert shell_result.exit_code == 0
    assert completed.after_tree
    assert restored["ok"]
    assert tracked.read_text(encoding="utf-8") == "before\n"
    assert not (workspace / "generated/output.txt").exists()
    assert manual.read_text(encoding="utf-8") == "manual\n"
    assert not (workspace / ".git").exists()
    secret_object = subprocess.run(
        [service.git_executable, "hash-object", secret],
        check=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    ).stdout.strip()
    repository = service.checkpoint_base / hashlib.sha256(
        b"plain-session"
    ).hexdigest()
    stored_objects = subprocess.run(
        [
            service.git_executable,
            f"--git-dir={repository}",
            "cat-file",
            "--batch-all-objects",
            "--batch-check=%(objectname)",
        ],
        check=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    ).stdout.splitlines()
    assert secret_object not in stored_objects

    service.cleanup("plain-session")

    assert workspace.is_dir()
    assert secret.read_text(encoding="utf-8") == "never captured\n"
    assert not service.has_checkpoint_session("plain-session")
    assert not repository.exists()


@requires_seatbelt
def test_plain_workspace_restore_rejects_same_path_manual_edit(
    tmp_path: Path,
) -> None:
    workspace = tmp_path / "conflict"
    workspace.mkdir()
    target = workspace / "target.txt"
    target.write_text("before\n", encoding="utf-8")
    service = GitWorktreeService(tmp_path / "conflict-data")
    service.prepare_plain("plain-conflict", workspace)
    checkpoint = service.begin_checkpoint(
        "plain-conflict",
        message_count=0,
        attributed=True,
    )
    assert checkpoint is not None
    service.record_file_preimage("plain-conflict", target)
    target.write_text("agent\n", encoding="utf-8")
    service.complete_checkpoint(
        "plain-conflict",
        checkpoint.checkpoint_id,
        message_count=2,
    )
    target.write_text("manual\n", encoding="utf-8")

    with pytest.raises(
        GitWorkspaceError,
        match="checkpoint conflicts with current edits",
    ):
        service.restore_checkpoint_code(
            "plain-conflict",
            checkpoint.checkpoint_id,
        )

    assert target.read_text(encoding="utf-8") == "manual\n"


@skip_on_ci
def test_failed_plain_delta_prunes_only_rolled_back_preimages(
    tmp_path: Path,
) -> None:
    workspace = tmp_path / "rollback"
    workspace.mkdir()
    retained = workspace / "retained.txt"
    retained.write_text("retained-before\n", encoding="utf-8")
    discarded = workspace / "discarded.txt"
    discarded.write_text("discarded-before\n", encoding="utf-8")
    service = GitWorktreeService(tmp_path / "rollback-data")
    service.prepare_plain("plain-rollback", workspace)
    checkpoint = service.begin_checkpoint(
        "plain-rollback",
        message_count=0,
        attributed=True,
    )
    assert checkpoint is not None
    service.record_file_preimage("plain-rollback", retained)

    applied = service.apply_file_delta(
        "plain-rollback",
        (discarded,),
        lambda: False,
    )

    repository = service.checkpoint_base / hashlib.sha256(
        b"plain-rollback"
    ).hexdigest()
    objects = subprocess.run(
        [
            service.git_executable,
            f"--git-dir={repository}",
            "cat-file",
            "--batch-all-objects",
            "--batch-check=%(objectname)",
        ],
        check=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    ).stdout.splitlines()
    retained_blob = subprocess.run(
        [service.git_executable, "hash-object", retained],
        check=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    ).stdout.strip()
    discarded_blob = subprocess.run(
        [service.git_executable, "hash-object", discarded],
        check=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    ).stdout.strip()

    assert not applied
    assert [
        item.path
        for item in service.store.list_checkpoint_files(
            checkpoint.checkpoint_id
        )
    ] == ["retained.txt"]
    assert retained_blob in objects
    assert discarded_blob not in objects


@skip_on_ci
def test_plain_cleanup_survives_missing_workspace_and_removes_sandbox(
    tmp_path: Path,
) -> None:
    workspace = tmp_path / "deleted"
    workspace.mkdir()
    target = workspace / "target.txt"
    target.write_text("before\n", encoding="utf-8")
    service = GitWorktreeService(tmp_path / "cleanup-data")
    session_id = "plain-deleted"
    service.prepare_plain(session_id, workspace)
    checkpoint = service.begin_checkpoint(
        session_id,
        message_count=0,
        attributed=True,
    )
    assert checkpoint is not None
    service.record_file_preimage(session_id, target)
    identities = (
        hashlib.sha256(session_id.encode("utf-8")).hexdigest(),
        hashlib.sha256(
            f"apply\0{session_id}".encode("utf-8")
        ).hexdigest(),
    )
    for identity in identities:
        sandbox = service.sandbox_base / identity
        sandbox.mkdir(parents=True, exist_ok=True)
        (sandbox / "stale").write_text("stale", encoding="utf-8")
    repository = service.checkpoint_base / hashlib.sha256(
        session_id.encode("utf-8")
    ).hexdigest()
    shutil.rmtree(workspace)

    service.cleanup(session_id)

    assert not service.has_checkpoint_session(session_id)
    assert not repository.exists()
    assert all(
        not (service.sandbox_base / identity).exists()
        for identity in identities
    )
