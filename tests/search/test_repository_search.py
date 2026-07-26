import io
import os
import subprocess
import time

import runtime.search.service as search_service
from runtime.search import search_repository_roots


def _git_repo(path):
    path.mkdir()
    subprocess.run(["git", "-C", path, "init", "-q"], check=True)
    return path


def test_text_search_respects_gitignore_symlinks_and_root_boundary(tmp_path):
    root = _git_repo(tmp_path / "repo")
    (root / "src").mkdir()
    (root / "src" / "runtime.py").write_text(
        "def durable_goal():\n    return 'needle'\n",
        encoding="utf-8",
    )
    (root / "src" / "other.py").write_text(
        "value = 'needle'\n",
        encoding="utf-8",
    )
    (root / "ignored").mkdir()
    (root / "ignored" / "secret.py").write_text(
        "secret = 'needle'\n",
        encoding="utf-8",
    )
    (root / ".gitignore").write_text("ignored/\n", encoding="utf-8")
    (root / ".ignore").write_text("private.txt\n", encoding="utf-8")
    (root / "private.txt").write_text("needle\n", encoding="utf-8")
    outside = tmp_path / "outside.py"
    outside.write_text("outside = 'needle'\n", encoding="utf-8")
    os.symlink(outside, root / "linked.py")

    result = search_repository_roots(
        [{"path": str(root), "label": "repo", "available": True}],
        query="needle",
        mode="text",
        limit=20,
    )

    assert result["ok"] is True
    assert result["truncated"] is False
    assert {match["path"] for match in result["matches"]} == {
        "src/other.py",
        "src/runtime.py",
    }
    assert all(match["root"] == str(root) for match in result["matches"])
    assert all("outside" not in match["text"] for match in result["matches"])


def test_git_search_disables_fsmonitor_and_drains_fast_stdout(tmp_path):
    root = _git_repo(tmp_path / "repo")
    marker = tmp_path / "hook-ran"
    hook = tmp_path / "fsmonitor.sh"
    hook.write_text(
        f"#!/bin/sh\ntouch '{marker}'\n",
        encoding="utf-8",
    )
    hook.chmod(0o700)
    subprocess.run(
        ["git", "-C", root, "config", "core.fsmonitor", str(hook)],
        check=True,
    )
    (root / "match.py").write_text("safe needle\n", encoding="utf-8")

    for _attempt in range(20):
        result = search_repository_roots(
            [{"path": str(root), "label": "repo", "available": True}],
            query="needle",
            mode="text",
            limit=10,
        )
        assert result["count"] == 1

    assert not marker.exists()


def test_non_git_search_respects_nested_ignore_files(tmp_path):
    root = tmp_path / "plain"
    root.mkdir()
    (root / "sub").mkdir()
    (root / "sub" / ".gitignore").write_text(
        "/secret.txt\n*.log\n!visible.log\n",
        encoding="utf-8",
    )
    (root / "sub" / "secret.txt").write_text(
        "nested needle\n",
        encoding="utf-8",
    )
    (root / "sub" / "visible.txt").write_text(
        "visible needle\n",
        encoding="utf-8",
    )
    (root / "sub" / "hidden.log").write_text(
        "hidden needle\n",
        encoding="utf-8",
    )
    (root / "sub" / "visible.log").write_text(
        "visible log needle\n",
        encoding="utf-8",
    )
    (root / "sub" / "deep").mkdir()
    (root / "sub" / "deep" / "secret.txt").write_text(
        "deep visible needle\n",
        encoding="utf-8",
    )

    result = search_repository_roots(
        [{"path": str(root), "label": "plain", "available": True}],
        query="needle",
        mode="text",
        limit=10,
    )

    assert [match["path"] for match in result["matches"]] == [
        "sub/deep/secret.txt",
        "sub/visible.log",
        "sub/visible.txt"
    ]


