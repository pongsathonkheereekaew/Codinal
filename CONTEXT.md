# Codinal

Codinal is a native coding-agent product that coordinates model work while
keeping execution, evidence, and user authority explicit.

## Runtime and work

**Rust-only product**:
A Codinal product state in which every shipped runtime and desktop execution
path is Rust, without a Python or WebView fallback.
_Avoid_: Hybrid runtime, temporary sidecar

**Read-only runtime**:
A usable runtime state that can present existing work and diagnostics but owns
no mutation authority.
_Avoid_: Broken mode, partial writer

**Execution vertical slice**:
The smallest complete turn that proves provider streaming, policy, approval,
one bounded mutation, receipt, interrupt, and recovery together.
_Avoid_: Provider demo, happy-path prototype

**Writer owner**:
The single runtime identity authorized to mutate one Codinal data history.
_Avoid_: Primary writer, dual writer

**Readiness gate**:
An evidence-backed condition that must hold before a capability becomes
available to the user.
_Avoid_: Feature flag, optimistic readiness

**Approval transaction**:
A durable user decision bound to one exact proposed consequence and its source
state.
_Avoid_: Confirmation dialog, blanket permission

**Receipt**:
The immutable durable account of what a turn attempted, used, changed, cost,
and concluded.
_Avoid_: Log line, success message

**Operation envelope**:
A versioned local request identity that binds one operation to its requester,
capability, deadline, idempotency key, payload digest, and payload.
_Avoid_: Command headers, job options

**Operation lifecycle**:
The accepted, running, cancelling, terminal, and restart-recovered states of
one operation, with one durable terminal receipt.
_Avoid_: Request status, progress message

**Idempotency binding**:
The rule that one idempotency key may replay its original operation only when
the capability and payload digest match; a different payload fails closed.
_Avoid_: Duplicate suppression, retry token

**Progress cursor**:
The last applied monotonic operation sequence from which a disconnected client
can resume without replaying a consequence.
_Avoid_: Event offset, UI refresh marker

## Providers and models

**Provider profile**:
An authorized endpoint, credential reference, model catalogue, capability
evidence, and cost policy treated as one selectable provider identity.
_Avoid_: API key, base URL

**Auto fallback**:
An optional budgeted route from a failed primary provider to an approved
secondary provider before user-visible output or consequences begin.
_Avoid_: Failback, silent retry

**Role profile**:
The user-authorized provider, model, effort, and budget defaults for one stage
of a multi-model workflow.
_Avoid_: Hardcoded model role

**Durable handoff**:
A structured transfer of objective, constraints, artifacts, evidence, and
unresolved risks between work stages.
_Avoid_: Transcript dump, chain-of-thought

**Evaluation ledger**:
A local record of objective model outcomes used to improve routing decisions
without duplicating source content.
_Avoid_: Telemetry, model leaderboard

**Workflow run**:
One approved sequence of model roles, budgets, handoffs, and resulting
artifacts treated as a durable unit of work.
_Avoid_: Agent swarm, conversation

**Stage attempt**:
One model's immutable attempt to perform a role within a workflow run.
_Avoid_: Agent instance, retry overwrite

**Cost reservation**:
A durable claim against an approved spending limit made before a provider
request begins and reconciled when usage becomes known.
_Avoid_: Cost estimate, usage counter

## Universal harness

**Harness Source Bundle**:
The canonical versioned set of universal policy, skills, standards, and host
capability declarations selected by the user.
_Avoid_: Live install, adapter copy

**User Overlay**:
User-owned harness content that remains distinct from managed source updates.
_Avoid_: Local drift, unmanaged copy

**Live Projection**:
The effective universal harness tree materialized for local discovery.
_Avoid_: Source repository, second SSOT

**Host Projection**:
The minimal generated links and configuration through which one coding host
consumes the universal harness.
_Avoid_: Host-owned source, duplicated skill pack

**Host adapter**:
The host-specific interpretation that plans and verifies one Host Projection.
_Avoid_: Provider adapter, installer script

## Desktop experience

**Conversation workbench**:
The primary task surface combining conversation, execution state, evidence,
and contextual review without becoming a general dashboard.
_Avoid_: Chat page, control dashboard

**Navigation sidebar**:
The independently collapsible and resizable left-side task navigation region;
collapsing it removes its full width without changing conversation or right-side
workbench state.
_Avoid_: Left panel, mini rail

**Workspace workbench**:
The independently visible and resizable right-side dock that keeps the active
workspace tool while the Navigation sidebar opens or closes.
_Avoid_: Tools card, context panel

**Environment card**:
The responsive floating context summary inside the conversation region; it
reflows and clamps to available space instead of exposing a resize divider.
_Avoid_: Right sidebar, environment panel

**Project context**:
The durable scope that groups source roots, chats, activity, and execution
defaults without owning the source files themselves.
_Avoid_: Folder shortcut, chat label

**Primary source root**:
The one selected root that supplies default working directory, Git/review
scope, and local discovery for a Project context; secondary roots remain
attached but never silently replace it.
_Avoid_: First folder, current directory

**Source attachment**:
A conversation-scoped reference to a file or folder that can be previewed,
removed, or retried without deleting or mutating the original source.
_Avoid_: Project root, uploaded copy

**Permission profile**:
The user-authorized approval and sandbox policy (`Ask for approval`, `Approve
for me`, `Full access`, or `Custom`) that governs an action; runtime readiness
does not imply a permission profile.
_Avoid_: Provider readiness, access label

**Workspace file split**:
The resizable divider inside the Files tool between the workspace tree and file
content; it is independent of the outer Workspace workbench width.
_Avoid_: Files sidebar, second workbench

**Panel width preference**:
The last user-selected visible width of a resizable structural region, restored
after hiding or relaunching; temporary window-size clamps do not overwrite it.
_Avoid_: Current width, collapsed width

**Semantic type role**:
A Codex-matched typography role whose metrics remain consistent across every
surface while headings, body text, controls, metadata, and code retain distinct
hierarchy; compact text never reduces interaction target size.
_Avoid_: Uniform font size, per-panel typography

**Responsive panel state**:
A temporary adaptation that protects readable conversation space by overlaying
an active Workspace workbench when needed while preserving Navigation's explicit
open/closed state, then restores the user's preferred panel widths when space
returns.
_Avoid_: Persisted auto-collapse, squeezed conversation

**Context/workbench composition**:
The Environment card may remain visible beside the Workspace workbench; the
Workbench owns one active detail tool at a time, while Sources may open as a
secondary drawer without replacing the Environment summary.
_Avoid_: One shared panel, mutually exclusive right surfaces

**Interactive frame budget**:
The display-driven rendering contract that follows native refresh up to 120 Hz
during interaction without continuous idle repaint, while background work stays
off the UI thread and system thermal or display limits remain authoritative.
_Avoid_: Fixed 120 FPS loop, busy repaint

**Codex parity target**:
The reference contract for matching Codex geometry, spacing, semantic
typography, panel behavior, and interaction while retaining Codinal identity
and original or native-system icon assets.
_Avoid_: Codex clone, OpenAI reskin
