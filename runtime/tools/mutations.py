"""Atomic root-scoped file mutations and sandboxed command execution."""

from __future__ import annotations

import os
import secrets
import stat
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Optional, Protocol

from runtime.sandbox import (
    InvalidCommandError,
    SandboxResult,
    SandboxUnavailableError,
)
from runtime.sessions import RootDir
from runtime.path_scope import owns_path

from .registry import ToolRegistry

_MAX_WRITE_BYTES = 5 * 1024 * 1024
_MAX_REPLACEMENTS = 10_000
_MAX_COMMAND_SECONDS = 600.0
_EXPECTED_ABSENT = object()


class ShellExecutor(Protocol):
    def run(
        self,
        command: str,
        *,
        timeout_seconds: Optional[float] = None,
    ) -> SandboxResult: ...


class MutationRecorder(Protocol):
    def record_file_preimage(
        self,
        path: Path,
        *,
        content: bytes | None,
        mode: int,
    ) -> None: ...

    def record_shell_fallback(self) -> None: ...


@dataclass(frozen=True)
class _Target:
    root: RootDir
    parent_parts: tuple[str, ...]
    parent: Path
    name: str
    display: str


@dataclass(frozen=True)
class _FileVersion:
    device: int
    inode: int
    size: int
    modified_ns: int
    changed_ns: int


def register_mutation_tools(
    registry: ToolRegistry,
    *,
    roots: list[RootDir],
    shell: ShellExecutor,
    mutation_recorder: MutationRecorder | None = None,
    write_scope: tuple[str, ...] = (),
) -> ToolRegistry:
    """Attach the built-in consequential tools to an existing registry."""
    paths = _WritablePaths(roots, write_scope=write_scope)

    def write_file(path: str, content: str) -> dict[str, Any]:
        if not isinstance(content, str):
            return {"ok": False, "error": "content must be text"}
        try:
            encoded = content.encode("utf-8")
        except UnicodeEncodeError:
            return {"ok": False, "error": "content must be valid UTF-8 text"}
        if len(encoded) > _MAX_WRITE_BYTES:
            return {"ok": False, "error": "content exceeds write limit"}
        target, error = paths.target(path)
        if target is None:
            return {"ok": False, "error": error}
        raw, existing_mode, version, error = _read_regular_file(
            target,
            allow_missing=True,
        )
        if error:
            return {"ok": False, "error": error}
        created = raw is None
        mode = existing_mode if not created else 0o600
        if not _record_file_preimage(
            mutation_recorder,
            target.parent / target.name,
            content=raw,
            mode=existing_mode,
        ):
            return {
                "ok": False,
                "error": "automatic checkpoint unavailable",
            }
        error = _atomic_write(
            target,
            encoded,
            mode=mode,
            expected=_EXPECTED_ABSENT if created else version,
        )
        if error:
            return {"ok": False, "error": error}
        return {
            "ok": True,
            "path": target.display,
            "bytes_written": len(encoded),
            "created": created,
        }

    def replace_in_file(
        path: str,
        old: str,
        new: str,
        expected_replacements: int = 1,
    ) -> dict[str, Any]:
        if not isinstance(old, str) or not old:
            return {"ok": False, "error": "old text must not be empty"}
        if not isinstance(new, str):
            return {"ok": False, "error": "new text must be text"}
        try:
            old_bytes = old.encode("utf-8")
            new_bytes = new.encode("utf-8")
        except UnicodeEncodeError:
            return {"ok": False, "error": "replacement must be valid UTF-8 text"}
        if len(old_bytes) > _MAX_WRITE_BYTES or len(new_bytes) > _MAX_WRITE_BYTES:
            return {"ok": False, "error": "replacement exceeds write limit"}
        if (
            not isinstance(expected_replacements, int)
            or isinstance(expected_replacements, bool)
            or not 1 <= expected_replacements <= _MAX_REPLACEMENTS
        ):
            return {"ok": False, "error": "invalid expected replacement count"}
        target, error = paths.target(path)
        if target is None:
            return {"ok": False, "error": error}
        raw, mode, version, error = _read_regular_file(target)
        if error:
            return {"ok": False, "error": error}
        assert raw is not None
        assert version is not None
        try:
            content = raw.decode("utf-8")
        except UnicodeDecodeError:
            return {"ok": False, "error": "file is not UTF-8 text"}
        count = content.count(old)
        if count != expected_replacements:
            return {
                "ok": False,
                "error": (
                    f"expected {expected_replacements} occurrence(s), "
                    f"found {count}"
                ),
            }
        result_size = (
            len(raw)
            - count * len(old_bytes)
            + count * len(new_bytes)
        )
        if result_size > _MAX_WRITE_BYTES:
            return {"ok": False, "error": "result exceeds write limit"}
        encoded = content.replace(old, new).encode("utf-8")
        if not _record_file_preimage(
            mutation_recorder,
            target.parent / target.name,
            content=raw,
            mode=mode,
        ):
            return {
                "ok": False,
                "error": "automatic checkpoint unavailable",
            }
        error = _atomic_write(
            target,
            encoded,
            mode=mode,
            expected=version,
        )
        if error:
            return {"ok": False, "error": error}
        return {
            "ok": True,
            "path": target.display,
            "replacements": count,
            "bytes_written": len(encoded),
        }

    def run_shell(
        command: str,
        timeout_seconds: Optional[float] = None,
    ) -> dict[str, object]:
        if timeout_seconds is not None and (
            not isinstance(timeout_seconds, (int, float))
            or isinstance(timeout_seconds, bool)
            or not 0 < timeout_seconds <= _MAX_COMMAND_SECONDS
        ):
            return {"error": "invalid timeout"}
        if (
            mutation_recorder is not None
            and not bool(
                getattr(shell, "transactional_mutations", False)
            )
        ):
            try:
                mutation_recorder.record_shell_fallback()
            except Exception:
                return {
                    "error": "automatic checkpoint unavailable"
                }
        try:
            result = shell.run(
                command,
                timeout_seconds=(
                    float(timeout_seconds)
                    if timeout_seconds is not None
                    else None
                ),
            )
        except InvalidCommandError:
            return {"error": "invalid command"}
        except SandboxUnavailableError:
            return {"error": "sandbox unavailable"}
        except (OSError, RuntimeError, ValueError):
            return {"error": "command execution failed"}
        return result.as_dict()

    registry.register(write_file, schema=_write_file_schema())
    registry.register(replace_in_file, schema=_replace_in_file_schema())
    registry.register(run_shell, schema=_run_shell_schema())
    return registry


