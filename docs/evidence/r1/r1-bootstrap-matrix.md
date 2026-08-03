# R1 Bootstrap Matrix Evidence

Status: PASS
Owner: runtime/bootstrap lead
Date: 2026-08-01

## Matrix cases
1) Fresh install
2) Existing install / upgrade
3) Interrupted migration + resume

For each case record:
- startup transition trace
- owner lock mode result
- migration lock status
- seed DB path ownership/writable checks
- recovery evidence
- rollback verification

### Executed evidence
- Fresh install:
  - `RuntimeBootstrap::from_values` now transitions through startup states and returns `RuntimeOwnerState::LockedActive` in `runtime_bootstrap_exclusively_owns_its_data_directory` test.
  - command: `cd crates/codinal-runtime && cargo test runtime_bootstrap_exclusively_owns_its_data_directory -- --nocapture`
  - status: passed
- Existing install / upgrade:
  - `RuntimeBootstrap::from_environment` can reuse configured `CODINAL_DATA_DIR` in `runtime_bootstrap_reuses_existing_installed_data_directory`.
  - command: `cd crates/codinal-runtime && cargo test runtime_bootstrap_reuses_existing_installed_data_directory -- --nocapture`
  - status: passed
- Interrupted migration + resume:
  - recovery assertions are covered by storage migration recovery tests.
  - command: `cargo test --manifest-path crates/codinal-storage/Cargo.toml failed_initial_migration_removes_staging_and_remains_retryable -- --nocapture`
  - command: `cargo test --manifest-path crates/codinal-storage/Cargo.toml corrupt_interrupted_destination_restores_backup_and_replays_migration -- --nocapture`
  - status: passed

## Gate checks
- [x] `owner_lock_mode == owned` (exclusive lock test + startup state assert)
- [x] writable DB path only under active owner (validated via single-writer bootstrap lock test + no concurrent ownership)
- [x] migration lock trace capture during reconcile/recover
- [x] dual-writer path hard-fail in smoke (second `RuntimeBootstrap::from_values` to same data dir returns error while first is active)

## Proof
- Log bundle:
  - `cargo test runtime_bootstrap_exclusively_owns_its_data_directory` (owner lock + startup trace + dual-writer hard-fail)
  - `cargo test runtime_bootstrap_records_migration_trace_for_reconcile` (migration trace capture)
  - `cargo test runtime_bootstrap_reuses_existing_installed_data_directory` (existing-install recovery path)
- Recovery transcript: `cargo test --manifest-path crates/codinal-storage/Cargo.toml failed_initial_migration_removes_staging_and_remains_retryable`, `cargo test --manifest-path crates/codinal-storage/Cargo.toml corrupt_interrupted_destination_restores_backup_and_replays_migration`

## Sign-off
- [x] approved to start R2 (dual-writer + migration-lock proof present in startup trace + bootstrap lock assertions)
