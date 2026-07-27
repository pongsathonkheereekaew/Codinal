# Phase 28 evidence — Git ship-loop UX

Date: 2026-07-27
P1 roadmap item: "Add branch graph, stage/commit/push UI and commit-level review."

## What shipped

- **Service layer** (`runtime/git/service.py`):
  - `log(session_id, *, limit=50)` — bounded session-branch commit history (base..HEAD) with structured fields (sha, parents, author, email, date, subject).
  - `graph(session_id, *, limit=50)` — ASCII branch graph + parsed commit list.
  - `push(session_id, *, remote="origin", set_upstream=False)` — pushes the session branch from `source_root` (where remotes live), requires clean source, surfaces failures. Minimal (no force/delete/tags).
  - `diff(..., commit=sha)` — per-commit diff mode, mutually exclusive with `staged`/`against_base`/`path`.
- **Control plane** (`runtime/control_plane/app.py`):
  - `GitControl` Protocol extended with `log`/`graph`/`push` and surfaced existing `stage`/`commit`.
  - 5 new auth-required routes: `POST /git/stage`, `POST /git/commit`, `GET /git/log`, `GET /git/graph`, `POST /git/push` (gated by `mutate_when_idle` like `apply`).
  - `GET /git/diff` now accepts `commit` param.
  - `push` records `domain="git", action="push"` in the Phase 27 audit ledger.
- **Desktop UI** (`desktop/ui/index.html`, `startup.js`, `app.css`):
  - Review panel extended with three sections above the diff view: branch + graph header (with Push button), commit composer (textarea + Stage all + Commit), and a clickable commit list (click a commit → per-commit diff).
  - `window.confirm` gate on Push (network write).

## Verification (fresh, 2026-07-27)

Service-layer tests (Darwin, `@requires_seatbelt`):

```
$ CI= ./.venv/bin/pytest -q tests/git_runtime/test_worktree_lifecycle.py -k "log_graph or log_respects or diff_commit_mode or push_advances"
....                                                                     [100%]
4 passed, 34 deselected in 2.37s
```

Route tests (CI lane):

```
$ ./.venv/bin/pytest -q tests/control_plane/test_session_routes.py -k "git_"
..........                                                               [100%]
10 passed, 38 deselected in 0.63s
```

Ship-loop E2E (`@skip_on_ci`, runs locally + release smoke): stage → commit → log shows the commit → graph renders it → per-commit diff → push advances the remote ref → audit ledger records `push`:

```
$ CI= ./.venv/bin/pytest -q tests/control_plane/test_production_runtime.py::test_git_ship_loop_stage_commit_log_graph_push
.                                                                        [100%]
1 passed in 1.07s
```

Full local suite:

```
$ CI= ./.venv/bin/pytest -q
729 passed, 53 warnings in 67.94s
```

`verify.sh`: PASS.

## Coverage map

| Layer | File | Tests |
|---|---|---|
| Service | `runtime/git/service.py` | `tests/git_runtime/test_worktree_lifecycle.py` (log/graph/diff-commit/push) |
| Routes | `runtime/control_plane/app.py` | `tests/control_plane/test_session_routes.py` (stage/commit/log/graph/push/diff-commit + 404) |
| Ship-loop E2E | `tests/control_plane/test_production_runtime.py` | `test_git_ship_loop_stage_commit_log_graph_push` |
| Desktop UI | `desktop/ui/*` | `tests/desktop_ui/test_ui_contract.py` (elements + wiring) |

## Non-goals (deferred)

- Force-push, delete-remote, tags (stay on CLI).
- GitHub PR creation/review/CI (next P1 item, separate phase — needs scoped GitHub credentials).
- Per-hunk stage (whole-path stage only; selective hunks is a separate P0 item).
- Interactive rebase / amend.