def _record_file_preimage(
    recorder: MutationRecorder | None,
    path: Path,
    *,
    content: bytes | None,
    mode: int,
) -> bool:
    if recorder is None:
        return True
    try:
        recorder.record_file_preimage(
            path,
            content=content,
            mode=mode,
        )
    except Exception:
        return False
    return True


class _WritablePaths:
    def __init__(
        self,
        roots: list[RootDir],
        *,
        write_scope: tuple[str, ...] = (),
    ) -> None:
        if not roots:
            raise ValueError("at least one workspace root is required")
        self._roots = roots
        self._write_scope = tuple(write_scope)

    def target(self, value: Any) -> tuple[Optional[_Target], str]:
        if not isinstance(value, str) or not 1 <= len(value) <= 4096:
            return None, "invalid path"
        try:
            primary = _root_path(self._roots[0])
        except (OSError, ValueError):
            return None, "workspace root is unavailable"
        candidate = Path(value).expanduser()
        if ".." in candidate.parts:
            return None, "path is outside writable roots"
        if not candidate.is_absolute():
            selected_root = self._roots[0]
            relative = candidate
        else:
            candidate = Path(os.path.abspath(candidate))
            matches: list[tuple[int, RootDir, Path]] = []
            for root in self._roots:
                if not _root_writable(root):
                    continue
                try:
                    root_path = _root_path(root)
                    relative = candidate.relative_to(root_path)
                except (OSError, ValueError):
                    continue
                matches.append((len(root_path.parts), root, relative))
            if not matches:
                return None, "path is outside writable roots"
            _, selected_root, relative = max(
                matches,
                key=lambda item: item[0],
            )
        if not _root_writable(selected_root):
            return None, "path is outside writable roots"
        parts = tuple(
            component
            for component in relative.parts
            if component not in {"", "."}
        )
        if not parts:
            return None, "invalid path"
        if any(component.casefold() == ".git" for component in parts):
            return None, "Git metadata is not writable"
        try:
            selected_path = _root_path(selected_root)
        except (OSError, ValueError):
            return None, "workspace root is unavailable"
        parent_parts = parts[:-1]
        parent = selected_path.joinpath(*parent_parts)
        ancestor = selected_path
        for component in parent_parts:
            ancestor = ancestor / component
            try:
                metadata = os.stat(ancestor, follow_symlinks=False)
            except FileNotFoundError:
                return None, "parent directory does not exist"
            except OSError:
                return None, "path is unavailable"
            if stat.S_ISLNK(metadata.st_mode):
                return None, "path is outside writable roots"
            if not stat.S_ISDIR(metadata.st_mode):
                return None, "parent is not a directory"
        target_path = parent / parts[-1]
        if self._write_scope and not owns_path(
            primary,
            self._write_scope,
            target_path,
        ):
            return None, "path is outside worker ownership"
        try:
            target_metadata = os.stat(
                target_path,
                follow_symlinks=False,
            )
        except FileNotFoundError:
            target_metadata = None
        except OSError:
            return None, "path is unavailable"
        if target_metadata is not None and stat.S_ISLNK(
            target_metadata.st_mode
        ):
            return None, "symbolic links are not writable"
        try:
            display = str(target_path.relative_to(primary))
        except ValueError:
            display = str(target_path)
        return (
            _Target(
                root=selected_root,
                parent_parts=parent_parts,
                parent=parent,
                name=parts[-1],
                display=display,
            ),
            "",
        )


