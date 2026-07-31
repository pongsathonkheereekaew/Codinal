Type: task
Status: resolved
Blocked by: 04

## Question

Can the native host launch `codinal-runtime` only against an isolated validated
shadow snapshot, verify authenticated readiness, and always retain Tauri/Python
as the production writer and rollback path?

## Answer

Yes. The native host now creates a fixture-validated SQLite backup outside the
production data directory, launches `codinal-runtime` against that snapshot,
and returns only after exact authenticated `/v1/health` readiness. Failed
startup stops the process before cleanup; confirmed shutdown waits for process
exit and then removes the snapshot. Nested production-data destinations are
rejected and bearer request material is zeroized.

The executable integration test proves the runtime lock is created in the
snapshot, production storage remains compatible before and after the run, and
the snapshot is removed after shutdown. Tauri still starts Python through the
unchanged `SidecarLaunch` path.

Verification: runtime 12 tests, native-host 8 tests, Tauri fallback 35 tests,
and both changed Rust crates pass `clippy --all-targets -D warnings`.
