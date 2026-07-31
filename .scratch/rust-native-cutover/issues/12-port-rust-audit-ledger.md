Type: task
Status: open
Blocked by: 11

## Question

Can the Rust runtime own the append-only, hash-chained audit ledger and expose
bounded redacted audit reads before any production mutation route is enabled?

## Destination

Advance the R2 security/policy gate in
`docs/plan/rust-native-runtime-cutover.md`: every consequential action must
share one Rust approval chokepoint and durable audit contract.

## Required evidence

- Hash-chain and restart verification match the Python v1 ledger.
- Payloads are bounded and secret-redacted before persistence.
- Corruption, replay, truncation, and concurrent append fail closed.
- Approval allow/deny outcomes produce compatible durable audit metadata.

## Out of scope

- Enabling production mutation routes before the full R2 gate passes.
