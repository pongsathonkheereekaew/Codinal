---
stage: C1
owner: codinal-runtime/storage
dependencies: [C0]
status: passed
---

# C1 writer ownership and migration gate

Exact fresh commands:

```text
cargo test --manifest-path crates/codinal-storage/Cargo.toml --lib -- --nocapture
cargo test --manifest-path crates/codinal-runtime/Cargo.toml --lib -- --nocapture
cargo test --manifest-path crates/codinal-runtime/Cargo.toml --tests -- --nocapture
cargo test --manifest-path crates/codinal-runtime/Cargo.toml --lib -- --test-threads=1 --nocapture
cargo test --manifest-path crates/codinal-runtime/Cargo.toml --tests -- --test-threads=1 --nocapture
cargo test --manifest-path desktop/native-host/Cargo.toml --lib -- --nocapture
```

Fixture/credential class: anonymized local SQLite copies and subprocesses;
no provider credentials.

Expected result: writer-lock exclusion, migration journal recovery at backup
fsync/database commit/commit marker boundaries, durable approvals/events,
cursor replay, and a second-connection interrupt all pass without mixed
history. The final ledger must attach the subprocess logs and migration corpus
manifest/checksums.

Rollback: restore the untouched anonymized copy; never run migration against a
user directory during this gate.

Stop condition: duplicate history, unreconciled journal, missed interrupt,
unverified backup, or any write from the read-only bootstrap.

Fresh deterministic result (2026-08-02): storage `28 passed`; runtime
`112 passed, 2 ignored` under both default-parallel and serial execution;
default-parallel `--tests` also passed with runtime `112/2`, bootstrap `5`, and
shadow owner launch `1`; native host `27 passed`. Two consecutive default-
parallel runtime library runs passed, so the previously documented fixture
race did not reproduce. The ignored tests are the separately approved
live-provider probes. The owner launch used an isolated snapshot and reported
migration `verified`, writer lock `held`, and event store `ready`; shutdown
removed the snapshot without changing its source fixture.

Attached evidence:

```text
66fb12701fe4071b82c3ba3ecfa34d3d7ec882c89a5ef5831e618b797d2a2f28  docs/evidence/cutover/c1/migration-corpus.sha256
01b537de625562b2adec8fd0e9f9f2d6224a780ef4403c2904cdfe93c6ad55e0  docs/evidence/cutover/c1/fresh-test-log.md
```
