Type: task
Status: open
Blocked by: 09, 12

## Question

Can the Rust runtime own authenticated live provider-secret updates so GPUI can
replace Tauri's provider settings commands without exposing secret values?

## Destination

Advance R2 and remove the Tauri-only `control_client` secret-sync bridge. The
native host remains the Keychain owner; the Rust runtime receives bounded
one-shot updates authenticated by both bearer and secret-sync tokens.

## Required evidence

- PUT/DELETE provider updates require exact bearer and secret-sync tokens.
- Provider IDs, base URL rules, size limits, and custom-provider boundaries
  match the bootstrap contract and fail closed.
- Secret values are zeroized, never returned, logged, audited, or persisted by
  the runtime.
- Audit metadata records only provider ID and configured/deleted outcome.
- GPUI can list status and apply/delete a provider through native host/runtime
  APIs without invoking a Tauri command.

## Out of scope

- Removing the Tauri fallback before the remaining settings, terminal, LSP,
  updater, OAuth, and release gates pass.
