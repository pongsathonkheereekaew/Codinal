Type: task
Status: open
Blocked by: 10

## Question

Can Rust upgrade an anonymized v1 data snapshot with a forward-only migration,
pre-migration backup, integrity verification, and interrupted-upgrade recovery
before it becomes the production data-directory writer?

## Destination

Pass the R1 storage gate in `docs/plan/rust-native-runtime-cutover.md` without
dual-writing Python-owned data or weakening the existing read contract.

## Required evidence

- A versioned migration corpus built from existing schema snapshots.
- Backup and restore behavior for success, corruption, and interrupted writes.
- One exclusive writer throughout cutover; directory replacement fails closed.
- Existing Rust read fixtures and Python compatibility fixtures remain green.

## Out of scope

- Deleting Python or Tauri before the remaining R2–R5 gates pass.
