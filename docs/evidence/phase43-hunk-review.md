# Phase 43 evidence — selective hunk-level review

Date: 2026-07-27
Roadmap item: "Add selective file/hunk accept/reject and preserve the existing conflict-abort invariant." (`docs/plan/codinal-parity-roadmap.md:102`) — closes the hunk-level half that Phase 33 deferred as "needs unified-diff parsing + `git apply`".

## Summary

Selective review now operates at **hunk granularity**, not just file granularity. A pure-Python unified-diff parser splits the session diff into per-file, per-hunk records; a new backend method reconstructs a patch from the chosen hunks and applies it via `git apply --check --unidiff-zero` then `git apply`, reusing the existing precondition checks and `_restore()` rollback pattern from file-level `apply_selected`. The review panel renders a per-hunk checkbox; `Apply selected (N hunks)` posts `{hunks:[...]}`.

**Semantics difference from file-level (intentional):** file-level apply is last-write-wins (`git checkout <branch> -- <paths>` always overwrites). Hunk-level apply is real 3-way — `git apply` refuses when surrounding context doesn't match, and source is rolled back to the pre-apply HEAD (the conflict-abort invariant preserved).

## What shipped

**1. Unified-diff parser** (`runtime/git/diff_parser.py`)
- `parse_diff(text) → list[FileDiff]` — splits on `diff --git` and `@@`; each `Hunk` carries its 0-based `index` within the file (the stable UI/backend identifier).
- `reconstruct_patch(files, selected) → str` — rebuilds a valid unified diff for the chosen `(path, hunk_index)` pairs, preserving `diff --git`/`index`/`---`/`+++`/`@@` headers.
- Strict: malformed input raises `ValueError`; empty selection raises.

**2. Backend `apply_selected_hunks`** (`runtime/git/service.py`)
- Same three precondition checks as `apply_selected` (clean session worktree, clean source, source-branch-unchanged) + per-hunk existence validation against `git diff --unified=0 base_commit...HEAD`.
- Reconstructs the patch, runs `git apply --check --unidiff-zero` (refuses on context mismatch → `WorktreeState.CONFLICT` + `_restore()`), then `git apply --unidiff-zero`, stages the touched paths, commits as one new source commit.
- Returns `{"strategy": "selective-hunks", "hunks": [...], "commit": <new_head>}`.

**3. Control plane** (`runtime/control_plane/app.py`)
- `_read_apply_selection` now accepts `{"hunks": [{"path","hunk_index"}, ...]}` OR `{"paths": [...]}` (mutually exclusive). Route dispatches hunk selection to `apply_selected_hunks`. File-level `{paths:...}` and apply-all (no body) unchanged.

**4. UI** (`desktop/ui/startup.js`)
- `renderDiff` splits each file block at `@@` headers into per-hunk groups, each with a `diff-hunk-select` checkbox (`dataset.path` + `dataset.hunkIndex`). The existing per-file checkbox stays (select-all-files).
- `state.selectedHunks: Set<string>` keyed `path::hunkIndex`. `updateApplyButton` shows `Apply selected (N hunks)` when hunks are selected, else falls back to file count, else `Apply to workspace`.
- `applyChanges` posts `{hunks: [...]}` when `selectedHunks` is non-empty; clears both sets on success.
- No `index.html` structural change — hunk checkboxes are JS-generated inside the existing `pre#diff-view` blocks.

## Verification

```
$ ./.venv/bin/pytest -q tests/git_runtime/test_diff_parser.py
.........                                                                 [100%]
9 passed
```

```
$ ./.venv/bin/pytest -q tests/git_runtime/test_worktree_lifecycle.py -k "hunks or selective"
...                                                                       [100%]
3 passed, 44 deselected    # 2 new hunk backend + 1 pre-existing file-level
```

```
$ ./.venv/bin/pytest -q tests/control_plane/test_production_runtime.py::test_selective_apply_hunks_e2e_applies_only_chosen_hunks
.                                                                         [100%]
1 passed    # E2E through the live control plane
```

```
$ ./.venv/bin/pytest -q tests/desktop_ui/test_ui_contract.py tests/control_plane/test_session_routes.py
.....                                                                     [100%]
69 passed   # UI contract + route tests (file-level still works)
```

```
$ CI= ./.venv/bin/pytest -q
<full suite>   # green (+4 new tests)
```

```
$ CI= ./verify.sh
Codinal verify: PASS
```

The new hunk tests carry the macOS Seatbelt skip guard (they prepare real worktrees), so the CI product lane stays green; they run locally and in the release smoke lane.
