# desktop/

Codinal Tauri app — React + Tauri v2 (Rust host). Populated in Phase 1+.

- `src-tauri/` — Rust: policy host (mints per-session bearer token, spawns Python sidecar), worktree service, sandbox launcher (`sandbox-exec` profile)
- `ui/` — React UI (vendored from OpenWorker `surfaces/gui/src/components/*`, rewired at the seam: `api.ts`, `App.tsx` WS event switch, `itemsFromMessages.ts`)

See:
- `docs/decisions/0001-codinal-foundation.md` — D4 (sandbox), D7 (control-plane + token), D8 (distribution)
- `docs/plan/codinal-mvp.md` — Phase 1/3/4
- `docs/plan/openworker-boundary-map.md` — vendor/rewire/rewrite split

**Phase 0a spikes (de-risked 2026-07-25):** control-plane auth ✅, sandbox-exec notarization ✅, embedded-Python notarization ✅. See plan for evidence.
