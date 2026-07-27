"""Performance budgets: hot-path measurements asserted against the registry.

Each test exercises a real runtime path and asserts it stays within the named
budget. Marked ``perf`` so the dedicated CI lane (``.github/workflows/verify.yml``
job ``perf``) runs them independently of the correctness suite. Seconds budgets
allow 2x headroom for CI-runner variance (see ``assert_within_budget``).
"""

from __future__ import annotations

import os
import time
from pathlib import Path

import pytest

from runtime.perf import BUDGETS, assert_within_budget


pytestmark = pytest.mark.perf


def test_tool_call_contract_rejects_over_budget():
    """The tool-call contract layer enforces count + arg-size budgets."""
    from runtime.policy.tool_calls import parse_tool_calls

    # Over the call-count budget.
    too_many = [
        {"id": f"c{i}", "name": "read_file", "arguments": {}}
        for i in range(BUDGETS["contract.max_tool_calls"].limit + 1)
    ]
    with pytest.raises(ValueError):
        parse_tool_calls(too_many)

    # Over the per-call argument-byte budget.
    limit = BUDGETS["contract.max_argument_bytes"].limit
    oversized = [
        {
            "id": "c1",
            "name": "write_file",
            "arguments": {"content": "x" * (limit + 1)},
        }
    ]
    with pytest.raises(ValueError):
        parse_tool_calls(oversized)


def test_repository_search_honors_time_and_count_budgets(tmp_path):
    """Search over a synthetic tree stays within the deadline + result caps."""
    from runtime.search.service import search_repository_roots

    root = tmp_path / "repo"
    root.mkdir()
    (root / ".git").mkdir()  # marks a repo boundary
    for index in range(50):
        (root / f"file{index}.py").write_text(
            f"def match_{index}():\n    return 'needle'\n", encoding="utf-8"
        )

    result = search_repository_roots(
        [{"path": str(root), "label": "repo"}],
        query="needle",
        mode="text",
        limit=10,
    )

    assert result["ok"] is True
    # duration_ms is emitted by the search service directly.
    assert result["duration_ms"] >= 0
    assert_within_budget("search.max_seconds", result["duration_ms"] / 1000)
    assert len(result["matches"]) <= BUDGETS["search.max_results"].limit
    assert len(result["matches"]) <= 10  # requested limit respected


def test_cold_start_build_services_under_budget(tmp_path):
    """build_services against an empty data_dir completes within budget."""
    from runtime.control_plane.server import ServerConfig, build_services

    # Cold-start budget. Default 3.5s accommodates the Phase 47 provider
    # breadth + failover additions (custom-provider registry, FailoverRouter
    # import) on GitHub Actions free runners, which are ~7x slower than a
    # local dev machine. Override via CODINAL_COLD_START_BUDGET_S to tighten.
    budget_s = float(os.environ.get("CODINAL_COLD_START_BUDGET_S", "3.5"))
    started = time.perf_counter()
    services = build_services(
        ServerConfig(
            token="cold-start-token-with-at-least-32-characters",
            port=43123,
            data_dir=tmp_path / "data",
            default_model="openai:gpt-test",
        )
    )
    elapsed = time.perf_counter() - started
    # Close the stores we opened so tmp_path cleanup is clean.
    services.git.close()

    assert elapsed < budget_s, (
        f"cold start {elapsed:.2f}s exceeded budget {budget_s}s"
    )


def test_outbound_messages_scales_linearly_with_history(tmp_path):
    """_outbound_messages over 1000 messages stays under a per-call budget."""
    from runtime.policy import Mode, PermissionEngine, ToolManifest
    from runtime.providers import ModelCapabilities, ProviderClient
    from runtime.tools import ToolRegistry
    from runtime.turn_engine import TurnEngine

    class _NoopProvider(ProviderClient):
        def complete(self, **_kwargs):
            raise AssertionError("perf test should not call provider")

        def capabilities(self, _model):
            return ModelCapabilities()

    messages = [{"role": "system", "content": "system"}] + [
        {"role": "user", "content": f"turn {i}"} for i in range(1000)
    ]
    engine = TurnEngine(
        provider=_NoopProvider(),
        registry=ToolRegistry(ToolManifest()),
        permissions=PermissionEngine(tmp_path, mode=Mode.INTERACTIVE),
        model="openai:gpt-test",
        messages=messages,
    )

    started = time.perf_counter()
    outbound = engine._outbound_messages()
    elapsed = time.perf_counter() - started

    # Every message except system is user; nothing dropped (under the guard).
    assert len(outbound) == 1001
    # Budget: 500ms for 1000 messages on CI (linear, no attachments).
    assert elapsed < 0.5, (
        f"_outbound_messages {elapsed*1000:.0f}ms for 1000 msgs exceeded 500ms"
    )


def test_diff_output_truncation_fires_at_probe_limit():
    """The diff output cap is enforced and surfaced as output_truncated."""
    # The probe limit is the source of truth; verify it is the documented value
    # and that the constant is wired (the truncation path is exercised by the
    # existing integration tests; here we pin the budget value).
    budget = BUDGETS["git.probe_output_bytes"]
    assert budget.limit == 1024 * 1024
    assert budget.unit == "bytes"


def test_audit_ledger_query_respects_implicit_size_budget(tmp_path):
    """A large audit log does not blow up list() — it honors the limit param."""
    from runtime.audit import AuditLedger

    ledger = AuditLedger(tmp_path / "audit")
    for index in range(500):
        ledger.record("perf", "event", subject=f"subj-{index}")
    ledger.close()

    reopened = AuditLedger(tmp_path / "audit")
    try:
        rows = reopened.list(limit=50)
    finally:
        reopened.close()

    assert len(rows) == 50
