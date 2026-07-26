#!/usr/bin/env python3
"""Merge harness Claude settings defaults into ~/.claude/settings.json (non-destructive)."""
from __future__ import annotations

import json
import sys
from pathlib import Path


def deep_merge_missing(dst: dict, src: dict) -> int:
    """Fill keys that are missing in dst from src. Never overwrite existing values."""
    added = 0
    for key, val in src.items():
        if key not in dst:
            dst[key] = val
            added += 1
        elif isinstance(dst[key], dict) and isinstance(val, dict):
            added += deep_merge_missing(dst[key], val)
    return added


def main() -> int:
    if len(sys.argv) != 3:
        print("usage: merge-claude-settings.py <defaults.json> <settings.json>", file=sys.stderr)
        return 2
    defaults_path = Path(sys.argv[1])
    settings_path = Path(sys.argv[2])
    defaults = json.loads(defaults_path.read_text(encoding="utf-8"))
    settings_path.parent.mkdir(parents=True, exist_ok=True)
    if settings_path.is_file():
        settings = json.loads(settings_path.read_text(encoding="utf-8"))
        if not isinstance(settings, dict):
            print("WARN: settings.json is not an object — left untouched", file=sys.stderr)
            return 0
    else:
        settings = {}
    added = deep_merge_missing(settings, defaults)
    settings_path.write_text(json.dumps(settings, indent=2) + "\n", encoding="utf-8")
    print(f"Claude settings ← defaults ({added} keys filled, existing kept)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
