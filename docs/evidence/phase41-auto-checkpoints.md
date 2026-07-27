# Phase 41 evidence — per-turn auto-checkpoints

Date: 2026-07-27
Roadmap item: "Add automatic per-turn checkpoints for Agent-authored files plus conversation position; restore code, conversation, or both without reverting manual edits." (`docs/plan/codinal-parity-roadmap.md:86`)

## Summary

The per-turn auto-checkpoint **mechanism already shipped** — Phase 41 added no production code. The roadmap checkbox was really missing **end-to-end evidence** for three of the five scenarios listed in the L54 evidence cell. This phase closes those three gaps with control-plane E2Es in `tests/control_plane/test_production_runtime.py`.

## Mechanism (already in place, file:line)

- **Begin at turn start:** `runtime/turns/service.py:440-472` — if no checkpoint is pending, calls `begin_checkpoint(session_id, message_count=before_message_count, attributed=True)`. The `before_message_count` is computed by walking back to the last `user` message, i.e. the turn boundary.
- **Capture at turn end:** `runtime/turns/service.py:660-735` — in the turn's `finally` block, `capture_checkpoint(..., message_count=len(engine.messages))` then `finalize_checkpoint`. A `TurnCheckpoint()` is persisted alongside.
- **Attributed preimages:** `runtime/tools/mutations.py` — `write_file` records preimages (L98); `run_shell` records attributed deltas or upgrades to whole-tree via `record_shell_fallback` (L175/L211).
- **Plain (non-Git) workspaces:** `begin_checkpoint` enforces `plain workspace checkpoints require attribution` (`runtime/git/service.py:523-529`).
- **Restore + manual-edit preservation:** `_apply_restore_patch` (`runtime/git/service.py:3075`) runs `git apply --check --unidiff-zero` first and raises `"checkpoint conflicts with current edits"` (L3098-3101) on same-path conflicts; different-path edits survive by attribution (only Agent-touched paths are in the patch).
- **Active-turn guard:** `runtime/turns/service.py:263-273` — `restore_when_idle` raises `SessionBusyError("session already has an active turn")` while a turn is active. The HTTP route (`runtime/control_plane/app.py:2739-2750`) maps this to 409.

## The five E2E scenarios (L54)

| # | Scenario | E2E location | Added this phase? |
|---|---|---|---|
| 1 | Git ignored-file restore | `test_turn_checkpoint_reconciles_ambiguous_restore_after_restart` | pre-existing |
| 2 | Non-Git restart reconciliation | `test_plain_workspace_checkpoint_restores_after_restart` | pre-existing |
| 3 | Same-path conflict-abort | `test_checkpoint_restore_aborts_same_path_manual_edit_e2e` | **yes** |
| 4 | Uncaptured-secret exclusion | `test_checkpoint_never_captures_uncaptured_secret_e2e` | **yes** |
| 5 | Active-turn manual-edit preservation | `test_manual_edit_during_active_turn_survives_restore_e2e` | **yes** |

All five now live in `tests/control_plane/test_production_runtime.py`.

### #3 — same-path conflict-abort (HTTP restore)

Git workspace; Agent writes `target.txt`; after `turn_end`, a manual edit overwrites the same `target.txt`; `POST /v1/sessions/{id}/checkpoints/{cp}/restore` returns **HTTP 409** with `"checkpoint conflicts with current edits"`, and `target.txt` is left at the manual value. This drives the invariant through the live `CheckpointRestoreCoordinator` → `resume_restore_code` → `_apply_restore_patch` path (not the direct `restore_checkpoint_code` used by the pre-existing service-level test).

### #4 — uncaptured-secret exclusion (full stack)

Plain workspace; `manual-secret.txt` is pre-created and never touched; Agent writes `agent.txt` via `write_file`; after `turn_end`, the test hashes the secret and enumerates every object in the session's content-addressed checkpoint store via `git --git-dir=<repo> cat-file --batch-all-objects`. Asserts the secret's blob is **absent** and `attributed_paths == {"agent.txt"}`.

### #5 — active-turn manual-edit preservation (was untested at any level)

Two-turn sequence. Turn 1 writes `agent.txt` and completes (seeds a restorable checkpoint). Turn 2 runs a `run_shell` that **blocks** until a release file appears (bounded 10s perl poll), keeping the turn active. While turn 2 is active:

- (a) restore of the turn-1 checkpoint returns **HTTP 409** `"session already has an active turn"` (the active-turn guard, previously only unit-tested for refusal);
- a manual edit to `manual.txt` (a *different* path) is injected mid-turn;
- the blocking shell is released and turn 2 drains to `turn_end`;
- (b) restore of the turn-1 checkpoint now succeeds (HTTP 200), and `manual.txt` survives — attribution means only Agent-touched paths are in the patch.

## Verification

```
$ ./.venv/bin/pytest -q \
    tests/control_plane/test_production_runtime.py::test_checkpoint_restore_aborts_same_path_manual_edit_e2e \
    tests/control_plane/test_production_runtime.py::test_checkpoint_never_captures_uncaptured_secret_e2e \
    tests/control_plane/test_production_runtime.py::test_manual_edit_during_active_turn_survives_restore_e2e
...                                                                      [100%]
3 passed in 14.25s
```

```
$ ./.venv/bin/pytest -q tests/control_plane/test_production_runtime.py
............................................                             [100%]
44 passed in 36.10s
```

```
$ CI= ./.venv/bin/pytest -q
865 passed, 1 skipped, 53 warnings in 89.98s   # was 862 before Phase 41 (+3)
```

```
$ CI= ./verify.sh
Codinal verify: PASS
```

The three new E2Es carry the module-level `pytestmark = skipif(CI=="true")` and per-test `skipif(platform != "Darwin")` guards, so the CI product lane stays green; they run locally and in the release smoke lane.
