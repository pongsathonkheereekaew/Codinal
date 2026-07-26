# Codinal production parity roadmap

Status: active
Evidence date: 2026-07-26
Competitive baseline:
[`docs/research/competitive-feature-matrix.md`](../research/competitive-feature-matrix.md)

## Destination

Codinal is a released, production-grade desktop AI coding application whose
daily coding, recovery, context, parallel-delivery, shipping, extension, and
administration workflows are competitive with Codex, Claude Desktop, Cursor,
and Z.ai ZCode, while remaining model-agnostic and enforcing every consequential
action through the harness policy boundary.

This roadmap carries execution, not only planning. A phase closes only when its
acceptance evidence is recorded from the real product surface.

## Non-negotiable invariants

1. Models, MCP servers, plugins, subagents, UI commands, and remote entry points
   never execute tools outside `PermissionEngine`.
2. Release builds use only signed embedded runtime code; provider secrets stay
   in native credential storage and never enter argv, logs, persisted messages,
   or updater metadata.
3. Parallel work uses isolated Git worktrees or remote workers. Adoption into a
   user's branch is explicit, reviewable, conflict-safe, and reversible.
4. Local-first features work without a Codinal cloud account. Networked
   indexing, telemetry, remote workers, and external control are opt-in and
   disclose data boundaries.
5. A green unit suite is not product evidence. Desktop workflows require
   packaged-app smoke/E2E evidence; distribution requires notarized,
   quarantined-artifact evidence.

## Current evidence

| Capability | State | Authoritative evidence |
| --- | --- | --- |
| Provider-neutral turns | Implemented; live Tier-1 conformance pending | `runtime/providers`, `runtime/turn_engine`, provider tests |
| Policy and approvals | Implemented | `runtime/policy`, approval broker E2E |
| OS shell sandbox | Implemented on macOS | sandbox negative tests and notarization spike |
| Isolated session worktrees | Implemented | Git lifecycle E2E and Apply conflict tests |
| Sessions/history/model swap | Implemented baseline | SQLite/session route/UI tests |
| Durable migrations/recovery/export | Implemented and verified | v0/v1/v2/v3 matrix, restore-from-backup startup E2E, authenticated export v1 with 32 MiB stored-data safety bound |
| Interrupted turn recovery | Streaming, approval, and parallel-tool baseline verified; plan/shell/apply-back pending | real SIGKILL/restart E2Es, durable approval ledger, no-replay multi-call tests |
| Diff review | Whole-session diff/apply implemented; selective hunks missing | desktop UI and Git route tests |
| Images/PDFs | Implemented and verified | desktop compose, validation, provider adaptation, restart/model-switch E2E |
| MCP | Secure connect/runtime tools implemented; lifecycle UI/governance missing | MCP contract/service tests |
| Multi-root and artifacts | Service methods exist; complete API/UI workflows missing | `runtime/sessions/service.py` |
| Plan/question/directory prompts | Engine primitives exist; production callbacks/UI missing | `runtime/turn_engine/engine.py` |
| Signed app/updater | Local signed artifacts pass; notarization/channel E2E pending | release scripts, Phase 5 evidence |
| Checkpoints | Git-worktree baseline, exact-path direct-file attribution (including ignored files), transactionally isolated shell attribution, and a crash-consistent composite restore journal are implemented with private object storage; non-Git coverage remains open | automatic lifecycle, ambiguous-boundary restart reconciliation, direct+shell ignored-file restore, same-path conflict-abort, and active-turn manual-edit preservation E2Es |
| Semantic index, parallel subagents, PR/CI, browser | Missing | no product evidence |

## Execution map

### Architecture gates

Resolve these before their dependent implementation:

- **Durable state:** introduce explicit SQLite/settings schema versions,
  forward-only migrations, pre-migration backup, integrity check, and recovery
  before checkpoints, forks, search indexes, plans, or goals add persisted
  state.
- **Editor:** embed a maintained editor component and speak standard LSP; do not
  build a text editor, parser, or language intelligence stack from scratch.
