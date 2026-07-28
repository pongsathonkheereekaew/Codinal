# OSS Terminal & Agentic-IDE UX Survey for Codinal

**Date:** 2026-07-28
**Scope:** What Codinal (Tauri + Rust shell + vanilla-JS UI + Python runtime; real PTY since Phase 46, CodeMirror 6 editor since Phase 49) can learn from open-source terminal emulators, shell frameworks, and agentic IDEs.
**Method:** Primary sources only — actual repo trees, READMEs, and source files fetched from each project. Code patterns quoted verbatim where load-bearing.

---

## TL;DR — what to copy, what to skip

| Project | Borrow? | Specific takeaway | Priority |
|---|---|---|---|
| **Wave Terminal** | **YES — closest analog** | WebglAddon + context-loss fallback, scrollback serialization via `SerializeAddon`, copy-on-select, CSI 2026 sync handling, debounce(50ms) resize. `frontend/app/view/term/termwrap.ts` is a near-direct blueprint for Codinal's `desktop/ui/startup.js`. | Must-copy |
| **OSC 133 shell-integration standard** | **YES** | The single enabling primitive for "blocks", command navigation, exit-code awareness. Emit/mark A/B/C/D in the spawned zsh. Adopted by VS Code, iTerm2, kitty, WezTerm, Ghostty. Alacritty still lacks it. | Must-copy |
| **Alacritty** | **YES — Rust PTY patterns** | `SIGCHLD` via signal-hook socket + `try_wait` (not blocking `waitpid`), bounded `READ_BUFFER_SIZE` + `MAX_LOCKED_READ` backpressure, `OnResize` via `TIOCSWINSZ`. Codinal's current reader is a single blocking thread — these are the upgrade paths. | Must-copy (PTY polish) |
| **Zed** | **YES — IDE structure** | Terminal backend = Alacritty's `alacritty_terminal` crate reused; GPUI separates "backend-neutral domain types (cells, modes, points, ranges)" from view. `TerminalBuilder` two-step spawn (file handles validated before model context). This separation is exactly how Codinal should evolve `pty.rs` + `startup.js`. | Must-copy (architecture) |
| **Ghostty** | **Nice-to-have** | Multi-thread per terminal (read/write/render), SIMD parser, Metal/OpenGL. Codinal uses xterm.js for rendering so most of this is N/A — but the "native UI, no Electron-style lowest-common-denominator" philosophy and rigorous xterm-spec conformance are worth the posture. | Nice-to-have |
| **Oh My Zsh** | **Stay independent — read-only** | Don't ship/bundle it. Detect it, *read* the user's enabled plugins (git aliases, etc.), and parse the prompt for branch/status. Shipping it couples Codinal to a 300+ plugin surface we don't need. | Read-only |
| **Warp** | **Conceptual only** | **Repo is issues-only; LICENSE says "currently closed-source".** The "blocks", prompt detection, and shell-integration engine are NOT in the open repo — only auxiliary crates (`warp_core`, `warp_completer`, `ai`, `semantic_selection`, `diff_validation`, `project_context`, `skills`) are visible. Borrow the *idea* of action-result blocks + OSC 133; do not expect to read the implementation. | Conceptual |
| **Tabby (Eugeny)** | **Nice-to-have** | Electron + node-pty + Angular, heavy plugin marketplace + MCP/AI plugins. Architecturally further from Codinal. Worth noting the plugin-marketplace UX and MCP-in-terminal pattern. | Nice-to-have |
| **Rio** | **Nice-to-have** | Rust + wgpu (Vulkan/Metal), explicit "desktops **and browsers**" goal. If Codinal ever wants a WASM-renderable terminal canvas, Rio's wgpu path is the reference. | Nice-to-have |

**The headline finding:** Codinal's existing PTY + xterm.js wiring (`desktop/src-tauri/src/pty.rs` + `desktop/ui/startup.js:3422–3569`) is functionally equivalent to Wave Terminal's `termwrap.ts`, but Wave has ~5 production-grade upgrades Codinal lacks: WebGL renderer with context-loss fallback, copy-on-select, search, CSI 2026 synchronized-output handling, and scrollback persistence via `SerializeAddon`. These are the highest-ROI, lowest-risk improvements. Layering OSC 133 shell-integration on top unlocks the Warp-style "blocks" UX that is the stated end goal.

---

## 1. Ghostty (ghostty-org/ghostty)

**Repo:** https://github.com/ghostty-org/ghostty · **Language:** Zig · **License:** MIT

### What it is
A "fast, feature-rich, cross-platform terminal emulator that uses platform-native UI" plus a C/Zig embeddable library (`libghostty`). The macOS app is true SwiftUI; the Linux app is GTK with systemd/cgroup integration. Strict adherence to de juro terminal specs, then xterm behavior, then other terminals.

