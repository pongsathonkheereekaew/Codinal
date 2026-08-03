# Codinal Rust-native UI cutover plan

Status: accepted
Decision date: 2026-08-02
Role: UI-only execution plan; subordinate to `rust-native-runtime-cutover.md`
Scrutinize verdict: OK (pass 3, 2026-08-02)

## Decision

Complete Codinal's desktop UI cutover incrementally from the existing Rust/GPUI
surface. UI-1 and UI-2 are extraction and modularization stages, not a
big-bang rewrite; retire the legacy JavaScript/WebView UI only after the Rust UI
has passed behavioral, accessibility, performance, bundle, and release gates.

This plan separates rendering, input, UI state, and UI effects from the Rust
runtime cutover. It does not create a second runtime, provider path, storage
owner, policy path, or tool-execution authority.

The target is **Synara-like workspace UX, not a Synara code or pixel clone**:
left navigation, conversation-first center, contextual/right tools, resizable
panes, persistent session state, and truthful capability-driven controls. The
Codinal safety model remains authoritative.

## Authority and boundaries

| Concern | Authority | This plan may do |
|---|---|---|
| Runtime ownership, migration, provider, policy, sandbox, receipts | [`rust-native-runtime-cutover.md`](./rust-native-runtime-cutover.md) | Consume its typed health/capability/event contracts |
| Control-plane wire/auth contract | `contracts/v1/` and `desktop/control-plane-client/` | Add UI parsing only when the runtime plan owns the contract change |
| GPUI rendering and input | `desktop/gpui/` | Refactor, test, and replace the UI implementation |
| Native PTY integration | `desktop/native-host/src/pty.rs` | Preserve the existing Rust path; do not create a second execution owner |
| Rust-native settings, OAuth, updater, and local read-only projections | Existing Rust controllers/helpers in `desktop/gpui/` and `desktop/native-host/` | Preserve their authority; refactor only their UI adapters and state projections |
| Legacy HTML/JS/editor bundles | `desktop/ui/`, `desktop/build.mjs` | Freeze, migrate tests, then retire after release gates |
| Capability truth | `docs/evidence/runtime-truth/capability-table.md` | Render it; never edit the generated table manually |

### In scope

- Rust/GPUI shell, navigation, conversation, composer, context panel, tools
  dock, approval/review surface, terminal presentation, settings presentation,
  focus and keyboard behavior.
- Pure Rust UI state projections/reducers and deterministic event-to-state
  mapping.
- Presentation/adapters for the existing Rust-native provider settings, OAuth,
  updater, native PTY, workspace preview, and bounded Git review paths; this
  plan does not add another authority for any of them.
- GPUI module decomposition and removal of UI state stored as presentation
  strings.
- Visual snapshots, UI reducer tests, accessibility evidence, performance
  measurements, and release/process/bundle checks.
- Migration of the existing `tests/desktop_ui/` contract from HTML/JS
  assertions to classified Rust/GPUI contract/evidence tests.

### Explicitly out of scope

- Runtime/provider/storage/policy/sandbox/migration implementation.
- New terminal, shell, Git/worktree, MCP, browser, remote, or collaboration
  capabilities. A missing or `501` route remains unavailable in the UI.
- Editor/LSP/inline completion parity. This remains deferred by the runtime
  plan; no replacement editor bundle is introduced by this plan.
- Linux/Windows release work, embedded browser engine, or a new UI framework.
- Importing Synara's React/Vite/Electron/Node stack or copying its product
  branding/assets.
- Optimistic UI that reports a mutation complete before a runtime response and
  durable receipt are observed.

## Verified starting point

The UI already has a usable Rust foundation, but the composition root is too
large and several projections are still presentation-oriented:

- `codinal-gpui` is a standalone Rust package pinned to a Zed GPUI revision
  ([`desktop/gpui/Cargo.toml`](../../desktop/gpui/Cargo.toml)).
