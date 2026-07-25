"""Skill model contract — classification, journal lifecycle, audit, and the
OpenCode native `permission.skill.deny` wiring."""
from __future__ import annotations

import json
from pathlib import Path

from adapters import opencode as opencode_adapter
from lib import manifest, skills as skills_lib


def _stage_core_yaml(tmp_agents_home: Path):
    (tmp_agents_home / "config").mkdir(exist_ok=True)
    (tmp_agents_home / "config" / "skills.yaml").write_text(
        "schema_version: 1\ncore: [ask-matt]\ndeprecated_frontmatter: [disable-model-invocation]\n"
    )


def test_classification_core_vs_catalog(tmp_agents_home: Path):
    _stage_core_yaml(tmp_agents_home)
    classes = skills_lib.classify(tmp_agents_home)
    assert classes["ask-matt"] == "core"
    assert classes["implement"] == "catalog"
    assert classes["easby-mastering"] == "catalog"   # nested leaf
    assert classes["nuiny"] == "catalog"


def test_journal_disable_enable_reset(tmp_agents_home: Path):
    _stage_core_yaml(tmp_agents_home)
    j = skills_lib.SkillJournal(tmp_agents_home)
    assert j.disabled() == set()
    assert j.disable("implement") is True
    assert j.disable("implement") is False   # idempotent
    assert j.disabled() == {"implement"}
    assert j.enable("implement") is True
    assert j.disabled() == set()
    j.disable("nuiny")
    prev = j.reset()
    assert prev == {"nuiny"}
    assert j.disabled() == set()


def test_core_cannot_be_disabled_via_audit(tmp_agents_home: Path):
    _stage_core_yaml(tmp_agents_home)
    j = skills_lib.SkillJournal(tmp_agents_home)
    # forcibly write a core name into the blacklist
    j.path.write_text(json.dumps({"disabled": ["ask-matt"], "schema_version": 1}))
    report = skills_lib.audit(tmp_agents_home)
    assert any("core skill cannot be disabled" in i for i in report["issues"])


def test_audit_flags_missing_core_and_unknown_disabled(tmp_agents_home: Path):
    _stage_core_yaml(tmp_agents_home)
    # core lists 'ask-matt' (exists); add a bogus core + bogus disabled entry
    (tmp_agents_home / "config" / "skills.yaml").write_text(
        "schema_version: 1\ncore: [ask-matt, ghost-skill]\n"
    )
    j = skills_lib.SkillJournal(tmp_agents_home)
    j.disable("implement")
    j.path.write_text(json.dumps({"disabled": ["implement", "no-such-skill"], "schema_version": 1}))
    report = skills_lib.audit(tmp_agents_home)
    issues = " ".join(report["issues"])
    assert "ghost-skill" in issues
    assert "no-such-skill" in issues


def test_opencode_apply_skill_state_adds_deny(tmp_agents_home: Path, tmp_home: Path,
                                              manifest_path: Path):
    _stage_core_yaml(tmp_agents_home)
    data = manifest.load(manifest_path)
    oc = opencode_adapter.OpenCodeAdapter(
        entry=data["hosts"]["opencode"], baseline=data["permission_baseline"],
        agents_home=tmp_agents_home, policy_source=tmp_agents_home / "AGENTS.md",
        commands_source=tmp_agents_home / "commands")
    oc.provision(tmp_home, enabled_skills={"ask-matt", "implement", "easby-mastering"})

    res = oc.apply_skill_state(tmp_home, disabled={"easby-mastering", "implement"})
    assert not res.conflicts, res.conflicts
    from lib import jsonc
    obj = jsonc.loads((tmp_home / ".config" / "opencode" / "opencode.jsonc").read_text())
    assert obj["permission"]["skill"] == {"easby-mastering": "deny", "implement": "deny"}
    # baseline still intact
    assert obj["permission"]["read"] == "allow"
    assert obj["permission"]["bash"]["*"] == "ask"


def test_opencode_apply_skill_state_user_permission_conflict(tmp_agents_home: Path,
                                                             tmp_home: Path,
                                                             manifest_path: Path):
    _stage_core_yaml(tmp_agents_home)
    data = manifest.load(manifest_path)
    oc = opencode_adapter.OpenCodeAdapter(
        entry=data["hosts"]["opencode"], baseline=data["permission_baseline"],
        agents_home=tmp_agents_home, policy_source=tmp_agents_home / "AGENTS.md",
        commands_source=tmp_agents_home / "commands")
    # user-owned custom permission (not harness baseline shape)
    cfgp = tmp_home / ".config" / "opencode" / "opencode.jsonc"
    cfgp.parent.mkdir(parents=True, exist_ok=True)
    cfgp.write_text('{\n  "$schema": "x",\n  "permission": {"*": "allow"}\n}\n')
    res = oc.apply_skill_state(tmp_home, disabled={"implement"})
    assert res.conflicts, "expected a conflict, not a silent overwrite"
    # file untouched
    assert '"*": "allow"' in cfgp.read_text()
