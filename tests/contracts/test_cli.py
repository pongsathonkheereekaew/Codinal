"""CLI contract — `harness host` / `harness verify` end-to-end against an
isolated agents-home + target home. Reuses the same fixtures as the adapter
tests so the seam is identical."""
from __future__ import annotations

import json
from pathlib import Path

import pytest

# imported at collection time (before the HOME-disabling fixture runs), so
# jsonschema/yaml resolve from the real user-site.
import harness_host


@pytest.fixture()
def cli(tmp_agents_home: Path, tmp_home: Path):
    """Return a helper that invokes the CLI against the isolated tree."""
    def _run(*argv: str) -> tuple[int, str]:
        full = ["--agents-home", str(tmp_agents_home)] + list(argv)
        code = harness_host.main(full)
        return code, ""
    return _run


def test_host_list(cli, capsys):
    code, _ = cli("host", "list")
    out = capsys.readouterr().out
    assert code == 0
    assert "opencode" in out
    assert "claude-code" in out


def test_host_inspect(cli, capsys):
    cli("host", "inspect", "opencode")
    out = capsys.readouterr().out
    assert "native_permissions" in out
    assert "config_merge" in out


def test_provision_then_verify(tmp_agents_home: Path, tmp_home: Path, capsys):
    agents = ["--agents-home", str(tmp_agents_home)]
    rc = harness_host.main(agents + ["host", "provision", "opencode",
                                     "--home", str(tmp_home),
                                     "--enable", "easby-mastering"])
    assert rc == 0, capsys.readouterr().out
    capsys.readouterr()  # drain provision output
    # effective state
    rc = harness_host.main(agents + ["verify", "--host", "opencode",
                                     "--home", str(tmp_home), "--json"])
    out = capsys.readouterr().out
    rows = json.loads(out)
    by_cap = {r["capability"]: r["status"] for r in rows}
    assert by_cap["policy_file"] == "supported"
    assert by_cap["command_dir"] == "supported"
    assert by_cap["native_permissions"] == "supported"
    assert by_cap["nested_skill_aliases"] == "supported"


def test_verify_tier1_gate_blocks_ready(tmp_agents_home: Path, tmp_home: Path, capsys):
    # claude-code has no adapter -> its Tier-1 capabilities stay unverified
    rc = harness_host.main(["--agents-home", str(tmp_agents_home),
                            "verify", "--host", "claude-code",
                            "--home", str(tmp_home)])
    assert rc == 1  # NOT READY
