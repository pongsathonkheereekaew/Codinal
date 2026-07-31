Status: resolved
Type: task
Blocked by: 03, 04, 05

## Question

How will replay/live parity, non-secret preference migration, opt-in dogfood,
and pre-cutover Tauri rollback be measured and operated?

## Answer

GPUI remains opt-in. Only the non-secret `desktop_shell` preference is
migratable; each replay/live run records contract and performance metrics.
Any GPUI launch or contract failure restarts the same session under Tauri
without changing sidecar state or evidence. After every G6 gate passes, Tauri
is retired permanently under the owner's approved Rust-only cutover. The full
metric/rollback contract is in `desktop/gpui-prototype/PARITY.md`.
