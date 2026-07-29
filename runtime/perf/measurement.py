"""Small, dependency-free primitives for reproducible performance samples."""

from __future__ import annotations

import math
import statistics
import time
from collections.abc import Callable
from typing import Any, TypeVar

T = TypeVar("T")


def summarize_samples(samples_ms: list[float]) -> dict[str, float | list[float]]:
    """Return an explicit, machine-readable summary without hiding outliers."""
    if not samples_ms:
        raise ValueError("at least one sample is required")
    values = [float(value) for value in samples_ms]
    if not all(math.isfinite(value) and value >= 0 for value in values):
        raise ValueError("samples must be finite non-negative values")
    ordered = sorted(values)
    p95_index = max(0, math.ceil(len(ordered) * 0.95) - 1)
    return {
        "samples_ms": values,
        "min_ms": ordered[0],
        "median_ms": statistics.median(ordered),
        "p95_ms": ordered[p95_index],
        "max_ms": ordered[-1],
    }


def measure_samples(
    factory: Callable[[], T],
    *,
    samples: int,
    cleanup: Callable[[T], Any] | None = None,
) -> dict[str, float | list[float]]:
    """Measure a cold factory repeatedly and clean up every constructed value."""
    if not 1 <= samples <= 50:
        raise ValueError("samples must be between 1 and 50")
    measurements: list[float] = []
    for _ in range(samples):
        started = time.perf_counter()
        value = factory()
        measurements.append((time.perf_counter() - started) * 1000)
        if cleanup is not None:
            cleanup(value)
    return summarize_samples(measurements)