def _read_regular_file(
    target: _Target,
    *,
    allow_missing: bool = False,
) -> tuple[Optional[bytes], int, Optional[_FileVersion], str]:
    try:
        directory_fd = _open_target_directory(target)
    except OSError:
        return None, 0, None, "target is unavailable"
    try:
        try:
            file_fd = os.open(
                target.name,
                os.O_RDONLY | os.O_NOFOLLOW | os.O_CLOEXEC,
                dir_fd=directory_fd,
            )
        except FileNotFoundError:
            return (
                (None, 0, None, "")
                if allow_missing
                else (None, 0, None, "target does not exist")
            )
        except OSError:
            return None, 0, None, "target is unavailable"
        try:
            metadata = os.fstat(file_fd)
            if not stat.S_ISREG(metadata.st_mode):
                return None, 0, None, "target is not a regular file"
            if metadata.st_size > _MAX_WRITE_BYTES:
                return None, 0, None, "file exceeds write limit"
            chunks = bytearray()
            while chunk := os.read(file_fd, 64 * 1024):
                chunks.extend(chunk)
                if len(chunks) > _MAX_WRITE_BYTES:
                    return None, 0, None, "file exceeds write limit"
            version = _FileVersion(
                device=metadata.st_dev,
                inode=metadata.st_ino,
                size=metadata.st_size,
                modified_ns=metadata.st_mtime_ns,
                changed_ns=metadata.st_ctime_ns,
            )
            return bytes(chunks), metadata.st_mode & 0o777, version, ""
        finally:
            os.close(file_fd)
    finally:
        os.close(directory_fd)


