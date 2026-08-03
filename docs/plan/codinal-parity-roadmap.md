# Codinal production parity roadmap

Status: historical parity inventory
Evidence date: 2026-07-26
Competitive baseline:
[`docs/research/competitive-feature-matrix.md`](../research/competitive-feature-matrix.md)

Runtime architecture and cutover order are superseded by
[`rust-native-runtime-cutover.md`](rust-native-runtime-cutover.md). Python
implementation references below are evidence sources, not allowed production
or fallback paths.

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
| Semantic index | Implemented; representative relevance/latency evidence pending | `runtime/indexing/semantic.py`, `tests/indexing/test_semantic_index.py` |
| PR/CI | Partial; create/status/merge/cleanup routes exist; full ship-loop evidence pending | `runtime/github`, control-plane routes, GitHub route tests |
| Browser | Partial; loopback preview/evidence and DOM annotation exist; screenshot/network capture pending | `runtime/preview`, Phase 35 evidence |

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
- [x] Native self-hosted gateway provider (OmniRoute). (Phase 45: registered
  OmniRoute as a sixth cloud backend — an OpenAI-compatible self-hosted
  gateway with 290+ upstream providers and 19 routing strategies. Widened the
  secret profile schema from `{api_key}` to `{api_key, base_url?}` so the
  gateway's user-configurable endpoint (default `http://localhost:20128/v1`)
  is settable via the native Settings UI alongside the key. The same schema
  slot future-proofs vLLM / LM Studio backends. Configurable base_url lives
  in macOS Keychain under `<provider>:base_url`; router reads it via
  `secrets.get_base_url("omniroute")` with the local fallback.)
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
  review panel; "Apply selected (N)" vs "Apply all". Phase 43: hunk-level
  via a pure-Python unified-diff parser (`runtime/git/diff_parser.py`) +
  `apply_selected_hunks` reconstructing a patch from chosen hunks and
  applying it with `git apply --check --unidiff-zero` then `git apply`.
  Per-hunk checkboxes in the review panel; `Apply selected (N hunks)`.
  File-level semantics is last-write-wins; hunk-level is real 3-way —
  refuses on context mismatch and rolls back to the pre-apply HEAD.)
- [x] Add an integrated terminal with visible history, interrupt/takeover, and
  the same sandbox/approval policy as model-requested shell calls. (Phase 26 +
  Phase 35 dev-server URL detection + Phase 31 interrupt crash recovery.)
- [x] Upgrade the integrated terminal to a real persistent PTY with ANSI color
  and TUI support (vim, htop, less). (Phase 46: replaced the one-shot
  subprocess runner with a Rust PTY primitive — `desktop/src-tauri/src/pty.rs`
  using `forkpty` via the `nix` crate, streaming bytes over Tauri events to a
  vendored xterm.js renderer in vanilla JS. No build step / no npm: xterm UMD
  files live in `desktop/ui/vendor/`. The terminal is a distinct trust class
  from the agent shell — see the trust-class-split note above. macOS-only;
  Windows/Linux PTY (ConPTY) deferred.)

Acceptance evidence:

- A notarized public build passes `stapler`, Gatekeeper, packaged smoke, updater
  install/restart, and rollback on a quarantined clean machine.
- A checkpoint E2E proves Agent changes can be restored while a manual edit made
  after the checkpoint remains untouched.
- Terminal and diff E2Es prove no alternate execution/apply bypass exists.

  > **Trust-class split (Phase 46):** the original "same sandbox as agent shell
  > calls" invariant applied to one-shot commands. The interactive user terminal
  > is now a distinct trust class: it runs **unsandboxed** (real HOME, network
  > allowed) as a trusted user action — the user is typing live, like their own
  > Terminal.app, and an interactive session's command cannot be pre-evaluated.
  > Agent-requested shell (`run_shell` tool) remains seatbelt-sandboxed,
  > one-shot, policy-gated, and network-denied. The two paths are isolated:
  > terminal = Rust PTY (`desktop/src-tauri/src/pty.rs`) streamed via Tauri
  > events; agent shell = `runtime/sandbox/shell.py`.

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

