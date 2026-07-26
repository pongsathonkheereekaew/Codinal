from __future__ import annotations

import platform
import stat
import subprocess
from pathlib import Path

import pytest

from runtime.git import (
    CheckpointState,
    DetachedHeadError,
    GitWorkspaceError,
    GitWorktreeService,
    WorktreeState,
)

requires_seatbelt = pytest.mark.skipif(
    platform.system() != "Darwin",
    reason="production worktree creation uses macOS Seatbelt",
)


def git(repo: Path, *arguments: str) -> str:
    result = subprocess.run(
        ["git", "-C", str(repo), *arguments],
        check=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    return result.stdout.strip()


def repository(tmp_path: Path, *, branch: str = "feature") -> Path:
    repo = tmp_path / "source"
    repo.mkdir()
    subprocess.run(
        ["git", "init", "-b", branch, str(repo)],
        check=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    git(repo, "config", "user.name", "Codinal Test")
    git(repo, "config", "user.email", "codinal@example.invalid")
    (repo / "tracked.txt").write_text("base\n", encoding="utf-8")
    git(repo, "add", "tracked.txt")
    git(repo, "commit", "-m", "base")
    return repo


@requires_seatbelt
def test_prepare_creates_one_isolated_branch_and_worktree_per_session(
    tmp_path: Path,
) -> None:
    repo = repository(tmp_path)
    source_head = git(repo, "rev-parse", "HEAD")
    (repo / "tracked.txt").write_text("uncommitted\n", encoding="utf-8")
    (repo / "untracked.txt").write_text("source only\n", encoding="utf-8")
    hook_marker = repo / "hook-ran"
    hook = repo / ".git" / "hooks" / "post-checkout"
    hook.write_text(
        f"#!/bin/sh\n/usr/bin/touch {hook_marker}\n",
        encoding="utf-8",
    )
    hook.chmod(0o755)
    service = GitWorktreeService(tmp_path / "data")

    record = service.prepare("session-one", repo)

    assert record.state is WorktreeState.ACTIVE
    assert record.source_root == repo.resolve()
    assert record.source_branch == "feature"
    assert record.base_commit == source_head
    assert record.source_dirty is True
    assert record.worktree_path.is_dir()
    assert record.worktree_path.is_relative_to(
        (tmp_path / "data" / "worktrees").resolve()
    )
    assert record.session_branch.startswith("codinal/session-")
    assert git(repo, "branch", "--show-current") == "feature"
    assert git(repo, "rev-parse", "HEAD") == source_head
    assert (repo / "tracked.txt").read_text(encoding="utf-8") == "uncommitted\n"
    assert (repo / "untracked.txt").exists()
    assert not hook_marker.exists()
    assert (
        record.worktree_path / "tracked.txt"
    ).read_text(encoding="utf-8") == "base\n"
    assert not (record.worktree_path / "untracked.txt").exists()
    assert git(record.worktree_path, "branch", "--show-current") == (
        record.session_branch
    )


@requires_seatbelt
def test_prepare_is_idempotent_across_service_restart(tmp_path: Path) -> None:
    repo = repository(tmp_path)
    data_dir = tmp_path / "data"
    first_service = GitWorktreeService(data_dir)
    first = first_service.prepare("stable-session", repo)
    nested = first_service.prepare("stable-session", repo / "tracked.txt")
    first_service.close()

    restarted = GitWorktreeService(data_dir)
    second = restarted.prepare("stable-session", repo)

    assert nested == first
    assert second == first
    assert len(git(repo, "worktree", "list", "--porcelain").split("worktree ")) == 3
    assert stat.S_IMODE(
        (data_dir / "git-worktrees.db").stat().st_mode
    ) == 0o600


@requires_seatbelt
def test_prepare_rejects_non_repository_without_creating_state(
    tmp_path: Path,
) -> None:
    folder = tmp_path / "folder"
    folder.mkdir()
    service = GitWorktreeService(tmp_path / "data")

    with pytest.raises(GitWorkspaceError, match="not a Git worktree"):
        service.prepare("not-git", folder)

    assert service.load("not-git") is None
    assert list((tmp_path / "data" / "worktrees").iterdir()) == []


@requires_seatbelt
def test_prepare_rejects_detached_source_head(tmp_path: Path) -> None:
    repo = repository(tmp_path)
    git(repo, "checkout", "--detach")
    service = GitWorktreeService(tmp_path / "data")

    with pytest.raises(DetachedHeadError):
        service.prepare("detached", repo)

    assert service.load("detached") is None


def test_store_rejects_invalid_session_id(tmp_path: Path) -> None:
    service = GitWorktreeService(tmp_path / "data")

    with pytest.raises(ValueError, match="invalid session id"):
        service.load("../escape")


@requires_seatbelt
def test_status_diff_stage_and_commit_stay_on_session_branch(
    tmp_path: Path,
) -> None:
    repo = repository(tmp_path)
    source_head = git(repo, "rev-parse", "HEAD")
    service = GitWorktreeService(tmp_path / "data")
    record = service.prepare("git-tools", repo)
    target = record.worktree_path / "tracked.txt"
    target.write_text("session edit\n", encoding="utf-8")

    status = service.status("git-tools")
    diff = service.diff("git-tools")
    escaped = service.stage("git-tools", "../outside")
    staged = service.stage("git-tools", "tracked.txt")
    committed = service.commit("git-tools", "Apply session edit")
    review = service.diff("git-tools", against_base=True)

    assert status["clean"] is False
    assert "tracked.txt" in status["porcelain"]
    assert "-base" in diff["diff"]
    assert "+session edit" in diff["diff"]
    assert escaped == {"ok": False, "error": "path escapes worktree"}
    assert staged == {"ok": True, "path": "tracked.txt"}
    assert committed["ok"] is True
    assert committed["commit"] == git(record.worktree_path, "rev-parse", "HEAD")
    assert "-base" in review["diff"]
    assert "+session edit" in review["diff"]
    assert git(repo, "rev-parse", "HEAD") == source_head
    assert (repo / "tracked.txt").read_text(encoding="utf-8") == "base\n"
    with pytest.raises(
        GitWorkspaceError,
        match="unapplied commits",
    ):
        service.cleanup("git-tools")
    assert record.worktree_path.is_dir()


@requires_seatbelt
def test_turn_checkpoint_restore_removes_only_agent_delta(
    tmp_path: Path,
) -> None:
    repo = repository(tmp_path)
    service = GitWorktreeService(tmp_path / "data")
    record = service.prepare("checkpoint-turn", repo)

    checkpoint = service.begin_checkpoint(
        "checkpoint-turn",
        message_count=2,
    )
    assert checkpoint is not None
    (record.worktree_path / "tracked.txt").write_text(
        "agent edit\n",
        encoding="utf-8",
    )
    (record.worktree_path / "generated.txt").write_text(
        "agent generated\n",
        encoding="utf-8",
    )
    completed = service.complete_checkpoint(
        "checkpoint-turn",
        checkpoint.checkpoint_id,
        message_count=4,
    )
    (record.worktree_path / "manual.txt").write_text(
        "manual after checkpoint\n",
        encoding="utf-8",
    )

    restored = service.restore_checkpoint_code(
        "checkpoint-turn",
        checkpoint.checkpoint_id,
    )

    assert completed.before_message_count == 2
    assert completed.after_message_count == 4
    assert restored == {
        "ok": True,
        "checkpoint_id": checkpoint.checkpoint_id,
        "scope": "code",
    }
    assert (record.worktree_path / "tracked.txt").read_text(
        encoding="utf-8"
    ) == "base\n"
    assert not (record.worktree_path / "generated.txt").exists()
    assert (record.worktree_path / "manual.txt").read_text(
        encoding="utf-8"
    ) == "manual after checkpoint\n"
    assert service.list_checkpoints("checkpoint-turn") == [
        completed
    ]


@requires_seatbelt
def test_checkpoint_capture_does_not_execute_repository_filters(
    tmp_path: Path,
) -> None:
    repo = repository(tmp_path)
    service = GitWorktreeService(tmp_path / "data")
    record = service.prepare("checkpoint-filter", repo)
    git(
        repo,
        "config",
        "filter.untrusted.clean",
        "touch filter-ran; cat",
    )
    git(repo, "config", "filter.untrusted.required", "true")
    (record.worktree_path / ".gitattributes").write_text(
        "tracked.txt filter=untrusted\n",
        encoding="utf-8",
    )

    checkpoint = service.begin_checkpoint(
        "checkpoint-filter",
        message_count=0,
    )

    assert checkpoint is not None
    assert not (record.worktree_path / "filter-ran").exists()


@requires_seatbelt
def test_checkpoint_objects_are_private_to_codinal_storage(
    tmp_path: Path,
) -> None:
    repo = repository(tmp_path)
    service = GitWorktreeService(tmp_path / "data")
    record = service.prepare("checkpoint-private", repo)
    secret = record.worktree_path / "manual-secret.txt"
    secret.write_text("private manual content\n", encoding="utf-8")
    object_id = git(repo, "hash-object", secret)

    checkpoint = service.begin_checkpoint(
        "checkpoint-private",
        message_count=0,
    )

    assert checkpoint is not None
    assert subprocess.run(
        ["git", "-C", str(repo), "cat-file", "-e", object_id],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    ).returncode != 0
    assert (
        git(
            repo,
            "for-each-ref",
            "--format=%(refname)",
            "refs/codinal/checkpoints/",
        )
        == ""
    )


@requires_seatbelt
def test_attributed_checkpoint_restores_ignored_agent_file_only(
    tmp_path: Path,
) -> None:
    repo = repository(tmp_path)
    (repo / ".gitignore").write_text(
        ".agent-cache\n",
        encoding="utf-8",
    )
    git(repo, "add", ".gitignore")
    git(repo, "commit", "-m", "ignore agent cache")
    service = GitWorktreeService(tmp_path / "data")
    record = service.prepare("checkpoint-attributed", repo)
    checkpoint = service.begin_checkpoint(
        "checkpoint-attributed",
        message_count=0,
        attributed=True,
    )
    assert checkpoint is not None
    recorder = service.mutation_recorder("checkpoint-attributed")
    ignored = record.worktree_path / ".agent-cache"
    recorder.record_file_preimage(ignored)
    ignored.write_text("agent output\n", encoding="utf-8")
    manual = record.worktree_path / "manual.txt"
    manual.write_text("manual during turn\n", encoding="utf-8")
    service.complete_checkpoint(
        "checkpoint-attributed",
        checkpoint.checkpoint_id,
        message_count=2,
    )

    service.restore_checkpoint_code(
        "checkpoint-attributed",
        checkpoint.checkpoint_id,
    )

    assert not ignored.exists()
    assert manual.read_text(encoding="utf-8") == (
        "manual during turn\n"
    )


@requires_seatbelt
def test_attributed_checkpoint_falls_back_before_shell_mutation(
    tmp_path: Path,
) -> None:
    repo = repository(tmp_path)
    (repo / ".gitignore").write_text(
        ".agent-cache\n",
        encoding="utf-8",
    )
    git(repo, "add", ".gitignore")
    git(repo, "commit", "-m", "ignore agent cache")
    service = GitWorktreeService(tmp_path / "data")
    record = service.prepare("checkpoint-shell-fallback", repo)
    checkpoint = service.begin_checkpoint(
        "checkpoint-shell-fallback",
        message_count=0,
        attributed=True,
    )
    assert checkpoint is not None
    recorder = service.mutation_recorder(
        "checkpoint-shell-fallback"
    )
    tracked = record.worktree_path / "tracked.txt"
    recorder.record_file_preimage(tracked)
    tracked.write_text("direct agent edit\n", encoding="utf-8")
    ignored = record.worktree_path / ".agent-cache"
    recorder.record_file_preimage(ignored)
    ignored.write_text("direct ignored edit\n", encoding="utf-8")
    recorder.record_shell_fallback()
    generated = record.worktree_path / "shell-output.txt"
    generated.write_text("shell agent edit\n", encoding="utf-8")
    service.complete_checkpoint(
        "checkpoint-shell-fallback",
        checkpoint.checkpoint_id,
        message_count=2,
    )

    service.restore_checkpoint_code(
        "checkpoint-shell-fallback",
        checkpoint.checkpoint_id,
    )

    assert tracked.read_text(encoding="utf-8") == "base\n"
    assert not ignored.exists()
    assert not generated.exists()


@requires_seatbelt
def test_attributed_checkpoint_leaves_extra_root_unmanaged(
    tmp_path: Path,
) -> None:
    repo = repository(tmp_path)
    extra_root = tmp_path / "extra"
    extra_root.mkdir()
    extra_file = extra_root / "valid.txt"
    service = GitWorktreeService(tmp_path / "data")
    service.prepare("checkpoint-extra-root", repo)
    checkpoint = service.begin_checkpoint(
        "checkpoint-extra-root",
        message_count=0,
        attributed=True,
    )
    assert checkpoint is not None

    service.mutation_recorder(
        "checkpoint-extra-root"
    ).record_file_preimage(extra_file)

    assert service.store.list_checkpoint_files(
        checkpoint.checkpoint_id
    ) == []


@requires_seatbelt
def test_next_checkpoint_finalizes_captured_pending_turn(
    tmp_path: Path,
) -> None:
    repo = repository(tmp_path)
    service = GitWorktreeService(tmp_path / "data")
    record = service.prepare("checkpoint-reconcile", repo)
    first = service.begin_checkpoint(
        "checkpoint-reconcile",
        message_count=0,
    )
    assert first is not None
    (record.worktree_path / "generated.txt").write_text(
        "generated\n",
        encoding="utf-8",
    )
    captured = service.capture_checkpoint(
        "checkpoint-reconcile",
        first.checkpoint_id,
        message_count=2,
    )

    second = service.begin_checkpoint(
        "checkpoint-reconcile",
        message_count=2,
    )

    assert captured.state is CheckpointState.PENDING
    assert captured.after_tree
    assert second is not None
    assert second.checkpoint_id != first.checkpoint_id
    completed = service.load_checkpoint(first.checkpoint_id)
    assert completed is not None
    assert completed.state is CheckpointState.COMPLETED
    assert service.pending_checkpoint("checkpoint-reconcile") == second


@requires_seatbelt
def test_checkpoint_conflict_aborts_without_partial_restore(
    tmp_path: Path,
) -> None:
    repo = repository(tmp_path)
    service = GitWorktreeService(tmp_path / "data")
    record = service.prepare("checkpoint-conflict", repo)
    checkpoint = service.begin_checkpoint(
        "checkpoint-conflict",
        message_count=0,
    )
    assert checkpoint is not None
    (record.worktree_path / "tracked.txt").write_text(
        "agent edit\n",
        encoding="utf-8",
    )
    (record.worktree_path / "generated.txt").write_text(
        "agent generated\n",
        encoding="utf-8",
    )
    service.complete_checkpoint(
        "checkpoint-conflict",
        checkpoint.checkpoint_id,
        message_count=2,
    )
    (record.worktree_path / "tracked.txt").write_text(
        "manual conflicting edit\n",
        encoding="utf-8",
    )

    with pytest.raises(
        GitWorkspaceError,
        match="conflicts with current edits",
    ):
        service.restore_checkpoint_code(
            "checkpoint-conflict",
            checkpoint.checkpoint_id,
        )

    assert (record.worktree_path / "tracked.txt").read_text(
        encoding="utf-8"
    ) == "manual conflicting edit\n"
    assert (record.worktree_path / "generated.txt").read_text(
        encoding="utf-8"
    ) == "agent generated\n"


@requires_seatbelt
def test_checkpoint_restore_preserves_later_nonoverlapping_manual_hunk(
    tmp_path: Path,
) -> None:
    repo = repository(tmp_path)
    (repo / "tracked.txt").write_text(
        "first\nsecond\nthird\nfourth\n",
        encoding="utf-8",
    )
    git(repo, "add", "tracked.txt")
    git(repo, "commit", "-m", "multiline base")
    service = GitWorktreeService(tmp_path / "data")
    record = service.prepare("checkpoint-hunks", repo)
    checkpoint = service.begin_checkpoint(
        "checkpoint-hunks",
        message_count=0,
    )
    assert checkpoint is not None
    (record.worktree_path / "tracked.txt").write_text(
        "agent first\nsecond\nthird\nfourth\n",
        encoding="utf-8",
    )
    service.complete_checkpoint(
        "checkpoint-hunks",
        checkpoint.checkpoint_id,
        message_count=2,
    )
    (record.worktree_path / "tracked.txt").write_text(
        "agent first\nsecond\nthird\nmanual fourth\n",
        encoding="utf-8",
    )

    service.restore_checkpoint_code(
        "checkpoint-hunks",
        checkpoint.checkpoint_id,
    )

    assert (record.worktree_path / "tracked.txt").read_text(
        encoding="utf-8"
    ) == "first\nsecond\nthird\nmanual fourth\n"


@requires_seatbelt
def test_cleanup_removes_checkpoint_metadata_and_git_refs(
    tmp_path: Path,
) -> None:
    repo = repository(tmp_path)
    service = GitWorktreeService(tmp_path / "data")
    service.prepare("checkpoint-cleanup", repo)
    checkpoint = service.begin_checkpoint(
        "checkpoint-cleanup",
        message_count=0,
    )
    assert checkpoint is not None
    service.complete_checkpoint(
        "checkpoint-cleanup",
        checkpoint.checkpoint_id,
        message_count=2,
    )
    prefix = "refs/codinal/checkpoints/checkpoint-cleanup/"
    assert (
        git(repo, "for-each-ref", "--format=%(refname)", prefix)
        == ""
    )
    assert any((tmp_path / "data" / "checkpoints").iterdir())

    service.cleanup("checkpoint-cleanup")

    assert not any((tmp_path / "data" / "checkpoints").iterdir())
    assert service.load_checkpoint(checkpoint.checkpoint_id) is None


@requires_seatbelt
def test_restore_older_checkpoint_removes_later_agent_turns_only(
    tmp_path: Path,
) -> None:
    repo = repository(tmp_path)
    service = GitWorktreeService(tmp_path / "data")
    record = service.prepare("checkpoint-history", repo)
    first = service.begin_checkpoint(
        "checkpoint-history",
        message_count=0,
    )
    assert first is not None
    (record.worktree_path / "tracked.txt").write_text(
        "first agent turn\n",
        encoding="utf-8",
    )
    service.complete_checkpoint(
        "checkpoint-history",
        first.checkpoint_id,
        message_count=2,
    )
    (record.worktree_path / "manual.txt").write_text(
        "manual between turns\n",
        encoding="utf-8",
    )
    second = service.begin_checkpoint(
        "checkpoint-history",
        message_count=2,
    )
    assert second is not None
    (record.worktree_path / "second-agent.txt").write_text(
        "second agent turn\n",
        encoding="utf-8",
    )
    service.complete_checkpoint(
        "checkpoint-history",
        second.checkpoint_id,
        message_count=4,
    )

    service.restore_checkpoint_code(
        "checkpoint-history",
        first.checkpoint_id,
    )

    assert (record.worktree_path / "tracked.txt").read_text(
        encoding="utf-8"
    ) == "base\n"
    assert not (record.worktree_path / "second-agent.txt").exists()
    assert (record.worktree_path / "manual.txt").read_text(
        encoding="utf-8"
    ) == "manual between turns\n"

    service.reapply_checkpoint_code(
        "checkpoint-history",
        first.checkpoint_id,
    )

    assert (record.worktree_path / "tracked.txt").read_text(
        encoding="utf-8"
    ) == "first agent turn\n"
    assert (record.worktree_path / "second-agent.txt").read_text(
        encoding="utf-8"
    ) == "second agent turn\n"
    assert (record.worktree_path / "manual.txt").read_text(
        encoding="utf-8"
    ) == "manual between turns\n"


@requires_seatbelt
def test_discard_checkpoint_history_removes_target_and_newer_refs(
    tmp_path: Path,
) -> None:
    repo = repository(tmp_path)
    service = GitWorktreeService(tmp_path / "data")
    record = service.prepare("checkpoint-discard", repo)
    checkpoints = []
    for index in range(3):
        checkpoint = service.begin_checkpoint(
            "checkpoint-discard",
            message_count=index * 2,
        )
        assert checkpoint is not None
        (record.worktree_path / f"turn-{index}.txt").write_text(
            f"turn {index}\n",
            encoding="utf-8",
        )
        checkpoints.append(
            service.complete_checkpoint(
                "checkpoint-discard",
                checkpoint.checkpoint_id,
                message_count=(index + 1) * 2,
            )
        )

    discarded = service.discard_checkpoint_history(
        "checkpoint-discard",
        checkpoints[1].checkpoint_id,
    )

    assert discarded == 2
    assert service.list_checkpoints("checkpoint-discard") == [
        checkpoints[0]
    ]
    for checkpoint in checkpoints[1:]:
        prefix = (
            "refs/codinal/checkpoints/checkpoint-discard/"
            f"{checkpoint.checkpoint_id}/"
        )
        assert (
            git(repo, "for-each-ref", "--format=%(refname)", prefix)
            == ""
        )


@requires_seatbelt
def test_apply_fast_forwards_recorded_source_branch_without_touching_main(
    tmp_path: Path,
) -> None:
    repo = repository(tmp_path, branch="main")
    main_head = git(repo, "rev-parse", "HEAD")
    git(repo, "checkout", "-b", "feature")
    service = GitWorktreeService(tmp_path / "data")
    record = service.prepare("apply-fast-forward", repo)
    (record.worktree_path / "generated.txt").write_text(
        "generated\n",
        encoding="utf-8",
    )
    service.stage("apply-fast-forward", "generated.txt")
    session_commit = service.commit(
        "apply-fast-forward",
        "Add generated file",
    )["commit"]

    applied = service.apply_back("apply-fast-forward")

    assert applied == {
        "ok": True,
        "strategy": "fast-forward",
        "commit": session_commit,
    }
    assert git(repo, "branch", "--show-current") == "feature"
    assert git(repo, "rev-parse", "HEAD") == session_commit
    assert git(repo, "rev-parse", "main") == main_head
    assert (repo / "generated.txt").read_text(encoding="utf-8") == "generated\n"
    assert record.worktree_path.is_dir()
    assert service.load("apply-fast-forward").state is WorktreeState.APPLIED

    service.cleanup("apply-fast-forward")

    assert not record.worktree_path.exists()
    assert service.load("apply-fast-forward") is None
    assert record.session_branch not in git(repo, "branch", "--list")


@requires_seatbelt
def test_apply_conflict_aborts_and_preserves_both_worktrees(
    tmp_path: Path,
) -> None:
    repo = repository(tmp_path)
    service = GitWorktreeService(tmp_path / "data")
    record = service.prepare("apply-conflict", repo)
    (record.worktree_path / "tracked.txt").write_text(
        "session version\n",
        encoding="utf-8",
    )
    service.stage("apply-conflict", "tracked.txt")
    service.commit("apply-conflict", "Session version")
    (repo / "tracked.txt").write_text("source version\n", encoding="utf-8")
    git(repo, "add", "tracked.txt")
    git(repo, "commit", "-m", "Source version")
    source_head = git(repo, "rev-parse", "HEAD")

    applied = service.apply_back("apply-conflict")

    assert applied == {
        "ok": False,
        "conflict": True,
        "error": "apply conflict; source was restored",
    }
    assert git(repo, "rev-parse", "HEAD") == source_head
    assert git(repo, "status", "--porcelain") == ""
    assert (repo / "tracked.txt").read_text(
        encoding="utf-8"
    ) == "source version\n"
    assert record.worktree_path.is_dir()
    assert (record.worktree_path / "tracked.txt").read_text(
        encoding="utf-8"
    ) == "session version\n"
    assert service.load("apply-conflict").state is WorktreeState.CONFLICT


@requires_seatbelt
def test_apply_refuses_dirty_source_without_modifying_it(
    tmp_path: Path,
) -> None:
    repo = repository(tmp_path)
    service = GitWorktreeService(tmp_path / "data")
    record = service.prepare("dirty-apply", repo)
    (record.worktree_path / "generated.txt").write_text(
        "generated\n",
        encoding="utf-8",
    )
    service.stage("dirty-apply", "generated.txt")
    service.commit("dirty-apply", "Session change")
    (repo / "tracked.txt").write_text("dirty source\n", encoding="utf-8")
    source_head = git(repo, "rev-parse", "HEAD")

    with pytest.raises(
        GitWorkspaceError,
        match="source worktree must be clean",
    ):
        service.apply_back("dirty-apply")

    assert git(repo, "rev-parse", "HEAD") == source_head
    assert (repo / "tracked.txt").read_text(
        encoding="utf-8"
    ) == "dirty source\n"
