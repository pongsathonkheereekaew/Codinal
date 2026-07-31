## Destination

Ship GPUI as Codinal's default native desktop shell only after it meets the
handoff's parity, security, accessibility, performance, signing, updater, and
packaged macOS E2E gates. After the gates pass, retire Tauri permanently.

## Notes

Source of truth: `codinal-gpui-migration-handoff-2026-07-31.md`. Preserve the
authenticated loopback control plane and existing Cursor-parity roadmap. Use
`implement`, `tdd`, `code-review`, `macos-design`, accessibility review, and
verification before each completed implementation ticket.

## Decisions so far

- [G0 authenticated native contract](issues/01-g0-authenticated-native-contract.md) — native client owns bearer credentials; REST and WebSocket descriptors are versioned and no token enters a URL.
- [G1 GPUI compatibility and native shell](issues/02-g1-gpui-compatibility-and-native-shell.md) — pin GPUI 0.2.2 in a standalone development shell; keep Tauri's release graph intact.
- [G2 coding workspace parity](issues/03-g2-coding-workspace-parity.md) — an isolated native four-pane prototype compiles; production panes need decoded-event reducers and virtualization.
- [G3 safety surfaces](issues/04-g3-safety-surfaces.md) — GPUI stays read-only until every mutation follows explicit confirmation and sidecar-state reload.
- [G4 WebView-dependent bridges](issues/05-g4-webview-dependent-bridges.md) — OAuth keeps the native deep-link relay; preview remains evidence-only until a constrained native renderer passes packaged tests.
- [G5 parity and rollback](issues/06-g5-parity-and-rollback.md) — GPUI is opt-in, collects contract/performance evidence, and can restart under Tauri without state migration.

## Superseding decision (2026-07-31)

The owner approved a Rust/GPUI-only end state. Tauri remains only until every
G6 gate is evidenced; then its shell, WebView UI, and release wiring are
removed in one dedicated, verified retirement change. There is no required
post-cutover stable-release fallback. Pre-cutover rollback remains mandatory.

## Not yet specified

- Native preview renderer choice after its loopback navigation contract is
  exercised in a packaged app.
- Quantitative parity thresholds relative to the current Tauri baseline.

## Out of scope

- Removing Tauri before GPUI has passed all G6 gates.
- Hosted Codinal services, source export, or changing the authenticated
  loopback control-plane trust boundary.
