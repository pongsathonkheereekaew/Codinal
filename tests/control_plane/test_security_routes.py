from __future__ import annotations

from types import SimpleNamespace

from fastapi.testclient import TestClient

from runtime.control_plane import create_control_plane_app


TOKEN = "test-session-token-with-at-least-32-characters"
AUTH = {"Authorization": f"Bearer {TOKEN}"}


class _Turns:
    async def recover(self):
        return 0

    async def shutdown(self):
        return None

    async def mutate_when_idle(self, _session_id, mutation):
        return mutation()


class _Git:
    def load(self, session_id):
        return SimpleNamespace(source_root="/workspace") if session_id == "session-1" else None

    def close(self):
        return None


class _Security:
    def status(self):
        return {"available": True, "max_cost_usd": 5}

    def scan(self, session_id, root):
        assert (session_id, root) == ("session-1", "/workspace")
        return {
            "ok": True,
            "finding_count": 1,
            "coverage": {"status": "complete"},
            "max_cost_usd": 5,
        }


class _Audit:
    def __init__(self):
        self.events = []

    def record(self, *args, **kwargs):
        self.events.append((args, kwargs))


def test_security_routes_require_a_git_session_and_audit_scans():
    audit = _Audit()
    services = SimpleNamespace(
        turns=_Turns(), git=_Git(), security=_Security(), audit=audit,
        restores=None, goals=None, workers=None, builds=None, mcp=None,
    )
    with TestClient(create_control_plane_app(token=TOKEN, services=services)) as client:
        status = client.get("/v1/security/status", headers=AUTH)
        scan = client.post("/v1/sessions/session-1/security/scan", headers=AUTH)
        missing = client.post("/v1/sessions/missing/security/scan", headers=AUTH)

    assert status.json() == {"available": True, "max_cost_usd": 5}
    assert scan.status_code == 200
    assert scan.json()["finding_count"] == 1
    assert missing.status_code == 404
    assert audit.events[0][0][:3] == ("security", "scan",)
