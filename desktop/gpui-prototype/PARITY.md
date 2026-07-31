# G5 parity and rollback contract

GPUI is opt-in during dogfood. The selector records only `desktop_shell=gpui`
as a non-secret local preference; it never copies bearer tokens, provider keys,
OAuth values, approval decisions, or preview contents.

Every GPUI replay/live run must record: fixture or session identifier, control
plane version, event count, approval/cancel outcome, Git/evidence outcome,
first-interactive-paint, P95 typing latency, terminal/tree/diff size, and RSS.
The same run is executable with `desktop_shell=tauri`; failure to start GPUI or
any contract mismatch automatically falls back to Tauri without changing the
sidecar, session, or stored evidence.

Rollback is one preference change plus process restart. It never migrates or
deletes user data.
