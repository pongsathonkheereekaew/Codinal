# Codinal Cursor-parity roadmap

**Status:** approved 2026-07-28
**Horizon:** 2-3 months, 5 phases, each its own PR.

Close the gap to Cursor (multi-file editor, LSP, inline completion, inline
edit) while keeping Codinal's strengths: sandboxed agent shell, tamper-evident
audit, provider-agnostic + auto-failover, native macOS app, real PTY terminal.

## Architectural shift: UI build pipeline

A minimal **esbuild** build step is introduced for the new editor surface. The
existing zero-build vanilla JS (`startup.js`, `app.css`, `xterm.js` vendor)
stays unchanged — they remain plain `<script src>` includes. Only the new
editor surface uses the bundler.

- `desktop/ui-src/` (TypeScript + CM6 imports) → esbuild → `desktop/ui/dist/`
  (single bundled `editor.js` + `editor.css`).
- `index.html` loads `./dist/editor.js` alongside existing scripts. The editor
  exposes a global `window.CodinalEditor` that vanilla JS calls into (same
  bridge pattern as xterm.js).
- CSP `script-src 'self'` is preserved (esbuild output is plain JS, no eval).
- CI: `cd desktop && npm ci && npm run build` before the existing verify.

**Why CodeMirror 6, not Monaco:** CM6 is ~100KB tree-shakeable vs Monaco's
2-5MB; CM6 is what Sourcegraph uses (migrated FROM Monaco for size +
modularity); CM6's incremental parser handles large files better. Monaco's
"VS Code parity out of the box" advantage doesn't justify 50× the bundle for
a Tauri app. LSP integration comes via community extension or our own glue.

## Phase 48 (1a) — Build infrastructure spike

Prove the build pipeline works inside this repo before building anything on
it. Standalone, no editor yet. **This phase gates everything — if the build
infra doesn't work cleanly under Tauri CSP + CI, we stop and reconsider.**

- `desktop/ui-src/editor.ts` setting `window.CodinalEditor = { hello: ... }`.
- `desktop/package.json` + `desktop/build.mjs` (esbuild, no framework).
- `index.html` loads `./dist/editor.js`; `startup.js` toasts the hello result.
- CI lane gains the npm build step.

**Verify:** Codinal verify: PASS + toast appears on launch.

## Phase 49 (1b) — Multi-file code editor

A real editor with tabs, syntax highlighting, save.

- `CodinalEditor` global: `openTab`, `closeTab`, `setActive`, `getContent`,
  `onSave`.
- CM6 instance per tab; 8 languages (JS/TS/Python/Rust/JSON/Markdown/CSS/HTML).
- File-size guard (>2MB opens read-only with banner).
- Dirty-state tracking.
- Backend `POST /v1/sessions/{id}/artifacts/write` — workspace-scoped
  (reuses `_artifact_target` sandbox check), no policy gate.
- UI: new grid row in `.workspace` (editor above, chat below — split row 6).
- Project tree click → opens tab. Cmd+S → save.

**Known risk (deferred):** user-vs-agent write conflict (last-write-wins for
now; "file changed on disk" awareness is a follow-up; checkpoints cover
agent-authored changes so recovery is possible).

## Phase 50 (2) — LSP client

Diagnostics + goto-definition + hover — the #1 gap vs Cursor.

- Rust shell manages language-server subprocesses (rust-analyzer, pyright,
  tsserver) via stdio JSON-RPC. `desktop/src-tauri/src/lsp.rs` mirrors
  `pty.rs` pattern.
- Tauri commands: `lsp_start`, `lsp_request`, `lsp_stop`.
- Frontend: CM6 diagnostic decorations + gutter markers; hover tooltips;
  Cmd+Click goto-def opens target file in a new tab.
- Language detection from extension; server binary must be on PATH
  (documented; not bundled).
- LSP glue: try `codemirror-languageserver`; else build our own thin client.

## Phase 51 (3) — Inline completion

Ghost-text multi-line completion — the #1 feature devs pick Cursor for.

- Trigger after ~300ms typing pause; send completion request to the
  configured model (respects routing — cheapest configured provider,
  including OmniRoute `auto/best-coding`).
- Request: file content + cursor position + language + (later) LSP context.
- Response → CM6 ghost-text decoration. Tab to accept, Esc to dismiss.
- Budget guard: max 1 in-flight; cancel on cursor move.
- Latency target <500ms first token (via FailoverRouter).

## Phase 52 (4) — Inline edit / Cmd-K

Highlight code → type instruction → AI replaces it.

- Selection-aware prompt to the model.
- Diff preview inline (reuse `renderDiff` logic).
- Accept/reject per-hunk (reuse selective-apply from Phase 33/43).

## Verification per phase
Codinal verify PASS + full pytest + (Phase 49+) editor smoke test in CI.

## Out of scope
- Cross-platform (Windows/Linux) — separate effort.
- Cloud sync / remote — separate effort.
- Bundling language servers — user installs them.
- Custom completion model training — we use configured providers.
