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

from .registry import ToolRegistry

_MAX_WRITE_BYTES = 5 * 1024 * 1024
_MAX_REPLACEMENTS = 10_000
_MAX_COMMAND_SECONDS = 600.0


class ShellExecutor(Protocol):
    def run(
        self,
        command: str,
        *,
        timeout_seconds: Optional[float] = None,
    ) -> SandboxResult: ...


class MutationRecorder(Protocol):
    def record_file_preimage(self, path: Path) -> None: ...

    def record_shell_fallback(self) -> None: ...


@dataclass(frozen=True)
class _Target:
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
) -> ToolRegistry:
    """Attach the built-in consequential tools to an existing registry."""
    paths = _WritablePaths(roots)

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
        existing, error = _existing_metadata(target)
        if error:
            return {"ok": False, "error": error}
        mode = existing.st_mode & 0o777 if existing else 0o600
        if not _record_file_preimage(
            mutation_recorder,
            target.parent / target.name,
        ):
            return {
                "ok": False,
                "error": "automatic checkpoint unavailable",
            }
        error = _atomic_write(target, encoded, mode=mode)
        if error:
            return {"ok": False, "error": error}
        return {
            "ok": True,
            "path": target.display,
            "bytes_written": len(encoded),
            "created": existing is None,
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
        if mutation_recorder is not None:
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
) -> bool:
    if recorder is None:
        return True
    try:
        recorder.record_file_preimage(path)
    except Exception:
        return False
    return True


class _WritablePaths:
    def __init__(self, roots: list[RootDir]) -> None:
        if not roots:
            raise ValueError("at least one workspace root is required")
        self._roots = roots

    def target(self, value: Any) -> tuple[Optional[_Target], str]:
        if not isinstance(value, str) or not 1 <= len(value) <= 4096:
            return None, "invalid path"
        primary = _root_path(self._roots[0])
        candidate = Path(value).expanduser()
        if not candidate.is_absolute():
            candidate = primary / candidate
        try:
            if candidate.is_symlink():
                return None, "symbolic links are not writable"
            parent = candidate.parent.resolve(strict=True)
        except FileNotFoundError:
            return None, "parent directory does not exist"
        except (OSError, RuntimeError):
            return None, "path is unavailable"
        if not parent.is_dir():
            return None, "parent is not a directory"
        if not self._inside_writable_root(parent):
            return None, "path is outside writable roots"
        target_path = parent / candidate.name
        try:
            display = str(target_path.relative_to(primary))
        except ValueError:
            display = str(target_path)
        return _Target(parent=parent, name=candidate.name, display=display), ""

    def _inside_writable_root(self, candidate: Path) -> bool:
        for root in self._roots:
            if not _root_writable(root):
                continue
            try:
                candidate.relative_to(_root_path(root))
                return True
            except ValueError:
                continue
        return False


def _existing_metadata(target: _Target) -> tuple[Optional[os.stat_result], str]:
    try:
        directory_fd = _open_directory(target.parent)
    except OSError:
        return None, "target is unavailable"
    try:
        try:
            metadata = os.stat(
                target.name,
                dir_fd=directory_fd,
                follow_symlinks=False,
            )
        except FileNotFoundError:
            return None, ""
        except OSError:
            return None, "target is unavailable"
    finally:
        os.close(directory_fd)
    if stat.S_ISLNK(metadata.st_mode):
        return None, "symbolic links are not writable"
    if not stat.S_ISREG(metadata.st_mode):
        return None, "target is not a regular file"
    return metadata, ""


def _read_regular_file(
    target: _Target,
) -> tuple[Optional[bytes], int, Optional[_FileVersion], str]:
    try:
        directory_fd = _open_directory(target.parent)
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
            return None, 0, None, "target does not exist"
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
    expected: Optional[_FileVersion] = None,
) -> str:
    try:
        directory_fd = _open_directory(target.parent)
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
        if expected is not None:
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


def _open_directory(path: Path) -> int:
    return os.open(
        path,
        os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW | os.O_CLOEXEC,
    )


def _root_path(root: Any) -> Path:
    value = root.get("path", "") if isinstance(root, dict) else getattr(
        root, "path", root
    )
    return Path(value).expanduser().resolve()


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
