# G5 parity and rollback contract

GPUI is the only supported Codinal desktop shell. The selector records only
`desktop_shell=gpui` as a non-secret local preference; it never copies bearer
tokens, provider keys, OAuth values, approval decisions, or preview contents.

Every GPUI replay/live run must record: fixture or session identifier, control
plane version, event count, approval/cancel outcome, Git/evidence outcome,
first-interactive-paint, P95 typing latency, terminal/tree/diff size, and RSS.
A GPUI startup or contract failure leaves production data unchanged and stops
with a diagnostic state; there is no Tauri/WebView fallback or silent shell
switch. GPUI owns and removes only its isolated Rust-runtime snapshot.

Rollback is one preference change plus process restart. It never migrates or
deletes user data.