- **Workers:** define one authenticated, versioned local/remote worker protocol
  with capability negotiation before adding subagents or SSH/cloud handoff.
- **Governance:** define signed package provenance and the managed-policy trust
  root before building a plugin marketplace or organization controls.

### P0 — Release and trust floor

- [ ] Notarize/staple the production artifact using a fresh credential, then
  quarantine-unzip-launch it on a clean runner.
- [ ] Publish the stable updater channel and prove check, signature validation,
  download, install, restart, and rollback behavior.
- [ ] Run live conformance against at least three cloud models and publish the
  exact supported capability matrix.
- [ ] Add automatic per-turn checkpoints for Agent-authored files plus
  conversation position; restore code, conversation, or both without reverting
  manual edits.
- [ ] Add selective file/hunk accept/reject and preserve the existing
  conflict-abort invariant.
- [ ] Add an integrated terminal with visible history, interrupt/takeover, and
  the same sandbox/approval policy as model-requested shell calls.

Acceptance evidence:

- A notarized public build passes `stapler`, Gatekeeper, packaged smoke, updater
  install/restart, and rollback on a quarantined clean machine.
- A checkpoint E2E proves Agent changes can be restored while a manual edit made
  after the checkpoint remains untouched.
- Terminal and diff E2Es prove no alternate execution/apply bypass exists.

### P0 — Reliability, safety, and operability floor

- [x] Add versioned durable-state migrations, backup, corruption recovery, and
  backward-compatible export before expanding the conversation schema.
- [ ] Restore interrupted sessions after app/runtime crash without replaying a
  completed tool call or losing an awaiting approval.
- [ ] Add structured redacted diagnostics, local support bundle, crash reports
  with explicit consent, health/status UI, and actionable provider/tool errors.
- [ ] Add prompt-injection and secret-exfiltration adversarial suites for
  repository content, MCP, web/browser content, terminal output, attachments,
  and remote messages.
- [ ] Set measurable cold-start, memory, indexing, streaming, diff, and
  large-history budgets; enforce regressions in CI.
- [ ] Make all primary workflows keyboard- and screen-reader-operable with
  visible focus, contrast, reduced-motion, and accessible status/approval
  announcements.

Acceptance evidence:

- Migration matrix upgrades every retained released schema and restores from an
  intentionally corrupted copy without overwriting the original.
- Kill/restart E2Es cover streaming, shell execution, approval wait, plan wait,
  and apply-back.
- Redaction corpus proves secrets never enter logs/support bundles.
- Accessibility audit and performance benchmark artifacts ship with releases.

### P0 — Daily coding and context floor

- [x] Ship bounded image/PDF attachment compose, persistence, reload, model
  switch degradation, and local PDF fallback.
- [ ] Add project file tree, open/reveal actions, explicit file/folder/Git
  context chips, and multi-root management.
- [ ] Add fast text/symbol search, then a local semantic index respecting
  ignore files, symlinks, repository boundaries, deletion, resource budgets,
  and index-schema migration.
- [ ] Add durable global session search, in-thread search, fork from message,
  Markdown export, and side conversations.
- [ ] Add model routing profiles and capability-aware selection without hiding
  the chosen provider, cost class, or degradation.
- [ ] Complete MCP add/edit/connect/disconnect/enable/disable UI with per-tool
  visibility, source, scope, auth state, and approval policy.

Acceptance evidence:

- Search relevance/latency corpus; index privacy and deletion tests.
- Restart E2E for attachment, fork, export, multi-root, and MCP lifecycle.
- Every context item shown in UI is exactly the context sent to the provider.

### P1 — Plans, goals, and parallel delivery

- [ ] Wire `propose_plan`, `ask_user`, and `request_directory` into durable,
  resumable UI cards and inbox state.
- [ ] Persist editable plans with verification criteria; approve selected tasks
  into execution without losing conversation context.
- [ ] Add background subagents with bounded ownership, dependency graph,
  status/notifications, steering, cancellation, and isolated worktrees.