- [`desktop/gpui/src/main.rs:282`](../../desktop/gpui/src/main.rs:282) owns
  bootstrap, the GPUI entity, session loading, stream reduction, approvals,
  settings, terminal state, panel resize, and most rendering.
- [`desktop/gpui/src/workbench.rs:9`](../../desktop/gpui/src/workbench.rs:9)
  already provides a pure reducer for readiness, streaming, approval,
  reconnect, receipts, bounded transcript state, and accessibility controls.
- [`desktop/gpui/src/shell_layout.rs:23`](../../desktop/gpui/src/shell_layout.rs:23)
  already resolves navigation/workbench/context widths and dock-versus-overlay
  placement with tests.
- [`desktop/gpui/src/session_stream.rs:16`](../../desktop/gpui/src/session_stream.rs:16)
  owns the reconnecting WebSocket worker and bounded event queue.
- [`desktop/gpui/src/side_panel.rs:13`](../../desktop/gpui/src/side_panel.rs:13)
  provides bounded workspace/file/review projections and tool-tab state.
- [`desktop/control-plane-client/src/lib.rs:70`](../../desktop/control-plane-client/src/lib.rs:70)
  already exposes typed `RuntimeHealth`, `RuntimeCapabilities`, sessions,
  messages, approvals, receipts, and turn commands.
- [`capability-table.md`](../evidence/runtime-truth/capability-table.md) marks
  projects, long-running work, review, terminal, and local files as partial;
  Git worktrees as missing; and browser as external-gated. UI parity must not
  upgrade those statuses.
- [`DesktopRuntime`](../../desktop/gpui/src/main.rs:389) currently has
  `Production` and `Shadow` variants; the launch branch is debug-only for
  Shadow at [`main.rs:5780`](../../desktop/gpui/src/main.rs:5780). UI-0 must
  classify Shadow as debug/test/dogfood-only; a shipped production path must
  use `Production` and must not acquire a second runtime authority.

The existing [`WorkspacePrototype`](../../desktop/gpui/src/main.rs:282) stores
both typed state and flattened strings such as `conversation` and `approvals`
([`main.rs:307`](../../desktop/gpui/src/main.rs:307)), while event parsing and
render composition remain in `main.rs`. The cutover removes this duplication
without changing the control-plane protocol.

## Target architecture

```text
GPUI input / paint
        |
        v
UiAction -> UiReducer -> UiState / UiEffect
                         |          |
                         |          `-> ControlPlaneClient command
                         `-> typed SessionEvent / RuntimeHealth
                                      |
                                      v
                              Rust runtime (authority)
```

The renderer never decides whether a consequential action is allowed. It
renders `UiState`, dispatches a typed `UiAction`, and observes the resulting
runtime event/receipt. The reducer is usable in unit tests without a GPUI
window, network, filesystem write, provider, or runtime process.

Local read-only projections (workspace/file preview and bounded Git review) and
designated Rust-host integrations (native PTY, provider settings, OAuth, and
updater) remain explicit effects with their existing owners. They are not a
license to put execution, policy, provider, or persistence authority in the
renderer.

### Proposed module ownership

Do not create a new UI framework or a new crate in the first pass. Split the
existing package along stable ownership seams:

```text
desktop/gpui/src/
  main.rs                 # bootstrap, entity wiring, top-level render only
  ui_model.rs             # pure UiState, UiAction, UiEffect, UiReducer
  session_projection.rs   # typed session/event mapping and replay ordering
  shell.rs                # top-level zones and focus routing
  navigation.rs           # task/session sidebar and selection
  conversation.rs         # bounded timeline rows and follow-bottom behavior
  composer.rs             # input, Run/Interrupt, model/effort display
  context_panel.rs        # environment, provider, readiness, approvals
  dock.rs                 # unified panel state, tabs, resize, lazy/kept panes
  terminal_view.rs        # PTY presentation and focus; no new execution owner
  review_view.rs          # bounded Git/file review presentation
  settings_view.rs        # provider/update/settings presentation
  accessibility.rs        # labels, roles, focus, keyboard, reduced motion
  light_theme.rs          # existing tokens/layout constants
  shell_layout.rs         # existing pure geometry contract
```

