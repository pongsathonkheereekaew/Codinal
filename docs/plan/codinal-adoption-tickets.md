# Codinal Competitive Adoption Tickets

Status: superseded implementation addendum
Date: 2026-08-01

Runtime status, Tauri/Python fallback, writer ownership, and delivery ordering in
this file are superseded by
[`rust-native-runtime-cutover.md`](rust-native-runtime-cutover.md). Reusable
behavior must be re-ticketed under that plan without Python/Tauri assumptions.

Canonical integration rule: this file is an implementation addendum. Once a
ticket is accepted, promote its ID and dependency into
`docs/plan/codinal-parity-roadmap.md`; do not maintain two competing copies of
the same status.

This is an additive implementation plan based on the competitor review. It does
not replace the parity roadmap. The goal is to copy useful behavior and
boundaries, not to import another project's dependency stack or product
assumptions.

## Decision

Adopt Comet's architectural ideas first. A typed command/transport boundary and
headed/headless session model fit Codinal's GPUI path and preserve the Tauri
fallback. Do not copy Comet's Loro, Durable Objects, R2, or other distributed
storage choices before Codinal has a measured need for them.

Use Deer Flow for run governance: durable receipts, explicit policies, and
bounded multi-agent work. Use JCode for operator-facing lifecycle and browser
workflow ergonomics. Keep proactive ambient behavior out of the MVP.

Implementation checkpoint (2026-08-01): the shared command transport is
compile-checked. Rust storage exposes a read-only turn receipt projection, and
the Python owner exposes the same `GET /v1/sessions/:id/turns` shape. Do not
add a Rust receipt writer until ownership changes by an explicit migration.

## Priority map

| Priority | Ticket | Borrowed idea | Rationale |
| --- | --- | --- | --- |
| P0 | COD-001 | Comet typed command bus and transport split | Creates the safest GPUI/Tauri seam. |
| P0 | COD-002 | Comet session attach/detach plus Deer Flow receipts | Makes runs inspectable and recoverable without distributed infrastructure. |
| P1 | COD-003 | JCode run/serve/connect lifecycle | Improves the operator loop after the transport seam is stable. |
| P1 | COD-004 | Deer Flow policy and sandbox profiles | Makes execution boundaries explicit before adding autonomy. |
| P2 | COD-005 | JCode browser-tool workflow | Useful UX, but not a prerequisite for the GPUI foundation. |
| P2 | COD-006 | Comet/Deer Flow observability and render discipline | Optimize from measurements, not from copied implementation details. |
| EXP | COD-007 | Ambient mode and multi-agent delegation | High external-effect and control-plane risk; feature-flag only. |

## Phase 0: transport foundation

### COD-001: typed command and transport boundary

Source signals: Comet's typed command flow; Codinal's GPUI parity and Tauri
rollback requirements in `docs/evidence/phase49-gpui-vs-comet.md` and
`desktop/gpui/PARITY.md`.

Scope:

- Before implementation, produce an entry-point map naming the existing GPUI,
  headless, and Tauri adapters plus three representative commands. If a
  surface does not exist, mark it unavailable instead of inventing a parallel
  path.
- Define a typed command envelope with command name, payload, request ID, and
  cancellation/deadline metadata.
- Route GPUI actions through one adapter into the existing runtime.
- Implement the same contract at the Tauri fallback boundary.
- Return a typed result/error envelope with a stable request ID.
- Add a headless transport harness that can exercise the contract without a
  window.

Acceptance criteria:

- The preflight map names three existing user actions, including run and
  stop/cancel or their current equivalents, and those actions use the command
  boundary from both GPUI and Tauri.
- No new GPUI view calls a provider/runtime implementation directly; the
  adapter is the only entry point.
- A cancelled, timed-out, and failed command produces a structured result and
  leaves the runtime in an observable state.
- A side-effecting command has an idempotency key; replaying the same key does
  not execute business logic twice. Reusing a request ID with a different
  payload returns a structured duplicate-request error.
- Cancellation after a command is already terminal is a safe no-op with a
  structured result.
- The same request can be traced from UI action to runtime result by request ID.
- Switching to the Tauri adapter preserves command semantics for the covered
  actions and does not require a second business-logic implementation.

Non-goals:

- No new provider abstraction unless the existing runtime cannot satisfy the
  contract.
- No distributed event bus, remote transport, or Comet storage dependency.

Dependencies: none. This is the first implementation ticket.

