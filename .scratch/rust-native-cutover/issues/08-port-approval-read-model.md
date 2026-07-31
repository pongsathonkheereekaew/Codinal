Type: task
Status: open
Blocked by: 07

## Question

Can Rust reconstruct and serve the pending-approval read model from the shadow
snapshot with the same public-session isolation and bearer authentication, so
GPUI can restore its safety pane without invoking Python or Tauri?

## Progress

The premise was corrected: Python pending approvals are live broker state and
cannot be reconstructed from a static SQLite snapshot. Rust now has the bounded,
session-scoped broker and authenticated read route foundation with compatible
IDs and public-session isolation. This ticket remains open because no Rust turn
engine/tool producer submits real requests yet; GPUI must not treat the empty
shadow broker as live parity.
