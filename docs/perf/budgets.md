# Performance budgets

Status: active (Phase 32, 2026-07-27)

Codinal enforces bounded resource use at every consequential path. This file
is the human index of those budgets, how they are tested, and how to change
one.

## Where the budgets live

The single source of truth for each limit is the constant at its enforcement
site (e.g. `runtime.search.service:_MAX_SECONDS`). The central registry at
`runtime/perf/budgets.py` indexes them by name — it imports the real values,
so changing a constant flows through automatically (no drift).

```python
from runtime.perf import BUDGETS
BUDGETS["search.max_seconds"]      # Budget(limit=2.0, unit="seconds", ...)
BUDGETS["engine.max_outbound_messages"]  # Budget(limit=2000, unit="count", ...)
```

## Groups

| Group | Example budgets | What they bound |
|---|---|---|
| tool_io | read 5MB/2000 lines, write 5MB, grep 5s, list 1000 | tool result sizes + deadlines |
| contract | 64 calls/turn, 1 MiB args | provider tool-call batch |
| sandbox | 120s timeout, 1 MiB output, 32 roots | seatbelt shell |
| search | 2s deadline, 5000 files, 32 MiB scanned | repository text/symbol search |
| index | 10s build, 2s query, 128 MiB DB | local semantic index |
| git | 10s probe, 1 MiB diff, 200 log entries | git diff/status/log |
| mcp | 64 KiB schema, 120s call | remote tool boundary |
| http | 15 MiB turn body, 10 MiB attachment, 5 attachments | control-plane request bodies |
| store | 32 MiB export, 128 KiB plan | conversation/session persistence |
| engine | 2000 outbound messages, 15s attachment rebuild | turn-engine hot paths |

## How a budget is enforced

- **Hard deadline** (seconds): the runtime uses `time.monotonic()` and stops
  the work, returning a partial result with `truncated`/`duration_ms` set.
- **Size cap** (bytes/lines/chars/count): the runtime truncates and sets
  `output_truncated` (or rejects the request at the contract layer).

## How a budget is tested

The `tests/perf/` suite (marker `@pytest.mark.perf`) measures each hot path
and asserts it stays within the named budget. Seconds budgets allow 2x
headroom for CI-runner variance (`assert_within_budget`).

The dedicated `perf` CI job (`.github/workflows/verify.yml`) runs this suite
on every PR, independent of the correctness lane. A regression fails the
merge gate.

## How to change a budget

1. Edit the constant at its source (e.g. `runtime/search/service.py:_MAX_SECONDS`).
2. The registry flows through automatically — no second edit needed.
3. Run `pytest tests/perf/ -m perf` to confirm the new limit holds.
4. Update the baseline below if the change is intentional.

## Baselines (observed)

Recorded on the dev machine (macOS, M-series) and the CI runner
(ubuntu-latest). Numbers are typical, not guaranteed — the budget is the
guarantee.

| Path | Dev (macOS) | CI (ubuntu) | Budget |
|---|---|---|---|
| cold start (`build_services`, empty data_dir) | ~0.3s | ~0.5s | 3.0s |
| search query (50 files) | <0.05s | <0.1s | 2.0s deadline |
| `_outbound_messages` (1000 msgs, no attachments) | ~5ms | ~10ms | 500ms |
| `_outbound_messages` (2000 msgs, over cap) | drops oldest + notice | same | 2000 msgs |

## Non-goals (deferred)

- Memory RSS budgets (would need a resident-set probe per process).
- Cross-platform baselines (CI lane is ubuntu-only; macOS dev numbers above).
- Streaming chunk-count cap (provider `max_tokens` bounds it today).
