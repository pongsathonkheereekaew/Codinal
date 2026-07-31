Status: in_progress
Type: task
Blocked by: 06

## Question

What evidence proves GPUI can become default while Tauri remains available for
one stable release: verifier, signing, packaged E2E, updater, authentication,
performance, security, and accessibility?

## Current evidence (2026-07-31)

- `CI=true ./verify.sh`: 927 passed, 115 skipped.
- `cargo clippy --manifest-path desktop/src-tauri/Cargo.toml --all-targets -- -D warnings`: passed.
- `scripts/smoke-macos-release.sh`: passed for the current signed bundle,
  including embedded runtime and authenticated sidecar launch.
- Gatekeeper validation is blocked: the current artifact has no stapled
  notarization ticket. The release workflow already performs notarize/staple
  once its Apple and updater signing secrets are configured.

`scripts/verify-gpui-migration.sh` is the non-publishing dogfood gate. It does
not authorize GPUI default cutover; that remains blocked on parity, a11y,
performance, updater E2E, and notarized candidate evidence.
