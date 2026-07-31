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

## Progress

- Rust `ProviderSecrets` now validates constant-time sync-token authorization,
  bounded live update/delete, stable provider IDs, and HTTP(S) base URLs.
- Rust runtime PUT/DELETE routes require bearer plus secret-sync tokens, audit
  only non-secret metadata before mutation, and zeroize raw buffers, headers,
  bodies, replacement secrets, and superseded values.
- The provider sync transport moved from the Tauri crate into `native-host`, so
  GPUI and Tauri share one native API. Tauri retains only temporary command
  orchestration while the GPUI settings form is ported.
- Custom-provider add/delete now uses the same dual-token, zeroizing native
  transport and a dedicated Rust route with bounded slug/URL/key validation.
- Definite runtime rejection rolls Keychain metadata back atomically; an
  ambiguous post-send failure preserves Keychain as restart source of truth
  instead of creating permanent inverse state.
- GPUI now renders standard/custom configured status directly from native-host
  Keychain APIs without exposing values or invoking Tauri.
- GPUI now owns a native provider-settings controller and a confirmed delete
  action that updates Keychain/runtime state without invoking Tauri.
- Remaining: GPUI provider edit controls with secure native text input.
