# Phase 32 evidence — performance budgets CI

Date: 2026-07-27
P0 roadmap item: "Set measurable cold-start, memory, indexing, streaming, diff, and large-history budgets; enforce regressions in CI."

## What shipped

- **Central budget registry** (`runtime/perf/budgets.py`) — indexes every enforced runtime limit (37 budgets across 10 groups) by importing the real constants, so there is no drift. `assert_within_budget(name, measured)` helper gives seconds budgets 2x headroom for CI variance.
- **Perf suite** (`tests/perf/`, 13 tests, `@pytest.mark.perf`):
  - `test_budget_registry.py` — registry completeness (every entry resolves to a real constant) + assert helper.
  - `test_hot_paths.py` — tool-call contract budgets, repository search (deadline + result caps via `duration_ms`), cold-start `build_services`, `_outbound_messages` scaling (1000 msgs < 500ms), diff output cap, audit ledger query bound.
  - `test_outbound_guard.py` — the new `_MAX_OUTBOUND_MESSAGES` soft cap.
- **Large-history soft guard** (`runtime/turn_engine/engine.py`) — `_MAX_OUTBOUND_MESSAGES = 2000`; over the cap, the oldest non-system messages are dropped with a notice so a runaway history degrades gracefully instead of OOM-ing the provider request. The only runtime behavior change; everything else is measurement + CI.
- **Dedicated `perf` CI lane** (`.github/workflows/verify.yml`) — separate job on ubuntu-latest, runs the perf suite with `--durations=0`, fails the merge gate on regression. Independent of the `product`/`desktop` lanes.
- **`docs/perf/budgets.md`** — the budget table, how they're enforced/tested, how to change one, and observed baselines.

## Verification (fresh, 2026-07-27)

Perf suite:

```
$ ./.venv/bin/pytest tests/perf/ -m perf --durations=0 -q
13 passed, 3 warnings in 0.50s
```

Full local suite (unchanged behavior outside the guard):

```
$ CI= ./.venv/bin/pytest -q
775 passed, 53 warnings in ... (no regressions; the guard only fires over 2000 msgs)
```

`verify.sh`: PASS.

## Coverage map

| Hot path | Test | Mechanism |
|---|---|---|
| tool-call contract | `test_tool_call_contract_rejects_over_budget` | 64 calls / 1 MiB args rejection |
| repository search | `test_repository_search_honors_time_and_count_budgets` | `duration_ms` + result caps |
| cold start | `test_cold_start_build_services_under_budget` | `build_services` wall-clock |
| large history | `test_outbound_messages_scales_linearly_with_history` | 1000 msgs < 500ms |
| outbound guard | `test_outbound_drops_oldest_when_over_budget` | soft cap at 2000 |
| diff cap | `test_diff_output_truncation_fires_at_probe_limit` | 1 MiB probe limit |
| audit query | `test_audit_ledger_query_respects_implicit_size_budget` | limit param honored |
| registry | `test_every_budget_resolves_to_a_real_module_constant` | no drift |

## Non-goals (deferred)

- Memory RSS budgets (resident-set probe per process).
- Cross-platform perf baselines (CI lane is ubuntu-only).
- Streaming chunk-count cap (provider `max_tokens` bounds it).
