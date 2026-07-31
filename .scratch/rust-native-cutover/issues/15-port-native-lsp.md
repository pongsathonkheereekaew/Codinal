Type: task
Status: open

## Question

Can the shared native host own language-server lifecycle and JSON-RPC so the
GPUI editor can replace Tauri LSP commands and notification events?

## Destination

Move the shell-neutral LSP registry into `native-host`, retain Tauri as a thin
adapter during cutover, then wire GPUI document lifecycle, diagnostics, and
symbol queries to the shared API.

## Required evidence

- Native-host owns subprocess lifecycle, framing, timeout, and path validation.
- The shared module contains no Tauri type or event dependency.
- Tauri fallback compiles through a compatibility re-export.
- GPUI exercises open/change/save/close plus diagnostics and symbol queries.
- Language servers shut down explicitly with the native shell.

## Progress

- The complete LSP registry and tests moved from Tauri into `native-host`.
- Tauri now consumes a thin compatibility re-export of the shared API.
- Remaining: GPUI editor/document integration and packaged parity evidence.
