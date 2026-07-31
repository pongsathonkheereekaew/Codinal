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
- [Define native runtime launch contract](issues/02-define-native-runtime-launch-contract.md) — the runtime must consume environment credentials, own a data-directory lock, prove authenticated health, and use stdin for future provider-secret bootstrap.
- [Implement native runtime bootstrap and owner lock](issues/04-implement-native-runtime-bootstrap-and-owner-lock.md) — executable startup now consumes credentials, holds an OS lock, and survives malformed loopback clients without releasing ownership.
- [Prove native runtime shadow launch](issues/05-prove-native-runtime-shadow-launch.md) — the native host now runs the real Rust binary only on a validated snapshot, verifies authenticated readiness, and cleans up after confirmed shutdown.
- [Port read-only session routes](issues/06-port-read-only-session-routes.md) — the authenticated Rust runtime now serves public session metadata and ordered messages directly from its isolated SQLite snapshot.
- [Wire GPUI to the native shadow runtime](issues/07-wire-gpui-to-native-shadow-runtime.md) — GPUI now owns Rust runtime launch, credentials, client reads, shutdown, and snapshot cleanup without a Tauri/Python startup path.
- [Port native provider-secret bootstrap](issues/09-port-native-secret-bootstrap.md) — GPUI now transfers Keychain profiles directly to Rust through bounded one-shot stdin; tokens and API keys remain in redacted zeroizing memory.
- [Port native PTY terminal](issues/14-port-native-pty-terminal.md) — PTY ownership and tests are moving out of Tauri into the shared native host before GPUI terminal wiring.
- [Port native LSP client](issues/15-port-native-lsp.md) — subprocess lifecycle and JSON-RPC now live in the shared native host; GPUI document integration remains.

## Not yet specified

- The bounded Rust approval broker/read route lacks a real Rust turn-engine
  producer; static shadow state is not live approval parity.
- Direct Rust provider adapters and turn ingestion must consume the native
  secret store before approval production can become live.
- GPUI production-pane design and performance/accessibility budgets need a
  concrete native runtime client surface before implementation can be scoped.
- Release signing, notarization, updater migration, and final deletion evidence
  are deferred until a non-Tauri package exists.

## Out of scope

- An immediate Tauri deletion before the replacement gates pass.