This is an ownership map, not an upfront file quota: extract `ui_model.rs` and
`session_projection.rs` first, then add view modules only when a seam owns
state/effects and has a focused test. The exact filenames may be adjusted
during implementation, but each new file must have one reason to change.
`main.rs` is the composition root, not a second state store.

## UI contract

### State

`UiState` must contain typed projections, not strings that are reparsed by the
renderer:

- `RuntimeHealth` and capability snapshot, including mode and stable reason;
- selected session and bounded session summaries;
- typed timeline blocks with stable IDs, role/kind, content, streaming state,
  sequence, and receipt linkage;
- composer state: idle, running, interrupting, approval-pending, reconnecting;
- pending approval projection with full review data when supplied by runtime;
- reconnect/cursor state and last accepted event sequence;
- navigation/context/dock state and persisted panel preferences;
- terminal presentation state and focus ownership;
- appearance, reduced motion, and accessibility/focus state.

The current [`WorkbenchState`](../../desktop/gpui/src/workbench.rs) remains the
initial reducer kernel. Its transition invariants are preserved while the
larger `WorkspacePrototype` state is extracted around it.

### Actions and effects

Every user action is one of:

- local view action: resize, select tab/session, scroll, focus, appearance;
- runtime query: health, sessions, messages, approvals, receipts;
- runtime command: create session, start turn, interrupt, resolve approval;
- bounded local read-only projection: workspace inspection, file preview, or
  Git review snapshot;
- designated Rust-host integration: open/resize/close the already-owned PTY
  view, provider settings, OAuth, or updater presentation.

Agent turn/session/tool mutations and approval decisions are dispatched through
the authenticated Rust control plane. Provider credential/config changes,
OAuth callback relay, updater actions, and the existing interactive local PTY
remain explicitly scoped native-Rust-host integrations with their own
confirmation/error handling until the runtime plan assigns them elsewhere; this
UI plan does not add or expand their authority.

The reducer may reject an action locally when state proves it invalid, but it
never silently converts a rejected action into success. Runtime effects carry
session/turn/approval identity and are ignored when their generation or ID is
stale.

### Event mapping

The UI keeps one event path:

```text
ControlPlaneClient::session_events
  -> SessionStreamWorker
  -> typed SessionEvent parser
  -> sequence/replay validator
  -> UiReducer
  -> GPUI repaint
```

The existing [`apply_session_stream_update`](../../desktop/gpui/src/main.rs:1555)
and [`parse_session_event`](../../desktop/gpui/src/main.rs:5320) path is
extracted, not duplicated. Live deltas and replayed deltas enter the same
reducer. A duplicate, unordered, malformed, oversized, wrong-session, or
stale-generation event is rejected visibly and cannot append duplicate
transcript text.

### Capability truth

Controls remain visible when useful, but enabled state comes only from
`RuntimeHealth.capabilities` and local state. The UI must distinguish:

- `read_only` versus `ready`;
- provider/model/effort unavailable;
- route not implemented or capability probe failed;
- approval pending or stale;
- reconnecting or receipt reload required;
- experimental execution disabled.

`501` is never treated as success. A visual pane may be implemented with
fixtures before its runtime route exists, but the release UI must show
`unavailable`/`experimental` truth and must not dispatch an unsupported command.

## Delivery sequence

### UI-0 — Freeze UI scope and evidence baseline

1. Inventory every current GPUI control, state field, command, event type,
   direct native-host call, and render function in `main.rs`.
2. Map each control to `UiAction`, runtime command/query, capability, and
   terminal receipt/error state.
