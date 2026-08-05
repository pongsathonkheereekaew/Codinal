# Codinal GPUI workbench contract

This is the owned C3 contract for Codinal's pure-Rust desktop shell. Codinal
matches the approved Codex light-shell geometry, spacing, typography, and panel
behavior while retaining Codinal branding and original/native iconography.

## Layout anatomy

- Header: a 48 px native light title row with a persistent Navigation toggle,
  task title, runtime status, Environment toggle, and Workbench toggle.
- Navigation sidebar: preferred width 308 px (the golden primary fixture edge), resizable from 220–420 px. Hide
  collapses it to 0 px without overwriting the preferred width. On constrained
  viewports the active Workbench moves to overlay mode while Navigation keeps
  the user's explicit open/closed state.
- Conversation: the primary flexible region. Transcript content is centered at
  a maximum width of 840 px; user messages remain right aligned, assistant
  output stays on the open canvas, and the composer remains anchored below it.
- Environment card: an independent floating contextual card for provider
  settings, updater state, and approval review. It remains forced visible for a
  pending approval and may remain co-visible with the Workspace Workbench. In
  overlay mode it shifts and responsively narrows to remain readable instead
  of being occluded. The Workbench still owns only one active detail tool at a
  time; Sources is a secondary drawer and does not replace the Environment
  summary.
- Workspace Workbench: preferred width 424 px, resizable from 320–720 px. It is
  a structural right dock when space permits and an occluding right overlay on
  narrow viewports. Open tools remain ordered tabs: `Review` (`⌃⇧G`),
  `Terminal` (`⌘J`), `Browser` (`⌘T`), `Files` (`⌘P`), and `Side chat`
  (`⌥⌘S`). Closing a Terminal tab hides its view without stopping the PTY.
- Files split: file detail and the right-side workspace tree are separated by a
  persisted divider; the tree preference is resizable from 140–320 px and its
  effective width is clamped when necessary to preserve at least 160 px for
  file detail.

All three preferred widths persist atomically in the desktop data directory.
Responsive collapse and overlay decisions are derived per viewport and are
never persisted over the user's preferences.

The semantic type roles are fixed: section 15 px semibold, body 13 px,
controls/tabs/sidebar 12 px, metadata 11 px, and code/terminal 12 px SF Mono.
Interactive hit targets remain 28–32 px even when their labels are smaller.

The shell, workspace tools, runtime, terminal, and file inspection are
Rust-native. The Browser tab must expose the same in-app anatomy, but remains
disabled with a truthful reason until an approved native platform bridge is
available. The current external system-browser action must stay explicitly
labeled and must not be relabeled as parity. Codinal does not use JavaScript,
HTML/CSS, Tauri, or a WebView as its application shell.

## Parity acceptance

The golden comparison viewport is 1710×1112 logical pixels at 2× capture scale.
Approved shell edges and spacing must be within 2 logical pixels of the
references, semantic type metrics must match except for operating-system text
antialiasing, and no supported panel state may clip, overlap unexpectedly, or
jump while resizing.

The comparison profile, token table, state matrix, and diff protocol are frozen
in the C3 sub-contract at
[`docs/evidence/cutover/c3/pixel-parity-contract.md`](../../docs/evidence/cutover/c3/pixel-parity-contract.md).

## Safety state contract

| State | Runtime authority | Visible action |
|---|---|---|
| Read-only | no writer / migration not verified | disabled action with reason code |
| Ready | Rust owner, store, and provider configured | `Run turn` |
| Running | active Rust turn and cancellation latch | `Interrupt turn` |
| Approval pending | durable exact request and full diff | review, approve once, or deny |
| Receipt | durable terminal outcome | reload receipt and session state |

Runtime health, events, and approvals remain the source of truth. GPUI state is
a projection and never grants permission.

## Accessibility and performance evidence

Rendering is invalidation- and display-driven. Codinal does not run a fixed
120 Hz repaint timer: active interactions may present at the display cadence
with an 8.33 ms frame target on 120 Hz hardware and a 16.67 ms target on 60 Hz
hardware; inactive or thermally constrained operation may run lower.

The release ledger must record keyboard navigation, VoiceOver labels and focus
restoration, contrast, reduced motion, transcript scale, stream rate,
input-to-paint P95, frame-time P95, idle wakeups, and RSS. Live macOS evidence
on the target refresh-rate hardware is required before C3 passes.
