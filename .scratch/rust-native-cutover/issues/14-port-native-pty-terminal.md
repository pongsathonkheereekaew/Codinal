Type: task
Status: open

## Question

Can the shared Rust native host own PTY lifecycle and byte streaming so GPUI
can replace Tauri terminal commands/events without changing trusted-terminal
semantics?

## Destination

Move PTY ownership and tests out of `desktop/src-tauri`, retain the Tauri
fallback as a thin callback adapter, then wire a GPUI terminal surface to the
same native registry.

## Required evidence

- PTY open/input/resize/kill behavior is tested from `native-host`.
- The native PTY module has no Tauri dependency or event type.
- Tauri fallback compiles against the shared API without its own PTY module.
- GPUI receives bounded byte chunks and exit state from the shared registry.
- Terminal rendering/input remains responsive and has an explicit shutdown
  path before the Tauri terminal surface is retired.

## Progress

- PTY implementation and integration tests moved from Tauri to `native-host`.
- Tauri now re-exports the native module and retains only event adaptation.
- GPUI now opens the trusted shell only after explicit user action, consumes
  bounded cursor-based output on a per-open generation, and dispatches
  interrupt/resize/kill operations off the foreground executor.
- Keyboard input now uses one generation-scoped bounded FIFO writer, GPUI's
  committed-text/IME path for Unicode input, xterm control/navigation/function
  sequences, and cancellation that discards queued bytes before shutdown.
- PTY output now feeds a bounded VT100 screen model instead of rendering raw
  escape bytes. Resize requests are coalesced, acknowledged by the kernel, and
  correlated with output cursor boundaries so redraw bytes use the correct
  geometry; failed geometry is stable rather than retried every paint.
- The terminal surface exposes a native accessibility role and its replay test
  holds visible output to the measured screen bounds under sustained output.
- Exit and stop clean up unique native session IDs and permit a fresh buffer,
  poll task, and PTY generation on reopen.
- Remaining: packaged interactive parity evidence before retiring the fallback
  terminal surface.
