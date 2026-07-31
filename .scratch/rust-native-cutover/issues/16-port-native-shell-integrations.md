Type: task
Status: open

## Question

Can workspace selection, project-item opening, and OAuth callback relay move to
the shared native host without weakening path identity or secret handling?

## Destination

Give GPUI shell-neutral APIs for workspace selection, vnode-safe project item
opening, strict OAuth deep-link parsing, and authenticated loopback relay while
Tauri remains only a temporary adapter.

## Required evidence

- Native-host owns selection validation and macOS project-item identity checks.
- OAuth callbacks reject ambiguous fields and zeroize sensitive values.
- Callback relay authenticates both runtime and secret-sync credentials.
- Tauri fallback compiles using only compatibility re-exports.
- GPUI wires workspace and deep-link flows without a WebView bridge.

## Progress

- Workspace selection, project opening, OAuth parsing, and callback relay moved
  into `native-host`; their existing identity/path tests moved with them.
- Tauri direct native-dialog, Objective-C, Keychain, and libc dependencies were
  removed where the shared host now owns them.
- Remaining: GPUI workspace/deep-link wiring and packaged parity evidence.
