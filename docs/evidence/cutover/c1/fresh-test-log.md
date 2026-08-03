# C1 fresh test log — 2026-08-02

All commands ran from the repository root on Darwin arm64. Fixtures were
generated only under per-test temporary directories; no provider credential or
production data directory was used.

```text
cargo test --manifest-path crates/codinal-storage/Cargo.toml --lib -- --nocapture
result: 28 passed; 0 failed; 0 ignored

cargo test --manifest-path crates/codinal-runtime/Cargo.toml --lib -- --nocapture
result: 112 passed; 0 failed; 2 ignored (default-parallel)

cargo test --manifest-path crates/codinal-runtime/Cargo.toml --lib -- --nocapture
result: 112 passed; 0 failed; 2 ignored (second default-parallel run)

cargo test --manifest-path crates/codinal-runtime/Cargo.toml --tests -- --nocapture
result: runtime library 112 passed/2 ignored; bootstrap 5 passed; shadow launch 1 passed (default-parallel)

cargo test --manifest-path crates/codinal-runtime/Cargo.toml --lib -- --test-threads=1 --nocapture
result: 112 passed; 0 failed; 2 ignored
ignored: the separately credentialed OpenCode Go and DeepSeek live probes

cargo test --manifest-path crates/codinal-runtime/Cargo.toml --tests -- --test-threads=1 --nocapture
result: runtime library 112 passed/2 ignored; bootstrap 5 passed; shadow launch 1 passed

cargo test --manifest-path desktop/native-host/Cargo.toml --lib -- --nocapture
result: 27 passed; 0 failed; 0 ignored
```

The corpus covers conversation schemas 0, 2, 3, 6, and 7 to version 8;
git-worktree schemas 0 through 4 to version 5; worker schema 1 to version 2;
all nine current database fixtures; backup, database-commit, and commit-marker
restart boundaries; writer-lock exclusion; durable replay; and owner launch on
an isolated shadow snapshot. Two default-parallel runtime runs and one
default-parallel integration run passed without the previously documented
fixture race. The shadow run reported migration `verified`, writer lock `held`,
and event store `ready`, then removed the snapshot without changing its source
fixture.
