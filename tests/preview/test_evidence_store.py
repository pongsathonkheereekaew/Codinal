"""Preview evidence store tests."""

import json

from runtime.preview import PreviewEvidenceStore


def test_add_list_clear_evidence_round_trip(tmp_path):
    store = PreviewEvidenceStore(tmp_path)
    store.add_evidence("s1", "console", "Uncaught TypeError at line 42")
    store.add_evidence(
        "s1",
        "annotation",
        {"x": 10, "y": 20, "w": 100, "h": 50, "note": "broken button"},
    )

    listed = store.list_evidence("s1")
    assert len(listed) == 2
    assert listed[0]["kind"] == "console"
    assert listed[0]["content"] == "Uncaught TypeError at line 42"
    assert listed[1]["kind"] == "annotation"
    assert isinstance(listed[1]["content"], dict)
    assert listed[1]["content"]["note"] == "broken button"

    cleared = store.clear_evidence("s1")
    assert cleared == 2
    assert store.list_evidence("s1") == []
    store.close()


def test_evidence_isolated_per_session(tmp_path):
    store = PreviewEvidenceStore(tmp_path)
    store.add_evidence("s1", "console", "error A")
    store.add_evidence("s2", "console", "error B")

    assert len(store.list_evidence("s1")) == 1
    assert len(store.list_evidence("s2")) == 1
    assert store.list_evidence("s1")[0]["content"] == "error A"
    store.close()


def test_rejects_invalid_kind(tmp_path):
    store = PreviewEvidenceStore(tmp_path)
    import pytest

    with pytest.raises(ValueError):
        store.add_evidence("s1", "bogus", "x")
    store.close()


def test_rejects_oversized_content(tmp_path):
    store = PreviewEvidenceStore(tmp_path)
    import pytest

    with pytest.raises(ValueError):
        store.add_evidence("s1", "console", "x" * 100_000)
    store.close()


def test_survives_restart(tmp_path):
    first = PreviewEvidenceStore(tmp_path)
    first.add_evidence("s1", "console", "persisted evidence")
    first.close()

    reopened = PreviewEvidenceStore(tmp_path)
    listed = reopened.list_evidence("s1")
    assert len(listed) == 1
    assert listed[0]["content"] == "persisted evidence"
    reopened.close()


def test_recovers_from_corrupt_database(tmp_path):
    first = PreviewEvidenceStore(tmp_path)
    first.add_evidence("s1", "console", "will be lost")
    first.close()

    (tmp_path / "preview.db").write_bytes(b"corrupt preview db")

    recovered = PreviewEvidenceStore(tmp_path)
    assert recovered.list_evidence("s1") == []

    preserved = list(
        (tmp_path / "recovery").glob("preview.db.corrupt-*.preserved")
    )
    assert preserved
    assert preserved[0].read_bytes() == b"corrupt preview db"
    recovered.close()