3. Capture deterministic state/layout fixtures for empty, read-only, ready,
   running, approval-pending, reconnecting, failed, completed, Light, Dark,
   and reduced-motion states. Use serialized `UiState`/`ResolvedShell`
   snapshots for unit evidence; native screenshots require an agreed GPUI
   capture harness or explicit manual/release evidence, not a claim of pixel
   parity from text snapshots.
4. Freeze UI-specific budgets and fixture identity in the canonical
   [`C3 measurement ticket`](../evidence/cutover/c3/measurement-ticket.md)
   before tuning; attach UI evidence to the existing
   [`C3 gate`](../evidence/cutover/c3/gate.md), not a second UI gate.
5. Classify every assertion in
   [`test_ui_contract.py:42`](../../tests/desktop_ui/test_ui_contract.py:42) as
   supported-and-migrate, deferred/out-of-scope-and-negative-test, or
   obsolete-legacy-only-with-rationale. Include the existing worker/plan,
   MCP/artifact, editor/LSP, third-party settings, and legacy-loader assertions
   in the inventory; record the result in
   `docs/evidence/cutover/c3/ui-test-classification.md`; do not delete any until
   its class and replacement evidence are recorded.

Gate: every visible action has an owner and a terminal state; no control is
unmapped; current capability statuses are recorded; deterministic state/layout
fixtures and performance samples are reproducible; any native screenshot has a
documented capture method.

### UI-1 — Pure model and projection kernel

1. Extract `UiState`, `UiAction`, `UiEffect`, `UiEvent`, and `UiReducer` from
   [`workbench.rs`](../../desktop/gpui/src/workbench.rs) and the stateful parts
   of `main.rs`.
2. Move session event parsing/order checks into `session_projection.rs`.
3. Replace `conversation: String`, `approvals: String`, and similar render
   strings with bounded typed projections; format text only at the leaf view.
4. Keep payload limits, stable block IDs, UTF-8 boundaries, sequence checks,
   generation checks, and receipt linkage explicit in the model.
5. Add fixture-driven tests for every valid/invalid transition and no-I/O
   reducer tests for stale, duplicate, malformed, and oversized events.

Gate: the reducer can replay a complete fixture from session load through
streaming, approval, interrupt, reconnect, and receipt without a GPUI window;
no reducer test needs a runtime process or provider.

### UI-2 — Modular GPUI shell with behavior preservation

1. Split `main.rs` into the module ownership seams without changing the wire
   contract or runtime behavior.
2. Keep the current three-zone anatomy: navigation sidebar, conversation-first
   center, and contextual/workbench pane ([`main.rs:3270`](../../desktop/gpui/src/main.rs:3270)).
3. Route all keyboard/mouse input through typed actions and one focus owner;
   preserve panel resize limits and persisted preferences from
   [`shell_layout.rs:37`](../../desktop/gpui/src/shell_layout.rs:37).
4. Keep GPUI as viewport/input plumbing. Do not put provider calls, policy
   decisions, file mutations, or agent tool execution in render methods.
5. Keep the current native PTY presentation path isolated and explicitly
   labeled; do not expand terminal authority in this UI stage.

Gate: existing read-only, session/approval, provider-settings, OAuth/update,
and PTY-presentation flows retain their explicit success/error states; the
production build starts one runtime and one session stream per selected
session; any `Shadow` runtime is debug/test/dogfood-only; no new process,
network, or storage owner appears.

### UI-3 — Transcript, composer, and streaming parity

1. Render typed timeline rows with stable IDs rather than rebuilding one large
   conversation string per event.
2. Coalesce deltas at frame boundaries, preserve bounded transcript limits, and
   keep follow-bottom behavior interruptible by user scroll.
3. Make `Run -> Interrupt`, reconnect, failure, and receipt states mutually
   explicit; no stale response can re-enable or disable the wrong session.
4. Display provider/model/effort and effective readiness without leaking
   secrets or pretending that a provider capability is complete.
5. Keep live and replayed event rendering on the same reducer path.

Gate: fixture replay and live stream produce the same final timeline/receipt;
duplicate/reordered events do not duplicate text; first-delta render and input
typing remain within the frozen UI budgets.

