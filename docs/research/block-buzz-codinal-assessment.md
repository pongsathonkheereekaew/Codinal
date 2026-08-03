# Block Buzz → Codinal assessment

Research date: 2026-07-31

## Bottom line

**Do not adopt Buzz as a foundation or pivot Codinal toward a relay-first collaboration product.** Buzz solves a broader, server-backed team workspace problem; Codinal is a local-first, safety-bound coding-agent desktop. Its best lessons are product and protocol patterns to **adapt**, not code to vendor.

Buzz is an Apache-2.0 Rust workspace built around a self-hosted Nostr relay. It models human, agent, workflow, review, and Git activity as signed events in one audit/search substrate. Its own README distinguishes shipped features from items still being wired. [README](https://github.com/block/buzz/blob/main/README.md) · [architecture](https://github.com/block/buzz/blob/main/ARCHITECTURE.md)

Codinal already has the core local coding-runtime foundations Buzz would not replace: policy-bound execution, Seatbelt sandboxing, per-session Git worktrees/apply-back, durable checkpoints, bounded workers, goals, plans, provider routing, authenticated control plane, and tamper-evident auditing. [Codinal runtime overview](../../runtime/README.md) · [worker protocol](../decisions/0002-worker-protocol.md) · [parity roadmap](../plan/codinal-parity-roadmap.md)

## What to adopt

1. **A unified, typed activity timeline for delivery evidence — P1.**
   Buzz makes messages, workflow steps, review approvals, and Git events queryable activity in a common event substrate; its relay event pipeline persists, fans out, indexes, audits, then triggers automation. [Buzz architecture: event pipeline](https://github.com/block/buzz/blob/main/ARCHITECTURE.md#4-event-pipeline)

   Codinal should expose its existing turn, approval, worker, checkpoint, Git, CI, and audit records as one *read model* in the session/project timeline. Keep the authoritative stores and policy boundaries intact; do not replace them with a generic event log. Success: a user can answer “why did this change land?” from one timeline that links plan item → worker/turn → diff → verification → approval → commit/PR.

2. **Branch/task rooms as a first-class UI projection — P1.**
   Buzz’s useful UX idea is that a branch channel contains the patch, review, CI result, discussion, and merge decision—the durable rationale around a change. [Buzz Projects: branches as channels](https://github.com/block/buzz/blob/main/VISION_PROJECTS.md#branches-as-channels)

   Adapt this to a Codinal “delivery room” bound to an existing session worktree/branch, not a new chat service. It should aggregate current Codinal artifacts and GitHub data, retain the session’s local-first semantics, and remain usable offline.

3. **Externally verifiable provenance for remote workers and artifacts — P2, gated.**
   Buzz uses per-actor cryptographic identity and signed Git/review/workflow events; its agent model separates an agent identity from its owner attestation. [Buzz Projects: agents and trust](https://github.com/block/buzz/blob/main/VISION_PROJECTS.md#the-web-of-trust) · [NIP-OA design](https://github.com/block/buzz/blob/main/docs/nips/NIP-OA.md)

   When Codinal implements remote/SSH workers, add signed artifact receipts with worker key, task/branch/base SHA, tool/version attestation, timestamps, and verification digest. This complements—rather than replaces—Codinal’s authenticated `codinal.worker.v1` protocol. Do not make Nostr a dependency unless federation becomes an explicit product goal.

## What to adapt carefully

1. **Event contracts, not an event-sourced rewrite — P2.** Buzz’s extensible “new kind” protocol is clean, but its relay is the single source of truth. [Architecture: protocol and core principle](https://github.com/block/buzz/blob/main/ARCHITECTURE.md#2-the-protocol) Codinal should define a versioned internal `ActivityEvent` envelope and projections over its current durable stores. Avoid dual writes and a migration to a relay/event-store as the runtime authority.

2. **Automation from explicit events — P2.** Buzz supports YAML workflows triggered by message, reaction, schedule, webhook, and Git events, while its documentation notes workflow approval gates are still being wired. [Buzz README: shipped/status table](https://github.com/block/buzz/blob/main/README.md#works-today--being-wired-up--strong-opinions-pending-code) · [workflow design](https://github.com/block/buzz/blob/main/VISION_PROJECTS.md#ci-and-workflows)

   Codinal can add opt-in, policy-governed automations such as “CI failed → draft diagnosis” or “PR review requested → start bounded review.” Every trigger must pass the current approval/risk/audit path; no ambient channel message may grant execution authority. This is a deliberate adaptation: Buzz documents that a workflow approval request does not yet persist/resume. [Buzz workflow limits](https://github.com/block/buzz/blob/main/ARCHITECTURE.md#buzz-workflow--yaml-as-code-automation-engine)

3. **Agent identity as a visible accountability object — P2.** Show stable local/remote worker identity, declared ownership paths, provider/model, permissions, and evidence receipts in worker cards and delivery rooms. Buzz’s human/agent symmetry is a strong UX principle, but Codinal must preserve stricter least-privilege separation: Codinal workers intentionally do **not** inherit parent approvals or roots.

## Do not adopt

1. **Relay-first/Nostr as Codinal’s control plane.** Buzz requires a self-hosted relay with WebSocket/REST clients plus Postgres, Redis, and S3/MinIO for its collaboration architecture. [Buzz README: architecture](https://github.com/block/buzz/blob/main/README.md#architecture) That conflicts with Codinal’s local-first runtime and would enlarge attack surface, operations, and offline failure modes.

2. **“Agents equal humans” as an authorization model.** Buzz scopes agents principally through identities and channel membership. [Buzz README](https://github.com/block/buzz/blob/main/README.md#stuff-you-do-in-buzz) Codinal correctly scopes consequential behavior through manifest, risk class, approval, path ownership, sandbox, and worktree isolation. Identity is useful provenance, not sufficient authorization.

3. **Buzz code vendoring for core agent execution.** `buzz-agent`/`buzz-dev-mcp` prioritize small ACP/MCP binaries and state that the shell runs at the operator’s trust level. [Buzz agent vision](https://github.com/block/buzz/blob/main/VISION_AGENT.md) Codinal needs its existing policy chokepoint and OS-enforced sandbox; importing Buzz execution code would create a second tool-authority path.

4. **Forge, social, and federation scope now.** Git hosting, channels, DMs, canvases, huddles, reputation, and multi-community federation are a different product. Buzz itself says it is not finished and labels several areas as pending. [Buzz README](https://github.com/block/buzz/blob/main/README.md#what-it-is-not)

5. **Security assumptions that weaken Codinal’s existing posture.** Buzz correctly validates auth, signatures, and channel membership before storing/fanning out events, including a private-channel subscription boundary. [Buzz event pipeline](https://github.com/block/buzz/blob/main/ARCHITECTURE.md#4-event-pipeline) But its documented workflow approval persistence and production rate limiting are incomplete. [Buzz workflow limits](https://github.com/block/buzz/blob/main/ARCHITECTURE.md#buzz-workflow--yaml-as-code-automation-engine) · [Buzz auth limits](https://github.com/block/buzz/blob/main/ARCHITECTURE.md#buzz-auth--authentication-and-authorization) Codinal should retain its fail-closed, durable approval and local sandbox boundaries.

## Recommended sequence

1. Specify the read-only `ActivityEvent` projection and render it in the existing session/branch UI; backfill from current audit, Git, worker, plan, and checkpoint stores.
2. Build the “delivery room” UI and GitHub/CI links on top of that projection; prove a disposable-repo task-to-PR trace end-to-end.
3. At the remote-worker milestone, add signed artifact receipts and verify them on adoption; defer any federation decision until a real cross-organization use case exists.

## Decision

**Yes, learn from Buzz; no, do not adopt it wholesale.** The high-value addition for Codinal is an evidence-rich collaborative delivery surface built atop its existing local, policy-enforced runtime—not a new relay, social workspace, or agent authorization model.