## Handoff-first execution process

This process is mandatory for every follow-up plan, patch, or spec review. Handoff
intake is a prerequisite to scrutiny; do not review from conversational memory
alone.

1. **Handoff intake first**
   - Read the newest handoff before reading secondary artifacts.
   - Extract the goal, changed state, constraints, open questions, and next actions.
   - Reconcile its claims against the current worktree and authoritative evidence.
   - Preserve rollback, local-first, policy-boundary, and low-risk constraints.
   - Treat an operator-supplied `/tmp` handoff as intake input only; durable handoffs belong under `docs/plan/handoffs/<date>-<topic>.md` and must record their source path and freshness date.
2. **Priority gate**
   - Classify each proposed enhancement as MVP, gated experiment, or deferred/no-go.
   - Do not start implementation until each ticket has an owner, dependency, acceptance evidence, and rollback boundary.
3. **Ticket gate**
   - Use the local ticket IDs below when no external tracker is configured.
   - Keep tickets independently verifiable and avoid bundling architecture changes with UI polish.
   - Every ticket must declare `Owner`, `Status`, `Dependencies`, `Rollback boundary`, `Acceptance threshold`, and `Required evidence (pending)` before implementation starts.
   - Status vocabulary is `Proposed`, `Blocked`, `In progress`, `Evidence-pending`, `Accepted`, `Deferred`, or `No-go`; historical `[x]` checkboxes do not replace current acceptance evidence.
4. **Five-round scrutiny gate**
   - Run all five rounds before calling a plan, spec, or patch final:
     1. Scope and intent: does the work serve the destination and the current phase?
     2. Traceability: can every claim follow to a real code path, artifact, or source?
     3. Claim versus fact: are proposed, implemented, deferred, and evidenced states distinct?
     4. Risk and cutover: are rollback, dual-writer, policy, secret, and packaging risks bounded?
     5. Go/no-go: do acceptance thresholds prove the objective, or does the item remain open?
   - Any finding that changes scope, dependency, or acceptance criteria requires a plan revision and a fresh five-round pass.
5. **Verification and evidence**
   - Run the narrow test first, then the affected package suite, then the required product/release check.
   - Record evidence in the same change as the implementation; do not treat a green unit suite as desktop or release evidence.
   - A required-evidence path is not evidence until the artifact exists, names its fixture/environment, and records an all-must-pass result.
6. **Handoff out**
   - Summarize completed work, measured verification, residual risks, exact next actions, and sensitive-data status.
   - The next session repeats this intake process rather than relying on conversational context.

## Competitive follow-up tickets

The competitive review identifies patterns to adapt, not dependencies to vendor. The
following priority split is the current recommendation.

### MVP / P1

#### CF-0 — Restore executable fallback and shell selector

- **Owner:** desktop/release lead
- **Status:** Proposed; the current worktree has no executable fallback shell or selector.
- **Goal:** restore the retained Tauri/WebView shell as an actual fallback and select the GPUI or fallback shell before runtime/data initialization.
- **Dependencies:** existing Tauri shell sources, current Web UI assets, `desktop/gpui/PARITY.md`, the authenticated control-plane contract, and one shared policy path.
- **Rollback boundary:** no data/schema migration; a preference change plus process restart returns to the fallback, and selector/contract failure selects it before creating runtime state, tokens, or secret bootstrap material.
- **Acceptance threshold:** the packaged test artifact contains both shell entrypoints; `desktop_shell=gpui` and `desktop_shell=tauri` are independently launchable; startup/contract failure chooses Tauri without mutating production data; both shells pass the same authentication/policy fixture; fallback selection is proven after restart.
- **Required evidence (pending):** `docs/evidence/competitive-followup/cf0-shell-fallback.md`, containing packaged artifact identifiers, selector cases, pre-initialization failure injection, restart rollback, and data-integrity results.

