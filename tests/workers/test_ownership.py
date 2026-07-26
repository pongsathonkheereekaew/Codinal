from pathlib import Path

from runtime.path_scope import owns_path


def test_ownership_accepts_exact_path_and_descendants(tmp_path: Path) -> None:
    workspace = tmp_path / "workspace"
    (workspace / "src" / "parser").mkdir(parents=True)

    assert owns_path(workspace, ("src/parser",), "src/parser")
    assert owns_path(
        workspace,
        ("src/parser",),
        workspace / "src" / "parser" / "token.py",
    )


def test_ownership_rejects_siblings_traversal_and_symlink_escape(
    tmp_path: Path,
) -> None:
    workspace = tmp_path / "workspace"
    outside = tmp_path / "outside"
    (workspace / "src" / "parser").mkdir(parents=True)
    (workspace / "src" / "other").mkdir()
    outside.mkdir()
    (workspace / "src" / "parser" / "escape").symlink_to(
        outside,
        target_is_directory=True,
    )

    assert not owns_path(workspace, ("src/parser",), "src/other/file.py")
    assert not owns_path(workspace, ("src/parser",), "../outside/file.py")
    assert not owns_path(
        workspace,
        ("src/parser",),
        "src/parser/escape/file.py",
    )
