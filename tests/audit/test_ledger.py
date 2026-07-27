import json
import sqlite3

from runtime.audit import AuditLedger


def test_ledger_chains_events_and_round_trips_payload(tmp_path):
    ledger = AuditLedger(tmp_path)
    first = ledger.record(
        "mcp",
        "connect",
        actor="host",
        subject="server-a",
        payload={"transport": "stdio", "tools": ["search"]},
    )
    second = ledger.record(
        "mcp",
        "disable",
        subject="server-a",
        payload={"reason": "policy"},
    )

    assert first["prev_hash"] == "0" * 64
    assert second["prev_hash"] == first["hash"]
    assert first["hash"] != second["hash"]

    rows = ledger.list(domain="mcp")
    assert [row["action"] for row in rows] == ["disable", "connect"]
    assert rows[1]["payload"] == {
        "transport": "stdio",
        "tools": ["search"],
    }
    assert ledger.verify_chain() is True
    ledger.close()


def test_ledger_detects_tampered_row(tmp_path):
    ledger = AuditLedger(tmp_path)
    ledger.record("mcp", "connect", subject="server-a")
    ledger.record("mcp", "disable", subject="server-a")
    ledger.close()

    connection = sqlite3.connect(tmp_path / "audit.db")
    connection.execute(
        "UPDATE events SET subject = 'forged' WHERE action = ?",
        ("connect",),
    )
    connection.commit()
    connection.close()

    reopened = AuditLedger(tmp_path)
    assert reopened.verify_chain() is False
    reopened.close()


def test_ledger_survives_restart_and_keeps_chain(tmp_path):
    first = AuditLedger(tmp_path)
    first.record("mcp", "connect", subject="server-a")
    first.record("mcp", "disable", subject="server-a")
    first.close()

    restarted = AuditLedger(tmp_path)
    rows = restarted.list(domain="mcp")
    assert [row["action"] for row in rows] == ["disable", "connect"]
    assert restarted.verify_chain() is True

    restarted.record("mcp", "disconnect", subject="server-a")
    assert restarted.verify_chain() is True
    restarted.close()


def test_ledger_recovers_from_corrupt_database_preserving_evidence(tmp_path):
    first = AuditLedger(tmp_path)
    first.record("mcp", "connect", subject="server-a")
    first.close()

    (tmp_path / "audit.db").write_bytes(b"corrupt audit db")

    recovered = AuditLedger(tmp_path)
    assert recovered.list() == []
    assert recovered.verify_chain() is True

    preserved = list((tmp_path / "recovery").glob("audit.db.corrupt-*.preserved"))
    assert preserved and preserved[0].read_bytes() == b"corrupt audit db"

    events_log = json.loads(
        (tmp_path / "recovery" / "events.jsonl").read_text().splitlines()[0]
    )
    assert events_log["action"] == "preserved_corrupt_state"
    recovered.close()
