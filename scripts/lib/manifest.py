"""Host capability manifest loader.

The manifest (config/hosts.yaml) is the single source of truth for every
supported host. Adapters and the `harness host` / `harness verify` CLIs read
it through this module so validation happens in one place.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import jsonschema
import yaml


class CapabilityStatus:
    SUPPORTED = "supported"
    PARTIAL = "partial"
    UNSUPPORTED = "unsupported"
    UNVERIFIED = "unverified"
    VALID = frozenset({SUPPORTED, PARTIAL, UNSUPPORTED, UNVERIFIED})


def load_schema(schema_path: Path) -> dict:
    return json.loads(schema_path.read_text())


def load(path: Path, schema_path: Path | None = None) -> dict:
    """Load + (optionally) validate the manifest. Raises on drift."""
    data = yaml.safe_load(path.read_text())
    if schema_path is not None:
        jsonschema.validate(data, load_schema(schema_path))
    return data


def hosts(data: dict) -> dict:
    return data["hosts"]


def capabilities(host_entry: dict) -> dict:
    return host_entry.get("capabilities", {})


def tier(host_entry: dict) -> int:
    return int(host_entry.get("tier", 3))


def expand_path(value: str, home: Path | None = None) -> Path:
    """Resolve a manifest path string. `~/...` against `home` (default $HOME),
    other values returned as-is (relative paths are caller-resolved)."""
    s = str(value)
    if s.startswith("~/"):
        base = home or Path.home()
        return base / s[2:]
    if s == "~":
        return home or Path.home()
    return Path(s)


def opencode_permission_object(baseline: dict) -> dict:
    """Map the universal permission baseline to OpenCode's config.permission
    rules (docs/permissions). Destructive patterns are denied inside `bash`."""
    bash: dict[str, str] = {"*": baseline["bash"]}
    for pat in baseline["destructive_deny"]:
        bash[pat] = "deny"
    return {
        "*": "ask",
        "read": baseline["read"],
        "edit": baseline["edit"],
        "bash": bash,
        "webfetch": baseline["webfetch"],
        "websearch": baseline["websearch"],
        "external_directory": baseline["external_directory"],
    }


def permission_diff(global_perm: dict[str, Any], baseline_perm: dict[str, Any]) -> list[str]:
    """Human-readable list of top-level divergences from the baseline."""
    diffs: list[str] = []
    for k in ("*", "read", "edit", "webfetch", "websearch", "external_directory"):
        gv = global_perm.get(k)
        bv = baseline_perm.get(k)
        if gv != bv and bv is not None:
            diffs.append(f"permission.{k}: global={bv!r} project={gv!r}")
    return diffs
