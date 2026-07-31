# Codinal self-hosted Cursor-parity plan

## Intent and boundary

Deliver a local-first coding-agent workflow comparable to Cursor's practical
agent loop: isolated execution, visible test evidence, durable review/apply,
and eventually trusted remote workers. This plan does not create a hosted
Codinal service or silently export source code, credentials, or artifacts.

The current product already provides the local primitives: `SandboxedShell`
denies networking, sessions use isolated Git worktrees/checkpoints, the control
plane authenticates loopback clients, and the worker protocol reserves remote
execution while rejecting it until its trust contract exists.

## Delivery order

### Phase A — explicit execution profiles and evidence

1. Add immutable `read`, `test`, and `build` execution profiles at the sandbox
   boundary. Every profile keeps direct-argv execution, bounded output,
   cancellation, filesystem scopes, and network denied by default.
2. Add a structured `ExecutionEvidence` store keyed by session/turn/tool call:
   profile, argv digest, exit status, timing, truncation, changed paths, and
   bounded stdout/stderr digests.
3. Surface the selected profile and evidence in the review panel. Applying a
   diff requires explicit evidence when a plan declares a verification command.

Acceptance: a model cannot widen filesystem/network authority by naming a
profile; cancellation and restart preserve evidence without replaying a command;
tests verify denial, timeout, output cap, and evidence integrity.

### Phase B — browser/dev-server verification

1. Add a browser verifier as a separate optional capability, never a shell
   escape. It may inspect only user-approved loopback preview origins.
2. Persist screenshot hash, console errors, network summary, and assertion
   result as preview evidence; do not retain cookies, request bodies, or secrets.
3. Add UI controls to start, stop, and inspect a verification run; no computer
   use or arbitrary web navigation in this phase.

Acceptance: an unapproved/non-loopback origin is rejected; the browser process
is killed on cancellation; the review panel links immutable evidence to the
candidate diff.

### Phase C — self-hosted remote worker enrollment

1. Implement a connection-bound remote-worker lease over mutually authenticated
   transport, with server-minted worker/session IDs and expiring capability
   grants. A remote worker never receives provider secrets or parent approvals.
2. Require attestation of sandbox profile and repository revision before task
   dispatch. Transfer only a Git worktree artifact/diff plus bounded evidence.
3. Reuse local worker states and conflict-aborting adoption; remote results are
   review-only until an authenticated explicit apply action.

Acceptance: replayed/expired leases, wrong revision, missing attestation,
unknown capabilities, oversized artifacts, and cross-worker paths all fail
closed. A local in-process remote-agent fixture completes the full protocol;
actual network deployments remain opt-in configuration.

### Phase D — review and automation workflow

1. Add a first-party review job that runs selected deterministic checks against
   a worktree/diff and records actionable findings with evidence.
2. Add a local PR handoff: create a review artifact with branch, diff, checks,
   evidence, and suggested fixes. GitHub publishing stays separately approved.
3. Add project/path-scoped declarative review rules; show the effective rule
   set before a job starts and reject executable rule content.

Acceptance: review rules cannot execute code or change permissions; a failed
check cannot be presented as passing; no remote GitHub operation occurs without
an approval card.

### Phase E — provider action compatibility

1. Add a data-driven per-model capability registry with conformance evidence
   for tools, streaming, vision, PDFs, structured output, and parallel calls.
2. Display model/action compatibility before dispatch and block unsupported
   actions before the provider request.
3. Keep native-provider adapters separate from OpenAI-compatible custom
   gateways; GitHub credentials remain integration-only unless a model adapter
   is explicitly added.

Acceptance: unknown models fail closed for privileged actions; capability
updates are auditable and do not alter past turn evidence.

## Release gates

- Focused unit and control-plane integration tests per phase.
- A macOS Seatbelt test proves deny-by-default filesystem/network behavior.
- An end-to-end local remote-worker fixture proves lease, attestation, artifact
  verification, review, and explicit adoption.
- UI contract and accessibility checks cover profile/evidence states.
- `./verify.sh`, signed packaged-app smoke, and packaged sidecar evidence pass.

## Five scrutiny passes

### 1. Intent and simpler alternative

Finding: cloning Cursor cloud services would add hosted identity, billing, and
source-retention obligations absent from Codinal. Evidence: the product is an
authenticated loopback sidecar (`desktop/README.md`) and remote handshakes are
explicitly rejected (`runtime/control_plane/app.py`, worker route). Change:
deliver self-hosted remote protocol first; defer SaaS control plane. Verdict:
fix-then-ship — scope is now bounded to self-hosted execution.

### 2. Remote trust trace

Finding: permitting `worker_kind=remote` before a connection-bound lease would
turn a client-declared label into authority. Evidence: `runtime/workers/coordinator.py`
currently rejects remote dispatch and ADR 0002 requires transport, attestation,
and artifact transfer. Change: Phase C makes lease/attestation/artifact checks
preconditions, not optional metadata. Verdict: fix-then-ship.

### 3. Sandbox trace

Finding: a "networked test" profile would weaken the existing global
`(deny network*)` boundary in `runtime/sandbox/shell.py`. Evidence: the current
Seatbelt profile has no egress exception. Change: Phase A has only offline
profiles; any future egress is a separately approved proxy capability. Verdict:
fix-then-ship.

### 4. Browser and evidence trace

Finding: embedding unrestricted browser/computer use would bypass the current
preview evidence model and create secret/cookie retention risk. Evidence:
`desktop/ui/index.html` marks browser/computer use planned pending approval and
audit contracts; `runtime/preview/evidence.py` stores bounded console/annotation
evidence. Change: Phase B is loopback-only verification with redacted,
content-minimizing evidence. Verdict: fix-then-ship.

### 5. Delivery and verification trace

Finding: one large parity release would make failures unreviewable and cannot
be proved by a UI-only smoke test. Evidence: `verify.sh` already separates
product, Rust, and policy gates; `scripts/smoke-macos-release.sh` proves only
the packaged sidecar launch. Change: independently committed phases with an
end-to-end protocol fixture and a final packaged smoke gate. Verdict:
fix-then-ship — Phase A is the implementation entry point.
