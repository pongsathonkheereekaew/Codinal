Type: task
Status: resolved
Blocked by: 05

## Question

Can the Rust runtime read compatible session and message data from its shadow
snapshot and serve the authenticated v1 session-list and session-message routes
without adding any writable storage API?

## Answer

Yes. `codinal-storage` opens `codinal.db` with SQLite read-only flags, returns
public non-worker session metadata in Python-compatible order, and decodes
ordered message payloads. `codinal-runtime` exposes those reads only through
the existing bearer-authenticated loopback listener. The real-binary shadow
launch test proves both routes against an isolated snapshot; no storage write
API or production-runtime selection was added.

Verified with locked runtime/storage tests and Clippy with warnings denied.
