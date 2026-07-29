"""Central performance-budget registry.

Aggregates the enforced limits scattered across the runtime into one
indexable place so tests and docs can reason about them without re-discovering
the constants. The registry references the real constants by import — a
constant change flows through automatically (no drift).
"""

from .budgets import BUDGETS, Budget, assert_within_budget
from .measurement import measure_samples, summarize_samples

__all__ = [
    "BUDGETS",
    "Budget",
    "assert_within_budget",
    "measure_samples",
    "summarize_samples",
]
