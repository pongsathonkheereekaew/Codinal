from pathlib import Path

from runtime.policy import ToolManifest
from runtime.sessions import RootDir
from runtime.tools import build_core_registry


def test_read_file_returns_numbered_window(tmp_path):
    (tmp_path / "code.py").write_text(
        "one\ntwo\nthree\n",
        encoding="utf-8",
    )
    registry = build_core_registry(
        [RootDir(tmp_path, writable=True)],
        manifest=ToolManifest(),
    )

    result = registry.execute(
        "read_file",
        {"path": "code.py", "start_line": 2, "max_lines": 2},
    )

    assert result == {
        "path": "code.py",
        "start_line": 2,
        "end_line": 3,
        "total_lines": 3,
        "content": "     2\ttwo\n     3\tthree",
    }


def test_read_file_blocks_parent_and_symlink_escape(tmp_path):
    outside = tmp_path.parent / "outside-secret.txt"
    outside.write_text("secret", encoding="utf-8")
    (tmp_path / "link.txt").symlink_to(outside)
    registry = build_core_registry(
        [RootDir(tmp_path, writable=True)],
        manifest=ToolManifest(),
    )

    parent = registry.execute("read_file", {"path": "../outside-secret.txt"})
    symlink = registry.execute("read_file", {"path": "link.txt"})

    assert parent == {"error": "path is outside readable roots"}
    assert symlink == {"error": "path is outside readable roots"}
    assert "secret" not in str((parent, symlink))


def test_absolute_path_in_extra_root_is_readable(tmp_path):
    workspace = tmp_path / "workspace"
    shared = tmp_path / "shared"
    workspace.mkdir()
    shared.mkdir()
    document = shared / "notes.txt"
    document.write_text("shared", encoding="utf-8")
    roots = [
        RootDir(workspace, writable=True),
        RootDir(shared, writable=False),
    ]
    registry = build_core_registry(roots, manifest=ToolManifest())

    result = registry.execute("read_file", {"path": str(document)})

    assert result["content"] == "     1\tshared"
    assert result["path"] == str(document)


def test_read_root_binding_rejects_retargeted_extra_root(tmp_path):
    workspace = tmp_path / "workspace"
    shared = tmp_path / "shared"
    outside = tmp_path / "outside"
    workspace.mkdir()
    shared.mkdir()
    outside.mkdir()
    (outside / "secret.txt").write_text("secret")
    metadata = shared.stat()
    registry = build_core_registry(
        [
            RootDir(workspace, writable=True),
            RootDir(
                shared,
                writable=False,
                device=metadata.st_dev,
                inode=metadata.st_ino,
            ),
        ],
        manifest=ToolManifest(),
    )
    shared.rename(tmp_path / "moved")
    shared.symlink_to(outside, target_is_directory=True)

    result = registry.execute(
        "read_file",
        {"path": str(shared / "secret.txt")},
    )

    assert result == {"error": "path is outside readable roots"}


def test_list_files_is_bounded_and_skips_generated_directories(tmp_path):
    (tmp_path / ".git").mkdir()
    (tmp_path / ".git" / "config").write_text("hidden")
    (tmp_path / "src").mkdir()
    (tmp_path / "src" / "a.py").write_text("a")
    (tmp_path / "src" / "b.py").write_text("b")
    registry = build_core_registry(
        [RootDir(tmp_path, writable=True)],
        manifest=ToolManifest(),
    )

    result = registry.execute(
        "list_files",
        {"path": ".", "max_results": 1},
    )

    assert result["count"] == 1
    assert result["truncated"] is True
    assert ".git" not in str(result)


def test_grep_is_literal_bounded_and_reports_file_lines(tmp_path):
    (tmp_path / "a.py").write_text(
        "value = '[literal]'\nother = 1\n",
        encoding="utf-8",
    )
    (tmp_path / "b.py").write_text(
        "text = '[literal]'\n",
        encoding="utf-8",
    )
    registry = build_core_registry(
        [RootDir(tmp_path, writable=True)],
        manifest=ToolManifest(),
    )

    result = registry.execute(
        "grep",
        {
            "pattern": "[literal]",
            "path": ".",
            "glob": "*.py",
            "max_results": 1,
        },
    )

    assert result["count"] == 1
    assert result["truncated"] is True
    assert result["matches"][0] == {
        "file": "a.py",
        "line": 1,
        "text": "value = '[literal]'",
    }


def test_registry_exposes_only_implemented_read_tools(tmp_path):
    registry = build_core_registry(
        [RootDir(tmp_path, writable=True)],
        manifest=ToolManifest(),
    )

    assert registry.names() == ["read_file", "list_files", "grep"]
    assert all(
        schema["function"]["parameters"]["additionalProperties"] is False
        for schema in registry.schemas()
    )
