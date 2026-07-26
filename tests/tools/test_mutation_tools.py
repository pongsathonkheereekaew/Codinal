from __future__ import annotations

import os
from pathlib import Path

from runtime.policy import RiskClass, ToolManifest
from runtime.sandbox import InvalidCommandError, SandboxResult
from runtime.sessions import RootDir
from runtime.tools import build_core_registry, register_mutation_tools
from runtime.tools import mutations


class FakeShell:
    def __init__(self) -> None:
        self.calls: list[tuple[str, float | None]] = []

    def run(
        self,
        command: str,
        *,
        timeout_seconds: float | None = None,
    ) -> SandboxResult:
        self.calls.append((command, timeout_seconds))
        return SandboxResult(
            exit_code=0,
            stdout="done\n",
            stderr="",
        )


def build_registry(
    workspace: Path,
    *,
    extra_roots: list[RootDir] | None = None,
    shell: object | None = None,
    mutation_recorder: object | None = None,
):
    roots = [
        RootDir(workspace, writable=True),
        *(extra_roots or []),
    ]
    registry = build_core_registry(roots, manifest=ToolManifest())
    fake_shell = shell or FakeShell()
    register_mutation_tools(
        registry,
        roots=roots,
        shell=fake_shell,
        mutation_recorder=mutation_recorder,
    )
    return registry, fake_shell


def test_registers_strict_manifest_bound_mutation_tools(
    tmp_path: Path,
) -> None:
    registry, _ = build_registry(tmp_path)

    assert registry.names() == [
        "read_file",
        "list_files",
        "grep",
        "write_file",
        "replace_in_file",
        "run_shell",
    ]
    for name, risk in {
        "write_file": RiskClass.WRITE_LOCAL,
        "replace_in_file": RiskClass.WRITE_LOCAL,
        "run_shell": RiskClass.EXEC,
    }.items():
        spec = registry.get(name)
        assert spec is not None
        assert spec.metadata.risk is risk
        parameters = spec.schema["function"]["parameters"]
        assert parameters["additionalProperties"] is False


def test_write_file_creates_and_atomically_replaces_content(
    tmp_path: Path,
) -> None:
    registry, _ = build_registry(tmp_path)
    target = tmp_path / "source.py"
    target.write_text("old", encoding="utf-8")
    target.chmod(0o640)
    old_inode = target.stat().st_ino

    result = registry.execute(
        "write_file",
        {"path": "source.py", "content": "print('new')\n"},
    )

    assert result == {
        "ok": True,
        "path": "source.py",
        "bytes_written": 13,
        "created": False,
    }
    assert target.read_text(encoding="utf-8") == "print('new')\n"
    assert target.stat().st_ino != old_inode
    assert target.stat().st_mode & 0o777 == 0o640


def test_mutation_recorder_observes_preimage_before_file_write(
    tmp_path: Path,
) -> None:
    target = tmp_path / ".ignored"
    target.write_text("manual\n", encoding="utf-8")

    class Recorder:
        def __init__(self):
            self.preimages = []

        def record_file_preimage(self, path):
            self.preimages.append(
                (path, path.read_text(encoding="utf-8"))
            )

        def record_shell_fallback(self):
            raise AssertionError("shell fallback was not expected")

    recorder = Recorder()
    registry, _ = build_registry(
        tmp_path,
        mutation_recorder=recorder,
    )

    result = registry.execute(
        "write_file",
        {"path": ".ignored", "content": "agent\n"},
    )

    assert result["ok"] is True
    assert recorder.preimages == [(target, "manual\n")]
    assert target.read_text(encoding="utf-8") == "agent\n"


def test_mutation_recorder_failure_prevents_file_and_shell_mutation(
    tmp_path: Path,
) -> None:
    target = tmp_path / "source.py"
    target.write_text("manual\n", encoding="utf-8")

    class FailingRecorder:
        def record_file_preimage(self, _path):
            raise OSError("private failure")

        def record_shell_fallback(self):
            raise OSError("private failure")

    shell = FakeShell()
    registry, _ = build_registry(
        tmp_path,
        shell=shell,
        mutation_recorder=FailingRecorder(),
    )

    written = registry.execute(
        "write_file",
        {"path": "source.py", "content": "agent\n"},
    )
    executed = registry.execute(
        "run_shell",
        {"command": "pwd"},
    )

    assert written == {
        "ok": False,
        "error": "automatic checkpoint unavailable",
    }
    assert executed == {
        "error": "automatic checkpoint unavailable",
    }
    assert target.read_text(encoding="utf-8") == "manual\n"
    assert shell.calls == []


def test_write_file_refuses_traversal_symlinks_and_missing_parent(
    tmp_path: Path,
) -> None:
    workspace = tmp_path / "workspace"
    outside = tmp_path / "outside"
    workspace.mkdir()
    outside.mkdir()
    (workspace / "escape").symlink_to(outside, target_is_directory=True)
    (workspace / "leaf").symlink_to(outside / "target")
    registry, _ = build_registry(workspace)

    traversal = registry.execute(
        "write_file",
        {"path": "../outside/traversal", "content": "bad"},
    )
    parent_link = registry.execute(
        "write_file",
        {"path": "escape/parent-link", "content": "bad"},
    )
    leaf_link = registry.execute(
        "write_file",
        {"path": "leaf", "content": "bad"},
    )
    missing = registry.execute(
        "write_file",
        {"path": "missing/child", "content": "bad"},
    )

    assert traversal == {"ok": False, "error": "path is outside writable roots"}
    assert parent_link == {
        "ok": False,
        "error": "path is outside writable roots",
    }
    assert leaf_link == {"ok": False, "error": "symbolic links are not writable"}
    assert missing == {"ok": False, "error": "parent directory does not exist"}
    assert list(outside.iterdir()) == []


