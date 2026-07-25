from __future__ import annotations

import platform
import stat
import subprocess
from pathlib import Path

import pytest

from runtime.git import (
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
