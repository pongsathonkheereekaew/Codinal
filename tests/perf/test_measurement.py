from __future__ import annotations

import pytest

from runtime.perf.measurement import measure_samples, summarize_samples

pytestmark = pytest.mark.perf


def test_summarize_samples_reports_stable_percentiles() -> None:
    result = summarize_samples([4.0, 1.0, 3.0, 2.0])

    assert result == {
        "samples_ms": [4.0, 1.0, 3.0, 2.0],
        "min_ms": 1.0,
        "median_ms": 2.5,
        "p95_ms": 4.0,
        "max_ms": 4.0,
    }


def test_summarize_samples_rejects_missing_or_invalid_values() -> None:
    with pytest.raises(ValueError, match="at least one"):
        summarize_samples([])
    with pytest.raises(ValueError, match="finite"):
        summarize_samples([float("inf")])


def test_measure_samples_closes_each_created_resource() -> None:
    closed: list[int] = []

    def factory() -> int:
        return len(closed)

    result = measure_samples(factory, samples=3, cleanup=closed.append)

    assert len(result["samples_ms"]) == 3
    assert closed == [0, 1, 2]