def test_ignore_files_are_nofollow_nonblocking_and_size_bounded(tmp_path):
    outside = tmp_path / "outside-ignore"
    outside.write_text("visible.txt\n", encoding="utf-8")

    symlink_root = tmp_path / "symlink-root"
    symlink_root.mkdir()
    (symlink_root / "visible.txt").write_text("needle\n", encoding="utf-8")
    os.symlink(outside, symlink_root / ".ignore")

    fifo_root = tmp_path / "fifo-root"
    fifo_root.mkdir()
    (fifo_root / "visible.txt").write_text("needle\n", encoding="utf-8")
    os.mkfifo(fifo_root / ".gitignore")

    huge_root = tmp_path / "huge-root"
    huge_root.mkdir()
    (huge_root / "visible.txt").write_text("needle\n", encoding="utf-8")
    (huge_root / ".ignore").write_bytes(b"x" * (64 * 1024 + 1))

    started = time.monotonic()
    for root in (symlink_root, fifo_root):
        result = search_repository_roots(
            [{"path": str(root), "label": root.name, "available": True}],
            query="needle",
            mode="text",
            limit=10,
        )
        assert [match["path"] for match in result["matches"]] == [
            "visible.txt"
        ]
    oversized = search_repository_roots(
        [{"path": str(huge_root), "label": "huge", "available": True}],
        query="needle",
        mode="text",
        limit=10,
    )
    assert oversized["matches"] == []
    assert oversized["truncated"] is True
    assert time.monotonic() - started < 2


def test_git_tracked_fifo_is_skipped_without_blocking(tmp_path):
    root = _git_repo(tmp_path / "repo")
    target = root / "blocked.txt"
    target.write_text("needle\n", encoding="utf-8")
    subprocess.run(["git", "-C", root, "add", "blocked.txt"], check=True)
    target.unlink()
    os.mkfifo(target)

    started = time.monotonic()
    result = search_repository_roots(
        [{"path": str(root), "label": "repo", "available": True}],
        query="needle",
        mode="text",
        limit=10,
    )

    assert time.monotonic() - started < 2
    assert result["matches"] == []


def test_git_stdout_without_nul_is_capped_before_buffering(
    tmp_path,
    monkeypatch,
):
    root = tmp_path / "repo"
    root.mkdir()

    class FakeProcess:
        def __init__(self):
            self.stdout = io.BytesIO(b"x" * (5 * 1024 * 1024))
            self.returncode = None

        def poll(self):
            return self.returncode

        def terminate(self):
            self.returncode = -15

        def kill(self):
            self.returncode = -9

        def wait(self, timeout=None):
            if self.returncode is None:
                self.returncode = 0
            return self.returncode

    monkeypatch.setattr(
        search_service.subprocess,
        "Popen",
        lambda *_args, **_kwargs: FakeProcess(),
    )
    root_fd = os.open(root, os.O_RDONLY | os.O_DIRECTORY)
    try:
        files, truncated = search_service._git_files(
            root,
            root_fd=root_fd,
            deadline=time.monotonic() + 2,
            max_files=10,
            cancelled=None,
        )
    finally:
        os.close(root_fd)

    assert files == []
    assert truncated is True


def test_expired_deadline_does_not_touch_filesystem_or_spawn_git(
    tmp_path,
    monkeypatch,
):
    root = tmp_path / "repo"
    root.mkdir()

    def unexpected_popen(*_args, **_kwargs):
        raise AssertionError("expired search spawned Git")

    monkeypatch.setattr(
        search_service.subprocess,
        "Popen",
        unexpected_popen,
    )
    result = search_repository_roots(
        [{"path": str(root), "label": "repo", "available": True}],
        query="needle",
        mode="text",
        limit=10,
        deadline=time.monotonic() - 1,
    )

    assert result["matches"] == []
    assert result["files_scanned"] == 0
    assert result["truncated"] is True


def test_additional_ignore_filter_observes_cancellation(tmp_path):
    root = tmp_path / "repo"
    root.mkdir()
    (root / ".ignore").write_text("ignored.txt\n", encoding="utf-8")
    calls = 0

    def cancelled():
        nonlocal calls
        calls += 1
        return calls >= 3

    root_fd = os.open(root, os.O_RDONLY | os.O_DIRECTORY)
    try:
        selected, truncated = search_service._filter_additional_ignores(
            root_fd,
            ["first.txt", "second.txt"],
            deadline=time.monotonic() + 2,
            cancelled=cancelled,
        )
    finally:
        os.close(root_fd)

    assert selected == []
    assert truncated is True


def test_symbol_search_returns_definition_kind_and_line(tmp_path):
    root = _git_repo(tmp_path / "repo")
    (root / "service.py").write_text(
        "class GoalCoordinator:\n"
        "    pass\n\n"
        "def build_goal_coordinator():\n"
        "    return GoalCoordinator()\n",
        encoding="utf-8",
    )

    result = search_repository_roots(
        [{"path": str(root), "label": "repo", "available": True}],
        query="GoalCoordinator",
        mode="symbol",
        limit=20,
    )

    assert result["matches"] == [
        {
            "root": str(root),
            "root_label": "repo",
            "path": "service.py",
            "line": 1,
            "column": 7,
            "text": "class GoalCoordinator:",
            "symbol": "GoalCoordinator",
            "kind": "class",
        }
    ]


