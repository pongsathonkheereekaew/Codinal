# ADR 0002 — Versioned worker protocol and isolated subagents

Status: accepted

## Context

Codinal needs background local subagents now and SSH/cloud workers later. A
local-only scheduler API would create a second trust model when remote workers
arrive. Workers must therefore share one authenticated, versioned protocol and
must never inherit authority merely because their parent session has it.

## Decision

The control plane owns orchestration. Every local or remote worker connects
through protocol version `codinal.worker.v1` and negotiates explicit
capabilities before receiving a task.

Required v1 capabilities:

- `task.execute`
- `task.status`
- `task.steer`
- `task.cancel`
- `artifact.git-worktree`

The task envelope contains a server-minted worker ID, parent and isolated child
session IDs, dependency IDs, model, task text, and non-empty repository-relative
ownership paths. Unknown fields, capabilities, versions, state transitions, and
client-chosen authority are rejected.

Local workers use a distinct Git worktree/session per worker. They begin with:

- no inherited tool/command approvals;
- no inherited additional roots;
- no directory-request tool;
- writes and shell-applied deltas restricted to declared ownership paths;
- provider access through the existing in-memory router, never through exported
  credentials.

Delegation starts from the parent session worktree, not the original checkout.
The parent must be clean so the child sees an exact committed baseline and
adoption applies back into the parent session for review before any top-level
workspace apply.

Workers may read the repository to understand dependencies. A worker cannot
write another worker's worktree because its `PermissionEngine`, mutation
registry, transactional shell, and Seatbelt sandbox are all built for its own
child session.

Worker state is durable and monotonic:

`queued → blocked|running → finalizing → succeeded → adopting → adopted`

`blocked` returns to `queued` only when dependencies succeed. Steering is
append-only and accepted only while running. Cancellation is terminal.
Any safe non-terminal execution state may fail or be cancelled. A completed
turn enters durable `finalizing` before Git commit. Restart fails closed for an
inactive `running` worker and resumes only durable `finalizing` work; it never
replays a completed tool call.

Adoption is a separate authenticated action. Only a succeeded worker with a
clean committed worktree can be adopted, using the existing conflict-aborting
Git apply-back path. Other worker results remain isolated.

Phase 19 enables the authenticated handshake and dispatch path for `local`
workers. Local dispatch performs the same v1 capability negotiation inside the
trusted coordinator before persisting or delivering a task; the HTTP handshake
mirrors that contract for control-plane clients. The v1 schema reserves
`remote`, but the control plane rejects remote
handshakes and dispatch until a connection-bound lease, transport, attestation,
and artifact-transfer implementation is present. A remote label never falls
back to local execution.

## Consequences

- Local and future remote execution share message/state semantics.
- Parallelism does not broaden authority.
- Task ownership is enforced at every mutation path, not only in prompts.
- Remote transport, leases, attestation, and artifact transfer can extend v1
  capabilities without bypassing the local policy boundary.
