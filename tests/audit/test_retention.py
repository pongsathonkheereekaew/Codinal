"""Audit ledger retention: prune + re-chain integrity."""

from __future__ import annotations

import os

from runtime.audit import AuditLedger
from runtime.audit.ledger import _MAX_EVENTS


def test_prune_removes_oldest_and_preserves_chain(tmp_path):
    ledger = AuditLedger(tmp_path / "audit")
    # Insert a small number of events then manually exceed the cap.
    for i in range(20):
        ledger.record("test", f"event-{i}", subject=f"s-{i}")
    assert ledger.count() == 20
    assert ledger.verify_chain() is True

    # Force prune by temporarily lowering the cap.
    import runtime.audit.ledger as mod
    original = mod._MAX_EVENTS
    mod._MAX_EVENTS = 10
    try:
        removed = ledger.prune()
    finally:
        mod._MAX_EVENTS = original

    assert removed == 10
    assert ledger.count() == 10
    # The surviving chain still verifies (oldest was re-chained to genesis).
    assert ledger.verify_chain() is True

    # The oldest surviving event is event-10 (0-9 were pruned).
    rows = list(reversed(ledger.list(limit=20)))
    assert rows[0]["action"] == "event-10"
    ledger.close()


def test_prune_noop_when_under_cap(tmp_path):
    ledger = AuditLedger(tmp_path / "audit")
    for i in range(5):
        ledger.record("test", f"event-{i}")

    removed = ledger.prune()

    assert removed == 0
    assert ledger.count() == 5
    assert ledger.verify_chain() is True
    ledger.close()


def test_retention_fires_automatically_on_record(tmp_path):
    """record() auto-prunes when the cap is exceeded."""
    import runtime.audit.ledger as mod
    original = mod._MAX_EVENTS
    mod._MAX_EVENTS = 10
    try:
        ledger = AuditLedger(tmp_path / "audit")
        for i in range(15):
            ledger.record("test", f"event-{i}")
        assert ledger.count() == 10
        assert ledger.verify_chain() is True
        ledger.close()
    finally:
        mod._MAX_EVENTS = original


def test_count_returns_total_events(tmp_path):
    ledger = AuditLedger(tmp_path / "audit")
    assert ledger.count() == 0
    ledger.record("test", "a")
    ledger.record("test", "b")
    assert ledger.count() == 2
    ledger.close()