## Phase 1: durable run state

### COD-002: receipt-backed run sessions

Source signals: Comet headed/headless sessions and Deer Flow receipts. The
existing parity roadmap remains the source of truth for Codinal's current run
states: `docs/plan/codinal-parity-roadmap.md`.

Scope:

- Assign every run a stable run ID and lifecycle state.
- Persist a compact receipt containing input, selected policy, state changes,
  timestamps, result/error, and the request IDs that affected the run.
- Allow a headed GPUI view to detach while the headless run continues, then
  reattach by run ID.
- Reuse the same receipt and session contract through the Tauri fallback.
- Define bounded retention and a recovery behavior for incomplete receipts.
- Serialize or version state transitions per run ID so attach, detach, retry,
  and cancellation races have a defined result.

Acceptance criteria:

- Restarting the UI does not silently start a duplicate run; the latest run can
  be inspected by ID and explicitly resumed, cancelled, or abandoned.
- A detached run continues without a live window, and reattachment restores
  current state rather than replaying commands.
- Concurrent attach/detach and cancellation cannot create two terminal states;
  transitions are ordered or versioned per run ID.
- Every terminal run has exactly one terminal receipt state, including failure
  and cancellation.
- A partial write or process interruption yields a recoverable `incomplete`
  receipt instead of a falsely successful run.
- Replaying an already applied side-effecting command does not add a second
  receipt transition.
- Receipt size and retention are bounded by an explicit local policy; no remote
  object store is required.

Non-goals:

- Cross-device synchronization.
- Full event sourcing or a distributed workbench.

Dependencies: COD-001.

## Phase 2: operator lifecycle

### COD-003: explicit run, serve, and connect workflow

Source signal: JCode's persistent run/serve/connect workflow.

Scope:

- Expose explicit actions for starting a run, serving its reachable endpoint,
  and reconnecting to an existing run on the current operator surface.
- Make the lifecycle visible in the same run receipt used by COD-002.
- Make reconnect idempotent and distinguish "not running", "not reachable",
  and "permission denied".

Acceptance criteria:

- An operator can start a run, obtain its connection state, disconnect the UI,
  and reconnect by run ID without creating a second run.
- Repeating serve/connect is idempotent and does not silently take over an
  unrelated process or port.
- Connection failures show a structured reason and a next action; they are not
  reported as a generic run failure.
- GPUI and Tauri expose the same lifecycle state for the covered workflow.

Non-goals:

- Ambient or proactive startup by default.
- A new remote deployment platform.

Dependencies: COD-001 and COD-002.

### COD-004: explicit execution policy profiles

Source signal: Deer Flow's policy, sandbox, approval, and governance workflow.

Scope:

- Define named local profiles such as read-only, workspace-write, and
  network-restricted using capabilities Codinal can actually enforce.
- Maintain an enforcement inventory that maps each profile capability to the
  real executor or OS mechanism that enforces it.
- Resolve the selected profile before execution and record the resolution in
  the run receipt.
- Require an explicit approval transition for actions outside the selected
  profile.

Acceptance criteria:

- A run cannot claim a policy that the executor did not receive.
- A denied operation returns a structured reason and leaves an auditable receipt
  entry; it does not silently fall back to a broader profile.
- A capability without a real enforcement mechanism is absent from the profile;
  profile metadata alone is never treated as sandboxing.
- Approval is scoped to the run and action, expires or is consumed according to
  a documented rule, and is visible in the receipt.
- The default profile is the least-privileged profile that supports the current
  MVP workflow.

Non-goals:

- Claiming OS-level isolation that Codinal does not implement.
- Importing Deer Flow's full multi-agent control plane.

Dependencies: COD-002. Before implementation, map each profile capability to
the real executor boundary; unsupported capabilities must be removed from the
profile rather than merely documented.

## Phase 3: targeted UX and measured performance

### COD-005: browser-tool interaction contract

Source signal: JCode's browser-tool UX.

Scope:

- Give browser actions stable names, bounded timeouts, visible inputs and
  outputs, and a run ID.
- Store a compact browser action summary in the run receipt.
- Keep destructive navigation or external side effects behind COD-004 policy
  and approval.

Acceptance criteria:

- A browser action can be inspected, cancelled, and retried without losing the
  parent run ID.
- Timeout, target-not-found, and permission-denied cases are distinguishable.
- Browser output is bounded and redacted according to the active policy.
- The workflow is usable through both the GPUI path and the Tauri fallback, or
  is explicitly marked unavailable in one path.

