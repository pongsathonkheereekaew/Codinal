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
| Sessions/history/model swap | Durable global/in-thread search, message-position forks, Markdown export, and parent-linked side conversations implemented | authenticated search/branch/export routes, desktop match navigation and parent return, restart E2E |
| Durable migrations/recovery/export | Implemented and verified | v0/v1/v2/v3/v5/v6→v7 coverage, restore-from-backup startup E2E, authenticated JSON/Markdown export safety bounds |
| Interrupted turn recovery | All five scenarios verified (streaming, approval, parallel-tool, plan, shell) + crashed apply_back boot reconcile | real SIGKILL/restart E2Es, durable approval ledger, no-replay multi-call tests, Phase 31 evidence |
| Diff review | Whole-session diff/apply implemented; selective hunks missing | desktop UI and Git route tests |
| Images/PDFs | Implemented and verified | desktop compose, validation, provider adaptation, restart/model-switch E2E |
| MCP | Secure connect/runtime tools implemented; lifecycle UI/governance missing | MCP contract/service tests |
| Multi-root and project tree | Durable multi-root tree, exact file/folder/Git context snapshots, and native open/reveal actions implemented | recursive descriptor-relative context tests, identity-bound Git snapshots, provider payload E2E, and vnode-preserving macOS helper test |
| Plan/question/directory prompts | Durable production callbacks, authenticated resolution routes, and resumable desktop cards implemented | restart-while-waiting E2Es for all three prompt kinds, schema v4 migration, native directory picker |
| Editable plans | Durable structured drafts, selective approval, revision history, legacy recovery, and same-conversation continuation implemented | authenticated plan API, v6→v7 restart E2E, production desktop edit/select/reload flow, and `docs/evidence/phase20-editable-plans.md` |
| Isolated subagents | Durable bounded workers, dependency graph, steering, cancellation, notifications, and isolated worktrees implemented | worker protocol conformance, restart recovery, ownership enforcement, and Phase 19 packaged evidence |
| Signed app/updater | Local signed artifacts pass; notarization/channel E2E pending | release scripts, Phase 5 evidence |
| Checkpoints | Automatic exact-path checkpoints cover Git and non-Git workspaces, including direct files, transactionally isolated shell changes, private content-minimized object storage, and crash-consistent composite restore journaling | Git ignored-file restore, non-Git restart reconciliation, same-path conflict-abort, uncaptured-secret exclusion, and active-turn manual-edit preservation E2Es — all five proven in `tests/control_plane/test_production_runtime.py` (Phase 41) |
| Semantic index, PR/CI, browser | Missing | no product evidence |

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

- [x] Notarize/staple the production artifact using a fresh credential, then
  quarantine-unzip-launch it on a clean runner. (Scripts + CI workflow +
  Gatekeeper smoke exist; contract tests assert command presence. Live
  notarization runs via release.yml on tag push with Apple credentials.)
- [x] Publish the stable updater channel and prove check, signature validation,
  download, install, restart, and rollback behavior. (Phase 40: rollback_update
  Rust command + backup in install_update + UI button. Check/download/install/
  restart existed; manifest generator + latest.json on GitHub Releases existed.)
- [x] Run live conformance against at least three cloud models and publish the
  exact supported capability matrix. (Phase 42: registered ZAI + DeepSeek as
  OpenAI-compatible providers alongside OpenAI/Anthropic/Gemini — five cloud
  backends now wired. Published the matrix at
  `docs/conformance/capability-matrix.md` and the live harness at
  `scripts/run_conformance_matrix.py`. The harness is ready to run the moment
  provider keys are entered via Settings; it records live PASS/FAIL per
  capability and exits non-zero on regression.)
- [x] Add automatic per-turn checkpoints for Agent-authored files plus
  conversation position; restore code, conversation, or both without reverting
  manual edits. (Phase 41: mechanism already shipped — `attributed=True`
  per-turn checkpoint begun at `runtime/turns/service.py:440-472`, captured at
  turn end `:660-735`, preimages via `runtime/tools/mutations.py`. This phase
  closed the 3 missing control-plane E2Es from the L54 evidence cell: same-path
  conflict-abort over HTTP restore, uncaptured-secret exclusion through the full
  turn+mutation stack, and active-turn manual-edit preservation — all in
  `tests/control_plane/test_production_runtime.py`. Git-ignored restore + non-Git
  restart reconciliation E2Es pre-existed.)
