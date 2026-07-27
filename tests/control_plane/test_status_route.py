from types import SimpleNamespace

from fastapi.testclient import TestClient

from runtime.audit import AuditLedger
from runtime.control_plane import create_control_plane_app
from runtime.events import EventHub
from runtime.oauth import OAuthCoordinator
from runtime.secrets import ProviderSecretService


TOKEN = "test-session-token-with-at-least-32-characters"
AUTH = {"Authorization": f"Bearer {TOKEN}"}


class _FakeTurns:
    async def recover(self):
        return 0

    async def shutdown(self):
        return True

    def is_active(self, _session_id):
        return False


class _FakeMcp:
    async def recover(self):
        return 0

    async def aclose(self):
        return None


def _client(tmp_path, *, secrets=None, audit=None):
    services = SimpleNamespace(
        events=EventHub(),
        settings={},
        secrets=secrets or ProviderSecretService(),
        oauth=OAuthCoordinator(),
        turns=_FakeTurns(),
        sessions=SimpleNamespace(list_sessions=lambda: []),
        mcp=_FakeMcp(),
        git=None,
        restores=None,
        approvals=None,
        interactions=None,
        plans=None,
        workers=None,
        builds=None,
        goals=None,
        audit=audit,
    )
    return TestClient(create_control_plane_app(token=TOKEN, services=services))


def test_status_route_returns_structured_secret_safe_health(tmp_path):
    secrets = ProviderSecretService()
    secrets.set_api_key("openai", "sk-super-secret-key-1234567890")
    audit = AuditLedger(tmp_path / "audit")
    client = _client(tmp_path, secrets=secrets, audit=audit)

    with client:
        response = client.get("/v1/status", headers=AUTH)

    assert response.status_code == 200
    body = response.json()
    assert "version" in body
    assert isinstance(body["uptime_seconds"], (int, float))
    assert body["uptime_seconds"] >= 0
    components = body["components"]
    assert components["audit_chain"] == "verified"
    assert components["session_count"] == 0
    providers = components["providers"]
    assert any(
        p["provider"] == "openai" and p["configured"] is True for p in providers
    )
    # No secret value leaks.
    assert "sk-super-secret-key-1234567890" not in response.text


def test_status_route_reports_tampered_audit_chain(tmp_path):
    audit = AuditLedger(tmp_path / "audit")
    audit.record("test", "event")
    audit.close()
    # Tamper: rewrite a row directly.
    import sqlite3

    conn = sqlite3.connect(tmp_path / "audit" / "audit.db")
    conn.execute("UPDATE events SET subject = 'forged'")
    conn.commit()
    conn.close()

    reopened = AuditLedger(tmp_path / "audit")
    client = _client(tmp_path, audit=reopened)
    try:
        with client:
            response = client.get("/v1/status", headers=AUTH)
        assert response.status_code == 200
        assert response.json()["components"]["audit_chain"] == "tampered"
    finally:
        reopened.close()


def test_status_route_requires_auth(tmp_path):
    client = _client(tmp_path)
    with client:
        response = client.get("/v1/status")
    assert response.status_code == 401


def test_audit_route_returns_events_and_chain_verification(tmp_path):
    audit = AuditLedger(tmp_path / "audit")
    audit.record("mcp", "connect", subject="server-a")
    audit.record("git", "push", subject="codinal/session-1")
    client = _client(tmp_path, audit=audit)
    try:
        with client:
            all_events = client.get("/v1/audit", headers=AUTH)
            filtered = client.get(
                "/v1/audit?domain=mcp", headers=AUTH
            )
    finally:
        audit.close()

    assert all_events.status_code == 200
    body = all_events.json()
    assert body["chain_verified"] is True
    actions = [event["action"] for event in body["events"]]
    assert "connect" in actions
    assert "push" in actions

    assert filtered.status_code == 200
    filtered_body = filtered.json()
    assert all(
        event["domain"] == "mcp" for event in filtered_body["events"]
    )


def test_audit_route_respects_limit_bound(tmp_path):
    audit = AuditLedger(tmp_path / "audit")
    for index in range(10):
        audit.record("test", f"event-{index}")
    client = _client(tmp_path, audit=audit)
    try:
        with client:
            response = client.get("/v1/audit?limit=3", headers=AUTH)
    finally:
        audit.close()

    assert response.status_code == 200
    assert len(response.json()["events"]) == 3


def test_audit_route_returns_503_when_ledger_unavailable(tmp_path):
    client = _client(tmp_path, audit=None)
    with client:
        response = client.get("/v1/audit", headers=AUTH)
    assert response.status_code == 503
    assert response.json()["detail"] == "audit ledger unavailable"


def test_audit_route_requires_auth(tmp_path):
    audit = AuditLedger(tmp_path / "audit")
    client = _client(tmp_path, audit=audit)
    try:
        with client:
            response = client.get("/v1/audit")
    finally:
        audit.close()
    assert response.status_code == 401
