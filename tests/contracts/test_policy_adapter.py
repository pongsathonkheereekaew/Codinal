"""PolicyLinkAdapter contract — the config-driven adapter used by every
non-OpenCode Tier-1/2 host. Verifies honest status reporting: provisioning
creates the expected symlinks, verify() never over-claims."""
from __future__ import annotations

from pathlib import Path

from adapters.base import PolicyLinkAdapter
from lib import manifest


def _build(name: str, manifest_path: Path, tmp_agents_home: Path, home: Path):
    data = manifest.load(manifest_path)
    a = PolicyLinkAdapter(
        entry=data["hosts"][name], baseline=data["permission_baseline"],
        agents_home=tmp_agents_home, policy_source=tmp_agents_home / "AGENTS.md",
        commands_source=tmp_agents_home / "commands")
    a.name = name
    return a


def test_codex_provision_and_verify(tmp_agents_home: Path, tmp_home: Path, manifest_path: Path):
    a = _build("codex", manifest_path, tmp_agents_home, tmp_home)
    pr = a.provision(tmp_home)
    assert not pr.conflicts, pr.conflicts
    link = tmp_home / ".codex" / "AGENTS.md"
    assert link.is_symlink() and link.exists()
    results = {r.name: r for r in a.verify(tmp_home)}
    assert results["policy_file"].status == "supported"
    # codex has no command_dir in the manifest -> honest unsupported
    assert results["command_dir"].status == "unsupported"
    # native_permissions declared unverified (not yet implemented) -> stays so
    assert results["native_permissions"].status == "unverified"


def test_zcode_commands_wired(tmp_agents_home: Path, tmp_home: Path, manifest_path: Path):
    a = _build("zcode", manifest_path, tmp_agents_home, tmp_home)
    a.provision(tmp_home)
    assert (tmp_home / ".zcode" / "commands").exists()
    results = {r.name: r for r in a.verify(tmp_home)}
    assert results["command_dir"].status == "supported"


def test_honest_no_overclaim_when_missing(tmp_agents_home: Path, tmp_home: Path, manifest_path: Path):
    a = _build("codex", manifest_path, tmp_agents_home, tmp_home)
    results = {r.name: r for r in a.verify(tmp_home)}  # no provision first
    assert results["policy_file"].status == "unsupported"
    assert "missing" in results["policy_file"].evidence


def test_uninstall_removes_only_owned(tmp_agents_home: Path, tmp_home: Path, manifest_path: Path):
    a = _build("codex", manifest_path, tmp_agents_home, tmp_home)
    a.provision(tmp_home)
    link = tmp_home / ".codex" / "AGENTS.md"
    source = tmp_agents_home / "AGENTS.md"
    assert link.exists() and source.exists()
    removed = a.uninstall(tmp_home)
    assert any(".codex/AGENTS.md" in r for r in removed)
    assert not link.exists()
    # REGRESSION: uninstall must never delete the source policy the link points to
    assert source.exists(), "uninstall deleted the source policy file!"