### UI-4 — Safety and approval surface

1. Render read-only/writer-lock/migration/provider/experimental reasons next to
   disabled actions, with keyboard and VoiceOver labels.
2. Render the full approval diff and its path, digest/hash, root/boundary,
   expiry, risk, and runtime provenance when supplied by the runtime contract.
3. Make approve, deny, expire, cancel, source-hash drift, reload, and failed
   receipt states distinct.
4. On approval completion, reload the authoritative pending/receipt state;
   never treat a click or HTTP `200` alone as completion.
5. Test approval IDs and session/turn generations so a late completion cannot
   resolve a different request.

The current [`PendingApproval`](../../desktop/control-plane-client/src/lib.rs:132)
type exposes tool, arguments, reason, risk, and optional command, but not the
full diff/path/hash/root/expiry contract. UI-4 must wait for the runtime plan's
C2a typed approval-review contract for live evidence; the UI must not invent or
infer missing review fields.

Gate: manual/live GPUI Safety UI E2E passes for read-only, pending, approve,
deny, expire, stale-source, interrupt, reconnect, and failure paths; no UI
action bypasses the Rust approval chokepoint.

### UI-5 — Unified Synara-like dock and tool projections

1. Unify current context/workbench/side-panel state behind a typed `DockState`
   with open/closed, active pane, ordered panes, resize, placement, and
   per-session persistence for UI preferences only, keyed by session ID and
   excluding transcript, approval, and secret data. Migrate the current global
   [`PanelPreferences`](../../desktop/gpui/src/shell_layout.rs:37) and
   entity-local tabs ([`side_panel.rs:22`](../../desktop/gpui/src/side_panel.rs:22))
   deliberately; runtime data must never be stored in the dock.
2. Preserve current tools: Review, Terminal, Browser, Files, and Side Chat.
   Add future pane metadata only as unavailable/capability-backed projections;
   do not add fake Git/worktree/embedded-browser behavior.
3. Implement tab switching, close/collapse, resize, docked-versus-overlay
   placement, keyboard navigation, and an explicit kept-alive terminal
   presentation contract; hiding a terminal must not implicitly kill the
   user-owned PTY.
4. Lazy-mount expensive panes and release hidden UI subscriptions/resources
   according to the pane contract; hidden panes cannot receive keyboard input
   or announce stale content.
5. Show the actual runtime capability and reason for every pane that is not
   fully supported. Keep local bounded file/review projections read-only until
   the runtime plan enables writes.

Gate: allowed dock preferences survive session reload without cross-session
leakage, including a fresh-process/reload test; pane selection/close/resize is
deterministic; unavailable panes cannot dispatch unsupported commands; terminal,
review, files, and browser external-gated states have explicit tests.

### UI-6 — Accessibility, performance, and maintainability gate

1. Add a GPUI accessibility matrix for keyboard-only navigation, focus order,
   focus restoration, labels/roles, announcements, contrast, reduced motion,
   and approval focus traps.
2. Measure cold/warm startup, input-to-visible-state, frame time, transcript
   replay, first-delta forwarding, typing latency, scroll latency, idle wakeups,
   RSS, and per-pane resource usage on supported macOS hardware.
3. Start with the runtime plan's budgets; freeze UI-specific numeric values in
   the canonical C3 measurement ticket before optimization. At minimum record:
   `input_to_paint_p95`, `frame_time_p95`, `first_delta_forward_p95`,
   `replay_4k_blocks_ms`, `typing_p95`, `rss_idle`, `rss_streaming`, and
   `idle_wakeups`.
   Also record the current editor source/dist measurements and the desired
   post-retirement state (`legacy UI absent/0`); the canonical shipped-size
   target must be reconciled in the runtime plan before UI-7.
4. Keep `main.rs` as a composition root target of at most 1,200 lines after
   extraction; keep each UI module single-purpose and testable without GPUI
   where possible. This is an advisory structural budget: missing it alone
   cannot fail a release, but the ledger must record the reason and the next
   extraction seam.