def test_read_only_extra_root_cannot_be_written(tmp_path: Path) -> None:
    workspace = tmp_path / "workspace"
    read_only = tmp_path / "reference"
    writable = tmp_path / "writable"
    workspace.mkdir()
    read_only.mkdir()
    writable.mkdir()
    registry, _ = build_registry(
        workspace,
        extra_roots=[
            RootDir(read_only, writable=False),
            RootDir(writable, writable=True),
        ],
    )

    denied = registry.execute(
        "write_file",
        {"path": str(read_only / "no"), "content": "bad"},
    )
    allowed = registry.execute(
        "write_file",
        {"path": str(writable / "yes"), "content": "good"},
    )

    assert denied == {"ok": False, "error": "path is outside writable roots"}
    assert allowed["ok"] is True
    assert (writable / "yes").read_text(encoding="utf-8") == "good"


def test_replace_in_file_requires_exact_expected_match_count(
    tmp_path: Path,
) -> None:
    target = tmp_path / "values.txt"
    target.write_text("old old", encoding="utf-8")
    registry, _ = build_registry(tmp_path)

    mismatch = registry.execute(
        "replace_in_file",
        {
            "path": "values.txt",
            "old": "old",
            "new": "new",
            "expected_replacements": 1,
        },
    )
    assert mismatch == {
        "ok": False,
        "error": "expected 1 occurrence(s), found 2",
    }
    assert target.read_text(encoding="utf-8") == "old old"

    replaced = registry.execute(
        "replace_in_file",
        {
            "path": "values.txt",
            "old": "old",
            "new": "new",
            "expected_replacements": 2,
        },
    )
    assert replaced == {
        "ok": True,
        "path": "values.txt",
        "replacements": 2,
        "bytes_written": 7,
    }
    assert target.read_text(encoding="utf-8") == "new new"


def test_replace_rejects_non_utf8_and_non_file_targets(
    tmp_path: Path,
) -> None:
    (tmp_path / "binary").write_bytes(b"\xff")
    (tmp_path / "directory").mkdir()
    registry, _ = build_registry(tmp_path)

    binary = registry.execute(
        "replace_in_file",
        {"path": "binary", "old": "a", "new": "b"},
    )
    directory = registry.execute(
        "replace_in_file",
        {"path": "directory", "old": "a", "new": "b"},
    )

    assert binary == {"ok": False, "error": "file is not UTF-8 text"}
    assert directory == {"ok": False, "error": "target is not a regular file"}


def test_replace_rejects_oversized_result_before_allocating_it(
    tmp_path: Path,
    monkeypatch,
) -> None:
    target = tmp_path / "values.txt"
    target.write_text("x x", encoding="utf-8")
    registry, _ = build_registry(tmp_path)
    monkeypatch.setattr(mutations, "_MAX_WRITE_BYTES", 8)

    result = registry.execute(
        "replace_in_file",
        {
            "path": "values.txt",
            "old": "x",
            "new": "12345",
            "expected_replacements": 2,
        },
    )

    assert result == {"ok": False, "error": "result exceeds write limit"}
    assert target.read_text(encoding="utf-8") == "x x"


def test_replace_does_not_clobber_a_concurrent_edit(
    tmp_path: Path,
    monkeypatch,
) -> None:
    target = tmp_path / "values.txt"
    target.write_text("old", encoding="utf-8")
    registry, _ = build_registry(tmp_path)
    atomic_write = mutations._atomic_write

    def race(edit_target, content, *, mode, expected=None):
        target.write_text("newer edit", encoding="utf-8")
        return atomic_write(
            edit_target,
            content,
            mode=mode,
            expected=expected,
        )

    monkeypatch.setattr(mutations, "_atomic_write", race)
    result = registry.execute(
        "replace_in_file",
        {"path": "values.txt", "old": "old", "new": "replacement"},
    )

    assert result == {
        "ok": False,
        "error": "file changed during replacement",
    }
    assert target.read_text(encoding="utf-8") == "newer edit"


def test_run_shell_returns_bounded_executor_result(tmp_path: Path) -> None:
    registry, shell = build_registry(tmp_path)

    result = registry.execute(
        "run_shell",
        {"command": "git status --short", "timeout_seconds": 30},
    )

    assert shell.calls == [("git status --short", 30.0)]
    assert result == {
        "exit_code": 0,
        "stdout": "done\n",
        "stderr": "",
        "timed_out": False,
        "interrupted": False,
        "output_truncated": False,
    }


def test_run_shell_surfaces_only_stable_validation_error(
    tmp_path: Path,
) -> None:
    class RejectingShell(FakeShell):
        def run(self, command, *, timeout_seconds=None):
            raise InvalidCommandError(f"secret detail: {command}")

    registry, _ = build_registry(tmp_path, shell=RejectingShell())

    result = registry.execute(
        "run_shell",
        {"command": "bad"},
    )

    assert result == {"error": "invalid command"}


def test_write_rejects_invalid_argument_types(tmp_path: Path) -> None:
    registry, _ = build_registry(tmp_path)

    assert registry.execute(
        "write_file",
        {"path": "file", "content": 42},
    ) == {"ok": False, "error": "content must be text"}
    assert registry.execute(
        "replace_in_file",
        {"path": "file", "old": "", "new": "x"},
    ) == {"ok": False, "error": "old text must not be empty"}


def test_new_file_uses_private_default_permissions(tmp_path: Path) -> None:
    registry, _ = build_registry(tmp_path)

    registry.execute(
        "write_file",
        {"path": "private", "content": "content"},
    )

    assert os.stat(tmp_path / "private").st_mode & 0o777 == 0o600
