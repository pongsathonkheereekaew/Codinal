"""Fast, bounded, root-scoped repository text and symbol search."""

from __future__ import annotations

import fnmatch
import os
import queue
import re
import stat
import subprocess
import threading
import time
from bisect import insort
from pathlib import Path
from typing import Any, Callable, Iterator

_MAX_QUERY_BYTES = 256
_MAX_RESULTS = 100
_MAX_ROOTS = 16
_MAX_FILES = 5_000
_MAX_FILE_BYTES = 1024 * 1024
_MAX_TOTAL_BYTES = 32 * 1024 * 1024
_MAX_SECONDS = 2.0
_MAX_GIT_OUTPUT_BYTES = 4 * 1024 * 1024
_MAX_DIRECTORY_ENTRIES = 20_000
_MAX_IGNORE_BYTES = 64 * 1024
_MAX_PREVIEW_CHARS = 500
_IGNORE_NAMES = {
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
_IGNORE_CASEFOLD = {name.casefold() for name in _IGNORE_NAMES}
_SYMBOL_PATTERNS = (
    re.compile(
        r"^\s*(?:(?:export|default|public|private|protected|static|"
        r"abstract|async|suspend|inline|open|operator|"
        r"pub(?:\([^)]*\))?)\s+)*"
        r"(?P<kind>class|interface|enum|struct|trait|type|def|function|"
        r"fn|func|fun)\s+(?P<name>[A-Za-z_$][\w$]*)"
    ),
    re.compile(
        r"^\s*(?:(?:export|public|private|protected|static)\s+)*"
        r"(?P<kind>const|let|var|val)\s+"
        r"(?P<name>[A-Za-z_$][\w$]*)"
    ),
)
_SYMBOL_KINDS = {
    "def": "function",
    "function": "function",
    "fn": "function",
    "func": "function",
    "fun": "function",
    "const": "variable",
    "let": "variable",
    "var": "variable",
    "val": "property",
}


def search_repository_roots(
    roots: list[dict[str, Any]],
    *,
    query: str,
    mode: str = "text",
    limit: int = 50,
    cancelled: Callable[[], bool] | None = None,
    deadline: float | None = None,
) -> dict[str, Any]:
    if not _valid_request(roots, query=query, mode=mode, limit=limit):
        return {"ok": False, "error": "invalid project search"}
    started = time.monotonic()
    deadline = min(
        deadline if deadline is not None else started + _MAX_SECONDS,
        started + _MAX_SECONDS,
    )
    if deadline <= started:
        return {
            "ok": True,
            "query": query,
            "mode": mode,
            "count": 0,
            "matches": [],
            "files_scanned": 0,
            "duration_ms": 0,
            "truncated": True,
            "cancelled": bool(cancelled is not None and cancelled()),
        }
    best: list[tuple[tuple[Any, ...], dict[str, Any]]] = []
    files_scanned = 0
    bytes_scanned = 0
    truncated = False
    case_sensitive = any(character.isupper() for character in query)
    needle = query if case_sensitive else query.casefold()

    active_roots = [
        root for root in roots if root.get("available") is not False
    ]
    for root_index, root_view in enumerate(active_roots):
        if (
            time.monotonic() >= deadline
            or cancelled is not None
            and cancelled()
        ):
            truncated = True
            break
        remaining_roots = len(active_roots) - root_index
        remaining_seconds = max(0.0, deadline - time.monotonic())
        root_deadline = min(
            deadline,
            time.monotonic()
            + max(0.01, remaining_seconds / max(1, remaining_roots)),
        )
        root_file_limit = max(
            1,
            (_MAX_FILES - files_scanned) // max(1, remaining_roots),
        )
        root_byte_limit = max(
            1,
            (_MAX_TOTAL_BYTES - bytes_scanned) // max(1, remaining_roots),
        )
        root = Path(str(root_view["path"])).expanduser()
        try:
            absolute = root.absolute()
            if (
                not absolute.is_absolute()
                or absolute.is_symlink()
                or absolute.resolve(strict=True) != absolute
            ):
                continue
            root_fd = os.open(
                absolute,
                os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW,
            )
            root_metadata = os.fstat(root_fd)
            expected_identity = (
                root_view.get("_device"),
                root_view.get("_inode"),
            )
            if (
                all(isinstance(value, int) for value in expected_identity)
                and expected_identity
                != (int(root_metadata.st_dev), int(root_metadata.st_ino))
            ):
                os.close(root_fd)
                continue
        except (OSError, RuntimeError):
            continue
        try:
            candidates, candidate_truncated = _candidate_files(
                absolute,
                root_fd=root_fd,
                deadline=root_deadline,
                max_files=root_file_limit,
                cancelled=cancelled,
            )
            truncated = truncated or candidate_truncated
            root_files_scanned = 0
            root_bytes_scanned = 0
            for relative in candidates:
                if (
                    time.monotonic() >= root_deadline
                    or files_scanned >= _MAX_FILES
                    or root_files_scanned >= root_file_limit
                    or bytes_scanned >= _MAX_TOTAL_BYTES
                    or root_bytes_scanned >= root_byte_limit
                    or cancelled is not None
                    and cancelled()
                ):
                    truncated = True
                    break
                opened = _open_relative_file(root_fd, relative)
                if opened is None:
                    continue
                try:
                    metadata = os.fstat(opened)
                    if (
                        not stat.S_ISREG(metadata.st_mode)
                        or metadata.st_size > _MAX_FILE_BYTES
                        or bytes_scanned + metadata.st_size
                        > _MAX_TOTAL_BYTES
                        or root_bytes_scanned + metadata.st_size
                        > root_byte_limit
                    ):
                        if metadata.st_size > _MAX_FILE_BYTES:
                            continue
                        truncated = True
                        break
                    payload = _read_file(opened, metadata.st_size)
                finally:
                    os.close(opened)
                if payload is None:
                    continue
                files_scanned += 1
                root_files_scanned += 1
                bytes_scanned += len(payload)
                root_bytes_scanned += len(payload)
                for match in _matches(
                    payload,
                    query=query,
                    needle=needle,
                    case_sensitive=case_sensitive,
                    mode=mode,
                    suffix=Path(relative).suffix.casefold(),
                ):
                    result = {
                        "root": str(absolute),
                        "root_label": (
                            str(root_view.get("label") or absolute.name)
                        ),
                        "path": relative,
                        **match,
                    }
                    rank = _match_rank(
                        query=query,
                        result=result,
                        root_index=root_index,
                    )
                    insort(best, (rank, result))
                    if len(best) > limit:
                        best.pop()
                        truncated = True
        finally:
            os.close(root_fd)

    selected = [result for _rank, result in best]
    return {
        "ok": True,
        "query": query,
        "mode": mode,
        "count": len(selected),
        "matches": selected,
        "files_scanned": files_scanned,
        "duration_ms": max(0, int((time.monotonic() - started) * 1000)),
        "truncated": truncated,
        "cancelled": bool(cancelled is not None and cancelled()),
    }


def _valid_request(
    roots: object,
    *,
    query: object,
    mode: object,
    limit: object,
) -> bool:
    return bool(
        isinstance(roots, list)
        and 1 <= len(roots) <= _MAX_ROOTS
        and all(
            isinstance(root, dict)
            and isinstance(root.get("path"), str)
            and Path(root["path"]).is_absolute()
            for root in roots
        )
        and isinstance(query, str)
        and _bounded_utf8(query, 1, _MAX_QUERY_BYTES)
        and "\x00" not in query
        and mode in {"text", "symbol"}
        and not isinstance(limit, bool)
        and isinstance(limit, int)
        and 1 <= limit <= _MAX_RESULTS
    )


def _candidate_files(
    root: Path,
    *,
    root_fd: int,
    deadline: float,
    max_files: int,
    cancelled: Callable[[], bool] | None,
) -> tuple[list[str], bool]:
    git = _git_files(
        root,
        root_fd=root_fd,
        deadline=deadline,
        max_files=max_files,
        cancelled=cancelled,
    )
    if git is not None:
        return git
    return _walk_files(
        root,
        root_fd=root_fd,
        deadline=deadline,
        max_files=max_files,
        cancelled=cancelled,
    )


def _git_files(
    root: Path,
    *,
    root_fd: int,
    deadline: float,
    max_files: int,
    cancelled: Callable[[], bool] | None,
) -> tuple[list[str], bool] | None:
    if (
        time.monotonic() >= deadline
        or cancelled is not None
        and cancelled()
    ):
        return [], True
    environment = {
        key: os.environ[key]
        for key in (
            "PATH",
            "SYSTEMROOT",
            "WINDIR",
            "TMPDIR",
            "TEMP",
            "TMP",
            "LANG",
            "LC_ALL",
        )
        if key in os.environ
    }
    environment.update(
        {
        "GIT_OPTIONAL_LOCKS": "0",
        "GIT_TERMINAL_PROMPT": "0",
            "GIT_CONFIG_NOSYSTEM": "1",
            "GIT_CONFIG_GLOBAL": os.devnull,
            "GIT_ATTR_NOSYSTEM": "1",
        }
    )
    try:
        process = subprocess.Popen(
            [
                "git",
                "-c",
                "core.fsmonitor=false",
                "-c",
                "core.untrackedCache=false",
                "-c",
                f"core.hooksPath={os.devnull}",
                "-C",
                str(root),
                "ls-files",
                "--cached",
                "--others",
                "--exclude-standard",
                "-z",
            ],
            stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            env=environment,
        )
    except OSError:
        return None
    assert process.stdout is not None
    chunks: queue.Queue[bytes | None] = queue.Queue(maxsize=8)
    stop_reader = threading.Event()

    def read_stdout() -> None:
        try:
            while not stop_reader.is_set():
                chunk = process.stdout.read(64 * 1024)
                if not chunk:
                    break
                while not stop_reader.is_set():
                    try:
                        chunks.put(chunk, timeout=0.05)
                        break
                    except queue.Full:
                        continue
        finally:
            while not stop_reader.is_set():
                try:
                    chunks.put(None, timeout=0.05)
                    break
                except queue.Full:
                    continue

    reader = threading.Thread(target=read_stdout, daemon=True)
    reader.start()
    buffer = b""
    output_bytes = 0
    files: list[str] = []
    truncated = False
    try:
        while True:
            remaining = deadline - time.monotonic()
            if (
                remaining <= 0
                or cancelled is not None
                and cancelled()
            ):
                truncated = True
                break
            try:
                chunk = chunks.get(timeout=min(remaining, 0.05))
            except queue.Empty:
                continue
            if chunk is None:
                break
            output_bytes += len(chunk)
            if output_bytes > _MAX_GIT_OUTPUT_BYTES:
                truncated = True
                break
            buffer += chunk
            while b"\x00" in buffer:
                raw, buffer = buffer.split(b"\x00", 1)
                relative = _decode_relative(raw)
                if relative is not None:
                    files.append(relative)
                if (
                    len(files) > max_files
                ):
                    truncated = True
                    break
            if truncated:
                break
        if truncated and process.poll() is None:
            process.terminate()
        try:
            process.wait(timeout=0.2)
        except subprocess.TimeoutExpired:
            process.kill()
            process.wait()
    finally:
        stop_reader.set()
        process.stdout.close()
        reader.join(timeout=0.2)
    if process.returncode not in {0, -15, -9} and not files:
        return None
    selected = sorted(
        set(files),
        key=lambda value: (value.casefold(), value),
    )[:max_files]
    selected, ignore_truncated = _filter_additional_ignores(
        root_fd,
        selected,
        deadline=deadline,
        cancelled=cancelled,
    )
    return selected, truncated or ignore_truncated


def _decode_relative(raw: bytes) -> str | None:
    try:
        relative = raw.decode("utf-8")
    except UnicodeDecodeError:
        return None
    parts = Path(relative).parts
    if (
        not relative
        or not _bounded_utf8(relative, 1, 4_096)
        or Path(relative).is_absolute()
        or ".." in parts
        or any(part.casefold() in _IGNORE_CASEFOLD for part in parts)
    ):
        return None
    return relative


def _walk_files(
    root: Path,
    *,
    root_fd: int,
    deadline: float,
    max_files: int,
    cancelled: Callable[[], bool] | None,
) -> tuple[list[str], bool]:
    files: list[str] = []
    truncated = False
    entries_scanned = 0
    stack: list[
        tuple[Path, list[tuple[str, str, bool, bool, bool]]]
    ] = [
        (root, [])
    ]
    while stack:
        if (
            time.monotonic() >= deadline
            or len(files) > max_files
            or entries_scanned >= _MAX_DIRECTORY_ENTRIES
            or cancelled is not None
            and cancelled()
        ):
            truncated = True
            break
        current, inherited_rules = stack.pop()
        base = (
            ""
            if current == root
            else current.relative_to(root).as_posix()
        )
        local_rules, ignore_complete = _ignore_rules(
            root_fd,
            base=base,
            deadline=deadline,
            cancelled=cancelled,
        )
        if not ignore_complete:
            truncated = True
            continue
        rules = [*inherited_rules, *local_rules]
        selected = []
        try:
            with os.scandir(current) as entries:
                for entry in entries:
                    entries_scanned += 1
                    if (
                        entries_scanned > _MAX_DIRECTORY_ENTRIES
                        or time.monotonic() >= deadline
                        or cancelled is not None
                        and cancelled()
                    ):
                        truncated = True
                        break
                    selected.append(entry)
        except OSError:
            continue
        selected.sort(key=lambda entry: (entry.name.casefold(), entry.name))
        directories = []
        for entry in selected:
            relative = (
                f"{base}/{entry.name}" if base else entry.name
            ).replace(os.sep, "/")
            if not _bounded_utf8(relative, 1, 4_096):
                continue
            if _ignored(relative, entry.is_dir(follow_symlinks=False), rules):
                continue
            if entry.is_symlink():
                continue
            if entry.is_dir(follow_symlinks=False):
                directories.append(Path(entry.path))
            elif entry.is_file(follow_symlinks=False):
                files.append(relative)
                if len(files) > max_files:
                    truncated = True
                    break
        stack.extend(
            (directory, rules) for directory in reversed(directories)
        )
    return files[:max_files], truncated


def _ignore_rules(
    root_fd: int,
    *,
    base: str,
    deadline: float,
    cancelled: Callable[[], bool] | None,
    names: tuple[str, ...] = (".gitignore", ".ignore"),
) -> tuple[list[tuple[str, str, bool, bool, bool]], bool]:
    rules = []
    for name in names:
        if (
            time.monotonic() >= deadline
            or cancelled is not None
            and cancelled()
        ):
            break
        relative = f"{base}/{name}" if base else name
        opened = _open_relative_file(root_fd, relative)
        if opened is None:
            continue
        try:
            metadata = os.fstat(opened)
            if (
                not stat.S_ISREG(metadata.st_mode)
            ):
                continue
            if metadata.st_size > _MAX_IGNORE_BYTES:
                return rules, False
            payload = _read_bounded(
                opened,
                _MAX_IGNORE_BYTES + 1,
                deadline=deadline,
                cancelled=cancelled,
            )
            if payload is None or len(payload) > _MAX_IGNORE_BYTES:
                return rules, False
            try:
                lines = payload.decode("utf-8", errors="strict").splitlines()
            except UnicodeDecodeError:
                return rules, False
            for line in lines:
                pattern = line.strip()
                if pattern.startswith(r"\#") or pattern.startswith(r"\!"):
                    pattern = pattern[1:]
                elif not pattern or pattern.startswith("#"):
                    continue
                negated = pattern.startswith("!")
                if negated:
                    pattern = pattern[1:]
                anchored = pattern.startswith("/")
                directory_only = pattern.endswith("/")
                pattern = pattern.strip("/")
                if pattern:
                    rules.append(
                        (
                            base,
                            pattern,
                            negated,
                            directory_only,
                            anchored,
                        )
                    )
        finally:
            os.close(opened)
    return rules, True


def _filter_additional_ignores(
    root_fd: int,
    files: list[str],
    *,
    deadline: float,
    cancelled: Callable[[], bool] | None,
) -> tuple[list[str], bool]:
    cache: dict[
        str,
        tuple[list[tuple[str, str, bool, bool, bool]], bool],
    ] = {}
    selected = []
    truncated = False
    for relative in files:
        if (
            time.monotonic() >= deadline
            or cancelled is not None
            and cancelled()
        ):
            truncated = True
            break
        parent = Path(relative).parent
        rules = []
        components = [Path(".")]
        current = Path()
        for component in parent.parts:
            current /= component
            components.append(current)
        for directory in components:
            base = "" if directory == Path(".") else directory.as_posix()
            if base not in cache:
                cache[base] = _ignore_rules(
                    root_fd,
                    base=base,
                    deadline=deadline,
                    cancelled=cancelled,
                    names=(".ignore",),
                )
            directory_rules, ignore_complete = cache[base]
            if not ignore_complete:
                truncated = True
                break
            if cancelled is not None and cancelled():
                truncated = True
                break
            rules.extend(directory_rules)
        if truncated:
            break
        if not _ignored(relative, False, rules):
            selected.append(relative)
    return selected, truncated


def _ignored(
    relative: str,
    directory: bool,
    rules: list[tuple[str, str, bool, bool, bool]],
) -> bool:
    parts = relative.split("/")
    ignored = any(part.casefold() in _IGNORE_CASEFOLD for part in parts)
    for base, pattern, negated, directory_only, anchored in rules:
        if base:
            if relative == base:
                local = ""
            elif relative.startswith(base + "/"):
                local = relative[len(base) + 1 :]
            else:
                continue
        else:
            local = relative
        local_parts = local.split("/")
        if anchored or "/" in pattern:
            matched = (
                fnmatch.fnmatch(local, pattern)
                or directory_only
                and local.startswith(pattern + "/")
            )
        else:
            matched = any(
                fnmatch.fnmatch(component, pattern)
                for component in local_parts
            )
        if directory_only and not directory and "/" not in local:
            matched = False
        if matched:
            ignored = not negated
    return ignored


def _open_relative_file(root_fd: int, relative: str) -> int | None:
    parts = Path(relative).parts
    if not parts or ".." in parts:
        return None
    descriptor = os.dup(root_fd)
    try:
        for component in parts[:-1]:
            child = os.open(
                component,
                os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW,
                dir_fd=descriptor,
            )
            os.close(descriptor)
            descriptor = child
        opened = os.open(
            parts[-1],
            os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK,
            dir_fd=descriptor,
        )
    except OSError:
        os.close(descriptor)
        return None
    os.close(descriptor)
    return opened


def _read_bounded(
    descriptor: int,
    limit: int,
    *,
    deadline: float,
    cancelled: Callable[[], bool] | None,
) -> bytes | None:
    payload = bytearray()
    while len(payload) < limit:
        if (
            time.monotonic() >= deadline
            or cancelled is not None
            and cancelled()
        ):
            return None
        try:
            chunk = os.read(
                descriptor,
                min(64 * 1024, limit - len(payload)),
            )
        except (BlockingIOError, OSError):
            return None
        if not chunk:
            break
        payload.extend(chunk)
    return bytes(payload)


def _read_file(descriptor: int, size: int) -> bytes | None:
    payload = b""
    while len(payload) < size:
        try:
            chunk = os.read(descriptor, min(64 * 1024, size - len(payload)))
        except OSError:
            return None
        if not chunk:
            break
        payload += chunk
        if b"\x00" in chunk or any(
            byte < 9 or 13 < byte < 32 for byte in chunk
        ):
            return None
    return payload


def _matches(
    payload: bytes,
    *,
    query: str,
    needle: str,
    case_sensitive: bool,
    mode: str,
    suffix: str,
) -> Iterator[dict[str, Any]]:
    try:
        text = payload.decode("utf-8", errors="strict")
    except UnicodeDecodeError:
        return
    for line_number, line in enumerate(text.splitlines(), 1):
        if mode == "symbol":
            symbol = _symbol(line, suffix=suffix)
            if symbol is None:
                continue
            candidate = (
                symbol["symbol"]
                if case_sensitive
                else symbol["symbol"].casefold()
            )
            if needle not in candidate:
                continue
            yield {
                "line": line_number,
                "column": line.find(symbol["symbol"]) + 1,
                "text": line[:_MAX_PREVIEW_CHARS],
                **symbol,
            }
            continue
        haystack = line if case_sensitive else line.casefold()
        column = haystack.find(needle)
        if column < 0:
            continue
        yield {
            "line": line_number,
            "column": column + 1,
            "text": line[:_MAX_PREVIEW_CHARS],
        }


def _symbol(line: str, *, suffix: str) -> dict[str, str] | None:
    if suffix == ".go":
        matched = re.match(
            r"^\s*func\s*(?P<receiver>\([^)]*\)\s*)?"
            r"(?P<name>[A-Za-z_]\w*)\s*\(",
            line,
        )
        if matched is not None:
            return {
                "symbol": matched.group("name"),
                "kind": "method" if matched.group("receiver") else "function",
            }
    for pattern in _SYMBOL_PATTERNS:
        matched = pattern.match(line)
        if matched is None:
            continue
        kind = matched.group("kind")
        return {
            "symbol": matched.group("name"),
            "kind": _SYMBOL_KINDS.get(kind, kind),
        }
    if suffix in {
        ".js",
        ".jsx",
        ".ts",
        ".tsx",
        ".java",
        ".kt",
        ".kts",
        ".cs",
        ".c",
        ".cc",
        ".cpp",
        ".cxx",
        ".h",
        ".hpp",
    }:
        if re.match(
            r"^\s*(?:return|await|new|throw|yield|case|else|do)\b",
            line,
        ):
            return None
        matched = re.match(
            r"^\s*(?:(?:export|public|private|protected|internal|static|"
            r"abstract|virtual|override|final|async|readonly|suspend|"
            r"inline|open|operator|get|set)\s+)*"
            r"(?:[A-Za-z_$][\w$:<>,?.\[\]*&]*\s+)?"
            r"(?P<name>[A-Za-z_$][\w$]*)\s*(?:<[^;>{}]*>)?\s*"
            r"\([^)]*\)\s*(?::[^{;=]+)?\s*(?:\{|=>|=)",
            line,
        )
        if (
            matched is not None
            and matched.group("name")
            not in {"if", "for", "while", "switch", "catch", "return"}
        ):
            return {"symbol": matched.group("name"), "kind": "method"}
    return None


def _match_rank(
    *,
    query: str,
    result: dict[str, Any],
    root_index: int,
) -> tuple[Any, ...]:
    normalized_query = query.casefold()
    symbol = str(result.get("symbol", ""))
    if symbol:
        normalized = symbol.casefold()
        relevance = (
            0
            if normalized == normalized_query
            else 1 if normalized.startswith(normalized_query) else 2
        )
    else:
        preview = str(result.get("text", "")).strip().casefold()
        words = re.findall(r"[A-Za-z0-9_$]+", preview)
        relevance = (
            0
            if preview == normalized_query
            else 1
            if normalized_query in words
            else 2 if preview.startswith(normalized_query) else 3
        )
    path = str(result["path"])
    return (
        relevance,
        root_index,
        path.casefold(),
        path,
        int(result["line"]),
        int(result["column"]),
        str(result.get("symbol", "")).casefold(),
        str(result.get("symbol", "")),
    )


def _bounded_utf8(value: str, minimum: int, maximum: int) -> bool:
    try:
        size = len(value.encode("utf-8"))
    except UnicodeEncodeError:
        return False
    return minimum <= size <= maximum
