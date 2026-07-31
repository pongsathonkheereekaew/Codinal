Type: task
Status: resolved
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

## Evidence

- `codinal-policy::AuditLedger` opens the migrated Python v1 database only
  after schema, SQLite integrity, retained-sequence, and full hash-chain checks.
- Python-compatible canonical JSON vectors cover ASCII, Thai/Unicode,
  surrogate pairs, fixed floats, and exponent-formatted floats.
- Immediate transactions serialize concurrent appends; tamper, tail
  truncation, malformed metadata, oversized payloads, and exhausted capacity
  fail closed.
- Recursive payload and metadata redaction supports live secret rotation and
  zeroizes replaced exact-secret values.
- Rust policy tests cover restart, retained/pruned ledgers, concurrency,
  persisted redaction, and compatible approval allow/deny metadata. Python's
  reference audit suite remains green.
- Production mutation routes remain disabled pending the rest of the R2 gate.
