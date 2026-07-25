"""OpenCode adapter (Tier 1).

Wires (against an isolated or real HOME):
  ~/.config/opencode/AGENTS.md         — symlink to ~/.agents/AGENTS.md
  ~/.config/opencode/commands/         — symlink to ~/.agents/commands
  ~/.config/opencode/opencode.jsonc    — baseline `permission` merged in place
                                         (JSONC comments preserved, atomic write)
  ~/.agents/skills/<alias>             — flat symlinks for enabled nested skills

Relies on OpenCode's native discovery of ~/.agents/skills/<name>/SKILL.md
(docs/skills). Never duplicates skill contents into ~/.config/opencode/skills.
"""
from __future__ import annotations

import json
import os
from pathlib import Path

from adapters.base import Adapter, CapabilityResult, ProjectOverride, ProvisionResult
from lib import jsonc
from lib.manifest import expand_path, opencode_permission_object, permission_diff
from lib.ownership import Ownership
from lib.symlink import ensure_symlink

CONFIG_SCHEMAS_VALUE = "https://opencode.ai/config.json"


class OpenCodeAdapter(Adapter):
    name = "opencode"

    # ----------------------------------------------------------------- paths
    def _config_dir(self, home: Path) -> Path:
        return expand_path(self.entry["config_dir"], home)

    def _config_file(self, home: Path) -> Path:
        return expand_path(self.entry["config_file"], home)

    def _skills_dir(self) -> Path:
        return self.agents_home / "skills"

    # ----------------------------------------------------------------- provisioning
    def provision(self, home: Path, *, dry_run: bool = False,
                  enabled_skills: set[str] | None = None) -> ProvisionResult:
        enabled = set(enabled_skills or [])
        pr = ProvisionResult(host=self.name, home=home, dry_run=dry_run)
        cfg_dir = self._config_dir(home)

        # 1. policy link
        self._link(pr, cfg_dir / "AGENTS.md", self.policy_source, label="AGENTS.md",
                   dry_run=dry_run)

        # 2. commands dir link
        if self.commands_source and self.commands_source.is_dir():
            self._link(pr, cfg_dir / "commands", self.commands_source,
                       label="commands", is_dir=True, dry_run=dry_run)
        else:
            pr.skipped.append("commands (source missing)")

        # 3. nested flat aliases (the enabled view OpenCode discovers natively)
        for alias, target in self._nested_alias_targets(enabled):
            self._link(pr, self._skills_dir() / alias, target,
                       label=f"skill:{alias}", dry_run=dry_run)

        # 4. merge permission baseline into opencode.jsonc
        self._merge_permission(pr, self._config_file(home), dry_run=dry_run)
        return pr

    def _link(self, pr: ProvisionResult, link: Path, target: Path, *,
              label: str, is_dir: bool = False, dry_run: bool,
              host_for_ownership: str | None = "opencode") -> None:
        if dry_run:
            pr.written.append(label)
            pr.add_diff(f"+ link {link} -> {target}")
            return
        try:
            kind = ensure_symlink(link, target, is_dir=is_dir)
            pr.written.append(f"{label} ({kind})")
            pr.add_diff(f"{kind} {link} -> {target}")
        except FileExistsError as e:
            pr.conflicts.append(f"{label}: {e}")
            return
        if host_for_ownership:
            Ownership(self.agents_home).record(link, host_for_ownership, is_symlink=True)

    def _merge_permission(self, pr: ProvisionResult, cfg: Path, *, dry_run: bool) -> None:
        desired = opencode_permission_object(self.baseline)
        existing_text = ""
        had_file = cfg.is_file()
        if had_file:
            existing_text = cfg.read_text()
        else:
            existing_text = '{\n  "$schema": "%s"\n}' % CONFIG_SCHEMAS_VALUE

        # validate existing; never touch a malformed file
        try:
            obj = jsonc.loads(existing_text)
        except jsonc.JsoncError as e:
            pr.conflicts.append(f"opencode.jsonc: parse failed ({e}); left untouched")
            return
        if not isinstance(obj, dict):
            pr.conflicts.append("opencode.jsonc: root is not an object; left untouched")
            return

        if "permission" in obj:
            current = obj.get("permission")
            if current == desired:
                pr.skipped.append("opencode.jsonc: permission already at baseline")
                return
            # user has configured permissions — do not overwrite (decision #9/#10)
            pr.conflicts.append(
                "opencode.jsonc: existing `permission` differs from baseline; "
                "not overwritten (merge manually or remove the key)")
            return

        if dry_run:
            pr.written.append("opencode.jsonc (+ permission)")
            pr.add_diff("+ opencode.jsonc: insert permission baseline")
            return

        new_text = jsonc.insert_top_level_key(existing_text, "permission", desired)
        ownership = Ownership(self.agents_home)
        backup = ownership.atomic_write_text(
            cfg, new_text, self.name,
            validate=lambda t: jsonc.loads(t),
        )
        if had_file and backup:
            pr.backups.append(str(backup))
        pr.written.append("opencode.jsonc (+ permission)")

    # ----------------------------------------------------------------- nested discovery
    def _nested_alias_targets(self, enabled: set[str] | None) -> list[tuple[str, Path]]:
        """Enabled nested skills as (flat_alias, target_dir). A nested skill is
        any <skills>/<group>/<name>/SKILL.md. `enabled=None` means all nested
        skills (preserve the current all-visible install until Phase 2 catalog
        gates the enabled view)."""
        out: list[tuple[str, Path]] = []
        skills = self._skills_dir()
        if not skills.is_dir():
            return out
        for group in sorted(skills.iterdir()):
            if not group.is_dir() or group.name.startswith("."):
                continue
            for sub in sorted(group.iterdir()):
                if not sub.is_dir() or sub.name.startswith("."):
                    continue
                if (sub / "SKILL.md").is_file() and (enabled is None or sub.name in enabled):
                    out.append((sub.name, sub))
        return out

    # ----------------------------------------------------------------- verify
    def verify(self, home: Path, *, project: Path | None = None) -> list[CapabilityResult]:
        results: list[CapabilityResult] = []
        cfg_dir = self._config_dir(home)

        # policy_file
        link = cfg_dir / "AGENTS.md"
        if link.exists() and link.read_text(encoding="utf-8", errors="replace"):
            results.append(self._cap("policy_file", "supported", f"{link} resolves"))
        else:
            results.append(self._cap("policy_file", "unsupported", f"missing/broken: {link}"))

        # command_dir
        cmds = cfg_dir / "commands"
        if (cmds.is_symlink() or cmds.is_dir()) and any(cmds.iterdir()):
            results.append(self._cap("command_dir", "supported", f"{cmds} wired"))
        else:
            results.append(self._cap("command_dir", "unsupported", f"empty/missing: {cmds}"))

        # native_permissions + config_merge depend on the config file
        cfg = self._config_file(home)
        perm_ok = False
        merge_ok = False
        perm_evidence = ""
        merge_evidence = ""
        if cfg.is_file():
            try:
                obj = jsonc.loads(cfg.read_text())
                perm = obj.get("permission")
                desired = opencode_permission_object(self.baseline)
                if isinstance(perm, dict) and all(perm.get(k) == desired.get(k)
                                                  for k in ("*", "read", "edit",
                                                            "webfetch", "websearch")):
                    perm_ok = True
                    perm_evidence = "permission baseline present"
                else:
                    perm_evidence = "permission missing or diverges from baseline"
                # config_merge: ownership journal claims the file
                merge_ok = Ownership(self.agents_home).owns(cfg, self.name)
                merge_evidence = "ownership: harness" if merge_ok else "ownership: not claimed"
            except jsonc.JsoncError as e:
                perm_evidence = merge_evidence = f"parse failed: {e}"
        results.append(self._cap("native_permissions",
                                 "supported" if perm_ok else "unsupported",
                                 perm_evidence or "no config file"))
        results.append(self._cap("config_merge",
                                 "supported" if merge_ok else "unsupported",
                                 merge_evidence or "no config file"))

        # skill_discovery — at least one enabled skill resolves natively
        skills = self._skills_dir()
        discovered = [d.name for d in skills.iterdir()
                      if d.is_dir() and (d / "SKILL.md").is_file()]
        if discovered:
            results.append(self._cap("skill_discovery", "supported",
                                     f"native: {len(discovered)} skill(s) resolve"))
        else:
            results.append(self._cap("skill_discovery", "unsupported",
                                     "no skills resolve under ~/.agents/skills"))

        # nested_skill_aliases
        nested_aliases = [d for d in skills.iterdir()
                          if d.is_symlink() and (d / "SKILL.md").exists()]
        if nested_aliases:
            results.append(self._cap("nested_skill_aliases", "supported",
                                     f"{len(nested_aliases)} flat alias(es) resolve"))
        else:
            results.append(self._cap("nested_skill_aliases", "unsupported",
                                     "no flat nested aliases"))

        # project_override
        if project is not None:
            overrides = self.detect_project_overrides(home, project=project)
            results.append(self._cap("project_override", "supported",
                                     f"{len(overrides)} override(s) detected"))
        else:
            results.append(self._cap("project_override", "unverified",
                                     "no project context provided"))

        # uninstall_ownership — journal claims any opencode path
        owns_any = bool(Ownership(self.agents_home).entries(host=self.name))
        results.append(self._cap("uninstall_ownership",
                                 "supported" if owns_any else "unsupported",
                                 "journal has opencode entries" if owns_any
                                 else "journal empty for opencode"))
        return results

    # ----------------------------------------------------------------- project override
    def detect_project_overrides(self, home: Path, *, project: Path) -> list[ProjectOverride]:
        overrides: list[ProjectOverride] = []
        baseline_perm = opencode_permission_object(self.baseline)
        for rel in self.entry.get("project_config", []):
            p = Path(project) / rel
            if not p.is_file():
                continue
            try:
                obj = jsonc.loads(p.read_text())
            except jsonc.JsoncError as e:
                overrides.append(ProjectOverride(path=str(p),
                                                 diff=f"unparseable: {e}"))
                continue
            perm = obj.get("permission")
            if isinstance(perm, dict):
                diffs = permission_diff(perm, baseline_perm)
                for d in diffs:
                    overrides.append(ProjectOverride(path=str(p), diff=d))
            elif perm is not None:
                overrides.append(ProjectOverride(path=str(p),
                                                 diff=f"permission={perm!r} (non-object)"))
        return overrides

    # ----------------------------------------------------------------- skill visibility
    def apply_skill_state(self, home: Path, disabled: set[str]) -> ProvisionResult:
        """Reflect the disabled-catalog journal as `permission.skill.<name>:
        deny` rules (docs/skills). Respects user-owned permission blocks."""
        pr = ProvisionResult(host=self.name, home=home, dry_run=False)
        cfg = self._config_file(home)
        if not cfg.is_file():
            pr.skipped.append("opencode.jsonc: not provisioned yet (run: harness host provision opencode)")
            return pr
        try:
            text = cfg.read_text()
            obj = jsonc.loads(text)
        except jsonc.JsoncError as e:
            pr.conflicts.append(f"opencode.jsonc parse failed: {e}")
            return pr
        if not isinstance(obj, dict):
            pr.conflicts.append("opencode.jsonc: root not an object")
            return pr

        baseline_perm = opencode_permission_object(self.baseline)
        catalog_disabled = sorted(d for d in disabled if d)
        desired = dict(baseline_perm)
        if catalog_disabled:
            desired["skill"] = {d: "deny" for d in catalog_disabled}

        current = obj.get("permission")
        if current == desired:
            pr.skipped.append("permission already reflects skill state")
            return pr

        if "permission" not in obj:
            new_text = jsonc.insert_top_level_key(text, "permission", desired)
        elif self._permission_owned(current, baseline_perm):
            new_text = jsonc.replace_top_level_key(text, "permission", desired)
        else:
            pr.conflicts.append("opencode.jsonc: user-configured `permission`; "
                                "skill deny not applied (merge manually)")
            return pr

        Ownership(self.agents_home).atomic_write_text(
            cfg, new_text, self.name, validate=lambda t: jsonc.loads(t))
        pr.written.append(f"permission.skill deny -> {catalog_disabled or '[]'}")
        return pr

    @staticmethod
    def _permission_owned(current: dict, baseline_perm: dict) -> bool:
        if not isinstance(current, dict):
            return False
        cur = {k: v for k, v in current.items() if k != "skill"}
        return cur == baseline_perm

    # ----------------------------------------------------------------- uninstall
    def uninstall(self, home: Path) -> list[str]:
        """Remove only paths the journal claims for opencode. Never touch
        user-owned files."""
        removed: list[str] = []
        ownership = Ownership(self.agents_home)
        entries = ownership.entries(host=self.name)
        for rel, meta in list(entries.items()):
            target = self.agents_home / rel if not rel.startswith("/") else Path(rel)
            # also resolve home-relative config paths
            if not target.exists() and not target.is_symlink():
                continue
            if meta.get("symlink"):
                target.unlink()
                removed.append(str(target))
            elif meta.get("owner") == "harness":
                # real file we wrote — safe to remove
                target.unlink()
                removed.append(str(target))
        return removed
