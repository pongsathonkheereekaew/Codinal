"""Bounded, root-scoped read tools for the coding runtime."""

from __future__ import annotations

import fnmatch
import os
import stat
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterator, Optional

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
_IGNORE_DIRS_CASEFOLD = {name.casefold() for name in _IGNORE_DIRS}


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
        opened, error = paths.open(path, directory=False)
        if opened is None:
            return {"error": error}
        try:
            metadata = os.fstat(opened.fd)
        except OSError:
            os.close(opened.fd)
            return {"error": "file is unavailable"}
        if not stat.S_ISREG(metadata.st_mode):
            os.close(opened.fd)
            return {"error": "not a readable file"}
        if metadata.st_size > _MAX_FILE_BYTES:
            os.close(opened.fd)
            return {"error": "file exceeds read limit"}
        start = _bounded_int(start_line, default=1, maximum=10_000_000)
        limit = _bounded_int(max_lines, default=_MAX_LINES, maximum=_MAX_LINES)
        selected: list[str] = []
        total = 0
        try:
            with os.fdopen(
                os.dup(opened.fd),
                "r",
                encoding="utf-8",
                errors="replace",
            ) as stream:
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
        finally:
            os.close(opened.fd)
        end = start + len(selected) - 1 if selected else start - 1
        result = {
            "path": paths.display(opened.path),
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
        opened, error = paths.open(path, directory=True)
        if opened is None:
            return {"error": error}
        limit = _bounded_int(
            max_results,
            default=200,
            maximum=_MAX_LIST_RESULTS,
        )
        entries: list[dict[str, str]] = []
        iterator = _walk_directory(opened.fd, opened.path)
        try:
            for candidate, kind in iterator:
                entries.append(
                    {
                        "path": paths.display(candidate),
                        "kind": kind,
                    }
                )
                if len(entries) > limit:
                    break
        except OSError:
            return {"error": "directory is unavailable"}
        finally:
            iterator.close()
            os.close(opened.fd)
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
        opened, error = paths.open(path, directory=True)
        if opened is None:
            return {"error": error}
        limit = _bounded_int(
            max_results,
            default=100,
            maximum=_MAX_GREP_RESULTS,
        )
        matches: list[dict[str, Any]] = []
        files_scanned = 0
        deadline = time.monotonic() + _MAX_GREP_SECONDS
        iterator = _walk_directory(opened.fd, opened.path)
        try:
            for candidate, kind in iterator:
                if (
                    time.monotonic() >= deadline
                    or files_scanned >= _MAX_GREP_FILES
                ):
                    break
                if kind != "file":
                    continue
                display = paths.display(candidate)
                if glob and not fnmatch.fnmatch(display, glob):
                    continue
                file_opened, _ = paths.open(str(candidate), directory=False)
                if file_opened is None:
                    continue
                try:
                    metadata = os.fstat(file_opened.fd)
                    if (
                        not stat.S_ISREG(metadata.st_mode)
                        or metadata.st_size > _MAX_FILE_BYTES
                    ):
                        continue
                    files_scanned += 1
                    with os.fdopen(
                        os.dup(file_opened.fd),
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
                finally:
                    os.close(file_opened.fd)
                if len(matches) > limit:
                    break
        finally:
            iterator.close()
            os.close(opened.fd)
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


@dataclass(frozen=True)
class _OpenedPath:
    fd: int
    path: Path


@dataclass(frozen=True)
class _RootBinding:
    path: Path
    device: int
    inode: int


class _ReadablePaths:
    def __init__(self, roots: list[RootDir]) -> None:
        if not roots:
            raise ValueError("at least one readable root is required")
        self._roots = roots

    def bindings(self) -> list[_RootBinding]:
        bindings = []
        for root in self._roots:
            try:
                path, device, inode = _root_binding(root)
            except (OSError, ValueError):
                continue
            bindings.append(_RootBinding(path, device, inode))
        return bindings

    def open(
        self,
        value: Any,
        *,
        directory: bool,
    ) -> tuple[Optional[_OpenedPath], str]:
        if not isinstance(value, str) or not 1 <= len(value) <= 4096:
            return None, "invalid path"
        bindings = self.bindings()
        if not bindings:
            return None, "readable roots are unavailable"
        candidate = Path(value).expanduser()
        if ".." in candidate.parts:
            return None, "path is outside readable roots"
        if not candidate.is_absolute():
            try:
                path, device, inode = _root_binding(self._roots[0])
            except (OSError, ValueError):
                return None, "readable roots are unavailable"
            binding = _RootBinding(path, device, inode)
            relative = candidate
        else:
            candidate = Path(os.path.abspath(candidate))
            matches = []
            for possible in bindings:
                try:
                    relative = candidate.relative_to(possible.path)
                except ValueError:
                    continue
                matches.append((len(possible.path.parts), possible, relative))
            if not matches:
                return None, "path is outside readable roots"
            _, binding, relative = max(matches, key=lambda item: item[0])
        parts = tuple(
            component
            for component in relative.parts
            if component not in {"", "."}
        )
        descriptors: list[int] = []
        try:
            flags = (
                os.O_RDONLY
                | os.O_DIRECTORY
                | os.O_NOFOLLOW
                | os.O_CLOEXEC
            )
            current_fd = os.open(binding.path, flags)
            descriptors.append(current_fd)
            metadata = os.fstat(current_fd)
            if (int(metadata.st_dev), int(metadata.st_ino)) != (
                binding.device,
                binding.inode,
            ):
                raise OSError("root identity changed")
            for index, component in enumerate(parts):
                final = index == len(parts) - 1
                component_flags = os.O_RDONLY | os.O_NOFOLLOW | os.O_CLOEXEC
                if not final or directory:
                    component_flags |= os.O_DIRECTORY
                current_fd = os.open(
                    component,
                    component_flags,
                    dir_fd=current_fd,
                )
                descriptors.append(current_fd)
            result_fd = os.dup(current_fd)
        except OSError:
            if _contains_symlink(binding.path, parts):
                return None, "path is outside readable roots"
            return None, "path is unavailable"
        finally:
            for descriptor in reversed(descriptors):
                try:
                    os.close(descriptor)
                except OSError:
                    pass
        return _OpenedPath(result_fd, binding.path.joinpath(*parts)), ""

    def display(self, path: Path) -> str:
        try:
            primary, _, _ = _root_binding(self._roots[0])
        except (OSError, ValueError):
            return str(path)
        try:
            return str(path.relative_to(primary))
        except ValueError:
            return str(path)


def _root_binding(root: Any) -> tuple[Path, int, int]:
    path = _root_path(root)
    device = (
        root.get("_device")
        if isinstance(root, dict)
        else getattr(root, "device", None)
    )
    inode = (
        root.get("_inode")
        if isinstance(root, dict)
        else getattr(root, "inode", None)
    )
    if device is None or inode is None:
        raise ValueError("root identity is unavailable")
    return path, int(device), int(inode)


def _root_path(root: Any) -> Path:
    if isinstance(root, dict):
        value = root.get("path", "")
    else:
        value = getattr(root, "path", root)
    path = Path(value).expanduser()
    resolved = path.resolve(strict=True)
    device = (
        root.get("_device")
        if isinstance(root, dict)
        else getattr(root, "device", None)
    )
    inode = (
        root.get("_inode")
        if isinstance(root, dict)
        else getattr(root, "inode", None)
    )
    metadata = os.stat(path, follow_symlinks=False)
    if (
        device is None
        or inode is None
        or path.is_symlink()
        or resolved != path.absolute()
        or (int(metadata.st_dev), int(metadata.st_ino))
        != (int(device), int(inode))
    ):
        raise ValueError("root identity changed")
    return resolved


def _walk_directory(
    directory_fd: int,
    base: Path,
) -> Iterator[tuple[Path, str]]:
    with os.scandir(directory_fd) as iterator:
        candidates = sorted(iterator, key=lambda entry: entry.name.casefold())
    directories = []
    files = []
    for candidate in candidates:
        if candidate.name.casefold() in _IGNORE_DIRS_CASEFOLD:
            continue
        try:
            if candidate.is_symlink():
                continue
            if candidate.is_dir(follow_symlinks=False):
                directories.append(candidate.name)
            elif candidate.is_file(follow_symlinks=False):
                files.append(candidate.name)
        except OSError:
            continue
    for name in directories:
        child = base / name
        yield child, "directory"
    for name in files:
        yield base / name, "file"
    for name in directories:
        try:
            child_fd = os.open(
                name,
                os.O_RDONLY
                | os.O_DIRECTORY
                | os.O_NOFOLLOW
                | os.O_CLOEXEC,
                dir_fd=directory_fd,
            )
        except OSError:
            continue
        try:
            yield from _walk_directory(child_fd, base / name)
        finally:
            os.close(child_fd)


def _contains_symlink(root: Path, parts: tuple[str, ...]) -> bool:
    candidate = root
    for component in parts:
        candidate = candidate / component
        try:
            if candidate.is_symlink():
                return True
        except OSError:
            return False
    return False


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
