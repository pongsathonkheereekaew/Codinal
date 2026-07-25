"""Bounded, root-scoped read tools for the coding runtime."""

from __future__ import annotations

import fnmatch
import os
import time
from pathlib import Path
from typing import Any, Iterable, Optional

from runtime.policy import ToolManifest
from runtime.sessions import RootDir

from .registry import ToolRegistry

_MAX_FILE_BYTES = 5 * 1024 * 1024
_MAX_LINES = 2_000
_MAX_LINE_CHARS = 500
_MAX_LIST_RESULTS = 1_000
_MAX_GREP_RESULTS = 1_000
_MAX_GREP_FILES = 2_000
_MAX_GREP_SECONDS = 5.0
_IGNORE_DIRS = {
    ".git",
    ".hg",
    ".svn",
    ".venv",
    "venv",
    "node_modules",
    "target",
    "dist",
    "build",
    "__pycache__",
    ".pytest_cache",
    ".mypy_cache",
    ".ruff_cache",
    ".next",
}


def build_core_registry(
    roots: list[RootDir],
    *,
    manifest: Optional[ToolManifest] = None,
) -> ToolRegistry:
    paths = _ReadablePaths(roots)
    registry = ToolRegistry(manifest or ToolManifest())

    def read_file(
        path: str,
        start_line: int = 1,
        max_lines: int = _MAX_LINES,
    ) -> dict[str, Any]:
        target, error = paths.resolve(path)
        if target is None:
            return {"error": error}
        if not target.is_file():
            return {"error": "not a readable file"}
        try:
            if target.stat().st_size > _MAX_FILE_BYTES:
                return {"error": "file exceeds read limit"}
        except OSError:
            return {"error": "file is unavailable"}
        start = _bounded_int(start_line, default=1, maximum=10_000_000)
        limit = _bounded_int(max_lines, default=_MAX_LINES, maximum=_MAX_LINES)
        selected: list[str] = []
        total = 0
        try:
            with target.open("r", encoding="utf-8", errors="replace") as stream:
                for line_number, line in enumerate(stream, 1):
                    total = line_number
                    if line_number < start or len(selected) >= limit:
                        continue
                    text = line.rstrip("\n\r")
                    if len(text) > _MAX_LINE_CHARS:
                        text = text[:_MAX_LINE_CHARS] + "… (line truncated)"
                    selected.append(f"{line_number:>6}\t{text}")
        except OSError:
            return {"error": "file is unavailable"}
        end = start + len(selected) - 1 if selected else start - 1
        result = {
            "path": paths.display(target),
            "start_line": start,
            "end_line": end,
            "total_lines": total,
            "content": "\n".join(selected),
        }
        if end < total:
            result["truncated"] = True
            result["next_start_line"] = end + 1
        return result

    def list_files(
        path: str = ".",
        max_results: int = 200,
    ) -> dict[str, Any]:
        base, error = paths.resolve(path)
        if base is None:
            return {"error": error}
        if not base.is_dir():
            return {"error": "not a readable directory"}
        limit = _bounded_int(
            max_results,
            default=200,
            maximum=_MAX_LIST_RESULTS,
        )
        entries: list[dict[str, str]] = []
        try:
            for candidate in _walk(base):
                resolved, _ = paths.resolve(str(candidate))
                if resolved is None:
                    continue
                entries.append(
                    {
                        "path": paths.display(resolved),
                        "kind": "directory" if resolved.is_dir() else "file",
                    }
                )
                if len(entries) > limit:
                    break
        except OSError:
            return {"error": "directory is unavailable"}
        truncated = len(entries) > limit
        entries = entries[:limit]
        return {
            "count": len(entries),
            "entries": entries,
            "truncated": truncated,
        }

    def grep(
        pattern: str,
        path: str = ".",
        glob: Optional[str] = None,
        max_results: int = 100,
    ) -> dict[str, Any]:
        if not isinstance(pattern, str) or not 1 <= len(pattern) <= 1_000:
            return {"error": "invalid search pattern"}
        if glob is not None and (
            not isinstance(glob, str) or not 1 <= len(glob) <= 256
        ):
            return {"error": "invalid filename glob"}
        base, error = paths.resolve(path)
        if base is None:
            return {"error": error}
        if not base.is_dir():
            return {"error": "not a readable directory"}
        limit = _bounded_int(
            max_results,
            default=100,
            maximum=_MAX_GREP_RESULTS,
        )
        matches: list[dict[str, Any]] = []
        files_scanned = 0
        deadline = time.monotonic() + _MAX_GREP_SECONDS
        for candidate in _walk_files(base):
            if time.monotonic() >= deadline or files_scanned >= _MAX_GREP_FILES:
                break
            resolved, _ = paths.resolve(str(candidate))
            if resolved is None:
                continue
            display = paths.display(resolved)
            if glob and not fnmatch.fnmatch(display, glob):
                continue
            try:
                if resolved.stat().st_size > _MAX_FILE_BYTES:
                    continue
                files_scanned += 1
                with resolved.open(
                    "r",
                    encoding="utf-8",
                    errors="ignore",
                ) as stream:
                    for line_number, line in enumerate(stream, 1):
                        if pattern not in line:
                            continue
                        matches.append(
                            {
                                "file": display,
                                "line": line_number,
                                "text": line.rstrip()[:_MAX_LINE_CHARS],
                            }
                        )
                        if len(matches) > limit:
                            break
            except OSError:
                continue
            if len(matches) > limit:
                break
        truncated = (
            len(matches) > limit
            or files_scanned >= _MAX_GREP_FILES
            or time.monotonic() >= deadline
        )
        matches = matches[:limit]
        return {
            "count": len(matches),
            "matches": matches,
            "truncated": truncated,
        }

    registry.register(read_file, schema=_read_file_schema())
    registry.register(list_files, schema=_list_files_schema())
    registry.register(grep, schema=_grep_schema())
    return registry