Dependencies: COD-002 and COD-004.

### COD-006: evidence-driven observability and rendering budget

Source signals: Comet transcript/rendering discipline and Deer Flow
observability.

Scope:

- Add measurements for command latency, receipt writes, session reattachment,
  transcript size, and GPUI frame/update cost.
- Set budgets only after capturing a baseline on representative Codinal runs.
- Optimize the first measured hot path; do not copy an optimization by name.

Acceptance criteria:

- A repeatable benchmark records baseline and post-change values for the chosen
  hot path.
- A slow command and a dropped/late UI update can be correlated by request ID
  and run ID.
- Transcript or receipt growth is bounded under a long-running session.
- The optimization has a rollback switch or is trivially revertible without
  changing the command contract.

Dependencies: COD-001 and COD-002. This ticket stays P2 until measurements
identify a real bottleneck.

## Experimental gate

### COD-007: ambient mode and multi-agent delegation

Borrow only the control-plane ideas after the local single-run path is proven.

Entry conditions:

- COD-001 through COD-004 are complete and their receipts are reliable.
- A feature flag disables the experiment by default.
- A per-run budget, cancellation path, approval gate, and kill switch exist.

Acceptance criteria:

- Every delegated action has a parent run ID, child run ID, owner, budget, and
  policy receipt.
- Ambient triggers cannot perform external side effects without an explicit
  approval rule.
- Cancellation reaches all active children within a documented bound.
- Disabling the flag removes the behavior without changing the normal run path.

Reject for now:

- Full autonomous background operation as a default.
- Loro/DO/R2-style distributed persistence copied from Comet.
- Multi-agent orchestration without a durable, inspectable receipt hierarchy.

## Implementation order and definition of done

1. Map the existing runtime entry points and GPUI/Tauri adapters before coding
   COD-001. If the map reveals a different seam, update the ticket rather than
   adding a parallel command path.
2. Implement COD-001, then prove the same three commands through GPUI, headless,
   and Tauri adapters.
3. Implement COD-002 before adding lifecycle or autonomy UX; the receipt is the
   recovery and audit spine.
4. Take COD-003 and COD-004 in parallel only if they touch separate files and
   the policy enforcement boundary is already known; otherwise policy first.
5. Treat COD-005 and COD-006 as P2 until their prerequisite path and baseline
   exist. Treat COD-007 as experimental only.

For every P0 implementation, record a GPUI/headless/Tauri matrix covering the
covered commands, success, cancellation, timeout, failure, duplicate replay,
and restart/reattach behavior. A ticket is not done on unit tests alone. The
rollback criterion is that selecting the Tauri fallback preserves the same
terminal receipt semantics for the covered commands.

This plan is complete enough to start implementation when the entry-point map
and the three representative commands are named. It does not claim any ticket
is implemented.

## Scrutiny record

Five outsider passes were applied before treating this addendum as an
implementation draft:

1. Intent: the plan was necessary only if it stayed additive and did not split
   roadmap ownership. Added the canonical integration rule.
2. Trace: the proposed GPUI -> adapter -> runtime -> receipt -> reattach path
   depended on unnamed existing entry points. Added the preflight map gate and
   explicit missing-surface behavior.
3. Verify: retries, duplicate requests, terminal cancellation, and concurrent
   attach/detach could otherwise create duplicate work or conflicting receipt
   states. Added idempotency and per-run transition criteria.
4. Scope: policy names could imply security enforcement that Codinal does not
   have. Added the enforcement inventory and a hard rule against metadata-only
   sandbox claims.
5. Release: the plan lacked an end-to-end proof and rollback criterion. Added
   the GPUI/headless/Tauri matrix and terminal-receipt parity requirement.

Verdict: ship this as the implementation draft; block COD-001 coding until the
preflight entry-point map and representative command names exist.

## Evidence and provenance

- Codinal/Comet parity evidence: `docs/evidence/phase49-gpui-vs-comet.md`
- Current parity plan: `docs/plan/codinal-parity-roadmap.md`
- Competitive matrix: `docs/research/competitive-feature-matrix.md`
- GPUI parity constraints: `desktop/gpui/PARITY.md`
- Reference projects: [jcode](https://github.com/1jehuang/jcode),
  [deer-flow](https://github.com/bytedance/deer-flow), and
  [comet](https://github.com/zeronsh/comet)
