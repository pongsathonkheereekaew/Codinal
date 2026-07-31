Type: task
Status: resolved
Blocked by: 06

## Question

Can the GPUI prototype launch and own the Rust shadow runtime, use the native
control-plane client for session and message data, and shut it down cleanly
without acquiring credentials or lifecycle state through Tauri?

## Answer

Yes. GPUI now requires the Rust runtime binary and production data directory,
mints its own bearer token, launches a validated disposable snapshot, and owns
the `ShadowRuntime` in window state so teardown stops the process and attempts
snapshot cleanup independently of shutdown errors. Session/message panes use the Rust client; unavailable routes are
disabled instead of falling back through Python or Tauri.