def _atomic_write(
    target: _Target,
    content: bytes,
    *,
    mode: int,
    expected: _FileVersion | object | None = None,
) -> str:
    try:
        directory_fd = _open_target_directory(target)
    except OSError:
        return "file write failed"
    temporary = f".codinal-{secrets.token_hex(16)}.tmp"
    file_fd: Optional[int] = None
    try:
        file_fd = os.open(
            temporary,
            os.O_WRONLY
            | os.O_CREAT
            | os.O_EXCL
            | os.O_NOFOLLOW
            | os.O_CLOEXEC,
            0o600,
            dir_fd=directory_fd,
        )
        view = memoryview(content)
        while view:
            written = os.write(file_fd, view)
            if written <= 0:
                raise OSError("short write")
            view = view[written:]
        os.fchmod(file_fd, mode)
        os.fsync(file_fd)
        os.close(file_fd)
        file_fd = None
        if expected is _EXPECTED_ABSENT:
            try:
                os.link(
                    temporary,
                    target.name,
                    src_dir_fd=directory_fd,
                    dst_dir_fd=directory_fd,
                    follow_symlinks=False,
                )
            except FileExistsError:
                return "file changed during write"
            except OSError:
                return "file write failed"
            try:
                os.unlink(temporary, dir_fd=directory_fd)
            except OSError:
                # The destination is already published. Cleanup is retried
                # below and must not make a committed write look failed.
                pass
            try:
                os.fsync(directory_fd)
            except OSError:
                # Publication already committed.
                pass
            return ""
        if expected is not None:
            assert isinstance(expected, _FileVersion)
            try:
                current = os.stat(
                    target.name,
                    dir_fd=directory_fd,
                    follow_symlinks=False,
                )
            except OSError:
                return "file changed during replacement"
            current_version = _FileVersion(
                device=current.st_dev,
                inode=current.st_ino,
                size=current.st_size,
                modified_ns=current.st_mtime_ns,
                changed_ns=current.st_ctime_ns,
            )
            if current_version != expected or not stat.S_ISREG(current.st_mode):
                return "file changed during replacement"
        os.replace(
            temporary,
            target.name,
            src_dir_fd=directory_fd,
            dst_dir_fd=directory_fd,
        )
        try:
            os.fsync(directory_fd)
        except OSError:
            # The rename already committed. Reporting failure here would falsely
            # tell the model that no mutation occurred.
            pass
        return ""
    except OSError:
        return "file write failed"
    finally:
        if file_fd is not None:
            os.close(file_fd)
        try:
            os.unlink(temporary, dir_fd=directory_fd)
        except FileNotFoundError:
            pass
        except OSError:
            pass
        os.close(directory_fd)


def _open_target_directory(target: _Target) -> int:
    root_path = _root_path(target.root)
    expected = _root_identity(target.root)
    flags = (
        os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW | os.O_CLOEXEC
    )
    descriptors: list[int] = []
    try:
        current_fd = os.open(root_path, flags)
        descriptors.append(current_fd)
        metadata = os.fstat(current_fd)
        if (int(metadata.st_dev), int(metadata.st_ino)) != expected:
            raise OSError("root identity changed")
        for component in target.parent_parts:
            current_fd = os.open(component, flags, dir_fd=current_fd)
            descriptors.append(current_fd)
        return os.dup(current_fd)
    finally:
        for descriptor in reversed(descriptors):
            try:
                os.close(descriptor)
            except OSError:
                pass


def _root_path(root: Any) -> Path:
    value = root.get("path", "") if isinstance(root, dict) else getattr(
        root, "path", root
    )
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


def _root_identity(root: Any) -> tuple[int, int]:
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
    return int(device), int(inode)


def _root_writable(root: Any) -> bool:
    if isinstance(root, dict):
        return bool(root.get("writable", False))
    return bool(getattr(root, "writable", False))


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


def _write_file_schema() -> dict[str, Any]:
    return _schema(
        "write_file",
        "Atomically write UTF-8 text inside a writable session root.",
        {
            "path": {"type": "string", "maxLength": 4096},
            "content": {"type": "string"},
        },
        ["path", "content"],
    )


def _replace_in_file_schema() -> dict[str, Any]:
    return _schema(
        "replace_in_file",
        "Atomically replace an exact number of text occurrences in a file.",
        {
            "path": {"type": "string", "maxLength": 4096},
            "old": {"type": "string"},
            "new": {"type": "string"},
            "expected_replacements": {
                "type": "integer",
                "minimum": 1,
                "maximum": _MAX_REPLACEMENTS,
            },
        },
        ["path", "old", "new"],
    )


def _run_shell_schema() -> dict[str, Any]:
    return _schema(
        "run_shell",
        "Run one direct argv in the workspace sandbox without shell syntax.",
        {
            "command": {"type": "string", "maxLength": 32768},
            "timeout_seconds": {
                "type": "number",
                "exclusiveMinimum": 0,
                "maximum": _MAX_COMMAND_SECONDS,
            },
        },
        ["command"],
    )
