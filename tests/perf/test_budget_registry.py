"""Registry-completeness test: every budget resolves to a real constant."""

from __future__ import annotations

import importlib

import pytest

from runtime.perf import BUDGETS, assert_within_budget


pytestmark = pytest.mark.perf


def test_registry_has_entries():
    assert len(BUDGETS) >= 30, "registry must index the enforced limits"


def test_every_budget_resolves_to_a_real_module_constant():
    """No drift: each budget's source path must import and expose the value."""
    for name, budget in BUDGETS.items():
        module_path, const_name = budget.source.rsplit(":", 1)
        # Some sources name a function:line (e.g. mcp.call_timeout); skip those.
        if "." in const_name or "(" in const_name:
            continue
        module = importlib.import_module(module_path)
        assert hasattr(module, const_name), (
            f"{name}: source {budget.source} does not expose {const_name}"
        )
        actual = getattr(module, const_name)
        assert actual == budget.limit, (
            f"{name}: registry limit {budget.limit} != source {actual}"
        )


def test_assert_within_budget_passes_under_limit():
    # seconds budget allows 2x headroom.
    assert_within_budget("search.max_seconds", 3.9)


def test_assert_within_budget_rejects_over_limit():
    with pytest.raises(AssertionError, match="exceeded budget"):
        assert_within_budget("search.max_seconds", 5.0)


def test_assert_within_budget_rejects_unknown():
    with pytest.raises(KeyError):
        assert_within_budget("no.such.budget", 1.0)