#### CF-1 — Shared typed transport and shell boundary

- **Owner:** runtime migration lead
- **Status:** Blocked on CF-0 and a committed fixture manifest; the shared typed transport and executable dual-shell fallback are not present yet.
- **Goal:** make GPUI and the retained fallback shell share one versioned command/event contract for the first agreed route/event slice without duplicating tool authority. Future TUI/headless clients are later consumers, not this ticket’s acceptance target.
- **Dependencies:** CF-0, current Rust control-plane client, Python reference route/event contracts, a committed fixture manifest naming the health/session/messages/approval-cancel/Git/evidence cases, and one `PermissionEngine` path.
- **Rollback boundary:** no data/schema migration; revert the transport adapter and restart on the retained existing client path.
- **Acceptance threshold:** the committed fixture manifest is complete before implementation; 100% of its health/session/messages/approval-cancel/Git/evidence cases pass in both shells; malformed and unknown commands are rejected; event names and approval outcomes match; zero alternate policy or secret paths are introduced; both shells are present in the packaged test artifact.
- **Required evidence (pending):** `docs/evidence/competitive-followup/cf1-typed-transport.md`, containing the fixture-manifest revision, protocol revision, shell pair, all-must-pass results, and malformed-input output.

#### CF-2 — Read-only `ActivityEvent` projection

- **Owner:** runtime evidence lead
- **Status:** Blocked; current stores do not retain complete historical lineage, stable cross-source watermarks, or a production tool-audit sink.
- **Goal:** unify turn, approval, worker, checkpoint, Git, CI, plan, and audit records into a delivery-timeline read model while retaining current authoritative stores.
- **Dependencies:** durable turn/approval/tool lineage, stable per-source IDs and watermarks, production audit-sink wiring, existing stores, audit redaction rules, one runtime owner lock, and a defined snapshot/watermark manifest.
- **Rollback boundary:** projection storage is disposable and read-only; delete/rebuild it from authoritative stores without changing those stores or the policy ledger.
- **Acceptance threshold:** two rebuilds from the same immutable manifest produce the same projection digest; every source has an explicit watermark and completeness result; projection writes zero authoritative records; only an allowlisted safe-field schema is emitted; all secret/raw-tool redaction cases pass; missing or partial source records fail visibly rather than silently inventing events.
- **Required evidence (pending):** `docs/evidence/competitive-followup/cf2-activity-event.md`, with the source-completeness matrix, snapshot manifest, rebuild digests, redaction results, restart result, and source-store provenance.

#### CF-3 — GPUI performance and rollback contract

- **Owner:** GPUI/release lead
- **Status:** Blocked until CF-0 and CF-1 restore the fallback, selector, typed fixture path, and packaged dual-shell artifact.
- **Goal:** adapt Comet’s coalesced redraw/transcript caching patterns only after establishing a measured GPUI-versus-fallback baseline.
- **Dependencies:** CF-0, CF-1, `desktop/gpui/PARITY.md`, startup/control-plane fixtures, a desktop measurement harness, and release packaging.
- **Rollback boundary:** preserve the fallback for one stable release; a preference change plus process restart must return to it without migrating or deleting user data.
- **Acceptance threshold:** the baseline fixture, probes, environment, and failure-injection cases are committed first; GPUI may not regress first-interactive-paint, typing P95, terminal/tree/diff throughput, or RSS by more than 10%; event count and approval outcome must match the fallback fixture; startup/contract failure must select the fallback before data mutation.
- **Required evidence (pending):** `docs/evidence/competitive-followup/cf3-gpui-rollback-performance.md`, with signed artifact identifiers, baseline/probe environment, metric thresholds, crash/restart result, failure injection, and fallback replay.

#### CF-4 — Read-only delivery room projection

