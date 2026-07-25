"""Ownership journal + atomic writes + backups (locked decisions #9, #10).

Every real-file write the harness performs is:
  1. validated before writing,
  2. backed up to ~/.agents/backups/<ts>/<rel> if it pre-exists and is real,
  3. written to a sibling temp file,
  4. validated again,
  5. atomically renamed into place,
  6. recorded in the ownership journal with a checksum.

Symlinks the harness creates are recorded but not backed up (they have no
user content). Uninstall only removes paths the journal claims.
"""
from __future__ import annotations

import hashlib
import json
import os
import tempfile
from datetime import datetime
from pathlib import Path
from typing import Any


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    h.update(path.read_bytes())
    return h.hexdigest()


def rel_from(path: Path, root: Path) -> str:
    # IMPORTANT: do not resolve() — a harness-created symlink whose target is
    # under `root` would otherwise be recorded as the source path, and uninstall
    # would delete the source. Operate on the lexical path only.
    try:
        return str(Path(path).relative_to(root))
    except ValueError:
        return str(path)


class Ownership:
    def __init__(self, agents_home: Path):
        self.agents_home = Path(agents_home)
        self.state_dir = self.agents_home / "state"
        self.backups_dir = self.agents_home / "backups"
        self.path = self.state_dir / "ownership.json"
        # NB: dirs are created lazily on write (save/record/backup), never on
        # read — verify/owns/entries must not touch the filesystem layout.

    def _ensure_dirs(self) -> None:
        self.state_dir.mkdir(parents=True, exist_ok=True)
        self.backups_dir.mkdir(parents=True, exist_ok=True)

    def load(self) -> dict:
        if not self.path.is_file():
            return {"paths": {}}
        try:
            return json.loads(self.path.read_text())
        except json.JSONDecodeError:
            return {"paths": {}}

    def save(self, data: dict) -> None:
        self._ensure_dirs()
        tmp = self.path.with_suffix(".json.tmp")
        tmp.write_text(json.dumps(data, indent=2, sort_keys=True))
        tmp.replace(self.path)

    def record(self, target: Path, host: str, *, is_symlink: bool = False) -> None:
        """Record (or refresh) harness ownership of `target`."""
        data = self.load()
        rel = rel_from(target, self.agents_home)
        entry = data["paths"].get(rel, {"owner": "harness", "hosts": [], "symlink": is_symlink})
        entry["owner"] = "harness"
        entry["symlink"] = bool(is_symlink)
        if host not in entry["hosts"]:
            entry["hosts"] = sorted(set(entry["hosts"]) | {host})
        entry["ts"] = datetime.utcnow().isoformat(timespec="seconds") + "Z"
        if not is_symlink and target.exists() and target.is_file():
            entry["sha256"] = sha256_file(target)
        data["paths"][rel] = entry
        self.save(data)

    def owns(self, target: Path, host: str | None = None) -> bool:
        rel = rel_from(target, self.agents_home)
        entry = self.load()["paths"].get(rel)
        if not entry or entry.get("owner") != "harness":
            return False
        if host is None:
            return True
        return host in entry.get("hosts", [])

    def entries(self, host: str | None = None) -> dict:
        data = self.load()["paths"]
        if host is None:
            return dict(data)
        return {k: v for k, v in data.items() if host in v.get("hosts", [])}

    def backup(self, target: Path) -> Path | None:
        """Copy a real pre-existing file into the timestamped backup dir.
        Returns the backup path or None if nothing to back up."""
        if not target.exists() or not target.is_file():
            return None
        self._ensure_dirs()
        ts = datetime.utcnow().strftime("%Y%m%dT%H%M%S")
        rel = rel_from(target, self.agents_home)
        dest = self.backups_dir / ts / rel
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_bytes(target.read_bytes())
        return dest

    def atomic_write_text(self, target: Path, text: str, host: str, *,
                          validate=None) -> Path | None:
        """Backup (if real pre-existing) → temp write → validate → rename →
        record ownership. Returns backup path if one was made, else None.
        `validate(text) -> None` must raise on invalid content."""
        if validate is not None:
            validate(text)
        backup_path = self.backup(target)
        target.parent.mkdir(parents=True, exist_ok=True)
        fd, tmp = tempfile.mkstemp(dir=str(target.parent), prefix=target.name + ".", suffix=".tmp")
        os.close(fd)
        Path(tmp).write_text(text)
        if validate is not None:
            validate(Path(tmp).read_text())
        os.replace(tmp, target)
        self.record(target, host, is_symlink=False)
        return backup_path