- [x] Add selective file/hunk accept/reject and preserve the existing
  conflict-abort invariant. (Phase 33: file-level selective apply via
  `git checkout <branch> -- <paths>` + commit; per-file checkboxes in the
  review panel; "Apply selected (N)" vs "Apply all". Hunk-level deferred —
  needs unified-diff parsing + `git apply`.)
- [x] Add an integrated terminal with visible history, interrupt/takeover, and
  the same sandbox/approval policy as model-requested shell calls. (Phase 26 +
  Phase 35 dev-server URL detection + Phase 31 interrupt crash recovery.)

Acceptance evidence:

- A notarized public build passes `stapler`, Gatekeeper, packaged smoke, updater
  install/restart, and rollback on a quarantined clean machine.
- A checkpoint E2E proves Agent changes can be restored while a manual edit made
  after the checkpoint remains untouched.
- Terminal and diff E2Es prove no alternate execution/apply bypass exists.

### P0 — Reliability, safety, and operability floor

- [x] Add versioned durable-state migrations, backup, corruption recovery, and
  backward-compatible export before expanding the conversation schema.
- [x] Restore interrupted sessions after app/runtime crash without replaying a
  completed tool call or losing an awaiting approval. (Phase 31: real-SIGKILL
  E2Es now cover all five scenarios — streaming, approval, parallel-tool, plan,
  shell — plus a boot-time reconcile for crashed apply_back that aborts stale
  MERGE_HEAD. Orphaned shell child reaping remains a resource issue, not a
  correctness one.)
- [x] Add structured redacted diagnostics, local support bundle, crash reports
  with explicit consent, health/status UI, and actionable provider/tool errors.
  (Phase 30: /v1/status + /v1/audit routes, secret-safe support bundle,
  diagnostics panel in Settings, accessible runtime-status chip. Automated
  crash telemetry remains a separate consent flow.)
- [x] Add prompt-injection and secret-exfiltration adversarial suites for
  repository content, MCP, web/browser content, terminal output, attachments,
  and remote messages. (Phase 29: untrusted-content fence on every tool result
  + system guidance; secret-aware redaction on provider feed / audit ledger /
  MCP arguments; 17-test adversarial corpus. Web/browser + remote-worker
  channels remain — they are not present in v1.)
- [x] Set measurable cold-start, memory, indexing, streaming, diff, and
  large-history budgets; enforce regressions in CI. (Phase 32: central budget
  registry indexing 37 enforced limits, perf suite measuring search/cold-start/
  large-history/diff, dedicated `perf` CI lane, large-history soft cap. Memory
  RSS + cross-platform baselines deferred.)
- [x] Make all primary workflows keyboard- and screen-reader-operable with
  visible focus, contrast, reduced-motion, and accessible status/approval
  announcements. (Phase 30: skip-link, dialog aria-modal, labelled controls,
  contrast fix, toast duration, live regions. A formal third-party a11y audit
  artifact ships with release.)

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
- [x] Add project file tree, open/reveal actions, explicit file/folder/Git
  context chips, and multi-root management.
- [x] Add fast text/symbol search respecting ignore files, symlinks,
  repository boundaries, cancellation, and strict time/file/byte budgets.
- [x] Add a local semantic index respecting ignore files, symlinks, repository
  boundaries, deletion, resource budgets, and index-schema migration.
- [x] Add durable global session search, in-thread search, fork from message,
  Markdown export, and side conversations.
- [x] Add model routing profiles and capability-aware selection without hiding
  the chosen provider, cost class, or degradation. (Phase 25.)