- **Owner:** review/evidence lead
- **Status:** Blocked on CF-2 and the complete ship-loop evidence.
- **Goal:** expose branch/task rationale for patch, review, CI, discussion, and merge only from records present in existing local-first stores; unavailable records must be explicit, not inferred, and the room must not create a second merge authority.
- **Dependencies:** CF-2, existing Git/PR routes, existing review UI, a complete disposable-repository ship-loop fixture, and an offline snapshot format.
- **Rollback boundary:** hide/remove the projection UI and discard only its read model; existing Git, PR, approval, and merge paths remain unchanged.
- **Acceptance threshold:** the disposable-repository task → commit → PR → failing CI → approved fix → green CI → merge → cleanup E2E passes; the room renders every available link from one snapshot and marks absent discussion/CI/merge records unavailable; offline sessions remain readable; the room performs zero new mutation or relay writes.
- **Required evidence (pending):** `docs/evidence/competitive-followup/cf4-delivery-room.md`, including the full ship-loop fixture reference, projection checksum, offline result, unavailable-source result, and mutation audit.

### Gated P1 trust prerequisites

#### CF-5 — Signed remote-worker and artifact receipts

- **Owner:** worker protocol lead
- **Status:** Deferred until remote dispatch is explicitly approved; remote dispatch remains fail-closed.
- **Goal:** add externally verifiable provenance when remote/SSH workers become an approved product path.
- **Dependencies:** CF-1, worker protocol identity reconciliation with ADR 0002, signed receipt format and key-rotation design, trust-root/enrollment design, persistent expiry/revocation/replay state, and artifact adoption flow.
- **Rollback boundary:** revoke the trust root, discard the receipt/artifact, and disable adoption; no receipt failure may grant local authority or alter authoritative stores.
- **Acceptance threshold:** zero invalid, expired, replayed, revoked, wrong-repository, wrong-task, or wrong-owner receipts are adopted; every valid receipt binds worker identity, owner attestation, session/task, repository/branch/base SHA, tool/version, policy digest, timestamp, and artifact digest.
- **Required evidence (pending):** `docs/evidence/competitive-followup/cf5-worker-receipts.md`, containing enrollment, threat, replay/revocation, provenance, and adoption results.

#### CF-6 — External notifications and long-job steering

- **Owner:** policy/control-plane lead
- **Status:** Deferred until CF-1/CF-2 and the trust prerequisites pass; local-first mode remains the default.
- **Goal:** support opt-in outbound notifications first; any inbound approval or steering is a separate, explicitly scoped intent path that never grants remote input local execution authority.
- **Dependencies:** CF-1, CF-2, CF-5, policy/approval broker, a separate channel principal from the local bearer, scoped channel credentials, persisted pending-intent storage, bounded queue/cursor retention, and an event replay cursor.
- **Rollback boundary:** disable the integration and revoke channel credentials; queued remote intents become explicit pending records and never auto-execute after reconnect; local sessions and approvals continue offline.
- **Acceptance threshold:** outbound notifications are read-only; inbound intents use a separate principal, explicit session/task/tool scope, expiry, nonce/idempotency key, redaction, audit attribution, and policy evaluation; zero unauthorized remote commands execute; disconnect/reconnect/revocation tests are deterministic; cold-start and mid-job offline tests preserve local safety and never auto-execute queued intents.
- **Required evidence (pending):** `docs/evidence/competitive-followup/cf6-external-control.md`, with the channel/scope matrix, authorization negatives, replay/revocation, redaction, disconnect, restart, queue-retention, and offline fallback results.

### Deferred / no-go

#### CF-7 — Relay/federation architecture decision

