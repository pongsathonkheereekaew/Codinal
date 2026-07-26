"""OpenCode adapter contract — the 7 behavioral guarantees locked in the
handoff (Phase 1). Each test maps 1:1 to a smoke probe in hosts.yaml."""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from adapters import opencode as opencode_adapter
from lib import manifest


@pytest.fixture()
def oc(manifest_path: Path, tmp_agents_home: Path):
    data = manifest.load(manifest_path)
    return opencode_adapter.OpenCodeAdapter(
        entry=data["hosts"]["opencode"],
        baseline=data["permission_baseline"],
        agents_home=tmp_agents_home,
        policy_source=tmp_agents_home / "AGENTS.md",
        commands_source=tmp_agents_home / "commands",
    )


def _enabled() -> set[str]:
    # Phase 1 enabled view: core + nested aliases that should resolve flat.
    return {"ask-matt", "implement", "easby-mastering", "nuiny"}


# 1. policy-link-resolves
def test_policy_link_resolves(oc, tmp_home: Path):
    oc.provision(tmp_home, enabled_skills=_enabled())
    link = tmp_home / ".config" / "opencode" / "AGENTS.md"
    assert link.exists(), f"missing {link}"
    assert "# universal agent policy" in link.read_text()
    [r] = [c for c in oc.verify(tmp_home) if c.name == "policy_file"]
    assert r.status == "supported", r.evidence


# 2. command-dir-wired
def test_command_dir_wired(oc, tmp_home: Path):
    oc.provision(tmp_home, enabled_skills=_enabled())
    cmds = tmp_home / ".config" / "opencode" / "commands"
    assert cmds.is_symlink() or cmds.is_dir()
    assert (cmds / "harness-sync.md").exists()
    [r] = [c for c in oc.verify(tmp_home) if c.name == "command_dir"]
    assert r.status == "supported", r.evidence


# 3. permission-present (universal baseline mapped to opencode rules)
def test_permission_present(oc, tmp_home: Path):
    oc.provision(tmp_home, enabled_skills=_enabled())
    cfg = json.loads((tmp_home / ".config" / "opencode" / "opencode.jsonc").read_text())
    perm = cfg["permission"]
    assert perm["*"] == "ask"
    assert perm["read"] == "allow"
    assert perm["edit"] == "ask"
    assert perm["bash"]["*"] == "ask"
    # destructive deny from baseline.destructive_deny
    assert perm["bash"].get("rm -rf *") == "deny"
    assert perm["bash"].get("git push *") == "deny"
    assert perm["webfetch"] == "ask"
    [r] = [c for c in oc.verify(tmp_home) if c.name == "native_permissions"]
    assert r.status == "supported", r.evidence


# 4. enabled-skills-only — never duplicate skill contents into opencode dir
def test_no_skill_duplication(oc, tmp_home: Path):
    oc.provision(tmp_home, enabled_skills=_enabled())
    dup = tmp_home / ".config" / "opencode" / "skills"
    assert not dup.exists(), "adapter must not duplicate skills; rely on native ~/.agents/skills"


# 5. nested-alias-resolves — flat symlink in the enabled view
def test_nested_alias_resolves(oc, tmp_agents_home: Path, tmp_home: Path):
    oc.provision(tmp_home, enabled_skills=_enabled())
    alias = tmp_agents_home / "skills" / "easby-mastering"
    assert alias.is_symlink(), f"{alias} not a symlink"
    assert (alias / "SKILL.md").exists()
    alias2 = tmp_agents_home / "skills" / "nuiny"
    assert alias2.is_symlink() and (alias2 / "SKILL.md").exists()
    [r] = [c for c in oc.verify(tmp_home) if c.name == "nested_skill_aliases"]
    assert r.status == "supported", r.evidence


# 6. malformed-jsonc-rejected — source file untouched on parse failure
def test_malformed_jsonc_rejected(oc, tmp_home: Path):
    cfg_path = tmp_home / ".config" / "opencode" / "opencode.jsonc"
    cfg_path.parent.mkdir(parents=True)
    malformed = '{\n  // a comment\n  "$schema": "x",\n  "permission": { "read" "allow" }\n'  # missing colon
    cfg_path.write_text(malformed)
    result = oc.provision(tmp_home, enabled_skills=_enabled())
    # file MUST be byte-identical (no destructive rewrite on parse failure)
    assert cfg_path.read_text() == malformed
    assert any("opencode.jsonc" in c or "parse" in c.lower() for c in result.conflicts), result.conflicts
    [r] = [c for c in oc.verify(tmp_home) if c.name == "config_merge"]
    assert r.status == "unsupported", r.evidence


# 7. project-override-detected
def test_project_override_detected(oc, tmp_home: Path, tmp_path: Path):
    oc.provision(tmp_home, enabled_skills=_enabled())
    project = tmp_path / "proj"
    (project / ".opencode").mkdir(parents=True)
    (project / ".opencode" / "opencode.json").write_text(
        json.dumps({"permission": {"read": "deny"}})
    )
    overrides = oc.detect_project_overrides(tmp_home, project=project)
    assert overrides, "expected at least one project override"
    assert any(o.path.endswith(".opencode/opencode.json") and "read" in o.diff for o in overrides)
    [r] = [c for c in oc.verify(tmp_home, project=project) if c.name == "project_override"]
    assert r.status == "supported", r.evidence


def test_dry_run_writes_nothing(oc, tmp_home: Path):
    result = oc.provision(tmp_home, enabled_skills=_enabled(), dry_run=True)
    assert result.dry_run is True
    assert result.diff, "dry run must describe the planned changes"
    assert not (tmp_home / ".config" / "opencode" / "opencode.jsonc").exists()


def test_uninstall_removes_all_owned_and_spares_source(oc, tmp_agents_home: Path,
                                                       tmp_home: Path):
    oc.provision(tmp_home, enabled_skills=_enabled())
    link = tmp_home / ".config" / "opencode" / "AGENTS.md"
    cfg = tmp_home / ".config" / "opencode" / "opencode.jsonc"
    alias = tmp_agents_home / "skills" / "easby-mastering"
    source_policy = tmp_agents_home / "AGENTS.md"
    assert link.exists() and cfg.exists() and alias.exists()
    removed = oc.uninstall(tmp_home)
    removed_str = " ".join(removed)
    assert "AGENTS.md" in removed_str
    assert "opencode.jsonc" in removed_str
    assert "easby-mastering" in removed_str
    assert not link.exists()
    assert not cfg.exists()
    assert not alias.exists()
    # source policy + nested source must survive
    assert source_policy.exists()
    assert (tmp_agents_home / "skills" / "easby" / "easby-mastering" / "SKILL.md").exists()
