"""Adapter base — dataclasses + Adapter protocol shared by every host."""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from lib.manifest import CapabilityStatus, expand_path
from lib.ownership import Ownership


@dataclass
class CapabilityResult:
    name: str
    status: str           # observed status (one of CapabilityStatus.VALID)
    evidence: str
    declared: str = ""    # manifest-declared status

    @property
    def ok(self) -> bool:
        """True when the observed status is supported/partial/unsupported and
        is at least as honest as the declaration (no unsupported claim that
        is actually unverified, etc.)."""
        if self.status not in CapabilityStatus.VALID:
            return False
        if self.declared == "supported" and self.status not in ("supported",):
            return False
        return True


@dataclass
class ProjectOverride:
    path: str
    diff: str             # e.g. "permission.read: global=allow project=deny"


@dataclass
class ProvisionResult:
    host: str
    home: Path
    dry_run: bool
    written: list[str] = field(default_factory=list)
    skipped: list[str] = field(default_factory=list)
    conflicts: list[str] = field(default_factory=list)
    backups: list[str] = field(default_factory=list)
    diff: str = ""

    def add_diff(self, line: str) -> None:
        if not self.diff:
            self.diff = line
        else:
            self.diff += "\n" + line


class Adapter:
    """Base adapter. Subclasses implement provision/verify/detect overrides."""
    name: str = ""

    def __init__(self, entry: dict, baseline: dict, agents_home: Path,
                 policy_source: Path, commands_source: Path | None = None):
        self.entry = entry
        self.baseline = baseline
        self.agents_home = Path(agents_home)
        self.policy_source = Path(policy_source)
        self.commands_source = Path(commands_source) if commands_source else None

    # --- API to implement -------------------------------------------------
    def provision(self, home: Path, *, dry_run: bool = False,
                  enabled_skills: set[str] | None = None) -> ProvisionResult:
        raise NotImplementedError

    def verify(self, home: Path, *, project: Path | None = None) -> list[CapabilityResult]:
        raise NotImplementedError

    def detect_project_overrides(self, home: Path, *, project: Path) -> list[ProjectOverride]:
        raise NotImplementedError

    def uninstall(self, home: Path) -> list[str]:
        raise NotImplementedError

    def apply_skill_state(self, home: Path, disabled: set[str]) -> ProvisionResult:
        """Apply the enabled-skill journal to the host. Default: unsupported
        (report, do nothing). Hosts with a native mechanism override."""
        pr = ProvisionResult(host=self.name, home=home, dry_run=False)
        pr.skipped.append(f"{self.name}: no native skill-visibility mechanism")
        return pr

    # --- shared helpers ---------------------------------------------------
    def inspect(self) -> dict:
        return {
            "name": self.name,
            "tier": self.entry.get("tier"),
            "min_version": self.entry.get("min_version"),
            "capabilities": self.entry.get("capabilities", {}),
            "smoke": self.entry.get("smoke", []),
        }

    def _cap(self, name: str, status: str, evidence: str) -> CapabilityResult:
        caps = self.entry.get("capabilities", {})
        declared = caps.get(name, {}).get("status", "")
        return CapabilityResult(name=name, status=status, evidence=evidence,
                                declared=declared)


