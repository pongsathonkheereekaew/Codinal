# Phase 33 evidence — selective file-level accept/reject

Date: 2026-07-27
P0 roadmap item: "Add selective file/hunk accept/reject and preserve the existing conflict-abort invariant." (File-level done; hunk-level deferred.)

## What shipped

- **`GitWorktreeService.apply_selected(session_id, paths)`** — applies a subset of the session branch's files to source via `git checkout <session_branch> -- <paths>` + a single commit. Same preconditions as `apply_back` (clean session + source). On any failure, source is restored to its pre-apply HEAD (`git checkout -- .` + `git reset --hard`) — the conflict-abort invariant holds. Marks the record `APPLIED`/`CONFLICT`/`FAILED` consistently.
- **`GitWorktreeService.changed_files(session_id)`** — `{ok, files: [{path, status}]}` from `git diff --name-status <base>..HEAD`.
- **Routes**: `GET /v1/sessions/{id}/git/files`; `POST /v1/sessions/{id}/git/apply` extended with an optional `{paths: [...]}` body (absent/empty → legacy whole-branch `apply_back`; present → `apply_selected`). Backward-compatible.
- **Desktop UI**: `renderDiff()` restructured into per-file blocks, each with a checkbox (`diff-file-select`); `state.selectedFiles` tracks selection; the apply button becomes "Apply selected (N)" when any files are checked, falling back to "Apply to workspace" when none.

## Verification (fresh, 2026-07-27)

Service tests (Darwin, `@requires_seatbelt`):

```
$ CI= ./.venv/bin/pytest -q tests/git_runtime/test_worktree_lifecycle.py -k "changed_files or apply_selected"
....                                                                     [100%]
4 passed, 40 deselected in 1.76s
```

Route tests (CI lane, fake git):

```
$ ./.venv/bin/pytest -q tests/control_plane/test_session_routes.py -k "git_files or git_apply"
....                                                                     [100%]
4 passed, 48 deselected in 0.50s
```

Selective apply E2E (`@skip_on_ci`): 3 files changed, select 2, apply → source has the 2, 3rd unchanged, one new commit, record `APPLIED`:

```
$ CI= ./.venv/bin/pytest -q tests/control_plane/test_production_runtime.py::test_selective_apply_e2e_applies_only_chosen_files
.                                                                        [100%]
1 passed in 1.03s
```

Full local suite:

```
$ CI= ./.venv/bin/pytest -q
797 passed, 53 warnings in 75.54s
```

`verify.sh`: PASS.

## Invariant preserved

`git checkout <branch> -- <path>` is last-write-wins (no merge conflict possible for a single path); the failure modes are checkout-failure or commit-failure, both of which trigger `_restore()` → source returns to exactly its pre-apply HEAD. The existing `reconcile_crashed_applies` (Phase 31) handles a kill mid-apply identically.

## Non-goals (deferred)

- Hunk-level selection (needs unified-diff parsing + `git apply`; separate phase).
- Per-file conflict resolution (selective apply is all-or-nothing per call; a conflicting path set aborts the whole apply).