### Why it's fast (primary source: project README + `src/Terminal.zig`)
- **Multi-threaded per terminal:** dedicated **read thread, write thread, and render thread** per terminal instance. (Codinal's PTY is single-reader-threaded.)
- **SIMD parser:** "a heavily optimized terminal parser that leverages CPU-specific SIMD instructions" on the read thread.
- **GPU rendering, native per-OS:** Metal + CoreText on macOS; OpenGL on Linux. No cross-platform rendering abstraction lowest-common-denominator.

### What maps to Codinal (and what doesn't)
| Ghostty pattern | Maps to Codinal? | How |
|---|---|---|
| Per-terminal read/write/render threads | **Partial.** Codinal owns the PTY in Rust (one reader thread today — `desktop/src-tauri/src/pty.rs:166-197`). Rendering is delegated to xterm.js in the JS UI, so there's no Rust render thread to add. The useful half: separating the **write path** (input) from the **read path** (output) in Rust so a blocked writer can't starve the reader. |
| SIMD parser | **No.** xterm.js does the parsing in JS/WebView. Codinal should not re-implement a VT parser in Rust while xterm.js owns the buffer. |
| GPU rendering | **No directly — but see Wave's WebglAddon** (§4). That is the Codinal-equivalent of "GPU rendering" and is a 1-day upgrade. |
| Native UI per platform | **Posture only.** Codinal's Tauri webview is already closer to native than Electron; lean into platform conventions (macOS menus, etc.) rather than fighting the webview. |
| Strict spec conformance | **Yes.** Set `TERM=xterm-256color` (already done in `pty.rs:245`) and aim for OSC 133 / DECRQSS correctness over chasing exotic sequences. |

### Pitfalls Ghostty surfaces
- Native UI means N codebases (SwiftUI + GTK + ...). Codinal's bet on Tauri+webview avoids this — don't re-introduce it by hand-rolling per-OS shells.
- A custom VT parser is a years-long investment (Ghostty's is). Reusing xterm.js's parser is the right call for Codinal unless it becomes the bottleneck.

---

## 2. Alacritty (alacritty/alacritty)

**Repo:** https://github.com/alacritty/alacritty · **Language:** Rust · **License:** Apache-2.0
**Key files:** `alacritty_terminal/src/tty/unix.rs`, `alacritty_terminal/src/event_loop.rs`

This is the most directly relevant Rust PTY reference — and notably **Zed reuses `alacritty_terminal` as its terminal backend** (see §3), so learning Alacritty's patterns pays off twice.

### PTY spawning (`tty/unix.rs`)
- Uses `rustix_openpty::openpty` → master + slave fds.
- Wires slave as the child's stdin via `builder.stdin(slave.try_clone()?)`.
- **Does not call `fork()` manually.** Uses `std::process::Command` with a `pre_exec` closure that is async-signal-safe:
  ```rust
  libc::setsid();
  set_controlling_terminal(slave_fd)?;
  libc::close(slave_fd);
  libc::close(master_fd);
  ```
  → then `builder.spawn()`.
- **Codinal difference:** Codinal *does* call `nix::unistd::fork()` manually with a hand-rolled child branch (`desktop/src-tauri/src/pty.rs:151-257`). This works but is higher-risk than the `pre_exec` + `Command::spawn` pattern. **Recommendation:** evaluate migrating to `pre_exec` for the child-setup branch; it removes the manual `mem::forget` + `dup2` + `_exit(127)` dance.

### Event loop (`event_loop.rs`) — the patterns Codinal should adopt
1. **Async polling, not blocking reads.** Uses the `polling` crate (Mio-like `Poller`); runs on a dedicated `"PTY reader"` thread that blocks on `self.poll.wait(&mut events, timeout)` and wakes on fd readiness. Codinal's reader (`pty.rs:166-197`) blocks on `libc::read` in a tight loop — fine for one session, but it can't be woken to resize/kill cleanly and can't multiplex multiple PTYs on one thread.
2. **Bounded backpressure.** Two explicit limits:
   - `READ_BUFFER_SIZE` — when unprocessed bytes exceed this, force an unfair lock acquisition: `None if unprocessed >= READ_BUFFER_SIZE => self.terminal.lock_unfair()`.
   - `MAX_LOCKED_READ` — `if processed >= MAX_LOCKED_READ { break; }` caps how long the reader holds the terminal lock per acquisition, so massive output (e.g. `cat huge.log`) doesn't starve the UI.
   - **Codinal today has neither.** A fast `yes` or a giant compile log will fill xterm.js's write queue unbounded.
3. **Resize via message channel + `OnResize`.** Resize is a `Msg::Resize(window_size)` sent into the loop's channel; the loop drains it and calls `self.pty.on_resize(window_size)`, which issues `libc::ioctl(fd, TIOCSWINSZ, &win)` (no `SIGWINCH` handler in the wrapper). Codinal already does the `TIOCSWINSZ` ioctl (`pty.rs:80-95`) — good. The takeaway is the *channel-based* dispatch so resize can't race the reader.
4. **Child exit via `SIGCHLD` signal-hook socket, not blocking wait.**
   ```rust
   signal_pipe::register(sigconsts::SIGCHLD, sender)
   ```
   The receive end is registered with the `Poller` under `PTY_CHILD_EVENT_TOKEN`; on readiness it does a 1-byte read then `self.child.try_wait()` (non-blocking) → `Some(ChildEvent::Exited(status))`.
   - **Codinal pitfall (already present):** `pty.rs:98-114` `Drop` polls `waitpid(WNOHANG)` in a 50×10ms spin loop then `join()`s the reader. If the child wedges, Drop can stall ~500ms+ and the reader join can block indefinitely. The signal-hook-socket pattern is strictly better.
5. **Write-interest tracking.** Input writes only register writable interest when `state.needs_write()`; otherwise the poller ignores writability. Avoids busy-polling a quiet PTY.

### TUI / escape-sequence handling
Alacritty does NOT special-case TUI apps; it parses the stream into a grid and lets the application drive via standard sequences. **Notable gap:** Alacritty still has an open issue ([#5850](https://github.com/alacritty/alacritty/issues/5850)) requesting **OSC 133** support — meaning Alacritty cannot do semantic prompt/block detection. Codinal should *not* inherit this limitation; see §8.

### Verdict for Codinal
- **Must-copy:** signal-hook `SIGCHLD` socket, bounded read buffer + `MAX_LOCKED_READ`, channel-dispatched resize.
- **Nice-to-have:** migrate from manual `fork` to `pre_exec`.

---

## 3. Zed (zed-industries/zed)

**Repo:** https://github.com/zed-industries/zed · **Language:** Rust · **License:** GPL-3.0 (with AGPL components) + Apache-2.0
**Key crates:** `crates/terminal`, `crates/terminal_view`, `crates/editor`, `crates/gpui*`, `crates/workspace`, `crates/assistant`/`agent`/`agent_ui`, `crates/collab`/`collab_ui`, `crates/edit_prediction`, `crates/project`

### Architecture (primary sources)
- **Custom retained-mode UI framework: GPUI** (`gpui`, with `gpui_macos`/`gpui_linux`/`gpui_windows`/`gpui_wgpu`/`gpui_web` backends). All editor/terminal/chat panes are GPUI views, not DOM.
- **Workspace = tree of dockable panes.** `crates/workspace` owns the pane grid; `terminal_view`, `editor`, `assistant` register as pane item types. The terminal is *just another pane* — same focus, split, and tab model as the editor.
- **Terminal backend is reused Alacritty.** `crates/terminal` wraps `alacritty_terminal`. The view layer (`crates/terminal_view`) renders `alacritty_terminal`'s grid into GPUI and dispatches backend-neutral actions. This is the key architectural lesson: **don't write your own VT state machine if you can embed a battle-tested one.** (Codinal's analog is xterm.js, which it already embeds.)
- **Backend/frontend separation in the terminal.** From `crates/terminal_view`: Alacritty provides "neutral domain types for terminal content, cells, modes, points, ranges, scroll commands, vi motions, hyperlinks, and search matches" and `TerminalView` "renders `TerminalContent` and dispatches backend-neutral actions." This keeps the UI swappable.
- **Two-step terminal spawn.** Because spawning a tty can fail and GPUI has no "model API for instantiation failures," Zed uses a `TerminalBuilder` that "splits tty instantiation into a 2 step process" — first create file handles and verify, *then* call the subscription method "from within a model context." A `TerminalView` wrapper "abstracts over failed and successful terminals."
  - **Maps directly to Codinal:** today `pty_open` returns a `Result` and the JS layer shows a red error line (`startup.js:3545-3548`). A typed "pending/ok/failed" state object on the Rust side would be cleaner.
- **Input routing (terminal_view).** Four distinct paths: raw `try_keystroke()` for direct keybindings; GPUI-synthesized dispatch for keys it hijacks; IME/paste via `View::replace_text_in_range()`; and a unified `.input()` API. Codinal currently funnels everything through xterm.js `onData` — adequate, but paste/IME edge cases are exactly where Zed's split helps.

### Collaboration
- "Multiplayer code editor." `Dockerfile-collab` + `livekit.yaml` indicate dedicated collab infra. The CRDT/sum-tree machinery lives in `crates/sum_tree` (also visible in Warp's repo — shared lineage). Out of scope for Codinal today, but the **pane-as-first-class-citizen** model is what makes multi-user shared panes possible later.

### AI/agent crates worth modeling
Zed's crate list is a roadmap for an agentic IDE: `agent`, `agent_servers`, `agent_settings`, `agent_skills`, `agent_ui`, `agent_skills`, `acp_thread` (agent communication protocol thread), `acp_tools`, `context_server` (MCP), `edit_prediction`, `edit_prediction_context`, `edit_prediction_metrics`, `project_context`/`project_context`-style. Codinal's Python control plane can mirror this decomposition.

### Verdict for Codinal
- **Must-copy:** pane-as-item model (terminal, editor, chat are interchangeable pane contents); backend-neutral terminal domain types; two-step spawn with a typed pending/ok/failed state.
- **Skip:** GPUI itself (Tauri's webview is Codinal's UI layer); full collab/CRDT until needed.

---

## 4. Wave Terminal (wavetermdev/waveterm)

**Repo:** https://github.com/wavetermdev/waveterm · **Languages:** TypeScript/React (frontend), Go (backend `wavesrv`), Electron (shell)
**Key files:** `frontend/app/view/term/termwrap.ts` (650 lines), `emain/emain-wavesrv.ts`, `frontend/app/block/block.tsx`

### ⚠️ Architecture correction to the brief
The brief asked "if it's a Tauri/WebView terminal" and called it the "closest architectural analog." **Wave is Electron, not Tauri.** Its backend is a **separate Go binary** (`wavesrv`) that Electron spawns. So Wave is *not* an architectural sibling of Codinal's Tauri shell. **However**, Wave's xterm.js frontend (`termwrap.ts`) is functionally identical to Codinal's `desktop/ui/startup.js` terminal block — and is more mature. That is the real value here.

### How Wave bridges terminal → UI (primary source: `emain-wavesrv.ts`)
1. Electron main **spawns the Go binary** as a child process:
   ```ts
   const proc = child_process.spawn(getWaveSrvPath(), { cwd: getWaveSrvCwd(), env: envCopy });
   ```
2. wavesrv writes a marker line to **stderr**: `WAVESRV-ESTART` with a regex `ws:([a-z0-9.:]+) web:([a-z0-9.:]+) version:...`. Electron parses out the **WebSocket endpoint** and **HTTP endpoint**.
3. The **React frontend** then connects to that WebSocket directly; PTY data is streamed as base64 "append" operations to a virtual file (`TermFileName`) surfaced via an RxJS-like file-subject. Frontend decodes: `base64ToArray(msg.data64)`.
4. Backend pushes lifecycle events back over stderr as `WAVESRV-EVENT:<json>` lines.
5. Lifecycle coupling: if wavesrv exits (and no update is running), the Electron app force-quits.

**Maps to Codinal:** Codinal's bridge is **simpler and arguably better** for its scale — Tauri events (`pty-data`/`pty-exit`) with base64 payloads go straight from the Rust reader thread to the JS listener (`startup.js:3491-3504`), no separate binary, no WebSocket. **Codinal should not adopt Wave's spawn-a-Go-binary design.** The lesson is the opposite: Wave needs the indirection because it has a separate backend language; Codinal doesn't.

### The `termwrap.ts` patterns Codinal should copy verbatim
This file is the single highest-value artifact in the survey. Concrete upgrades over Codinal's `startup.js:3458-3549`:

1. **WebGL renderer with context-loss fallback.** Codinal uses the default DOM canvas renderer.
   ```ts
   setTermRenderer(renderer: "webgl" | "dom") {
     // ...
     const addon = new WebglAddon();
     this.webglContextLossDisposable = addon.onContextLoss(() => {
       this.setTermRenderer("dom");   // graceful degrade
     });
     this.terminal.loadAddon(addon);
   }
   ```
   Load `@xterm/addon-webgl`, try WebGL, and on `onContextLoss` fall back to the DOM renderer. Big perf win for scroll/throughput; the fallback makes it safe.

2. **Debounced resize at 50ms (Codinal uses 80ms).** Wave also only sends the resize RPC **if dimensions actually changed**:
   ```ts
   handleResize() {
     const oldRows = this.terminal.rows, oldCols = this.terminal.cols;
     this.fitAddon.fit();
     if (oldRows !== this.terminal.rows || oldCols !== this.terminal.cols) {
       RpcApi.ControllerInputCommand(TabRpcClient, { blockid, termsize: { rows, cols } });
     }
   }
   ```
   Codinal currently fires `pty_resize` on every debounced observer tick even when cols/rows are unchanged (`startup.js:3513-3525`). **Add the no-op guard.**

3. **Scrollback persistence via `SerializeAddon`.** Wave tracks `dataBytesProcessed`; once it exceeds `MinDataProcessedForCache`, it runs `serializeAddon.serialize()` on `requestIdleCallback` and calls `services.BlockService.SaveTerminalState(blockId, serialized, "full", ptyOffset, termSize)`. On reload it writes the cached state back to xterm.js *then* appends new streamed data.
   - **Maps to Codinal:** this is exactly how Codinal can survive session/workspace switches and app restarts without losing terminal history. Today `closeTerminalView()` (`startup.js:3551-3564`) just disposes — scrollback is lost.

4. **Copy-on-select with search-bar focus guard.**
   ```ts
   this.terminal.onSelectionChange(debounce(50, () => {
     if (!globalStore.get(copyOnSelectAtom)) return;
     const active = document.activeElement;
     if (active != null && active.closest(".search-container") != null) return; // don't clobber search nav
     let selectedText = this.terminal.getSelection();
     // ... trim trailing whitespace, write to clipboard
   }));
   ```
   Codinal has no copy-on-select and no search.

5. **CSI 2026 synchronized-output handling.** Wave registers CSI handlers to watch mode `2026` toggles and clear-scrollback (`params[0] === 3`) so full-screen repaints (e.g. from TUI apps) don't visually tear. Codinal's xterm.js will receive these sequences but nothing coordinates the repaint.

6. **Held-data queue before first render.** If bytes arrive before xterm.js is mounted/ready, Wave pushes to `this.heldData.push(decodedData)` and flushes once ready — avoiding lost early bytes (shell banner, etc.). Codinal opens the PTY *after* mount (`startup.js:3536-3543`) so this is less acute, but the pattern is defensive.

### Block model (`frontend/app/block/block.tsx`)
- A `Block` is a generic container (`Block` → `BlockInner` → `BlockFull`) with a `viewType` string that dynamically resolves a `viewComponent` (terminal, webview, editor, AI). A global `blockregistry` (de)registers view models by block id; `dispose()` on unmount prevents leaks.
- **Command Blocks** "isolate and monitor individual commands" — conceptually the same as Warp blocks, surfaced as a first-class UI primitive rather than a single scrolling buffer.
- **Maps to Codinal:** Codinal's current `#terminal-host` is a single monolithic terminal. The Wave pattern suggests making the terminal *one view type among several* in a block/pane registry — which converges with Zed's pane model (§3) and is the path to Cursor-parity (chat pane, editor pane, terminal pane, diff pane all peers).

### Durable SSH sessions
Wave advertises "durable SSH sessions that survive network interruptions and restarts" — implemented by `wsh` (Go CLI) managing remote shells. Not immediately relevant to Codinal's local-trusted-terminal scope, but the *survive-restart* property is the same scrollback-persistence lesson above.

### Verdict for Codinal
- **Must-copy (from `termwrap.ts`):** WebglAddon + context-loss fallback; no-op-guarded debounced resize; `SerializeAddon` scrollback persistence; copy-on-select; held-data queue; CSI 2026 handling.
- **Do NOT copy:** the Electron-spawns-Go-binary bridge. Codinal's Tauri-direct event bridge is simpler and appropriate.

---

## 5. Warp (warpdotdev/Warp)

**Repo:** https://github.com/warpdotdev/warp · ⚠️ **ISSUES-ONLY — NOT OPEN SOURCE**
**License file verbatim:** *"Warp (https://warp.dev) is currently closed-source. Whether Warp will be open sourced and the strategy around it if so, are both still a work in progress."*
**README verbatim:** *"This is an issues-only repo for Warp where you can submit issues, bugs and feature requests."*

### ⚠️ Correction to the brief and to web-search noise
Several 2026 web results (knightli.com, developersdigest.tech, Reddit AMAs) claim Warp went AGPL/open-source in May 2026 with "~56k stars." **The repo's own LICENSE and README contradict this.** What *is* publicly browsable in `warpdotdev/warp`:
- `crates/*` — a set of **auxiliary** Rust crates (see below). These appear to be build/test/cloud helpers, not the terminal engine.
- `app/src/*` — the directory listing is visible (ai, ai_assistant, app_state, auth, billing, ...) but the code is **not** under an open license.
- The actual **terminal engine, block parser, shell-integration injector, and GPU renderer are not in the open repo.**

Treat Warp as a **closed-source conceptual reference**, not a readable codebase. Do not waste effort cloning `warpdotdev/warp` expecting to read the block implementation.

### Conceptual model (from public docs + the visible crate names)
The visible crates are themselves a useful feature inventory for an agentic terminal:
- `warp_core` — `command.rs`, `semantic_selection/`, `session_id.rs`, `sync_queue.rs`
- `warp_completer` — shell completion engine
- `ai/` — `agent/`, `diff_validation/`, `project_context/`, `skills/`, `document.rs`, `workspace.rs`
- `mcp` — Model Context Protocol integration
- `input_classifier`, `natural_language_detection`, `languages`, `syntax_tree`
- `sum_tree` — CRDT-ish sum-tree (shared lineage with Zed's crate of the same name)
- `command-signatures-v2` — typed command signatures

### The "blocks" model (conceptual, corroborated)
Warp groups each command + its output into an **action-result block**. The boundary detection is built on **OSC 133** shell-integration markers (confirmed by Warp issue [#6718](https://github.com/warpdotdev/warp/issues/6718), where users emit `\e]133;A\e\\` via `PROMPT_COMMAND`). The shell is instrumented (zsh by default) to emit the A/B/C/D markers; Warp's (closed) parser segments the stream into blocks, each carrying the command text, output, and exit code. These blocks then feed AI features (explain, debug, command suggestions).

### Verdict for Codinal
- **Borrow the concept:** action-result blocks keyed off OSC 133 markers. This is the explicit Codinal end-goal ("Cursor-parity"). The implementation path is open: instrument the spawned zsh (§8) and segment in JS/xterm.js (or in Rust before emitting to JS).
- **Do not** expect to read Warp's source. The visible crates are a feature checklist, not a blueprint.

---

## 6. Oh My Zsh (ohmyzsh/ohmyzsh)

**Repo:** https://github.com/ohmyzsh/ohmyzsh · **Language:** shell (zsh) · **License:** MIT
~189k stars, 2,500+ contributors, actively maintained.

### What it actually provides
- **300+ plugins** (git, docker, homebrew, node, python, ruby, rails, macos, dotenv, bundler, rbenv, ...) — mostly aliases + completions + prompt hooks.
- **140+ themes** controlling prompt layout (default `robbyrussell`).
- **`oh-my-zsh.sh` loader:** reads `~/.zshrc`, sources core libs, loads enabled plugins/themes; supports async git-prompt rendering and `zstyle`-based alias skipping.
- **Auto-updater** (`omz update`) and a `custom/` directory for user plugins (drop a `*.plugin.zsh` file).

### Should Codinal integrate?
**No — stay independent; read-only detection.** Rationale:
1. Codinal spawns its own zsh (`desktop/src-tauri/src/pty.rs:232-235`) with `env_clear()` and a minimal env. Bundling OMZ would either (a) fight `env_clear` or (b) require re-introducing the user's full env — undermining the trusted/untrusted split.
2. OMZ is a *user configuration framework*, not a library. Embedding it couples Codinal to its 300+ plugin surface and update cadence.
3. The user already has OMZ if they want it; Codinal's trusted terminal should respect `$SHELL` and the user's rc files, not replace them.

### What a coding agent *gains* from OMZ-awareness (read-only)
- **Alias parsing:** read enabled plugins' alias files to expand `gst` → `git status` before showing command history to the agent or user.
- **Prompt state:** OMZ's async git prompt already computes branch/status; Codinal could *read* that (or compute it independently) instead of re-shelling out to `git`.
- **Safe config edits:** if Codinal ever helps the user configure their shell, writing to `custom/plugins/` is the non-destructive path.

### Verdict for Codinal
- **Detect, don't ship.** On PTY spawn, sniff `$ZSH`/`$OMZ` env or `~/.oh-my-zsh`. Use the knowledge to (a) expand aliases in command history and (b) enrich agent context with the user's actual shell vocabulary. Never bundle OMZ into Codinal.

---

## 7. Other Rust/Web terminals (Tabby, Rio)

### Tabby (Eugeny/tabby)
- **Stack:** Electron + TypeScript + Angular + node-pty. Web-based (also ships as a self-hostable web app for SSH/SFTP/Telnet).
- **Relevance:** Heavy plugin marketplace (installable from Settings) including **MCP/AI assistant plugins**, Docker/serial connections, sync-to-GitHub-Gist, nested split panes, multi-chord shortcuts.
- **Takeaways for Codinal:** (a) The plugin-marketplace-in-a-terminal UX is a proven pattern; Codinal's Python-runtime + skills system is the natural home for an equivalent. (b) MCP-in-the-terminal is emerging as table stakes — Zed, Tabby, and Warp all have it. Codinal should plan for an MCP surface in the terminal pane. (c) Nested split panes + multi-chord shortcuts are the power-user UX bar.
- **Architecturally further from Codinal** (Electron vs Tauri, Angular vs vanilla JS) — borrow UX, not structure.

### Rio (raphamorim/rio)
- **Stack:** Rust + **wgpu** (Vulkan/Metal/Metal), hardware-accelerated. Explicit design goal: "run in desktops **and browsers**."
- **Relevance:** If Codinal ever wants a terminal canvas that can render in a WebView via WASM/WebGPU (or move rendering off xterm.js), Rio's wgpu path is the reference implementation. Rio is also a clean example of a Rust terminal built cross-platform from day one.
- **For now:** nice-to-have. xterm.js in the Tauri webview is sufficient; revisit Rio only if xterm.js rendering becomes a bottleneck and a WebGPU canvas is desired.

### (Not separately investigated: "Eugine" appears to be a misspelling of "Eugeny" — the Tabby maintainer's username. Treated as Tabby.)

---

## 8. Cross-cutting: OSC 133 shell integration (the unblocking primitive)

**Spec:** FinalTerm-derived "Semantic Prompts" — [gitlab.freedesktop.org/Per_Bothner/specifications · proposals/semantic-prompts.md](https://gitlab.freedesktop.org/Per_Bothner/specifications/-/blob/master/proposals/semantic-prompts.md)
**Adopted by:** VS Code, iTerm2, kitty, WezTerm, Ghostty, Konsole, Contour, Windows Terminal (v1.18+). **Notably absent:** Alacritty ([#5850](https://github.com/alacritty/alacritty/issues/5850)) and tmux passthrough ([#3064](https://github.com/tmux/tmux/issues/3064)).

### The four markers
| Sequence | Meaning |
|---|---|
| `OSC 133;A ST` (`\e]133;A\e\\`) | Start of **prompt** |
| `OSC 133;B ST` | End of prompt / start of **user input** |
| `OSC 133;C ST` | Start of **command output** |
| `OSC 133;D [;<exitcode>] ST` | End of output (optional **exit code**) |

### Why this is the single most valuable thing in this survey
OSC 133 is the open, standardized mechanism behind every "blocks"-style UX (Warp, WezTerm zones, VS Code command navigation, kitty prompt-jumping). It is the difference between a scrolling byte buffer and a structured stream of `{prompt, command, output, exit_code}` records. For Codinal, adopting it means:

1. **Blocks/Command navigation for free** — the explicit Cursor-parity feature.
2. **Exit-code awareness** without parsing prompt text — feed accurate success/failure to the agent.
3. **Per-command AI actions** (explain this output, debug this failure) — exactly Warp's value prop.
4. **Compatibility** with shells the user already instruments (starship emits OSC 133; user's existing zshrc may already produce it).

### Concrete implementation path for Codinal
**Producer side (Rust PTY spawn):** inject shell-integration into the spawned zsh. Set `ZDOTDIR` to a Codinal-controlled dir, or prepend to the user's rc via `precmd`/`preexec` hooks:
```zsh
# emit before each prompt
precmd() { printf '\e]133;A\e\\' }
# emit after the user types Enter, before output
preexec() { printf '\e]133;C\e\\' }
# finalize the prompt with end-of-prompt marker (B) and end-of-output (D with exit code)
```
(VS Code's and iTerm2's shell-integration scripts are the production references; both are open and small.)

Codinal currently does `cmd.env_clear()` (`pty.rs:240`), which makes clean injection *easier* — Codinal owns the env and can set `ZDOTDIR`/`PROMPT_COMMAND` without fighting the user's rc. The trade-off: Codinal deliberately keeps a *trusted* terminal (real HOME, real PATH) — so injection should be **additive** (prepend markers) not **replace** the user's shell config.

**Consumer side (JS/xterm.js):** register an OSC handler on the xterm.js parser (`term.parser.registerOscHandler(133, ...)`) to record block boundaries into a JS-side array of `{startOffset, command, exitCode}`. xterm.js exposes the buffer + markers API needed to render blocks as discrete UI regions. (Warp's closed engine does this in Rust; Codinal can do it in JS since xterm.js owns the buffer.)

**Security note (from [the VS Code shell-integration RCE writeup](https://blog.solidsnail.com/posts/vscode-shell-integ-rce)):** treat OSC 133 data as untrusted input — a malicious command can emit fake markers. Never execute "commands" inferred from markers without user confirmation; use them only for UI segmentation and agent *context*, not as an execution trust boundary.

---

## 9. Concrete recommendations for Codinal (prioritized)

### Tier 1 — Must-copy (high ROI, low risk, fits existing architecture)
1. **Adopt OSC 133 shell integration** (§8). Inject markers in the spawned zsh (`pty.rs`); consume them in `startup.js` via `term.parser.registerOscHandler`. This unblocks blocks, command nav, and exit-code-aware agent context. **Single highest-value change.**
2. **Port Alacritty's PTY robustness patterns to `pty.rs`** (§2):
   - Replace the `Drop` spin-wait (`pty.rs:98-114`) with a `SIGCHLD` signal-hook socket + `try_wait`.
   - Add bounded backpressure (`READ_BUFFER_SIZE` + `MAX_LOCKED_READ`) so `cat huge.log` doesn't flood xterm.js.
   - Dispatch resize through a channel so it can't race the reader.
3. **Copy Wave's `termwrap.ts` xterm.js upgrades** (§4):
   - `@xterm/addon-webgl` + `onContextLoss` → DOM fallback.
   - No-op-guarded debounced resize (skip when cols/rows unchanged).
   - `SerializeAddon` scrollback persistence across session/workspace switches and app restarts.
   - Copy-on-select + search (`@xterm/addon-search`).
   - CSI 2026 synchronized-output handling.
4. **Two-step, typed PTY spawn** (Zed §3): expose a `pending | ok | failed` state instead of a `Result<string>` so the UI can render clean transitions instead of red error text.

### Tier 2 — Should-copy (architectural, medium effort)
5. **Promote the terminal to a first-class pane/block** (Zed §3 + Wave §4): make terminal, editor, and chat interchangeable view types in a registry. This is the structural prerequisite for Cursor-parity layouts.
6. **MCP in the terminal pane** (Tabby §7, Zed `context_server`/`mcp` crates, Warp `mcp`): plan an MCP surface so terminal-resident tools can talk to the agent.
7. **Backend-neutral terminal domain types in Rust** (Zed §3): model cells/modes/points/ranges in Rust even though xterm.js holds the buffer, so future swaps (e.g. to a Rust VT or Rio's wgpu canvas) don't require a rewrite.

### Tier 3 — Nice-to-have / later
8. **GPU/WebGPU rendering** (Ghostty §1, Rio §7): only if xterm.js DOM/canvas rendering becomes a measured bottleneck. WebglAddon (Tier 1) likely suffices.
9. **Detect (don't ship) Oh My Zsh** (§6): alias expansion + prompt-state enrichment for agent context.
10. **Collaboration / shared panes** (Zed §3 `sum_tree`/`collab`): defer until multi-user is on the roadmap.

### Pitfalls to avoid (sourced from the above)
- **Don't** treat `warpdotdev/warp` as open source — it is issues-only; the block engine is closed (§5).
- **Don't** write a custom VT parser in Rust while xterm.js owns the buffer — Ghostty/Alacritty's parsers took years and don't apply when the WebView does parsing (§1, §2).
- **Don't** bundle Oh My Zsh; it fights Codinal's `env_clear` trusted-terminal model (§6).
- **Don't** trust OSC 133 markers as an execution boundary — they're UI-segmentation only (§8).
- **Don't** spawn a separate backend binary a la Wave's Go `wavesrv` — Codinal's Tauri-direct event bridge is simpler and appropriate at this scale (§4).
- **Don't** block `Drop` on `waitpid` (current `pty.rs:98-114`) — use `SIGCHLD` + `try_wait` (§2).

---

## Primary sources consulted

- Ghostty — https://github.com/ghostty-org/ghostty (README, `src/Terminal.zig`)
- Alacritty — https://github.com/alacritty/alacritty ; `alacritty_terminal/src/tty/unix.rs`, `alacritty_terminal/src/event_loop.rs`
- Zed — https://github.com/zed-industries/zed ; `crates/terminal_view` (README), `crates/` directory
- Wave Terminal — https://github.com/wavetermdev/waveterm ; `frontend/app/view/term/termwrap.ts`, `emain/emain-wavesrv.ts`, `frontend/app/block/block.tsx`
- Warp — https://github.com/warpdotdev/warp (LICENSE + README confirm issues-only/closed-source); visible `crates/*` and `app/src/*` listings
- Oh My Zsh — https://github.com/ohmyzsh/ohmyzsh (README)
- Tabby — https://github.com/Eugeny/tabby (README)
- Rio — https://github.com/raphamorim/rio (README)
- OSC 133 spec — https://gitlab.freedesktop.org/Per_Bothner/specifications/-/blob/master/proposals/semantic-prompts.md
- OSC 133 adoption — https://iterm2.com/documentation-escape-codes.html ; https://sw.kovidgoyal.net/kitty/shell-integration/ ; https://wezterm.org/shell-integration.html ; https://code.visualstudio.com/docs/terminal/shell-integration ; https://github.com/alacritty/alacritty/issues/5850 ; https://github.com/warpdotdev/warp/issues/6718
- VS Code shell-integration security — https://blog.solidsnail.com/posts/vscode-shell-integ-rce