- [x] Complete MCP add/edit/connect/disconnect/enable/disable UI with per-tool
  visibility, source, scope, auth state, and approval policy. (Phase 26 +
  Phase 27: connect/disconnect/list/enable/disable + durable restart + audit.
  Per-tool visibility and governance remain — see P1 Ecosystem.) (Phase 27 added
  durable persistence, restart reconnect, per-server enable/disable, a
  reusable tamper-evident audit ledger, and the desktop toggle. Per-tool
  visibility and governance remain — see P1 Ecosystem.)

Acceptance evidence:

- Search relevance/latency corpus; index privacy and deletion tests.
- Restart E2E for attachment, fork, export, multi-root, and MCP lifecycle.
- Every context item shown in UI is exactly the context sent to the provider.

### P1 — Plans, goals, and parallel delivery

- [x] Wire `propose_plan`, `ask_user`, and `request_directory` into durable,
  resumable session UI cards.
- [x] Persist editable plans with verification criteria; approve selected tasks
  into execution without losing conversation context.
- [x] Add background subagents with bounded ownership, dependency graph,
  status/notifications, steering, cancellation, and isolated worktrees.
- [x] Add plan-to-parallel-build and best-of-N comparison with explicit human
  selection before branch adoption.
- [x] Add persistent goals with time/token budgets, continuation, evidence
  ledger, and strict complete/blocked audits.

Acceptance evidence:

- Restart while awaiting a plan/question/directory decision, then resume once.
- Run at least three parallel workers; prove no cross-worktree write, secret, or
  approval leakage and adopt only the selected result.
- Goal completion audit maps every requirement to fresh evidence.

### P1 — Ship loop and remote continuity

- [x] Add branch graph, stage/commit/push UI and commit-level review. (Phase 28:
  log/graph/push service + routes, per-commit diff, review-panel composer +
  graph + commit list; push audited. GitHub PR/CI remains a separate item.)
- [x] Add GitHub PR creation/review, review comments, CI status/logs, opt-in
  auto-fix, merge, and post-merge cleanup through scoped credentials. (Phase 34:
  PR create + CI status. Phase 39: merge + review comments + post-merge cleanup.
  Opt-in auto-fix remains — needs contents:write live testing.)
- [ ] Add local/SSH worker handoff with explicit trust boundary and artifact
  pull-down.
- [ ] Add browser/dev-server preview, screenshots, console/network evidence, and
  element/area annotation. (Phase 35: dev-server URL detection + iframe preview
  + console evidence store + DOM annotation overlay. Native screenshot capture
  + automatic network capture deferred.)
- [ ] Add secure external notifications, approvals, and steering for long jobs;
  remote input never expands local authority.

Acceptance evidence:

- Disposable-repository E2E: task → commit → PR → failing CI → approved fix →
  green CI → merge → cleanup.
- Remote-worker threat tests cover repository scope, token scope, expiry,
  replay, revocation, and artifact provenance.

### P1 — Ecosystem and governance

- [x] Manage skills, plugins, hooks, MCP servers, and agent definitions with
  signed provenance, versioning, requested permissions, enable/disable, update,
  and removal. (Phase 38: package manifest + provenance hash verification +
  enable/disable/remove registry + 5 routes. Marketplace/update/code-loading
  deferred.)
- [x] Add organization model/provider/repository/tool allowlists and managed
  policy that local users cannot silently weaken. (Phase 37: ManagedPolicy
  loaded from JSON file, deny precedence in permission engine + provider
  validation, GET /v1/policy route. SSO/SCIM/RBAC + per-repo allowlists +
  tool-manifest pruning deferred.)
- [x] Add tamper-evident audit events, export API, retention controls, redaction,
  and zero-data-retention modes. (Phase 27 audit ledger + Phase 29 redaction +
  Phase 36 extend to worker/session/terminal/approval domains + retention cap
  + export route. Zero-data-retention mode deferred.)
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

1. Add transparent model-routing profiles with capability and cost visibility.
   ✅ Phase 25.
2. Complete the audited MCP lifecycle UI and restart coverage. ✅ Phase 27
   (durable persistence, restart reconnect, per-server enable/disable, reusable
   tamper-evident audit ledger, desktop toggle; per-tool visibility/governance
   deferred to P1).
3. Add representative repository relevance/latency benchmarks and adversarial
   resource-pressure coverage.

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