5. Record any copied GPUI/Comet behavior with commit/path/license provenance;
   do not copy Synara assets or source without a separate provenance entry.

Gate: fresh evidence passes the accessibility matrix, frozen numeric budgets,
transcript stress fixture, and module/unit test suite; no optimization removes
payload limits, readiness truth, receipts, or approval semantics.

### UI-7 — Legacy UI retirement and Rust-only release evidence

1. For [`test_ui_contract.py:42`](../../tests/desktop_ui/test_ui_contract.py:42),
   migrate supported safety,
   accessibility, diagnostics, and core-session assertions to GPUI/UI-model
   tests; add explicit unavailable/deferred negative tests for out-of-scope
   workers/plans, MCP/artifacts, editor/LSP, third-party settings, or other
   unsupported surfaces; remove only obsolete legacy-only assertions with a
   recorded rationale. Retain release smoke tests; do not reduce coverage to
   compile-only checks.
2. Update [`verify.yml`](../../.github/workflows/verify.yml) to remove the
   Node/editor build only when the legacy UI is retired, and replace it with the
   Rust UI gates. Update
   [`measure-rust-release-artifacts.sh`](../../scripts/measure-rust-release-artifacts.sh)
   to report the retired legacy UI as absent/zero rather than treating its old
   source/dist size as a live bundle metric, then refresh the canonical C3
   measurement ticket and gate.
3. Reconcile the runtime plan's current editor-bundle wording with the
   Rust-only decision before this gate: amend that canonical plan through its
   approval path so the post-retirement target is explicit, rather than
   silently overriding it here.
4. Remove the legacy UI startup path, stale HTML/JS assets, editor bundle
   loader, and release references only after UI-6, the runtime plan's C3b
   package/process/SBOM gate, and the reconciliation above pass.
5. Verify a fresh install, upgrade, reconnect, and rollback-compatible release
   starts the Rust/GPUI surface and no legacy UI process/assets are required.
6. Keep incompatible schema rollback and data recovery owned by the runtime
   plan; UI retirement must not change data recovery semantics.

Gate: packaged artifact/process/SBOM inspection proves the shipped desktop UI
uses Rust/GPUI only; Rust UI tests and release E2E cover the same safety and
diagnostics/core-session surface previously asserted by `tests/desktop_ui/`,
with every deferred or obsolete assertion classified and accounted for.

## Dependency matrix

| UI stage | Can start with current tree | Requires runtime-plan evidence | Blocks release |
|---|---:|---|---:|
| UI-0 | yes | current capability snapshot | no |
| UI-1 | yes | typed event fixtures may be historical | no |
| UI-2 | yes | none beyond current read-only path | no |
| UI-3 | yes with fixtures | C2a event/stream/receipt contract for live gate | yes |
| UI-4 | yes with fixtures | C1/C2a approval, hash, receipt, readiness evidence | yes |
| UI-5 | yes for projection | route capability evidence per pane | no for unsupported panes; yes for claimed panes |
| UI-6 | after UI-1/UI-2 | C2a/C3 performance and release fixtures | yes |
| UI-7 | after UI-6 | C3b Rust-only package/process/SBOM gate and explicit reconciliation of the runtime plan's editor-bundle target | yes |

If a UI task discovers a missing runtime field or route, stop at the boundary:
record the dependency in the runtime plan and keep the UI projection disabled
or fixture-backed. Do not implement a shadow runtime path inside GPUI.

## Verification commands and evidence

The canonical UI ledger is
[`docs/evidence/cutover/c3/gate.md`](../evidence/cutover/c3/gate.md), with
numeric definitions in
[`measurement-ticket.md`](../evidence/cutover/c3/measurement-ticket.md). It
must include the fixture checksum, supported hardware, command, threshold,
result, artifact, and stop condition; do not create a parallel UI gate. The
minimum command set is:

```bash
cargo fmt --manifest-path desktop/gpui/Cargo.toml -- --check
cargo clippy --manifest-path desktop/gpui/Cargo.toml --all-targets -- -D warnings
cargo test --manifest-path desktop/gpui/Cargo.toml
cargo test --manifest-path desktop/control-plane-client/Cargo.toml
TOOLCHAINS=Metal cargo check --manifest-path desktop/gpui/Cargo.toml
CI=true ./verify.sh
scripts/smoke-macos-release.sh
scripts/measure-rust-release-artifacts.sh
```

The existing [`scripts/verify-gpui-migration.sh`](../../scripts/verify-gpui-migration.sh)
remains a combined migration/release gate; it is not a substitute for the
UI-model, accessibility, stress, or visual evidence described here.

Until UI-7 removes the legacy build step, the product job in
[`verify.yml`](../../.github/workflows/verify.yml) still installs Node and runs
`npm ci && npm run build` before `verify.sh`; therefore `CI=true ./verify.sh`
alone is not evidence of a Rust-only release. The UI ledger must record the
workflow change and the post-change command output.

Required evidence before UI-7:

1. Rust UI-model transition and event-replay tests;
2. GPUI shell/keyboard/focus/approval E2E plus provider-settings,
   OAuth/update, PTY-presentation, and bounded local-projection smoke;
3. accessibility matrix including VoiceOver/manual evidence;
4. transcript/stream stress and fixed cold/warm performance report;
5. the `docs/evidence/cutover/c3/ui-test-classification.md` manifest covering
   supported, deferred, and obsolete `tests/desktop_ui/` assertions;
6. bundle/process/SBOM report proving no legacy UI dependency in the release,
   including the updated artifact metrics;
7. provenance/NOTICE update for any copied or adapted upstream code/assets.

## Stop conditions

Stop and do not widen the rewrite when any of these occurs:

- a UI action needs a runtime route that is not implemented or not evidenced;
- a reducer test requires a live provider, network, filesystem mutation, or
  GPUI window;
- an event can be applied twice, out of order, to a different session, or after
  a stale generation without a visible rejection;
- an approval click can appear successful without a durable runtime response;
- a pane creates an unbounded task, socket, terminal, transcript, or resource
  while hidden;
- a benchmark cannot distinguish UI time from provider/network time;
- a production build can select `DesktopRuntime::Shadow` or introduce a second
  runtime/stream owner;
- removing legacy JS would remove diagnostics, accessibility, or safety coverage
  not yet represented in Rust tests;
- copied upstream source or assets lack an exact provenance/license record.

## Definition of done

This UI plan is complete when:

- GPUI/Rust is the only shipped desktop UI path;
- UI state is typed, bounded, replayable, and independent of rendering;
- all agent turn/session/tool mutations and approval decisions go through the
  authenticated Rust control plane; provider credentials/config, OAuth,
  updater, and the existing local PTY remain explicitly scoped native-Rust
  integrations until the runtime plan assigns them elsewhere;
- live/replayed streams, approvals, receipts, readiness, reconnect, and errors
  have identical tested behavior;
- supported and unsupported capabilities are visibly truthful;
- Synara-like dock/workspace interactions work without importing Synara's stack;
- accessibility and performance budgets have fresh evidence;
- supported legacy UI safety/diagnostics/core-session assertions have Rust/GPUI
  equivalents; deferred and obsolete assertions are explicitly classified
  rather than silently deleted;
- release/process/SBOM/provenance evidence passes and the runtime plan's C3b
  gate remains green.

## Relationship to the runtime plan

The runtime plan remains the only authority for execution, storage, provider,
policy, approval, migration, security, cache/prompt-cost telemetry, and release
sequencing. This document only turns its GPUI product specification and C3/C3b
UI gates into an implementable UI workstream. If the documents conflict, the
runtime plan wins; this plan must be amended rather than weakening its
invariants.
