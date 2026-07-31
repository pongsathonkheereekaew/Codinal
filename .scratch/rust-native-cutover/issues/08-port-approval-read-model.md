Type: task
Status: resolved
Blocked by: 07

## Question

Can Rust reconstruct and serve the pending-approval read model from the shadow
snapshot with the same public-session isolation and bearer authentication, so
GPUI can restore its safety pane without invoking Python or Tauri?

## Progress

The premise was corrected: Python pending approvals are live broker state and
cannot be reconstructed from a static SQLite snapshot. Rust now has the bounded,
session-scoped broker, authenticated read route, and a live Ollama turn producer
with compatible IDs and public-session isolation. This ticket remains open
until GPUI restores its approval review/decision pane against that live state.

## Evidence

- GPUI loads the selected public session's live pending approvals from the
  authenticated Rust route and renders bounded risk/tool/reason/argument detail.
- Denial requires a native confirmation step, is persisted to the Rust audit
  ledger before broker removal, and reloads live state after the runtime reply.
- A successful denial followed by reload failure clears stale actionable UI
  state and reports the partial result explicitly.
- Approval outcomes whose executor semantics are not ported (`once`,
  `always_tool`, `always_command`) return `409` and remain pending instead of
  reporting false success.
- HTTP tests cover authenticated decision parsing, unsupported outcome
  rejection, broker retention/removal, and durable audit metadata.
