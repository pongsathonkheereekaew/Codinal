# Phase 31 evidence — crash recovery completeness (plan/shell/apply-back)

Date: 2026-07-27
P0 roadmap item: "Restore interrupted sessions after app/runtime crash without replaying a completed tool call or losing an awaiting approval." Acceptance: "Kill/restart E2Es cover streaming, shell execution, approval wait, plan wait, and apply-back."

## What shipped

### Apply-back crash reconcile (the real correctness fix)
- `GitWorktreeService.reconcile_crashed_applies()` (`runtime/git/service.py`) — on boot, scans every stored worktree; for any whose source has a stale `MERGE_HEAD` (left by a crashed `apply_back`/`apply_many`), runs `git merge --abort`, verifies clean + head restored, and marks the record `WorktreeState.CONFLICT`. On abort failure, marks `FAILED`.
- Wired into the FastAPI lifespan (`app.py`) at boot, alongside `restores.reconcile()`.
- `GitWorktreeStore.list_records()` added to enumerate all records.
- **Before this fix**: a kill mid-`git merge` left the source worktree dirty with `MERGE_HEAD` and no recorded state — the next apply was blocked by `_is_clean` with no recovery path.

### Crash worker modes (`tests/fixtures/crash_recovery_worker.py`)
- `plan` — provider emits `propose_plan`; parks in `AWAITING_APPROVAL` with a pending plan interaction.
- `shell` — provider emits `run_shell("sleep 30")`; auto-approved so it reaches `EXECUTING`.

### SIGKILL E2Es (real process kill + restart)
- `test_sigkill_during_plan_wait_resurfaces_without_replay` — plan re-surfaces; no provider call on resume (pending tool re-handled, not replayed).
- `test_sigkill_during_shell_execution_abandons_call_without_replay` — in-flight `run_shell` abandoned; tool result records "unknown"/"interrupted"; turn recovers and completes; provider called once.
- `test_apply_back_crash_reconciles_stale_merge_on_restart` — stale `MERGE_HEAD` cleaned by boot reconcile; record marked `CONFLICT`.

## Verification (fresh, 2026-07-27)

Service-level (Darwin, `@requires_seatbelt`):

```
$ CI= ./.venv/bin/pytest -q tests/git_runtime/test_worktree_lifecycle.py -k "reconcile_crashed"
..                                                                       [100%]
2 passed, 38 deselected in 0.98s
```

SIGKILL E2Es (`@skip_on_ci`, real SIGKILL via crash worker):

```
$ CI= ./.venv/bin/pytest -q tests/control_plane/test_production_runtime.py::test_sigkill_during_plan_wait_resurfaces_without_replay tests/control_plane/test_production_runtime.py::test_sigkill_during_shell_execution_abandons_call_without_replay tests/control_plane/test_production_runtime.py::test_apply_back_crash_reconciles_stale_merge_on_restart
...                                                                      [100%]
3 passed in 8.39s
```

Full local suite:

```
$ CI= ./.venv/bin/pytest -q
775 passed, 53 warnings in 74.28s
```

`verify.sh`: PASS.

## Coverage map (all five crash scenarios now verified)

| Scenario | Test | Type |
|---|---|---|
| streaming | `test_sigkill_during_streaming_resumes_one_answer` | real SIGKILL (existing) |
| approval wait | `test_sigkill_after_approval_ack_resumes_without_reprompt` | real SIGKILL (existing) |
| parallel tool | `test_sigkill_during_parallel_tools_never_replays_either_call` | real SIGKILL (existing) |
| **plan wait** | `test_sigkill_during_plan_wait_resurfaces_without_replay` | real SIGKILL (**new**) |
| **shell execution** | `test_sigkill_during_shell_execution_abandons_call_without_replay` | real SIGKILL (**new**) |
| **apply-back** | `test_apply_back_crash_reconciles_stale_merge_on_restart` + service test | reconcile (**new**) |

## Non-goals (deferred)

- Orphaned shell child-process reaping on restart (correctness preserved — no replay — but the leaked `sleep` process is a resource issue; requires persisting process-group IDs).
- Crash telemetry (Phase 30 support bundle covers diagnostics).