class PolicyLinkAdapter(Adapter):
    """Config-driven adapter for hosts whose provisioning is "symlink the
    instruction file + commands dir, and rely on native skill discovery."

    This is the honest default for claude-code / codex / cursor / gemini-cli /
    zcode / openclaw / hermes. Capabilities that need host-specific work
    (native permissions, config merge, project override) report their declared
    status unchanged — `harness verify` never claims more than is proven.
    """

    def _instruction_targets(self, home: Path) -> list[tuple[Path, str]]:
        out = []
        for f in self.entry.get("instruction_files", []):
            out.append((expand_path(f["path"], home), f.get("kind", "symlink")))
        return out

    def provision(self, home: Path, *, dry_run: bool = False,
                  enabled_skills: set[str] | None = None) -> ProvisionResult:
        from lib.symlink import ensure_symlink
        pr = ProvisionResult(host=self.name, home=home, dry_run=dry_run)
        for dest, kind in self._instruction_targets(home):
            if kind != "symlink":
                pr.skipped.append(f"{dest} (kind={kind}; managed elsewhere)")
                continue
            if dry_run:
                pr.written.append(str(dest))
                pr.add_diff(f"+ link {dest} -> {self.policy_source}")
                continue
            try:
                k = ensure_symlink(dest, self.policy_source)
                pr.written.append(f"{dest} ({k})")
                pr.add_diff(f"{k} {dest}")
                Ownership(self.agents_home).record(dest, self.name, is_symlink=True)
            except FileExistsError as e:
                pr.conflicts.append(str(e))
        cmd_rel = self.entry.get("command_dir")
        if cmd_rel and self.commands_source and self.commands_source.is_dir():
            dest = expand_path(cmd_rel, home)
            if dry_run:
                pr.written.append(str(dest))
            else:
                try:
                    k = ensure_symlink(dest, self.commands_source, is_dir=True)
                    pr.written.append(f"{dest} ({k})")
                    Ownership(self.agents_home).record(dest, self.name, is_symlink=True)
                except FileExistsError as e:
                    pr.conflicts.append(str(e))
        return pr

    def verify(self, home: Path, *, project: Path | None = None) -> list[CapabilityResult]:
        results: list[CapabilityResult] = []
        # policy_file
        targets = self._instruction_targets(home)
        if targets:
            dest, kind = targets[0]
            ok = dest.exists() and (kind != "symlink" or dest.is_symlink())
            if kind == "adapter":
                ok = dest.is_file() and "AGENTS.md" in dest.read_text(encoding="utf-8", errors="replace")
            results.append(self._cap("policy_file",
                                     "supported" if ok else "unsupported",
                                     f"{dest} {'resolves' if ok else 'missing/broken'}"))
        else:
            results.append(self._cap("policy_file", "unsupported", "no instruction_files"))

        # command_dir
        cmd_rel = self.entry.get("command_dir")
        if cmd_rel:
            dest = expand_path(cmd_rel, home)
            ok = (dest.is_symlink() or dest.is_dir()) and (not dest.exists() or any(dest.iterdir()))
            results.append(self._cap("command_dir",
                                     "supported" if ok else "unsupported",
                                     f"{dest} {'wired' if ok else 'empty/missing'}"))
        else:
            results.append(self._cap("command_dir", "unsupported", "no command_dir"))

        # skill_discovery
        results.append(self._verify_skill_discovery(home))
        # nested aliases
        results.append(self._verify_nested_aliases(home))
        # the host-specific capabilities just echo their declared status
        for cap in ("native_permissions", "config_merge",
                    "project_override", "uninstall_ownership"):
            declared = self.entry.get("capabilities", {}).get(cap, {}).get("status", "unverified")
            if cap == "uninstall_ownership":
                owns_any = bool(Ownership(self.agents_home).entries(host=self.name))
                results.append(self._cap(cap, "supported" if owns_any else declared,
                                         "journal has entries" if owns_any else "declared status"))
            else:
                results.append(self._cap(cap, declared, f"declared {declared}"))
        return results

    def _verify_skill_discovery(self, home: Path) -> CapabilityResult:
        disc = self.entry.get("skill_discovery")
        # native ~/.agents/skills?
        native = self.agents_home / "skills"
        if isinstance(disc, list):
            paths = disc
        elif isinstance(disc, dict):
            paths = []
        else:
            paths = []
        has_native = any("agents/skills" in p.replace("~", "") for p in paths)
        if has_native and native.is_dir() and any(native.iterdir()):
            return self._cap("skill_discovery", "supported",
                             f"native {native}: {sum(1 for _ in native.iterdir())} entries")
        # host-specific adapter dir?
        host_dir = home / ("." + self.name.replace("-code", "").replace("-cli", ""))
        # fall back: declared status
        declared = self.entry.get("capabilities", {}).get("skill_discovery", {}).get("status", "unverified")
        return self._cap("skill_discovery", declared,
                         f"discovery not verified for {self.name}")

    def _verify_nested_aliases(self, home: Path) -> CapabilityResult:
        skills = self.agents_home / "skills"
        nested = [d for d in skills.iterdir()
                  if d.is_symlink() and (d / "SKILL.md").exists()] if skills.is_dir() else []
        if nested:
            return self._cap("nested_skill_aliases", "supported",
                             f"{len(nested)} flat alias(es)")
        declared = self.entry.get("capabilities", {}).get("nested_skill_aliases", {}).get("status", "unverified")
        return self._cap("nested_skill_aliases", declared, "none observed")

    def detect_project_overrides(self, home: Path, *, project: Path) -> list[ProjectOverride]:
        return []  # Phase 4 implements host-specific project-override detection

    def uninstall(self, home: Path) -> list[str]:
        removed: list[str] = []
        ownership = Ownership(self.agents_home)
        for rel, meta in ownership.entries(host=self.name).items():
            target = self.agents_home / rel if not rel.startswith("/") else Path(rel)
            if target.is_symlink():
                target.unlink()
                removed.append(str(target))
            elif meta.get("owner") == "harness" and target.exists():
                target.unlink()
                removed.append(str(target))
        return removed
