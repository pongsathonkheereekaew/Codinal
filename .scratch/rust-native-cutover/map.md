## Destination

Ship Codinal as a Rust-native runtime with a production GPUI shell, then remove
the Python runtime and Tauri/WebView only after their replacement has passed
the R0–R5 gates in `docs/plan/rust-native-runtime-cutover.md`.

## Notes

Follow the staged-cutover decision: Tauri remains the production fallback until
the corresponding Rust and GPUI capability has recorded parity evidence.
Do not dual-write production SQLite data or expose bearer/provider secrets.

## Decisions so far

- [Decouple native host from Tauri](issues/01-decouple-native-host-from-tauri.md) — native host now owns token, secure launch, and Keychain bootstrap; Tauri consumes the crate unchanged as fallback.

## Not yet specified

- The exact capability order after the native-host seam is decoupled depends
  on the native runtime's authenticated v1 route and storage parity.
- GPUI production-pane design and performance/accessibility budgets need a
  concrete native runtime client surface before implementation can be scoped.
- Release signing, notarization, updater migration, and final deletion evidence
  are deferred until a non-Tauri package exists.

## Out of scope

- An immediate Tauri deletion before the replacement gates pass.
