"""Extension registry tests — register/list/enable/disable/remove/verify."""

import json

import pytest

from runtime.extensions import ExtensionRegistry


def _manifest(**overrides):
    base = {
        "kind": "skill",
        "name": "my-skill",
        "version": "1.0.0",
        "publisher": "acme",
        "requested_permissions": ["read_file"],
    }
    base.update(overrides)
    return base


def test_register_and_list(tmp_path):
    reg = ExtensionRegistry(tmp_path)
    pkg = reg.register(_manifest())
    assert pkg.id == "acme/my-skill"
    assert pkg.kind == "skill"
    assert pkg.enabled is True
    assert pkg.manifest_hash  # SHA-256 hex
    assert len(pkg.requested_permissions) == 1

    listed = reg.list()
    assert len(listed) == 1
    assert listed[0].id == "acme/my-skill"
    reg.close()


def test_enable_disable(tmp_path):
    reg = ExtensionRegistry(tmp_path)
    reg.register(_manifest())
    assert reg.set_enabled("acme/my-skill", False) is True
    pkg = reg.get("acme/my-skill")
    assert pkg.enabled is False
    assert reg.set_enabled("acme/my-skill", True) is True
    assert reg.get("acme/my-skill").enabled is True
    reg.close()


def test_remove(tmp_path):
    reg = ExtensionRegistry(tmp_path)
    reg.register(_manifest())
    assert reg.remove("acme/my-skill") is True
    assert reg.get("acme/my-skill") is None
    assert reg.remove("acme/my-skill") is False
    reg.close()


def test_verify_provenance(tmp_path):
    reg = ExtensionRegistry(tmp_path)
    reg.register(_manifest())
    assert reg.verify("acme/my-skill") is True
    reg.close()


def test_verify_detects_tampered_manifest(tmp_path):
    reg = ExtensionRegistry(tmp_path)
    reg.register(_manifest())
    reg.close()
    # Directly modify the stored manifest hash to simulate tampering.
    conn = sqlite3.connect(tmp_path / "extensions.db")
    conn.execute(
        "UPDATE extensions SET manifest_hash = 'tampered' WHERE id = ?",
        ("acme/my-skill",),
    )
    conn.commit()
    conn.close()

    reopened = ExtensionRegistry(tmp_path)
    assert reopened.verify("acme/my-skill") is False
    reopened.close()


def test_survives_restart(tmp_path):
    reg = ExtensionRegistry(tmp_path)
    reg.register(_manifest(name="persisted"))
    reg.close()

    reopened = ExtensionRegistry(tmp_path)
    assert len(reopened.list()) == 1
    assert reopened.get("acme/persisted").version == "1.0.0"
    reopened.close()


def test_invalid_manifest_rejected(tmp_path):
    reg = ExtensionRegistry(tmp_path)
    with pytest.raises(ValueError):
        reg.register({"kind": "bogus", "name": "x", "version": "1", "publisher": "p"})
    reg.close()


import sqlite3  # noqa: E402 (needed for tamper test)
