Type: task
Status: resolved
Blocked by:

## Question

Can `codinal-native-host` own the existing token, secure launch, and Keychain
bootstrap implementation without source-path imports from `desktop/src-tauri`,
while preserving its current test contract?

## Answer

Yes. `host.rs` and `secrets.rs` now belong to `codinal-native-host`; Tauri
imports the crate as a local path dependency and re-exports the modules to
preserve its existing callers and tests. The Keychain service/schema and
sidecar launch contract are unchanged. Verification: native-host (5 tests) and
Tauri (35 tests) pass, as do both crates' `clippy -D warnings` checks.
