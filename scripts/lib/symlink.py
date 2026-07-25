"""Shared symlink helpers (relative, idempotent, non-destructive)."""
from __future__ import annotations

import os
from pathlib import Path


def rel_target(target: Path, link: Path) -> str:
    return os.path.relpath(str(target), start=str(link.parent))


def ensure_symlink(link: Path, target: Path, *, is_dir: bool = False) -> str:
    """Create/refresh `link` as a relative symlink to `target`.

    Returns one of: 'created', 'refreshed', 'ok'. Refuses to overwrite a
    non-symlink real file/dir (raises FileExistsError) — caller backs up first.
    """
    if link.is_symlink():
        current = os.readlink(link)
        expected = rel_target(target, link)
        if current == expected:
            return "ok"
        link.unlink()
        link.symlink_to(expected, target_is_directory=is_dir)
        return "refreshed"
    if link.exists():
        raise FileExistsError(f"refusing to replace real path: {link}")
    link.parent.mkdir(parents=True, exist_ok=True)
    link.symlink_to(rel_target(target, link), target_is_directory=is_dir)
    return "created"
