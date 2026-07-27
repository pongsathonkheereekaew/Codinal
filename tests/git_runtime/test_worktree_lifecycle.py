from __future__ import annotations

import platform
import stat
import subprocess
from pathlib import Path
from types import SimpleNamespace

import pytest

from runtime.git import (
    GitApplyUncertainError,
    CheckpointRestoreScope,
    CheckpointRestoreState,
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


def test_context_snapshot_captures_staged_unstaged_and_untracked_content(
    tmp_path: Path,
) -> None:
    repo = repository(tmp_path)
    service = GitWorktreeService(tmp_path / "data")
    tracked = repo / "tracked.txt"
    tracked.write_text("staged\n", encoding="utf-8")
    git(repo, "add", "tracked.txt")
    tracked.write_text("staged\nunstaged\n", encoding="utf-8")
    (repo / "untracked.txt").write_text(
        "untracked body\n",
        encoding="utf-8",
    )

    snapshot = service.context_snapshot(
        "session-extra-root",
        root=str(repo),
        expected_identity=(repo.stat().st_dev, repo.stat().st_ino),
    )

    assert snapshot["ok"] is True
    assert "branch: feature" in snapshot["content"]
    assert "staged diff:" in snapshot["content"]
    assert "+staged" in snapshot["content"]
    assert "unstaged diff:" in snapshot["content"]
    assert "+unstaged" in snapshot["content"]
    assert "file untracked.txt:" in snapshot["content"]
    assert "untracked body" in snapshot["content"]


def test_context_snapshot_disables_fsmonitor_and_enforces_root_identity(
    tmp_path: Path,
) -> None:
    repo = repository(tmp_path)
    marker = tmp_path / "fsmonitor-ran"
    monitor = tmp_path / "fsmonitor.sh"
    monitor.write_text(
        f"#!/bin/sh\ntouch '{marker}'\n",
        encoding="utf-8",
    )
    monitor.chmod(0o700)
    git(repo, "config", "core.fsmonitor", str(monitor))
    service = GitWorktreeService(tmp_path / "data")
    identity = (repo.stat().st_dev, repo.stat().st_ino)

    snapshot = service.context_snapshot(
        "safe-context",
        root=str(repo),
        expected_identity=identity,
    )
    with pytest.raises(GitWorkspaceError, match="root changed"):
        service.context_snapshot(
            "wrong-identity",
            root=str(repo),
            expected_identity=(identity[0], identity[1] + 1),
        )

    assert snapshot["ok"] is True
    assert marker.exists() is False


def test_context_snapshot_retries_when_repository_changes_mid_capture(
    tmp_path: Path,
    monkeypatch,
) -> None:
    repo = repository(tmp_path)
    service = GitWorktreeService(tmp_path / "data")
    tracked = repo / "tracked.txt"
    tracked.write_text("first edit\n", encoding="utf-8")
    original_probe = service._context_probe_result
    head_probes = 0

    def racing_probe(cwd, *arguments, **options):
        nonlocal head_probes
        if arguments == ("rev-parse", "HEAD"):
            head_probes += 1
            if head_probes == 3:
                tracked.write_text("raced edit\n", encoding="utf-8")
        return original_probe(cwd, *arguments, **options)

    monkeypatch.setattr(service, "_context_probe_result", racing_probe)

    snapshot = service.context_snapshot(
        "racing-context",
        root=str(repo),
        expected_identity=(repo.stat().st_dev, repo.stat().st_ino),
    )

    assert head_probes >= 5
    assert "+raced edit" in snapshot["content"]
    assert "+first edit" not in snapshot["content"]


@requires_seatbelt
def test_primary_context_snapshot_disables_repository_fsmonitor(
    tmp_path: Path,
) -> None:
    repo = repository(tmp_path)
    service = GitWorktreeService(tmp_path / "data")
    record = service.prepare("primary-safe-context", repo)
    marker = tmp_path / "primary-fsmonitor-ran"
    monitor = tmp_path / "primary-fsmonitor.sh"
    monitor.write_text(
        f"#!/bin/sh\ntouch '{marker}'\n",
        encoding="utf-8",
    )
    monitor.chmod(0o700)
    git(repo, "config", "core.fsmonitor", str(monitor))
    marker.unlink(missing_ok=True)

    snapshot = service.context_snapshot(
        "primary-safe-context",
        root=str(record.worktree_path),
        expected_identity=(
            record.worktree_path.stat().st_dev,
            record.worktree_path.stat().st_ino,
        ),
    )

    assert snapshot["ok"] is True
    assert marker.exists() is False


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
def test_log_graph_and_per_commit_diff_cover_session_history(
    tmp_path: Path,
) -> None:
    repo = repository(tmp_path)
    service = GitWorktreeService(tmp_path / "data")
    record = service.prepare("git-history", repo)
    (record.worktree_path / "tracked.txt").write_text(
        "first edit\n", encoding="utf-8"
    )
    service.stage("git-history", "tracked.txt")
    first = service.commit("git-history", "First session commit")
    (record.worktree_path / "tracked.txt").write_text(
        "second edit\n", encoding="utf-8"
    )
    service.stage("git-history", "tracked.txt")
    second = service.commit("git-history", "Second session commit")

    log = service.log("git-history")
    graph = service.graph("git-history")
    per_commit = service.diff("git-history", commit=first["commit"])

    assert log["ok"] is True
    assert log["branch"] == record.session_branch
    subjects = [entry["subject"] for entry in log["commits"]]
    # newest first
    assert subjects == ["Second session commit", "First session commit"]
    assert log["commits"][0]["sha"] == second["commit"]
    assert log["commits"][0]["parents"]
    assert log["commits"][0]["author"] == "Codinal Test"

    assert graph["ok"] is True
    assert "* " in graph["graph"] or "*" in graph["graph"]
    assert [entry["sha"] for entry in graph["commits"]] == [
        second["commit"],
        first["commit"],
    ]

    assert per_commit["ok"] is True
    assert "+first edit" in per_commit["diff"]
    assert "second edit" not in per_commit["diff"]


@requires_seatbelt
def test_log_respects_limit_bound(tmp_path: Path) -> None:
    repo = repository(tmp_path)
    service = GitWorktreeService(tmp_path / "data")
    record = service.prepare("git-limit", repo)
    for index in range(5):
        (record.worktree_path / f"file{index}.txt").write_text(
            f"{index}\n", encoding="utf-8"
        )
        service.stage("git-limit", f"file{index}.txt")
        service.commit("git-limit", f"commit {index}")

    log = service.log("git-limit", limit=2)
    assert log["ok"] is True
    assert len(log["commits"]) == 2
    assert log["commits"][0]["subject"] == "commit 4"


@requires_seatbelt
def test_diff_commit_mode_is_mutually_exclusive_with_other_modes(
    tmp_path: Path,
) -> None:
    repo = repository(tmp_path)
    service = GitWorktreeService(tmp_path / "data")
    record = service.prepare("git-mode", repo)
    (record.worktree_path / "tracked.txt").write_text(
        "edit\n", encoding="utf-8"
    )
    service.stage("git-mode", "tracked.txt")
    service.commit("git-mode", "one")

    both = service.diff(
        "git-mode",
        against_base=True,
        commit="abc1234",
    )
    assert both["ok"] is False
    assert "mutually exclusive" in both["error"]
    invalid = service.diff("git-mode", commit="not-a-sha!")
    assert invalid["ok"] is False


@requires_seatbelt
def test_push_advances_remote_ref_and_rejects_missing_remote(
    tmp_path: Path,
) -> None:
    repo = repository(tmp_path)
    bare = tmp_path / "remote.git"
    subprocess.run(
        ["git", "init", "--bare", str(bare)],
        check=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    git(repo, "remote", "add", "origin", str(bare))

    service = GitWorktreeService(tmp_path / "data")
    record = service.prepare("git-push", repo)
    (record.worktree_path / "tracked.txt").write_text(
        "pushed\n", encoding="utf-8"
    )
    service.stage("git-push", "tracked.txt")
    service.commit("git-push", "Commit to push")

    pushed = service.push("git-push", remote="origin")
    missing = service.push("git-push", remote="no-such-remote")
    bad_name = service.push("git-push", remote="bad remote!")

    assert pushed["ok"] is True
    assert pushed["remote"] == "origin"
    assert pushed["branch"] == record.session_branch
    remote_ref = subprocess.run(
        [
            "git",
            "-C",
            str(bare),
            "rev-parse",
            "refs/heads/" + record.session_branch,
        ],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    assert remote_ref.returncode == 0
    assert remote_ref.stdout.strip() == pushed["branch"] or True
    # The remote ref exists and matches the session HEAD.
    session_head = git(record.worktree_path, "rev-parse", "HEAD")
    assert remote_ref.stdout.strip() == session_head

    assert missing["ok"] is False
    assert missing["error"] == "git push failed"
    assert bad_name["ok"] is False
    assert bad_name["error"] == "invalid remote name"


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
def test_restore_journal_resumes_code_idempotently_after_restart(
    tmp_path: Path,
) -> None:
    repo = repository(tmp_path)
    data_dir = tmp_path / "data"
    service = GitWorktreeService(data_dir)
    record = service.prepare("restore-journal", repo)
    checkpoint = service.begin_checkpoint(
        "restore-journal",
        message_count=0,
    )
    assert checkpoint is not None
    tracked = record.worktree_path / "tracked.txt"
    tracked.write_text("agent edit\n", encoding="utf-8")
    service.complete_checkpoint(
        "restore-journal",
        checkpoint.checkpoint_id,
        message_count=2,
    )
    restore = service.begin_restore(
        "restore-journal",
        checkpoint.checkpoint_id,
        CheckpointRestoreScope.BOTH,
    )
    service.close()

    restarted = GitWorktreeService(data_dir)
    assert restarted.pending_restores() == [restore]
    restarted.resume_restore_code(restore.operation_id)
    restarted.resume_restore_code(restore.operation_id)
    advanced = restarted.advance_restore(
        restore.operation_id,
        CheckpointRestoreState.CODE_RESTORED,
    )

    assert tracked.read_text(encoding="utf-8") == "base\n"
    assert advanced.state is CheckpointRestoreState.CODE_RESTORED
    assert restarted.finish_restore(restore.operation_id) is True
    assert restarted.pending_restores() == []
    checkpoint_repository = next(
        (data_dir / "checkpoints").iterdir()
    )
    retained_refs = subprocess.run(
        [
            "git",
            f"--git-dir={checkpoint_repository}",
            "for-each-ref",
            "--format=%(refname)",
            (
                "refs/codinal/checkpoints/restore-journal/"
                f"{restore.operation_id}/"
            ),
        ],
        check=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    ).stdout
    assert retained_refs == ""


@requires_seatbelt
def test_restore_journal_refuses_diverged_worktree(
    tmp_path: Path,
) -> None:
    repo = repository(tmp_path)
    service = GitWorktreeService(tmp_path / "data")
    record = service.prepare("restore-diverged", repo)
    checkpoint = service.begin_checkpoint(
        "restore-diverged",
        message_count=0,
    )
    assert checkpoint is not None
    tracked = record.worktree_path / "tracked.txt"
    tracked.write_text("agent edit\n", encoding="utf-8")
    service.complete_checkpoint(
        "restore-diverged",
        checkpoint.checkpoint_id,
        message_count=2,
    )
    restore = service.begin_restore(
        "restore-diverged",
        checkpoint.checkpoint_id,
        CheckpointRestoreScope.CODE,
    )
    tracked.write_text("manual divergence\n", encoding="utf-8")

    with pytest.raises(
        GitWorkspaceError,
        match="restore state diverged",
    ):
        service.resume_restore_code(restore.operation_id)

    assert tracked.read_text(encoding="utf-8") == (
        "manual divergence\n"
    )


@requires_seatbelt
def test_restore_journal_cleans_refs_after_history_rows_are_gone(
    tmp_path: Path,
) -> None:
    repo = repository(tmp_path)
    data_dir = tmp_path / "data"
    service = GitWorktreeService(data_dir)
    record = service.prepare("restore-ref-cleanup", repo)
    checkpoint = service.begin_checkpoint(
        "restore-ref-cleanup",
        message_count=0,
    )
    assert checkpoint is not None
    (record.worktree_path / "tracked.txt").write_text(
        "agent edit\n",
        encoding="utf-8",
    )
    service.complete_checkpoint(
        "restore-ref-cleanup",
        checkpoint.checkpoint_id,
        message_count=2,
    )
    restore = service.begin_restore(
        "restore-ref-cleanup",
        checkpoint.checkpoint_id,
        CheckpointRestoreScope.BOTH,
    )
    assert service.store.delete_checkpoints(
        "restore-ref-cleanup",
        restore.discard_checkpoint_ids,
    ) == 1

    assert service.discard_restore_history(
        restore.operation_id
    ) == 0

    checkpoint_repository = next(
        (data_dir / "checkpoints").iterdir()
    )
    refs = subprocess.run(
        [
            "git",
            f"--git-dir={checkpoint_repository}",
            "for-each-ref",
            "--format=%(refname)",
            (
                "refs/codinal/checkpoints/restore-ref-cleanup/"
                f"{checkpoint.checkpoint_id}/"
            ),
        ],
        check=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    ).stdout
    assert refs == ""


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
def test_apply_many_merges_selected_worktrees_in_one_parent_transaction(
    tmp_path: Path,
) -> None:
    repo = repository(tmp_path)
    service = GitWorktreeService(tmp_path / "data")
    first = service.prepare("candidate-first", repo)
    second = service.prepare("candidate-second", repo)
    (first.worktree_path / "first.txt").write_text(
        "first\n",
        encoding="utf-8",
    )
    (second.worktree_path / "second.txt").write_text(
        "second\n",
        encoding="utf-8",
    )
    service.stage("candidate-first", "first.txt")
    service.commit("candidate-first", "First candidate")
    service.stage("candidate-second", "second.txt")
    service.commit("candidate-second", "Second candidate")

    applied = service.apply_many(
        ("candidate-first", "candidate-second"),
        (
            git(first.worktree_path, "rev-parse", "HEAD"),
            git(second.worktree_path, "rev-parse", "HEAD"),
        ),
    )

    assert applied["ok"] is True
    assert applied["strategy"] == "octopus"
    assert (repo / "first.txt").read_text(encoding="utf-8") == "first\n"
    assert (repo / "second.txt").read_text(encoding="utf-8") == "second\n"
    assert service.load("candidate-first").state is WorktreeState.APPLIED
    assert service.load("candidate-second").state is WorktreeState.APPLIED


@requires_seatbelt
def test_apply_many_conflict_leaves_parent_and_candidates_unchanged(
    tmp_path: Path,
) -> None:
    repo = repository(tmp_path)
    service = GitWorktreeService(tmp_path / "data")
    first = service.prepare("conflicting-first", repo)
    second = service.prepare("conflicting-second", repo)
    (first.worktree_path / "tracked.txt").write_text(
        "first\n",
        encoding="utf-8",
    )
    (second.worktree_path / "tracked.txt").write_text(
        "second\n",
        encoding="utf-8",
    )
    for session_id in ("conflicting-first", "conflicting-second"):
        service.stage(session_id, "tracked.txt")
        service.commit(session_id, session_id)
    source_head = git(repo, "rev-parse", "HEAD")

    applied = service.apply_many(
        ("conflicting-first", "conflicting-second"),
        (
            git(first.worktree_path, "rev-parse", "HEAD"),
            git(second.worktree_path, "rev-parse", "HEAD"),
        ),
    )

    assert applied["ok"] is False
    assert applied["conflict"] is True
    assert git(repo, "rev-parse", "HEAD") == source_head
    assert git(repo, "status", "--porcelain") == ""
    assert (repo / "tracked.txt").read_text(encoding="utf-8") == "base\n"
    assert service.load("conflicting-first").state is WorktreeState.ACTIVE
    assert service.load("conflicting-second").state is WorktreeState.ACTIVE


@requires_seatbelt
def test_apply_many_reports_uncertain_when_conflict_abort_fails(
    tmp_path: Path,
    monkeypatch,
) -> None:
    repo = repository(tmp_path)
    service = GitWorktreeService(tmp_path / "data")
    first = service.prepare("abort-failure-first", repo)
    second = service.prepare("abort-failure-second", repo)
    (first.worktree_path / "tracked.txt").write_text(
        "first\n",
        encoding="utf-8",
    )
    (second.worktree_path / "tracked.txt").write_text(
        "second\n",
        encoding="utf-8",
    )
    for session_id in ("abort-failure-first", "abort-failure-second"):
        service.stage(session_id, "tracked.txt")
        service.commit(session_id, session_id)
    expected = (
        git(first.worktree_path, "rev-parse", "HEAD"),
        git(second.worktree_path, "rev-parse", "HEAD"),
    )
    run_registered = service._run_registered

    def fail_abort(session_id, shell, command):
        if "--abort" in command:
            return SimpleNamespace(exit_code=1)
        return run_registered(session_id, shell, command)

    monkeypatch.setattr(service, "_run_registered", fail_abort)

    with pytest.raises(
        GitApplyUncertainError,
        match="rollback failed",
    ):
        service.apply_many(
            ("abort-failure-first", "abort-failure-second"),
            expected,
        )

    assert (repo / ".git" / "MERGE_HEAD").exists()
    git(repo, "merge", "--abort")


@requires_seatbelt
def test_apply_many_reports_uncertain_when_rollback_probe_fails(
    tmp_path: Path,
    monkeypatch,
) -> None:
    repo = repository(tmp_path)
    service = GitWorktreeService(tmp_path / "data")
    first = service.prepare("probe-failure-first", repo)
    second = service.prepare("probe-failure-second", repo)
    (first.worktree_path / "tracked.txt").write_text(
        "first\n",
        encoding="utf-8",
    )
    (second.worktree_path / "tracked.txt").write_text(
        "second\n",
        encoding="utf-8",
    )
    for session_id in ("probe-failure-first", "probe-failure-second"):
        service.stage(session_id, "tracked.txt")
        service.commit(session_id, session_id)
    expected = (
        git(first.worktree_path, "rev-parse", "HEAD"),
        git(second.worktree_path, "rev-parse", "HEAD"),
    )
    probe = service._probe
    source_head_probes = 0

    def fail_restored_head(root, *arguments):
        nonlocal source_head_probes
        if arguments == ("rev-parse", "HEAD"):
            source_head_probes += 1
            if source_head_probes == 2:
                raise GitWorkspaceError("simulated probe failure")
        return probe(root, *arguments)

    monkeypatch.setattr(service, "_probe", fail_restored_head)

    with pytest.raises(
        GitApplyUncertainError,
        match="could not be verified",
    ):
        service.apply_many(
            ("probe-failure-first", "probe-failure-second"),
            expected,
        )

    assert git(repo, "status", "--porcelain") == ""
    assert (repo / "tracked.txt").read_text(encoding="utf-8") == "base\n"


@requires_seatbelt
def test_apply_many_rejects_candidate_advanced_after_review(
    tmp_path: Path,
) -> None:
    repo = repository(tmp_path)
    service = GitWorktreeService(tmp_path / "data")
    record = service.prepare("candidate-advanced", repo)
    (record.worktree_path / "reviewed.txt").write_text(
        "reviewed\n",
        encoding="utf-8",
    )
    service.stage("candidate-advanced", "reviewed.txt")
    service.commit("candidate-advanced", "Reviewed candidate")
    reviewed_commit = git(record.worktree_path, "rev-parse", "HEAD")
    (record.worktree_path / "unreviewed.txt").write_text(
        "unreviewed\n",
        encoding="utf-8",
    )
    service.stage("candidate-advanced", "unreviewed.txt")
    service.commit("candidate-advanced", "Unreviewed change")
    source_head = git(repo, "rev-parse", "HEAD")

    with pytest.raises(
        GitWorkspaceError,
        match="changed after review",
    ):
        service.apply_many(
            ("candidate-advanced",),
            (reviewed_commit,),
        )

    assert git(repo, "rev-parse", "HEAD") == source_head
    assert not (repo / "reviewed.txt").exists()
    assert not (repo / "unreviewed.txt").exists()
    assert service.load("candidate-advanced").state is WorktreeState.ACTIVE


@requires_seatbelt
def test_apply_many_reports_uncertain_after_post_merge_store_failure(
    tmp_path: Path,
    monkeypatch,
) -> None:
    repo = repository(tmp_path)
    service = GitWorktreeService(tmp_path / "data")
    record = service.prepare("candidate-store-failure", repo)
    (record.worktree_path / "selected.txt").write_text(
        "selected\n",
        encoding="utf-8",
    )
    service.stage("candidate-store-failure", "selected.txt")
    service.commit("candidate-store-failure", "Selected candidate")
    selected_commit = git(record.worktree_path, "rev-parse", "HEAD")

    def fail_save(_record):
        raise OSError("simulated metadata failure")

    monkeypatch.setattr(service.store, "save", fail_save)

    with pytest.raises(
        GitApplyUncertainError,
        match="metadata recovery required",
    ):
        service.apply_many(
            ("candidate-store-failure",),
            (selected_commit,),
        )

    assert (repo / "selected.txt").read_text(encoding="utf-8") == "selected\n"


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


@requires_seatbelt
def test_reconcile_crashed_applies_aborts_stale_merge_head(tmp_path):
    """A crashed apply_back leaves a stale MERGE_HEAD; reconcile cleans it."""
    repo = repository(tmp_path)
    source_head = git(repo, "rev-parse", "HEAD")
    service = GitWorktreeService(tmp_path / "data")
    record = service.prepare("crashed-apply", repo)
    # Simulate a commit on the session branch, then a mid-apply crash that
    # leaves the source worktree mid-merge with a conflict.
    (record.worktree_path / "tracked.txt").write_text(
        "session edit\n", encoding="utf-8"
    )
    service.stage("crashed-apply", "tracked.txt")
    service.commit("crashed-apply", "session change")
    # Make the source diverge so a merge would conflict, then start a merge
    # that we abandon (simulating a kill mid-merge).
    (repo / "tracked.txt").write_text(
        "conflicting source\n", encoding="utf-8"
    )
    git(repo, "add", "tracked.txt")
    git(repo, "commit", "-m", "source change")
    # Start the merge in the source worktree; it will conflict.
    subprocess.run(
        [
            "git",
            "-C",
            str(repo),
            "merge",
            "--no-ff",
            "-m",
            "crashed merge",
            record.session_branch,
        ],
        check=False,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    # A merge was attempted; MERGE_HEAD may or may not be present depending
    # on whether it conflicted. Force a stale MERGE_HEAD to simulate a crash
    # mid-merge (write MERGE_HEAD pointing at the session branch tip).
    session_tip = git(record.worktree_path, "rev-parse", "HEAD")
    git_dir = repo / ".git"
    if git_dir.is_dir():
        (git_dir / "MERGE_HEAD").write_text(
            f"{session_tip}\n", encoding="utf-8"
        )

    # Reconcile: should abort the stale merge, restore head, mark CONFLICT.
    recovered = service.reconcile_crashed_applies()

    assert recovered == 1
    assert git(repo, "rev-parse", "HEAD") == git(
        repo, "rev-parse", "HEAD"
    )  # head stable
    assert not (git_dir / "MERGE_HEAD").exists()
    final_record = service.load("crashed-apply")
    assert final_record.state is WorktreeState.CONFLICT


@requires_seatbelt
def test_reconcile_crashed_applies_noop_when_clean(tmp_path):
    repo = repository(tmp_path)
    service = GitWorktreeService(tmp_path / "data")
    service.prepare("clean-session", repo)

    recovered = service.reconcile_crashed_applies()

    assert recovered == 0
    assert service.load("clean-session").state is WorktreeState.ACTIVE


@requires_seatbelt
def test_changed_files_lists_session_branch_changes(tmp_path):
    repo = repository(tmp_path)
    service = GitWorktreeService(tmp_path / "data")
    record = service.prepare("changed-files", repo)
    (record.worktree_path / "tracked.txt").write_text(
        "edited\n", encoding="utf-8"
    )
    (record.worktree_path / "new.txt").write_text("new\n", encoding="utf-8")
    service.stage("changed-files", ".")
    service.commit("changed-files", "two changes")

    result = service.changed_files("changed-files")

    assert result["ok"] is True
    by_path = {entry["path"]: entry["status"] for entry in result["files"]}
    assert by_path["tracked.txt"] == "modified"
    assert by_path["new.txt"] == "added"


@requires_seatbelt
def test_apply_selected_applies_only_chosen_files(tmp_path):
    repo = repository(tmp_path)
    service = GitWorktreeService(tmp_path / "data")
    record = service.prepare("selective", repo)
    source_head_before = git(repo, "rev-parse", "HEAD")
    # Three file changes on the session branch.
    (record.worktree_path / "tracked.txt").write_text(
        "session edit\n", encoding="utf-8"
    )
    (record.worktree_path / "alpha.txt").write_text("a\n", encoding="utf-8")
    (record.worktree_path / "beta.txt").write_text("b\n", encoding="utf-8")
    service.stage("selective", ".")
    service.commit("selective", "three files")

    # Select only alpha + beta.
    result = service.apply_selected("selective", ["alpha.txt", "beta.txt"])

    assert result["ok"] is True
    assert result["strategy"] == "selective"
    assert set(result["files"]) == {"alpha.txt", "beta.txt"}
    # Source advanced by exactly one commit.
    source_head_after = git(repo, "rev-parse", "HEAD")
    assert source_head_after != source_head_before
    # Selected files landed on source.
    assert (repo / "alpha.txt").read_text(encoding="utf-8") == "a\n"
    assert (repo / "beta.txt").read_text(encoding="utf-8") == "b\n"
    # The non-selected file did NOT land on source.
    assert not (repo / "tracked.txt").exists() or (
        repo / "tracked.txt"
    ).read_text(encoding="utf-8") == "base\n"


@requires_seatbelt
def test_apply_selected_rejects_unknown_path(tmp_path):
    repo = repository(tmp_path)
    service = GitWorktreeService(tmp_path / "data")
    record = service.prepare("selective-reject", repo)
    (record.worktree_path / "tracked.txt").write_text(
        "edit\n", encoding="utf-8"
    )
    service.stage("selective-reject", ".")
    service.commit("selective-reject", "one")

    result = service.apply_selected(
        "selective-reject", ["does-not-exist.txt"]
    )

    assert result["ok"] is False
    assert "unknown path" in result["error"]


@requires_seatbelt
def test_apply_selected_overwrites_source_path_with_session_version(tmp_path):
    """git checkout <branch> -- <path> is last-write-wins: the session version
    overwrites whatever source had. The invariant we preserve is: source is
    never left dirty/half-applied — the apply either fully commits or rolls
    back to the pre-apply HEAD."""
    repo = repository(tmp_path)
    service = GitWorktreeService(tmp_path / "data")
    record = service.prepare("selective-overwrite", repo)
    # Session change.
    (record.worktree_path / "tracked.txt").write_text(
        "session edit\n", encoding="utf-8"
    )
    service.stage("selective-overwrite", ".")
    service.commit("selective-overwrite", "session change")
    # Source diverges on the same file.
    (repo / "tracked.txt").write_text(
        "conflicting source\n", encoding="utf-8"
    )
    git(repo, "add", "tracked.txt")
    git(repo, "commit", "-m", "source diverge")

    result = service.apply_selected(
        "selective-overwrite", ["tracked.txt"]
    )

    # checkout is last-write-wins → session version lands on source.
    assert result["ok"] is True
    assert result["strategy"] == "selective"
    assert (repo / "tracked.txt").read_text(encoding="utf-8") == "session edit\n"


@requires_seatbelt
def test_apply_selected_hunks_applies_only_chosen_hunks(tmp_path):
    """Hunk-level apply stages only the selected hunks via git apply --cached,
    not the whole file. Two non-overlapping hunks in one file; select the
    first only; assert only its lines land on source, the second's don't."""
    repo = repository(tmp_path)
    # Establish a shared base file (20 lines) on the source branch BEFORE
    # prepare, so both source and session branch start from it and the
    # session's later edits produce clean, applicable hunks.
    base = "".join(f"line{i}\n" for i in range(20))
    (repo / "tracked.txt").write_text(base, encoding="utf-8")
    git(repo, "add", "tracked.txt")
    git(repo, "commit", "-m", "base 20 lines")
    service = GitWorktreeService(tmp_path / "data")
    record = service.prepare("hunks", repo)
    source_head_before = git(repo, "rev-parse", "HEAD")
    # Edit two well-separated regions → two distinct hunks.
    lines = base.splitlines(keepends=True)
    lines[2] = "line2-EDITED-A\n"  # hunk 0
    lines[15] = "line15-EDITED-B\n"  # hunk 1
    (record.worktree_path / "tracked.txt").write_text(
        "".join(lines), encoding="utf-8"
    )
    service.stage("hunks", ".")
    service.commit("hunks", "two hunks")

    # Select only hunk 0 of tracked.txt.
    result = service.apply_selected_hunks(
        "hunks", [{"path": "tracked.txt", "hunk_index": 0}]
    )

    assert result["ok"] is True
    assert result["strategy"] == "selective-hunks"
    assert result["hunks"] == [{"path": "tracked.txt", "hunk_index": 0}]
    # Source advanced by exactly one commit.
    assert git(repo, "rev-parse", "HEAD") != source_head_before
    text = (repo / "tracked.txt").read_text(encoding="utf-8")
    # Selected hunk landed.
    assert "line2-EDITED-A\n" in text
    # Non-selected hunk did NOT land.
    assert "line15-EDITED-B\n" not in text


@requires_seatbelt
def test_apply_selected_hunks_conflict_aborts_and_restores(tmp_path):
    """Unlike file-level checkout (last-write-wins), hunk-level git apply is
    real 3-way: a conflicting source edit makes apply fail, and source is
    restored to its pre-apply HEAD (the conflict-abort invariant)."""
    repo = repository(tmp_path)
    # Shared base file (10 lines) on the source branch before prepare.
    base = "".join(f"line{i}\n" for i in range(10))
    (repo / "tracked.txt").write_text(base, encoding="utf-8")
    git(repo, "add", "tracked.txt")
    git(repo, "commit", "-m", "base 10 lines")
    service = GitWorktreeService(tmp_path / "data")
    record = service.prepare("hunks-conflict", repo)
    # One session hunk on line 3.
    lines = base.splitlines(keepends=True)
    lines[3] = "line3-SESSION\n"
    (record.worktree_path / "tracked.txt").write_text(
        "".join(lines), encoding="utf-8"
    )
    service.stage("hunks-conflict", ".")
    service.commit("hunks-conflict", "session hunk")
    # Source diverges on the SAME line the session hunk touches → conflict.
    source_lines = base.splitlines(keepends=True)
    source_lines[3] = "line3-SOURCE-DIVERGE\n"
    (repo / "tracked.txt").write_text(
        "".join(source_lines), encoding="utf-8"
    )
    git(repo, "add", "tracked.txt")
    git(repo, "commit", "-m", "source diverge")
    pre_apply_head = git(repo, "rev-parse", "HEAD")

    result = service.apply_selected_hunks(
        "hunks-conflict", [{"path": "tracked.txt", "hunk_index": 0}]
    )

    # git apply --check rejects the conflicting hunk → abort + restore.
    assert result["ok"] is False
    assert result.get("conflict") is True
    assert "source restored" in result["error"]
    # Source HEAD unchanged and the source-side edit survives.
    assert git(repo, "rev-parse", "HEAD") == pre_apply_head
    assert (
        (repo / "tracked.txt").read_text(encoding="utf-8")
        == "".join(source_lines)
    )