def test_symbol_search_covers_common_method_syntaxes(tmp_path):
    root = _git_repo(tmp_path / "repo")
    (root / "service.ts").write_text(
        "class Service {\n  async runTask(): Promise<void> {}\n}\n",
        encoding="utf-8",
    )
    (root / "service.go").write_text(
        "func (service *Service) RunTask() {}\n"
        "func BuildService() {}\n",
        encoding="utf-8",
    )
    (root / "Service.java").write_text(
        "public final void runTask() {}\n",
        encoding="utf-8",
    )
    (root / "Service.kt").write_text(
        "suspend fun runTask() = Unit\n",
        encoding="utf-8",
    )

    result = search_repository_roots(
        [{"path": str(root), "label": "repo", "available": True}],
        query="runtask",
        mode="symbol",
        limit=20,
    )

    assert {
        (match["path"], match["symbol"], match["kind"])
        for match in result["matches"]
    } == {
        ("Service.java", "runTask", "method"),
        ("Service.kt", "runTask", "function"),
        ("service.go", "RunTask", "method"),
        ("service.ts", "runTask", "method"),
    }

    go_function = search_repository_roots(
        [{"path": str(root), "label": "repo", "available": True}],
        query="BuildService",
        mode="symbol",
        limit=20,
    )
    assert go_function["matches"][0]["kind"] == "function"


def test_symbol_search_rejects_call_expressions(tmp_path):
    root = _git_repo(tmp_path / "repo")
    (root / "calls.ts").write_text(
        "return doThing()\n"
        "await fetch()\n"
        "new Service()\n",
        encoding="utf-8",
    )

    for query in ("doThing", "fetch", "Service"):
        result = search_repository_roots(
            [{"path": str(root), "label": "repo", "available": True}],
            query=query,
            mode="symbol",
            limit=20,
        )
        assert result["matches"] == []


def test_relevance_ranking_prefers_exact_symbol_across_roots(tmp_path):
    primary = _git_repo(tmp_path / "primary")
    secondary = _git_repo(tmp_path / "secondary")
    (primary / "z.py").write_text(
        "class GoalCoordinatorHelper:\n    pass\n",
        encoding="utf-8",
    )
    (secondary / "a.py").write_text(
        "class GoalCoordinator:\n    pass\n",
        encoding="utf-8",
    )

    result = search_repository_roots(
        [
            {"path": str(primary), "label": "primary", "available": True},
            {"path": str(secondary), "label": "secondary", "available": True},
        ],
        query="GoalCoordinator",
        mode="symbol",
        limit=1,
    )

    assert result["matches"][0]["root_label"] == "secondary"
    assert result["matches"][0]["symbol"] == "GoalCoordinator"
    assert result["truncated"] is True


def test_invalid_utf8_and_control_binary_do_not_manufacture_matches(tmp_path):
    root = _git_repo(tmp_path / "repo")
    (root / "invalid.bin").write_bytes(b"sec\xffret\n")
    (root / "control.bin").write_bytes(b"sec\x01ret\n")

    result = search_repository_roots(
        [{"path": str(root), "label": "repo", "available": True}],
        query="secret",
        mode="text",
        limit=10,
    )

    assert result["matches"] == []


def test_search_is_bounded_and_rejects_invalid_requests(tmp_path):
    root = _git_repo(tmp_path / "repo")
    for index in range(120):
        (root / f"match-{index}.txt").write_text(
            f"bounded needle {index}\n",
            encoding="utf-8",
        )

    started = time.monotonic()
    result = search_repository_roots(
        [{"path": str(root), "label": "repo", "available": True}],
        query="needle",
        mode="text",
        limit=25,
    )

    assert time.monotonic() - started < 2
    assert result["count"] == 25
    assert result["truncated"] is True
    assert result["files_scanned"] <= 5_000
    assert search_repository_roots(
        [{"path": str(root), "label": "repo", "available": True}],
        query="",
        mode="text",
        limit=25,
    ) == {"ok": False, "error": "invalid project search"}
    wrong_identity = search_repository_roots(
        [
            {
                "path": str(root),
                "label": "repo",
                "available": True,
                "_device": -1,
                "_inode": -1,
            }
        ],
        query="needle",
        mode="text",
        limit=25,
    )
    assert wrong_identity["matches"] == []
    assert wrong_identity["files_scanned"] == 0
