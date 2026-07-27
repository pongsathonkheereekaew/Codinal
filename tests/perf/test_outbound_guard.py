"""Outbound history soft-cap guard."""

from __future__ import annotations

import pytest

from runtime.policy import Mode, PermissionEngine, ToolManifest
from runtime.providers import ModelCapabilities, ProviderClient
from runtime.tools import ToolRegistry
from runtime.turn_engine import TurnEngine


pytestmark = pytest.mark.perf


class _NoopProvider(ProviderClient):
    def complete(self, **_kwargs):
        raise AssertionError("perf test should not call provider")

    def capabilities(self, _model):
        return ModelCapabilities()


def _engine_with_history(tmp_path, count):
    messages = [{"role": "system", "content": "system"}] + [
        {"role": "user", "content": f"turn {i}"} for i in range(count)
    ]
    return TurnEngine(
        provider=_NoopProvider(),
        registry=ToolRegistry(ToolManifest()),
        permissions=PermissionEngine(tmp_path, mode=Mode.INTERACTIVE),
        model="openai:gpt-test",
        messages=messages,
    )


def test_outbound_drops_oldest_when_over_budget(tmp_path):
    from runtime.turn_engine.engine import _MAX_OUTBOUND_MESSAGES

    over = _MAX_OUTBOUND_MESSAGES + 50
    engine = _engine_with_history(tmp_path, over)

    outbound = engine._outbound_messages()

    # System preserved + notice + at most _MAX_OUTBOUND_MESSAGES total.
    assert len(outbound) <= _MAX_OUTBOUND_MESSAGES
    roles = [m.get("role") for m in outbound]
    assert roles[0] == "system"  # original system kept
    assert any("omitted" in str(m.get("content", "")) for m in outbound)
    # The most recent messages survived.
    assert outbound[-1]["content"] == f"turn {over - 1}"


def test_outbound_keeps_everything_under_budget(tmp_path):
    from runtime.turn_engine.engine import _MAX_OUTBOUND_MESSAGES

    engine = _engine_with_history(tmp_path, 100)

    outbound = engine._outbound_messages()

    assert len(outbound) == 101  # system + 100 user
    assert not any("omitted" in str(m.get("content", "")) for m in outbound)
    assert _MAX_OUTBOUND_MESSAGES >= 1000  # sanity: budget is generous
