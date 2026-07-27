# Phase 46 — Real PTY terminal

**Branch:** `codinal/phase-46-real-terminal`
**Status:** verified locally; PR pending.

## Goal

Replace the one-shot subprocess "terminal" (textarea → POST `/terminal/run` →
captured stdout in a `<pre>`) with a real persistent interactive PTY: ANSI
color, true-color, alternate-screen TUI apps (vim, htop, less), resize, and
live keystroke I/O — matching the terminal quality of every agentic IDE peer
(Cursor, Windsurf, Codex desktop).

## Approach

The terminal is a **pure Rust-shell feature**. The Python control plane never
touches the PTY (it's a kernel object; owning it in Rust is correct, and it
avoids multiplexing high-throughput bytes onto the assistant-event websocket).

```
[xterm.js frontend] ←tauri events→ [Rust pty.rs: forkpty + reader thread]
       ↑                                   ↑
   user keystrokes                    child process (user's $SHELL)
   via pty_input command              runs UNSANDBOXED in workspace cwd
```

### Trust-class split (architectural decision)

The roadmap invariant "terminal uses the same sandbox as agent shell calls"
was written for one-shot commands and is incompatible with a persistent
interactive PTY (the seatbelt denies network, uses a temp HOME, and the policy
gate evaluates a complete command string — none of which fits an interactive
session). Revised into two trust classes:

- **Agent shell** (`run_shell` tool): unchanged — seatbelt-sandboxed via
  `runtime/sandbox/shell.py`, one-shot, policy-gated, network-denied.
- **User terminal** (interactive PTY): trusted user action, unsandboxed, real
  HOME, network allowed. Equivalent to the user opening their own Terminal.app.

The two paths are fully isolated in code.

## Changes

### Rust

- `desktop/src-tauri/src/pty.rs` (NEW) — `PtySession` + `PtyRegistry`.
  - `spawn()` calls `nix::pty::openpty` + `nix::unistd::fork`; child does
    `setsid` + `dup2` slave onto stdio + `exec`s `$SHELL` (fallback
    `/bin/zsh`) with `cwd=workspace`, real `HOME`, `TERM=xterm-256color`.
  - Reader thread reads master fd in 4KB chunks via raw `libc::read`,
    invokes an `emit` closure per chunk (+ `None` on EOF).
  - `write_input` via `libc::write`; `resize` via `TIOCSWINSZ` ioctl;
    `kill` via `SIGKILL` to child + reap (`waitpid` WNOHANG) + join reader.
  - `PtyRegistry`: `Mutex<HashMap<String, PtySession>>` with
    `open`/`write`/`resize`/`kill`.
  - macOS-only (`#![cfg(target_os = "macos")]`).
- `desktop/src-tauri/Cargo.toml` — added
  `nix = { version = "=0.29.0", features = ["term", "process", "signal"] }`.
- `desktop/src-tauri/src/lib.rs`:
  - `DesktopState` += `ptys: pty::PtyRegistry` (macOS cfg).
  - 4 Tauri commands: `pty_open` (spawns + wires `emit` → Tauri `pty-data`/
    `pty-exit` events, base64-encoded), `pty_input`, `pty_resize`, `pty_kill`.
    Non-mac stubs return `Unsupported`.
  - Registered all four in `invoke_handler!`.

### Vendored xterm.js (`desktop/ui/vendor/`, NEW)

- `xterm.js` (UMD, 289KB), `xterm.css`, `xterm-addon-fit.js` — pinned
  `@xterm/xterm@5.5.0` + `@xterm/addon-fit@0.10.0`, MIT license preserved.
  Loaded via `<script src>` in `index.html`. **No `package.json`, no npm, no
  build step.**
- `README.md` documents the pin + update procedure.

### Frontend

- `desktop/ui/index.html` — replaced the textarea/timeout/run/stop/`<pre>`
  terminal panel with `<div id="terminal-host">` + Restart/Clear buttons;
  loaded the two vendor scripts + `xterm.css`.
- `desktop/ui/startup.js`:
  - `__codinalListen` shim over `window.__TAURI__.event.listen`.
  - `openTerminalView()` — lazily mounts xterm `Terminal` (IntersectionObserver
    on the panel), opens a PTY via `pty_open`, wires `term.onData` →
    `pty_input`, listens for `pty-data` (base64 → `Uint8Array` → `term.write`)
    and `pty-exit`, and a `ResizeObserver` → `fitAddon.fit()` + `pty_resize`.
  - `closeTerminalView()` / `restartTerminalView()` — kill + dispose / reopen.
  - Session/workspace switch calls `closeTerminalView()` (replaces the old
    textarea clear).
  - Removed: `runTerminalCommand`, `stopTerminalCommand`,
    `formatTerminalResult`, `setTerminalBusy` (kept as a no-op shim for legacy
    callers).
- `desktop/ui/app.css` — `.terminal-host` sized container for xterm.

### Tests

- `desktop/src-tauri/tests/pty.rs` (NEW, 5 tests) —
  `pty_open_writes_input_and_reads_output` (echo round-trip),
  `pty_exit_emits_none_when_child_exits`, `pty_resize_does_not_error`,
  `pty_kill_removes_session_from_registry`, `pty_write_to_unknown_session_errors`.
  All pass against a real `forkpty`.
- `tests/desktop_ui/test_ui_contract.py` — updated terminal-id assertions to
  the new contract; added `pty_open`/`pty_input`/`pty_resize`/`pty_kill`/
  `pty-data`/`pty-exit` string assertions.

### Docs

- `docs/plan/codinal-parity-roadmap.md` — trust-class-split note at L122;
  Phase 46 entry in the P0 release-floor checklist.

## Verification

```
cd desktop/src-tauri && cargo test --test pty          # 5 passed
cd desktop/src-tauri && cargo build --release          # clippy clean
./verify.sh                                            # Codinal verify: PASS
```

Manual smoke (documented, not automated): open terminal → `ls`, `vim`, `htop`,
`cargo build` → confirm color + TUI render + exit codes; resize window →
xterm refits + child gets SIGWINCH.

## Out of scope (deferred)

- Code viewer / editor / LSP / completion (separate P2 epic).
- Cross-platform PTY (Windows ConPTY, Linux).
- Scrollback search, copy/paste themes, font configuration.
- Live conformance run (operational, not code).
