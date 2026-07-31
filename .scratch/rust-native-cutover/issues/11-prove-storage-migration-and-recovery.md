Type: task
Status: resolved
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

## Progress

- Rust can migrate an immutable `codinal.db` snapshot into a newly created,
  private destination through the released v0/v1/v2/v3/v6/v7 boundaries to v8.
- The destination receives a private, fsynced SQLite backup before mutation;
  the migration commits in one transaction and must pass `integrity_check`.
- Recovery preserves corrupt main/journal/WAL/SHM files, restores the newest
  valid backup, and replays the remaining forward-only chain.
- Future versions fail before a destination is created and the Python-owned
  source is never opened for writing.
- The same staged migration/recovery engine now covers `git-worktrees.db`
  through v5 and `workers.db` through v2, including retained checkpoint and
  worker comparison metadata across every released boundary.

The six single-version stores now use schema-matched Rust migrations. A whole
data-directory publisher stages all nine databases, verifies the shared v1
inventory, rejects source-contained destinations and unsupported inputs, then
publishes with one directory rename. Reports distinguish published durability
and cleanup state so no post-publication error is ambiguous.

## Resolution

The R1 migration/recovery corpus now covers every durable SQLite database,
released multi-version boundaries, private fsynced backups, corrupt SQLite
companions, retryable recovery, future-version refusal, and atomic all-database
publication without writing the Python-owned source.

## Out of scope

- Deleting Python or Tauri before the remaining R2–R5 gates pass.
