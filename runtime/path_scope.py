"""Resolved workspace path boundaries shared across runtime layers."""

from __future__ import annotations

from pathlib import Path


def owns_path(
    workspace: str | Path,
    ownership: tuple[str, ...],
    candidate: str | Path,
) -> bool:
    """Return whether candidate resolves inside one declared owned path."""
    if not ownership:
        return True
    root = Path(workspace).expanduser().resolve()
    value = Path(candidate).expanduser()
    resolved = (
        value.resolve()
        if value.is_absolute()
        else (root / value).resolve()
    )
    try:
        resolved.relative_to(root)
    except ValueError:
        return False
    for owned in ownership:
        boundary = (root / owned).resolve()
        try:
            boundary.relative_to(root)
            resolved.relative_to(boundary)
            return True
        except ValueError:
            continue
    return False