- **Owner:** architecture lead
- **Status:** No-go; no implementation or dependency adoption is authorized.
- **Decision:** do not adopt Comet’s Loro/DO/R2 stack or Buzz’s relay-first/Nostr control plane now.
- **Dependencies:** concrete cross-organization collaboration requirement and explicit product approval.
- **Rollback boundary:** no code, schema, storage-authority, or dependency change is allowed during reconsideration.
- **Acceptance threshold before revisit:** threat model, operational cost model, retention decision, migration/rollback rehearsal, local/offline proof, and product-owner approval all exist; otherwise remain no-go.
- **Required evidence (pending):** `docs/decisions/cf7-relay-federation.md` plus the linked threat, cost, retention, migration, and approval artifacts.

## Competitive follow-up scrutiny record

- **Review date:** 2026-08-01
- **Source handoff:** `/tmp/handoff-codinal-update-plan-2026-08-01T00:00:00Z` (freshness stated in the handoff as 2026-08-01; treated as intake input only).
- **Artifact reviewed:** this roadmap's handoff-first process and CF-0–CF-7 ticket set, reconciled against the current worktree and the GPUI comparison evidence.
- **Method:** handoff intake first, then five outsider-review rounds. No runtime or packaging code was changed by this review.

### Round 1 — Scope and intent

- The competitive work serves the destination only when it protects the GPUI rollback requirement and remains local-first.
- The simpler safe sequence is CF-0 fallback restoration, then the narrow CF-1 transport slice, then CF-2/CF-3/CF-4 projections and performance work. Remote trust/control remains gated, and relay/federation remains no-go.
- Revision made: added CF-0 and split CF-6's outbound notification scope from inbound control intents.

### Round 2 — Traceability

- GPUI currently launches the native runtime directly (`desktop/gpui/src/main.rs`), the Rust runtime returns `501` for WebSocket/Git/preview surfaces (`crates/codinal-runtime/src/lib.rs`), and the release bundle packages only GPUI plus the runtime (`scripts/build-macos-release.sh`). Therefore CF-0 is a real prerequisite, not polish.
- The current event hub has no durable event ID or watermark (`runtime/events/models.py`, `runtime/events/hub.py`); current worker/build stores and approval state cannot alone rebuild a complete timeline. CF-2 now names lineage, watermark, audit-sink, and completeness prerequisites.
- Current GitHub reads are live and the packaged smoke launches one shell (`runtime/github`, `scripts/smoke-macos-release.sh`); CF-4 now requires a full ship-loop fixture and an offline snapshot.

### Round 3 — Claim versus fact

- Implemented, proposed, blocked, deferred, and no-go states are now explicit in the ticket metadata; required evidence remains pending until each named artifact exists.
- The current evidence table no longer claims that semantic indexing, PR/CI, and browser support are uniformly missing: indexing is implemented, while representative benchmarks and broader ship-loop/browser capture remain pending.
- GPUI's current surface is still a prototype: it has no production performance probes, a bounded string transcript, and no composer parity (`desktop/gpui/src/main.rs`). Those are treated as acceptance gaps, not shipped behavior.

### Round 4 — Risk and cutover

- CF-0 requires shell selection before runtime/data/token/secret initialization and preserves a no-schema rollback boundary.
- CF-1/CF-3 require both shells in the packaged artifact and reject startup/contract failure after data mutation. CF-2 is disposable/read-only with an allowlisted safe-field schema. CF-5/CF-6 require separate trust, scope, expiry, replay, revocation, redaction, and adoption gates.
- CF-7 explicitly forbids dependency, schema, storage-authority, and relay changes while no-go remains in force.

### Round 5 — Go/no-go

- **Go:** documentation/process change only; CF-0 is the next implementation candidate.
- **Blocked:** CF-1, CF-2, CF-3, and CF-4 remain non-implementable until their stated prerequisites and evidence paths exist.
- **Deferred:** CF-5 and CF-6 remain fail-closed until trust and local-first prerequisites pass.
- **No-go:** CF-7 remains rejected.
- **Verdict:** fix-then-ship. The roadmap is ready for CF-0 ticketing, but no competitive runtime feature should be called accepted before its required evidence artifact passes.