- [ ] Add plan-to-parallel-build and best-of-N comparison with explicit human
  selection before branch adoption.
- [ ] Add persistent goals with time/token budgets, continuation, evidence
  ledger, and strict complete/blocked audits.

Acceptance evidence:

- Restart while awaiting a plan/question/directory decision, then resume once.
- Run at least three parallel workers; prove no cross-worktree write, secret, or
  approval leakage and adopt only the selected result.
- Goal completion audit maps every requirement to fresh evidence.

### P1 — Ship loop and remote continuity

- [ ] Add branch graph, stage/commit/push UI and commit-level review.
- [ ] Add GitHub PR creation/review, review comments, CI status/logs, opt-in
  auto-fix, merge, and post-merge cleanup through scoped credentials.
- [ ] Add local/SSH worker handoff with explicit trust boundary and artifact
  pull-down.
- [ ] Add browser/dev-server preview, screenshots, console/network evidence, and
  element/area annotation.
- [ ] Add secure external notifications, approvals, and steering for long jobs;
  remote input never expands local authority.

Acceptance evidence:

- Disposable-repository E2E: task → commit → PR → failing CI → approved fix →
  green CI → merge → cleanup.
- Remote-worker threat tests cover repository scope, token scope, expiry,
  replay, revocation, and artifact provenance.

### P1 — Ecosystem and governance

- [ ] Manage skills, plugins, hooks, MCP servers, and agent definitions with
  signed provenance, versioning, requested permissions, enable/disable, update,
  and removal.
- [ ] Add organization model/provider/repository/tool allowlists and managed
  policy that local users cannot silently weaken.
- [ ] Add tamper-evident audit events, export API, retention controls, redaction,
  and zero-data-retention modes.
- [ ] Add SSO/SCIM/RBAC and managed deployment profiles without moving local
  tool execution outside its sandbox.

Acceptance evidence:

- Malicious-extension suite proves install-time disclosure and runtime policy
  enforcement.
- Admin-policy E2E proves deny precedence across UI, model, MCP, plugin,
  subagent, terminal, and remote control paths.

### P2 — Editor intelligence, platforms, and differentiated workflows

- [ ] Add language-server symbol navigation, diagnostics, references, rename,
  and code actions.
- [ ] Add low-latency multi-line/cross-file completion and scoped inline edit
  on the maintained editor/LSP foundation, with explicit local/cloud data
  handling.
- [ ] Package and sign Intel macOS, Windows x64/ARM64, and Linux x64/ARM64;
  preserve sandbox and updater guarantees per platform.
- [ ] Add repo knowledge/wiki, scheduled tasks, voice input, and opt-in
  visual/computer-use tools.

Acceptance evidence:

- Language/latency benchmark across representative repositories.
- Signed update/install/rollback matrix on every supported architecture.
- Scheduled and computer-use actions obey the same approval and audit model.

## Immediate frontier

1. Extend automatic per-turn checkpoints to non-Git workspaces. Exact-path
   direct-file attribution (including ignored Git-worktree files),
   transactionally isolated shell attribution, and crash-consistent
   multi-scope restore journaling are implemented.
2. Complete plan/question/directory prompts, because their engine contracts
   already exist and they unblock safe plan-to-build.
3. Build searchable/forkable sessions and explicit context/file-tree surfaces.
4. Add parallel isolated subagents only after checkpoint recovery is proven.

## Decisions so far

- Codinal targets both command-center and editor-centric workflows; Cursor's
  code intelligence is not excluded merely because the current shell is a
  command center.
- Semantic indexing is local-first. A future shared/cloud index requires
  separate explicit consent and retention controls.
- Checkpoints precede parallel autonomy: recovery is a prerequisite for more
  concurrent mutation.
- Existing engine capabilities are wired before parallel replacements are
  invented.
- “Zcode” means Z.ai ZCode for this roadmap; the unrelated macOS app-builder
  product remains documented as an ambiguity in the research note.
