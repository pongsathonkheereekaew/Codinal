---
stage: C5
owner: codinal-runtime/tools
dependencies: [C4a-c]
status: passed
---

# C5 tool expansion gate

The implementation order is shell sandbox, Git/worktrees, then MCP. Each tool
class must reuse the runtime policy, workspace/symlink boundary, approval,
interrupt, audit, receipt, and recovery path. No tool schema is enabled merely
because a host declares support.

Stop condition: policy bypass, external/network access without approval,
destructive command escape, missing interrupt, missing receipt, or unrecovered
partial mutation.

Deterministic implementation result (2026-08-02): `24 codinal-tools` tests
pass across shell, Git/worktree failure/retry, MCP, approval, interrupt, audit, receipt,
restart recovery, output-limit/timeout, malformed JSON-RPC, idempotent
operation lifecycle, deadline enforcement, and cancelled execution-boundary
cases. Fresh targeted runs for the Git approval boundary, Git worktree
lifecycle, MCP approval, and MCP interrupt/timeout all passed. The checked-in
stdio MCP fixture validates the incoming JSON-RPC method
before returning a result. Failed worktree recovery removes only the
prevalidated operation-owned target and preserves siblings. A real `git
worktree add` process was interrupted after its checkout hook materialized the
target; the terminal receipt reported interruption, the owned target was
recovered, and a sibling path survived. The authenticated runtime operation
route test, runtime suite (`116 passed, 3 ignored`), and `-D warnings` clippy
checks pass. The runtime worker now stops before tool execution when start
progress, cancellation, or deadline validation fails, and persists terminal
progress failures instead of silently discarding them. No user repository,
home directory, network server, or credentialed MCP endpoint was touched.

The checked-in [per-tool matrix](adversarial-matrix.md) maps every fresh local
shell/Git/MCP and operation-ledger test to its adversarial condition. Local Git
process failure/retry/partial-target recovery, the checked-in MCP stdio server,
and MCP child timeout/interrupt are covered. External user-repository and
credentialed MCP-host conformance remains out of scope for the deterministic
gate run.

Artifact checksum (fresh local adversarial suite):

Source checksums:

```text
cdde7ab5f061a17f2add4c9eb66bfa5046b6100f424bfccbb102eb2833be06da  crates/codinal-tools/src/lib.rs
e914c68d28cb9c789b39554ca56a3775ae05d6603a7f59e5adb11578e43d59ca  crates/codinal-tools/src/operation.rs
1d5543c690e5763fc6874cde930c454e82ca3449773756843ad2e53a6ba4f8f0  crates/codinal-runtime/src/lib.rs
```
