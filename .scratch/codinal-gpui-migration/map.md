## Destination

Ship GPUI as Codinal's default native desktop shell only after it meets the
handoff's parity, security, accessibility, performance, signing, updater, and
packaged macOS E2E gates, with a one-click Tauri fallback retained for one
stable release.

## Notes

Source of truth: `codinal-gpui-migration-handoff-2026-07-31.md`. Preserve the
authenticated loopback control plane and existing Cursor-parity roadmap. Use
`implement`, `tdd`, `code-review`, `macos-design`, accessibility review, and
verification before each completed implementation ticket.

## Decisions so far

- [G0 authenticated native contract](issues/01-g0-authenticated-native-contract.md) — native client owns bearer credentials; REST and WebSocket descriptors are versioned and no token enters a URL.

## Not yet specified

- Exact GPUI crate revision and supported toolchain after an upstream
  compatibility spike.
- Native preview renderer choice after its loopback navigation contract is
  exercised in a packaged app.
- Quantitative parity thresholds relative to the current Tauri baseline.

## Out of scope

- Removing Tauri before GPUI has passed all G6 gates.
- Hosted Codinal services, source export, or changing the authenticated
  loopback control-plane trust boundary.
