---
stage: C4a-c
owner: codinal-harness/runtime
dependencies: [C1, C2a]
status: passed
---

# C4a-c Harness Manager and workflow gate

Exact fresh commands:

```text
cargo test --manifest-path crates/codinal-harness/Cargo.toml --lib -- --nocapture
cargo clippy --manifest-path crates/codinal-harness/Cargo.toml --all-targets -- -D warnings
cargo test --manifest-path crates/codinal-runtime/Cargo.toml --lib harness_inventory_route_is_read_only_and_reports_projection_drift -- --nocapture
```

Fixture class: isolated temporary source bundles, user overlays, live
projections, OpenCode host roots, malformed host files, symlink boundaries,
and durable workflow ledgers. No user home or external host is mutated.

Expected result: Source Bundle/User Overlay/Live Projection/Host Projection
inventory is read-only; plans bind to an inventory fingerprint; non-owned and
malformed files are byte-preserved; overlays survive updates; only journal-
owned paths can be removed; writes require exact approval; receipts verify and
rollback; Planner→Implementer→Reviewer attempts reload with immutable profile
snapshots, handoffs, budgets, retry, and evaluation entries.

Rollback: use the generated receipt against the isolated fixture only.

Stop condition: non-owned mutation, overlay deletion, hidden stage, expired or
mismatched approval, unsafe symlink traversal, or unverifiable rollback.

Fresh result (2026-08-02): 14 Harness Manager tests, clippy with `-D warnings`,
and the authenticated runtime inventory-route test
`harness_inventory_route_is_read_only_and_reports_projection_drift` passed.
The canonical repository verifier also passed with 1,048 Python tests (1
skipped) and all Rust cutover suites. No user home or external host was
mutated.

Artifact checksums:

```text
e1fe7706f9cbc1105a2043f98bb7c0dbcb01418b7ddae5992009a7a7b9bd4653  crates/codinal-harness/src/inventory.rs
dafd405f9cda38967271721a714b68ddba53003693534c41073a937202ab9df8  crates/codinal-harness/src/workflow.rs
1d5543c690e5763fc6874cde930c454e82ca3449773756843ad2e53a6ba4f8f0  crates/codinal-runtime/src/lib.rs
```
