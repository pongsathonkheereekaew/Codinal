# Codinal GPUI migration handoff

## Decision

Build GPUI in parallel behind a development-only shell selector. Do not do a
big-bang rewrite. Tauri/WebView remains the signed release fallback until GPUI
passes parity, accessibility, performance, and packaged macOS E2E gates.

## Current architecture

- Desktop shell: `desktop/src-tauri/`; current UI: `desktop/ui/`.
- Authenticated loopback backend: `runtime/control_plane/app.py`.
- Preserve all existing Universal roadmap work in
  `docs/plan/codinal-cursor-parity.md`; do not restore `7cc163e`.

## GPUI delivery plan

### G0 — contract first

1. Define a versioned Rust `ControlPlaneClient` for sessions, stream events,
   approvals, preview evidence, audit, Git, workers, and settings.
2. Add golden JSON/event fixtures from the current client and shared contract
   tests.
3. Add `desktop_shell=tauri|gpui` for development only.

Gate: GPUI connects to the same authenticated sidecar without secrets in UI
state or logs.

### G1 — native shell

1. Pin GPUI/toolchain; document macOS/Linux support.
2. Implement window lifecycle, Metal rendering, menus, shortcuts, theme,
   dialogs, secure secret handoff, updater status, and safe sidecar shutdown.
3. Preserve signing, notarization, and updater contracts.

Gate: signed GPUI app starts/stops the sidecar and passes token/auth/cleanup
smoke tests.

### G2 — coding workspace

Implement virtualized streamed conversation, terminal, diff viewer, file tree,
command palette, cancellation, copy/selection, focus and keyboard navigation.

Gate: real sidecar read/write/approval/cancel/diff flow; P95 typing, 10k-line
terminal scroll, 10k-file tree, RSS, and accessibility meet or beat Tauri.

### G3 — safety surfaces

Implement approval cards, plan/evidence review, Git checkpoint/apply, workers,
audit export, and bounded execution/preview evidence rendering.

Gate: approvals remain explicit; evidence/audit survives restart and is visible
before apply.

### G4 — WebView-dependent bridges

Use existing system-browser/deep-link OAuth. Replace preview iframe only with a
constrained native WebView child or loopback renderer; navigation must remain
loopback-only and redirects/external origins fail closed. Keep office preview
local-only.

Gate: packaged OAuth, preview allow/deny, and attachment E2E pass.

### G5 — parity and rollback

Run both shells on replay/live fixtures, migrate non-secret preferences only,
dogfood behind opt-in feature flag, and retain one-click Tauri rollback.

### G6 — cutover

GPUI becomes default only after `./verify.sh`, signing, packaged macOS E2E,
updater, sidecar authentication, performance, security, and a11y gates pass.
Keep Tauri for one stable release before removal.

## Required checks

- Unit: protocol decoding, reducers, redaction, URL/navigation guard.
- Integration: sidecar, approval/cancel/restart, evidence, Git, workers.
- UI: keyboard-only, screen-reader, focus/dialog/error/loading states.
- Performance: first interactive paint, P95 typing, terminal/diff/tree, RSS.
- Release: verifier, signing, packaged start/stop, updater, preview E2E.

## Scrutiny verdict

Fix-then-ship via G0–G6. GPUI is valuable for editor-heavy surfaces, but it is
pre-1.0 and current preview/OAuth/accessibility bridges are load-bearing; a
parallel measurable migration is required.

## Suggested skills

`implement`, `tdd`, `code-review`, `macos-design`, `a11y-architect`,
`verification-before-completion`.

## Existing roadmap continuation

Return to `docs/plan/codinal-cursor-parity.md` Phase C. Remote lease commits:
`f4737dd`, `1344a9d`, `3aee3ef`. Remote dispatch remains fail-closed until
enrollment, attestation, artifact transfer, review-only adoption, and tests are
complete.
