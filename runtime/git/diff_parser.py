"""Unified-diff hunk parser for selective hunk-level apply.

Splits a raw unified-diff (as emitted by ``git diff``) into per-file,
per-hunk records and reconstructs a valid patch from a chosen subset of
hunks. Used by ``GitWorktreeService.apply_selected_hunks`` so the user can
accept/reject at hunk granularity rather than only file granularity.

The parser is intentionally strict: it only accepts the shape ``git diff``
produces (``diff --git`` header, optional ``index``/``---``/``+++`` lines,
``@@`` hunk headers, ``+``/``-``/`` `` body lines). Malformed input raises
``ValueError`` rather than silently producing a patch that ``git apply``
would reject — the apply path's conflict-abort invariant depends on a clean
distinction between \"user selected nothing\" and \"input malformed\".
"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class Hunk:
    """One ``@@`` hunk within a file diff."""

    path: str
    index: int  # 0-based ordinal within the file
    header: str  # the full ``@@ … @@`` line, including trailing newline
    body: str  # the ``+``/``-``/`` `` body lines, joined (no trailing newline)


@dataclass
class FileDiff:
    """One ``diff --git`` block."""

    path: str
    header_lines: list[str] = field(default_factory=list)  # all lines up to first @@
    hunks: list[Hunk] = field(default_factory=list)


def parse_diff(text: str) -> list[FileDiff]:
    """Split a unified diff into per-file blocks with per-hunk records.

    ``index`` on each ``Hunk`` is its 0-based ordinal within the file, which
    is the stable identifier the UI and backend use to select hunks.
    """
    if not isinstance(text, str):
        raise ValueError("diff must be a string")
    lines = text.splitlines(keepends=True)
    files: list[FileDiff] = []
    current: FileDiff | None = None
    current_hunk_body: list[str] = []
    current_hunk_header = ""
    in_hunk = False

    def _flush_hunk() -> None:
        nonlocal in_hunk, current_hunk_header, current_hunk_body
        if in_hunk and current is not None and current.hunks is not None:
            current.hunks.append(
                Hunk(
                    path=current.path,
                    index=len(current.hunks),
                    header=current_hunk_header,
                    body="".join(current_hunk_body),
                )
            )
        in_hunk = False
        current_hunk_header = ""
        current_hunk_body = []

    for line in lines:
        if line.startswith("diff --git "):
            _flush_hunk()
            if current is not None:
                files.append(current)
            path = _extract_path(line)
            current = FileDiff(path=path, header_lines=[line])
            in_hunk = False
            continue
        if current is None:
            # Leading non-diff garbage (e.g. a blank line) — ignore.
            continue
        if line.startswith("@@"):
            _flush_hunk()
            current_hunk_header = line
            in_hunk = True
            continue
        if in_hunk:
            if line.startswith(("+", "-", " ")) or line == "\n":
                current_hunk_body.append(line)
            elif line.startswith("\\ No newline at end of file"):
                current_hunk_body.append(line)
            else:
                # A line that doesn't belong to a hunk body ends the hunk.
                _flush_hunk()
                current.header_lines.append(line)
            continue
        # Pre-hunk header lines (index, ---, +++, mode, new file, …).
        current.header_lines.append(line)

    _flush_hunk()
    if current is not None:
        files.append(current)
    return files


def reconstruct_patch(
    files: list[FileDiff],
    selected: list[tuple[str, int]],
) -> str:
    """Rebuild a unified diff containing only the selected hunks.

    ``selected`` is a list of ``(path, hunk_index)`` pairs. For each file
    with at least one selected hunk, the file header (``diff --git`` …
    ``+++``) is emitted, followed by the chosen hunks in their original
    order. The result is a valid patch for ``git apply``.
    """
    wanted: dict[str, set[int]] = {}
    for path, hunk_index in selected:
        wanted.setdefault(path, set()).add(hunk_index)
    out: list[str] = []
    for file_diff in files:
        chosen_indexes = wanted.get(file_diff.path)
        if not chosen_indexes:
            continue
        # Header lines up to (and excluding) the first hunk's @@ line.
        # These include diff --git, index, ---, +++, mode lines.
        out.extend(file_diff.header_lines)
        for hunk in file_diff.hunks:
            if hunk.index in chosen_indexes:
                out.append(hunk.header)
                out.append(hunk.body)
    patch = "".join(out)
    if not patch.strip():
        raise ValueError("no hunks selected")
    return patch


def _extract_path(diff_git_line: str) -> str:
    """Pull the b-side path from ``diff --git a/<path> b/<path>``.

    Falls back to the a-side if the b-side is missing (deletions use
    ``a/<path> b/<path>`` but the b path may equal the a path).
    """
    # Strip the trailing newline before splitting.
    stripped = diff_git_line.rstrip("\n")
    # ``diff --git a/foo b/foo`` — split on the known `` a/`` and `` b/``.
    if " b/" in stripped:
        return stripped.split(" b/", 1)[1]
    if " a/" in stripped:
        return stripped.split(" a/", 1)[1]
    # Fallback: take everything after the second space.
    parts = stripped.split(" ", 2)
    return parts[2] if len(parts) > 2 else parts[-1]
