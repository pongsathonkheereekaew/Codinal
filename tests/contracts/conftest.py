"""Isolated fixtures: real manifest/schema/policy from the repo, throwaway
AGENTS_HOME + HOME per test so nothing touches the live machine."""
from __future__ import annotations

import os
import shutil
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[2]
HARNESS = REPO / "harness"
# Make scripts/lib + scripts/adapters importable in the dev tree
# (harness content moved under harness/ in the Codinal migration).
for sub in ("scripts",):
    p = HARNESS / sub
    if str(p) not in sys.path:
        sys.path.insert(0, str(p))


@pytest.fixture()
def repo_root() -> Path:
    return REPO


@pytest.fixture()
def manifest_path(repo_root: Path) -> Path:
    return HARNESS / "config" / "hosts.yaml"


@pytest.fixture()
def schema_path(repo_root: Path) -> Path:
    return HARNESS / "schemas" / "host-capability.schema.json"


@pytest.fixture()
def tmp_agents_home(tmp_path: Path) -> Path:
    """A fake ~/.agents SSOT: minimal skills tree (incl. nested), policy,
    commands, and writable state/ + backups/ dirs."""
    home = tmp_path / "agents-home"
    skills = home / "skills"
    # flat core skills
    (skills / "ask-matt").mkdir(parents=True)
    (skills / "ask-matt" / "SKILL.md").write_text(
        "---\nname: ask-matt\ndescription: Router skill.\n---\nbody\n"
    )
    (skills / "implement").mkdir(parents=True)
    (skills / "implement" / "SKILL.md").write_text(
        "---\nname: implement\ndescription: Implement a ticket.\n---\nbody\n"
    )
    # nested skills (mirror the real layout under skills/easby + skills/insurance)
    (skills / "easby" / "easby-mastering").mkdir(parents=True)
    (skills / "easby" / "easby-mastering" / "SKILL.md").write_text(
        "---\nname: easby-mastering\ndescription: Mastering KB.\n---\nbody\n"
    )
    (skills / "insurance" / "nuiny").mkdir(parents=True)
    (skills / "insurance" / "nuiny" / "SKILL.md").write_text(
        "---\nname: nuiny\ndescription: Slide deck builder.\n---\nbody\n"
    )
    # policy + commands
    (home / "AGENTS.md").write_text("# universal agent policy\n")
    (home / "commands").mkdir()
    (home / "commands" / "harness-sync.md").write_text("# sync\n")
    # staged manifest + schema so the CLI can load from agents_home
    shutil.copytree(HARNESS / "config", home / "config")
    shutil.copytree(HARNESS / "schemas", home / "schemas")
    # runtime state
    (home / "state").mkdir()
    (home / "backups").mkdir()
    return home


@pytest.fixture()
def tmp_home(tmp_path: Path) -> Path:
    """An empty HOME directory the adapter writes into."""
    h = tmp_path / "home"
    h.mkdir()
    return h


@pytest.fixture(autouse=True)
def _no_real_home(monkeypatch):
    """Guarantee no test accidentally reads the real $HOME."""
    monkeypatch.setenv("HOME", "/__disabled__")
    yield