class _ReadablePaths:
    def __init__(self, roots: list[RootDir]) -> None:
        if not roots:
            raise ValueError("at least one readable root is required")
        self._roots = roots

    def resolved_roots(self) -> list[Path]:
        return [_root_path(root) for root in self._roots]

    def resolve(self, value: Any) -> tuple[Optional[Path], str]:
        if not isinstance(value, str) or not 1 <= len(value) <= 4096:
            return None, "invalid path"
        candidate = Path(value).expanduser()
        if not candidate.is_absolute():
            candidate = self.resolved_roots()[0] / candidate
        try:
            resolved = candidate.resolve()
        except OSError:
            return None, "path is unavailable"
        for root in self.resolved_roots():
            try:
                resolved.relative_to(root)
                return resolved, ""
            except ValueError:
                continue
        return None, "path is outside readable roots"

    def display(self, path: Path) -> str:
        primary = self.resolved_roots()[0]
        try:
            return str(path.relative_to(primary))
        except ValueError:
            return str(path)


def _root_path(root: Any) -> Path:
    if isinstance(root, dict):
        value = root.get("path", "")
    else:
        value = getattr(root, "path", root)
    return Path(value).expanduser().resolve()


def _walk(base: Path) -> Iterable[Path]:
    for directory, dirs, files in os.walk(base, followlinks=False):
        current = Path(directory)
        dirs[:] = sorted(
            name
            for name in dirs
            if name not in _IGNORE_DIRS
            and not (current / name).is_symlink()
        )
        for name in dirs:
            yield current / name
        for name in sorted(files):
            yield current / name


def _walk_files(base: Path) -> Iterable[Path]:
    for candidate in _walk(base):
        if candidate.is_file():
            yield candidate


def _bounded_int(value: Any, *, default: int, maximum: int) -> int:
    if not isinstance(value, int) or isinstance(value, bool) or value <= 0:
        return default
    return min(value, maximum)


def _read_file_schema() -> dict[str, Any]:
    return _schema(
        "read_file",
        "Read numbered lines from a text file inside the session roots.",
        {
            "path": {"type": "string"},
            "start_line": {"type": "integer"},
            "max_lines": {"type": "integer"},
        },
        ["path"],
    )


def _list_files_schema() -> dict[str, Any]:
    return _schema(
        "list_files",
        "List bounded files and directories inside the session roots.",
        {
            "path": {"type": "string"},
            "max_results": {"type": "integer"},
        },
        [],
    )


def _grep_schema() -> dict[str, Any]:
    return _schema(
        "grep",
        "Search files for a literal text pattern inside the session roots.",
        {
            "pattern": {"type": "string"},
            "path": {"type": "string"},
            "glob": {"type": "string"},
            "max_results": {"type": "integer"},
        },
        ["pattern"],
    )


def _schema(
    name: str,
    description: str,
    properties: dict[str, Any],
    required: list[str],
) -> dict[str, Any]:
    return {
        "type": "function",
        "function": {
            "name": name,
            "description": description,
            "parameters": {
                "type": "object",
                "properties": properties,
                "required": required,
                "additionalProperties": False,
            },
        },
    }
