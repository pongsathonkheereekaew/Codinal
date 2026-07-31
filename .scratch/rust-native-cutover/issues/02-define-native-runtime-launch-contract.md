Type: research
Status: resolved
Blocked by: 01

## Question

What authenticated process lifecycle and command-line contract must the
Rust-native runtime expose so the native host can launch it without leaking
credentials or allowing concurrent writers?

## Answer

The host launches a packaged, validated runtime binary with no credential
arguments. It supplies only `CODINAL_SESSION_TOKEN`, `CODINAL_PORT`, and
`CODINAL_DATA_DIR` through the child environment; the runtime validates and
removes the token before starting any child work. It must validate a nonzero
loopback port and an existing non-symlink data directory, acquire an exclusive
owner lock inside that directory before opening writable stores, bind only
`127.0.0.1`, and expose authenticated `/v1/health` for the host's bounded
readiness probe. The host treats a failed probe as startup failure and shuts
the child down; it retains the existing explicit kill-and-wait shutdown path.

Provider secrets remain outside this R1 launch contract. When Rust provider
adapters arrive, they must use a one-shot stdin bootstrap rather than argv or
environment, matching the current native-owned Keychain boundary.

Evidence: `NativeRuntimeLaunch` already keeps token material out of arguments
(`desktop/native-host/src/host.rs`); `RuntimeConfig` already enforces the
loopback and non-symlink inputs (`crates/codinal-runtime/src/lib.rs`); the
remaining executable bootstrap and inter-process ownership lock are absent.
