"""Manifest + schema contract: the shipped hosts.yaml must validate, and the
loader must reject drift early."""
from __future__ import annotations

import json
from pathlib import Path

import jsonschema
import pytest
import yaml

from lib import manifest


def test_shipped_manifest_validates(manifest_path: Path, schema_path: Path):
    data = manifest.load(manifest_path)
    schema = json.loads(schema_path.read_text())
    jsonschema.validate(data, schema)


def test_shipped_manifest_loads(manifest_path: Path):
    data = manifest.load(manifest_path)
    assert data["schema_version"] == 1
    assert data["hosts"]["opencode"]["tier"] == 1
    for host in ("opencode", "claude-code", "codex", "cursor",
                 "gemini-cli", "zcode", "openclaw", "hermes", "generic"):
        assert host in data["hosts"], host


def test_opencode_capability_vocabulary(manifest_path: Path):
    data = manifest.load(manifest_path)
    caps = data["hosts"]["opencode"]["capabilities"]
    for cap, entry in caps.items():
        assert entry["status"] in CapabilityStatus.VALID, cap
    for required in ("policy_file", "skill_discovery", "nested_skill_aliases",
                     "command_dir", "native_permissions", "config_merge",
                     "project_override", "uninstall_ownership"):
        assert required in caps, required


def test_invalid_manifest_rejected(tmp_path: Path, schema_path: Path):
    bad = tmp_path / "hosts.yaml"
    bad.write_text("schema_version: 1\nhosts:\n  BAD NAME:\n    tier: 9\n")
    schema = json.loads(schema_path.read_text())
    data = yaml.safe_load(bad.read_text())
    with pytest.raises(jsonschema.ValidationError):
        jsonschema.validate(data, schema)


# late import so the VALID set is exercised through the public symbol
from lib.manifest import CapabilityStatus  # noqa: E402
