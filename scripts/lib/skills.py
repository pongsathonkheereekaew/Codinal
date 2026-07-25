"""Core/catalog skill model + enabled-state journal.

Source of truth = ~/.agents/skills/<name>/SKILL.md (every installed skill).
Classification = config/skills.yaml `core` list; everything else is catalog.
Enabled state = state/enabled-skills.json (`disabled`: a blacklist of catalog
skills the user turned off). Core skills are never disable-able.

Default journal keeps the current all-visible behavior (decision #14): catalog
defaults to enabled until a future release flips the default.
"""
from __future__ import annotations

import json
from pathlib import Path

import yaml

CORE_DEFAULT: tuple[str, ...] = ()


def load_core(agents_home: Path) -> set[str]:
    path = agents_home / "config" / "skills.yaml"
    if not path.is_file():
        return set()
    data = yaml.safe_load(path.read_text()) or {}
    return set(data.get("core", []) or [])


def _flat_skill_names(skills_dir: Path) -> set[str]:
    """All skill names OpenCode-style discovery can see: top-level dirs with a
    SKILL.md, plus nested <group>/<name> leaves."""
    names: set[str] = set()
    if not skills_dir.is_dir():
        return names
    for entry in sorted(skills_dir.iterdir()):
        if entry.name.startswith("."):
            continue
        if (entry / "SKILL.md").is_file():
            names.add(entry.name)
        elif entry.is_dir():
            for sub in entry.iterdir():
                if sub.name.startswith("."):
                    continue
                if (sub / "SKILL.md").is_file():
                    names.add(sub.name)
    return names


def classify(agents_home: Path) -> dict[str, str]:
    """Return {skill_name: 'core' | 'catalog'} for every discovered skill."""
    core = load_core(agents_home)
    names = _flat_skill_names(agents_home / "skills")
    return {n: ("core" if n in core else "catalog") for n in names}


class SkillJournal:
    """Persisted enabled-state. `disabled` is a blacklist of catalog skills."""

    def __init__(self, agents_home: Path):
        self.agents_home = Path(agents_home)
        self.path = self.agents_home / "state" / "enabled-skills.json"

    def load(self) -> dict:
        if not self.path.is_file():
            return {"disabled": [], "schema_version": 1}
        try:
            data = json.loads(self.path.read_text())
        except json.JSONDecodeError:
            return {"disabled": [], "schema_version": 1}
        data.setdefault("disabled", [])
        data["disabled"] = sorted(set(data["disabled"]))
        return data

    def save(self, data: dict) -> None:
        data["disabled"] = sorted(set(data.get("disabled", [])))
        data["schema_version"] = 1
        self.path.parent.mkdir(parents=True, exist_ok=True)
        tmp = self.path.with_suffix(".json.tmp")
        tmp.write_text(json.dumps(data, indent=2, sort_keys=True))
        tmp.replace(self.path)

    def disabled(self) -> set[str]:
        return set(self.load()["disabled"])

    def disable(self, name: str) -> bool:
        data = self.load()
        d = set(data["disabled"])
        if name in d:
            return False
        d.add(name)
        data["disabled"] = sorted(d)
        self.save(data)
        return True

    def enable(self, name: str) -> bool:
        data = self.load()
        d = set(data["disabled"])
        if name not in d:
            return False
        d.discard(name)
        data["disabled"] = sorted(d)
        self.save(data)
        return True

    def reset(self) -> set[str]:
        """Clear the blacklist. Returns the previously-disabled set."""
        data = self.load()
        prev = set(data["disabled"])
        data["disabled"] = []
        self.save(data)
        return prev


def enabled_set(agents_home: Path) -> tuple[set[str], set[str]]:
    """(enabled, disabled) skill name sets given classification + journal.
    Core is always enabled; catalog enabled unless blacklisted."""
    classes = classify(agents_home)
    journal = SkillJournal(agents_home).disabled()
    disabled = {n for n in journal if classes.get(n) == "catalog"}
    enabled = {n for n, c in classes.items() if n not in disabled}
    return enabled, disabled


def audit(agents_home: Path) -> dict:
    """Coverage + consistency report (no writes)."""
    classes = classify(agents_home)
    core_list = load_core(agents_home)
    journal = SkillJournal(agents_home).disabled()
    issues = []
    # declared core that doesn't exist
    for n in sorted(core_list - set(classes)):
        issues.append(f"core skill declared but not installed: {n}")
    # blacklisted core (not allowed)
    for n in sorted(journal & core_list):
        issues.append(f"core skill cannot be disabled: {n}")
    # blacklisted unknown
    for n in sorted(journal - set(classes)):
        issues.append(f"disabled entry is not an installed skill: {n}")
    return {
        "total": len(classes),
        "core": sum(1 for c in classes.values() if c == "core"),
        "catalog": sum(1 for c in classes.values() if c == "catalog"),
        "disabled": sorted(journal & set(classes)),
        "issues": issues,
    }
