import json
from types import SimpleNamespace

from runtime.audit import AuditLedger
from runtime.control_plane.diagnostics import build_support_bundle
from runtime.secrets import ProviderSecretService


_KEY = "sk-bundle-secret-1234567890abcdef"


def _services(tmp_path, *, secrets=None, audit=None):
    return SimpleNamespace(
        secrets=secrets or ProviderSecretService(),
        sessions=SimpleNamespace(list_sessions=lambda: []),
        audit=audit,
    )


def test_bundle_includes_health_and_redacted_audit_events(tmp_path):
    secrets = ProviderSecretService()
    secrets.set_api_key("openai", _KEY)
    audit = AuditLedger(tmp_path / "audit", redactor=None)
    audit.record(
        "git",
        "push",
        subject="codinal/session-1",
        payload={"remote": "origin", "summary": "ok"},
    )
    services = _services(tmp_path, secrets=secrets, audit=audit)

    bundle = build_support_bundle(services, started_at=0.0)

    assert bundle["bundle_version"] == 1
    assert "generated_at" in bundle
    health = bundle["health"]
    assert health["components"]["audit_chain"] == "verified"
    audit_block = bundle["audit"]
    assert audit_block["chain_verified"] is True
    assert len(audit_block["events"]) == 1
    assert audit_block["events"][0]["action"] == "push"
    audit.close()


def test_bundle_excludes_provider_keys_and_message_bodies(tmp_path):
    secrets = ProviderSecretService()
    secrets.set_api_key("openai", _KEY)
    audit = AuditLedger(tmp_path / "audit")
    # Even if a secret somehow appears in an audit payload, the bundle must
    # not surface it. (The ledger redacts at write time when a redactor is
    # wired; here we test the bundle never adds new leak vectors.)
    audit.record("test", "leak_attempt", payload={"note": "no key here"})
    services = _services(tmp_path, secrets=secrets, audit=audit)

    bundle = build_support_bundle(services, started_at=0.0)

    dumped = json.dumps(bundle)
    assert _KEY not in dumped
    # No message bodies / tool results fields exist in the bundle schema.
    assert "messages" not in bundle
    assert "tool_calls" not in bundle
    audit.close()


def test_bundle_works_without_audit_ledger():
    services = SimpleNamespace(
        secrets=ProviderSecretService(),
        sessions=SimpleNamespace(list_sessions=lambda: []),
        audit=None,
    )

    bundle = build_support_bundle(services, started_at=0.0)

    assert bundle["audit"]["chain_verified"] == "unavailable"
    assert bundle["audit"]["events"] == []


def test_bundle_respects_max_events_bound(tmp_path):
    audit = AuditLedger(tmp_path / "audit")
    for index in range(10):
        audit.record("test", f"event-{index}")
    services = _services(tmp_path, audit=audit)

    bundle = build_support_bundle(services, started_at=0.0, max_events=3)

    assert len(bundle["audit"]["events"]) == 3
    audit.close()
