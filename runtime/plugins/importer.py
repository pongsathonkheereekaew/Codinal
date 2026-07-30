"""Read-only import of declarative Claude/Codex plugin assets."""
from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class PluginImport:
    status: str
    manifest: dict[str, Any]
    diagnostics: tuple[str, ...]


def import_plugin(root: str | Path, *, host: str) -> PluginImport:
    if host not in {"claude", "codex"}:
        raise ValueError(f"unsupported plugin host: {host}")
    base = Path(root).resolve()
    manifest_path = base / (".claude-plugin/plugin.json" if host == "claude" else ".codex-plugin/plugin.json")
    raw = json.loads(manifest_path.read_text(encoding="utf-8"))
    author = raw.get("author", {})
    publisher = author.get("name") if isinstance(author, dict) else author
    skills = [_skill(path) for path in sorted((base / "skills").glob("*/SKILL.md"))] if (base / "skills").is_dir() else []
    diagnostics = tuple(
        f"rejected executable plugin content: {name}"
        for name in ("hooks", "scripts", "installers") if (base / name).exists()
    )
    status = "translated_with_gaps" if diagnostics else "translated"
    return PluginImport(status, {
        "schema": "codinal.integration.v1", "id": f"{publisher}/{raw['name']}",
        "version": raw.get("version", "0.0.0"), "publisher": publisher,
        "requested_permissions": [], "host_requirements": ["skill_discovery"],
        "model_requirements": [], "assets": {"skills": skills},
    }, diagnostics)


def _skill(path: Path) -> dict[str, str]:
    content = path.read_text(encoding="utf-8")
    name = path.parent.name
    if content.startswith("---"):
        for line in content.splitlines()[1:]:
            if line == "---": break
            if line.startswith("name:"):
                name = line.partition(":")[2].strip()
    return {"name": name, "content": content}
