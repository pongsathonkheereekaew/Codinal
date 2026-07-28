# OSS LSP Client & Editor Survey — For Codinal Phase 50–52

**Date:** 2026-07-28
**Scope:** Primary-source investigation of how leading open-source editors implement LSP clients, so Codinal (Tauri/Rust shell + vanilla JS UI + Python runtime + CodeMirror 6 editor) can design its own LSP module.
**Method:** Read actual source files (`*.rs`, `*.ts`, `*.go`) from each project's GitHub repo on `main`/`master`, not blog posts.

---

## TL;DR — What Codinal Should Steal

| Concern | Best reference | Why |
|---|---|---|
| **JSON-RPC framing over stdio** | Helix `helix-lsp/src/transport.rs` | Cleanest 3-task (read/write/err) Tokio implementation; ~200 lines; message queueing during `initialize` |
| **Subprocess spawn + kill_on_drop** | Helix `client.rs` (`start`, `kill_on_drop(true)`) | Prevents zombie servers; cleanest lifecycle in the survey |
| **Multi-server registry + routing** | Zed `crates/project/src/lsp_store.rs` (`LanguageServerTree`, `LanguageServerSeed`, `get_or_insert_language_server`) | Mature file→server routing, multi-root, capability gating |
| **Diagnostics → editor decorations** | FurqanSoftware `codemirror-languageserver` `src/plugin.ts` (`processDiagnostics` → `setDiagnostics`) | **Routes diagnostics through CM6's `@codemirror/lint`, NOT custom `Decoration`** — the right pattern for our JS side |
| **Rust↔JS bridge for CM6** | marimo-team fork `languageServerWithClient` + custom `Transport` | One client shared across views; pluggable transport — perfect for a Rust-owned stdio server fronted by a JS shim |
| **LSP for AI context (not editor UI)** | OpenCode `internal/lsp/` | Validates exposing diagnostics to the LLM via a tool; minimal feature surface |

**Single most important architectural decision for Codinal:** Keep the LSP subprocess + JSON-RPC framing in **Rust (Tauri shell)**, and bridge to CM6 via a **custom Transport implementation in JS** (à la FurqanSoftware's `languageServerWithTransport`). Do **not** spawn servers from JS or rely on a WebSocket relay if avoidable.

---

## 1. Zed (`zed-industries/zed`) — Rust

**Stack:** Rust + GPUI (custom GUI). The reference Rust LSP implementation.

### Where the code lives
- `crates/lsp/src/lsp.rs` — protocol-level `LanguageServer` struct, JSON-RPC framing, message I/O
- `crates/lsp/src/input_handler.rs` — base-protocol stream parser
- `crates/project/src/lsp_store.rs` — **multi-server management** (the part most worth studying)
- `crates/project/src/lsp_command.rs` — typed wrappers for each LSP feature (hover, definition, etc.)
- `crates/project/src/lsp_command/` — per-command modules

### LSP client architecture (subprocess + JSON-RPC)
The `LanguageServer` struct (`crates/lsp/src/lsp.rs`) owns the spawned child via piped `stdin`/`stdout`/`stderr`:

- **Spawn:** `LanguageServer::new` / `new_internal` spawns the process with all three streams piped, then spawns async background tasks for each.
- **Outgoing framing:** `handle_outgoing_messages` writes `"Content-Length: <n>\r\n\r\n"` then the JSON bytes to `stdin`. (Confirmed verbatim in source.)
- **Incoming framing:** `handle_incoming_messages` reads `stdout` via the `input_handler`, parsing the base protocol then dispatching responses/notifications.
- **Request lifecycle:** `request()` assigns an ID, registers a response handler, and arms a `request_timeout` so calls can never hang forever. `notify()` is fire-and-forget.
- **Callbacks:** `on_notification(method, callback)` / `on_request(method, callback)` register async handlers per method.
- **Graceful shutdown:** `Drop` automatically calls `shutdown()` with `SERVER_SHUTDOWN_TIMEOUT = 5s`, drains streams, then kills the child. No orphaned processes.
- **Initialize params:** `default_initialize_params` builds the `InitializeParams` declaring client capabilities (codeAction, completion, semanticTokens, etc.).
- **Testing:** `FakeLanguageServer` (behind `test-support` feature) uses in-memory pipes — no subprocess needed for unit tests. **Steal this pattern.**

`LanguageServerBinary` (`{ path, arguments, env }`) is the value type for "a launchable server" — a clean boundary between discovery and execution.

### Multi-server management (`lsp_store.rs`) — the standout
Zed separates concerns into three layers:
- **`LocalLspStore`** — host-side: owns lifecycles, does formatting, routes messages
- **`RemoteLspStore`** — guest-side (collab): pure passthrough RPC
- **`LspStore`** — unified public interface over both

Routing is the clever part:
- **`LanguageServerSeed`** (`{ worktree_id, server_name, toolchain, initial_settings }`) is the dedup key. Same seed → reuse running server (and register an additional project root); new seed → `start_language_server`.
- **`LanguageServerState`** enum: `Starting { init_futures }` | `Running { server: Arc<LanguageServer> }`. Lets callers await readiness without blocking.
- **`get_or_insert_language_server`** is the single entry point.
- **`language_server_ids_for_buffer`** resolves which servers own a given buffer by path + language.
- **`setup_lsp_messages`** registers all `on_notification`/`on_request` callbacks on a fresh server.

### Diagnostics flow (server → buffer)
1. `LocalLspStore` receives `textDocument/publishDiagnostics`.
2. The bound `CachedLspAdapter` runs `process_diagnostics` (language-specific filtering/rewrite — e.g. strip noise from rust-analyzer).
3. `merge_lsp_diagnostics` is called with a `DocumentDiagnosticsUpdate`, converting LSP positions to buffer coordinates via `Unclipped<PointUtf16>`.
4. Diagnostics land in `LocalLspStore.diagnostics`, keyed `WorktreeId → Arc<RelPath> → LanguageServerId`.

**Lesson for Codinal:** decouple raw LSP diagnostic JSON from editor coordinates, and keep a language-specific adapter seam so different servers can be normalized.

### Goto-definition / hover
Implemented via the **`LspCommand` trait** in `crates/project/src/lsp_command.rs`. Every feature is a struct implementing:
```
trait LspCommand {
    type Response;
    type LspRequest;
    type ProtoRequest;
    fn check_capabilities(&self, ...) -> bool;   // capability gate, else default
    fn to_lsp(&self, ...) -> Self::LspRequest;   // build params
    fn response_from_lsp(&self, ...) -> Self::Response;  // decode
    // + to_proto / from_proto / response_to_proto for collab
}
```
Commands implemented: `GetDefinitions`, `GetDeclarations`, `GetTypeDefinitions`, `GetImplementations`, `GetReferences`, `GetHover`, `GetCompletions`, `GetSignatureHelp`, `GetDocumentSymbols`, `PrepareRename`, `PerformRename`, `OnTypeFormatting`, `GetCodeActions`, `GetDocumentHighlights`, `InlayHints`, `GetCodeLens`, `GetDocumentColor`, `GetFoldingRanges`, `GetDocumentLinks`, `LinkedEditingRange`, `SemanticTokensDelta`, `GetDocumentDiagnostics`.

**Lesson:** a single trait that bundles capability-check + encode + decode per command is far cleaner than scattered `match` statements. Consider an analogous Rust trait for Codinal's LSP module.

### Portability to Codinal
**High.** Pure Rust, Apache-2.0. The `crates/lsp` crate is largely self-contained. The `LspCommand` trait pattern and `FakeLanguageServer` test harness translate directly to our Tauri shell.

**Files to study first:** `crates/lsp/src/lsp.rs`, `crates/project/src/lsp_command.rs`, then `lsp_store.rs`.

---

## 2. Helix (`helix-editor/helix`) — Rust

**Stack:** Rust + tokio + crossterm TUI. The most readable LSP code in the survey.

### Where the code lives (`helix-lsp/src/`)
- `client.rs` — `Client` struct + `start` + shutdown logic
- `transport.rs` — **JSON-RPC framing** (the cleanest reference)
- `jsonrpc.rs` — JSON-RPC 2.0 type defs (`Id`, `Call`, `Output`, `ErrorCode`)
- `lib.rs` — `Registry` (multi-server manager) + `file_event::Handler`
- `file_event.rs` — `didChangeWatchedFiles` plumbing
- `file_operations.rs` — `willCreate`/`didCreate` etc.

### Subprocess management (`client.rs`)
`Client` owns a tokio `Child` created with **`kill_on_drop(true)`** — so dropping the client always reaps the process. Three shutdown strategies exist:
- `shutdown_and_exit` — graceful: await shutdown response, then send `exit`
- `force_shutdown` — fire-and-forget shutdown + immediate exit, "Quitting therefore never blocks on a slow server" (their comment). **Good default for a desktop app.**
- `wait_shutdown_flushed` — resolves after `exit` is actually flushed to stdin

`Client::start` (the factory):
1. `helix_stdx::env::which(binary)` resolves the path
2. spawns `tokio::process::Command` with piped stdin/stdout/stderr
3. wraps streams in `BufReader`/`BufWriter`, hands them to `Transport::start`
4. returns `(Client, UnboundedReceiver<ServerMessage>, Arc<Notify>)` — the `Notify` signals when `initialize` completes

State on `Client`:
- `id`, `name`
- `server_tx: UnboundedSender<Payload>` — outbound channel
- atomic ID counter
- `OnceCell<ServerCapabilities>` — set once after handshake (cheap clone, never re-init)
- `OnceLock` for file-operation interests
- `Mutex<Vec<WorkspaceFolder>>` — multi-root support

Key methods: `initialize`, `supports_feature(LanguageServerFeature)`, `try_add_doc` (decides whether an existing client can absorb a new doc; if the server lacks multi-root support it returns `false` so a fresh client is spawned), `did_change_text_document` (maps Helix `ChangeSet` → `TextDocumentContentChangeEvent`, choosing Full vs Incremental by server preference).

### JSON-RPC framing (`transport.rs`) — copy this
`Transport::start` spawns **three tokio tasks**:
- **read (`recv`)** — parses headers, matches responses to pending requests, forwards server→client calls
- **write (`send`)** — `tokio.select!` over: init signal, `client_rx` (outbound), `inject_rx`. Messages are buffered in `pending_messages` **until `initialize` completes**, then flushed in order. This is the correct fix for the classic "client sent a request before initialize returned" bug.
- **err** — line-buffered stderr logging

Framing:
- Outgoing: `send_string_to_server` writes `"Content-Length: {}\r\n\r\n"` + JSON bytes
- Incoming: `recv_server_message` reads lines until `"\r\n"`, splits each at first `": "`, parses `Content-Length` to an int, then `read_exact(n)` for the body

Types: `Payload` = `Request | Notification | Response`; `ServerMessage` = serde-auto-deserialized `Output | Call`.

### Multi-server management (`lib.rs` → `Registry`)
- **`SlotMap<LanguageServerId, Client>`** (`inner`) + **`HashMap<String, Vec<Client>>`** (`inner_by_name`) — dual index by id and by name
- `SelectAll` over each client's `UnboundedReceiverStream` → one aggregated `incoming` stream the editor reads from. Simple and effective.
- **Tombstones:** `stop(name)` drains the client vec but leaves an empty vec, signaling "manually stopped, don't auto-restart". Subtle but important.
- `start_client` resolves workspace via `find_lsp_workspace` (upward search for root markers), checks `required_root_patterns` against the dir, then spawns `Client::start`, all inside an async task that signals `Notify` on completion.
- `file_event::Handler` is owned by the registry; clients are added/removed as servers start/stop, and `MethodCall::RegisterCapability` dynamically attaches watchers.
- `LspProgressMap` tracks `WorkDoneProgress` tokens (Created/Started) for the spinner UI.

### Diagnostics, hover, goto
- `PublishDiagnostics` arrives as a `Notification` variant in the aggregated `incoming` stream; the editor's main loop updates its diagnostic store.
- Hover/definition/references are `client.call::<lsp::request::HoverRequest>(params)` style — generic over the `lsp_types` request trait, each returning a typed result.

### Portability to Codinal
**Highest of all surveyed.** MIT-licensed, pure Rust, tokio-based, and the framing code is tiny and self-contained. `transport.rs` + `client.rs` can be adapted almost verbatim into Codinal's Tauri shell.

**Files to study first:** `helix-lsp/src/transport.rs` (framing), `client.rs` (lifecycle), then `lib.rs` (registry).

---

## 3. CodeMirror 6 LSP — community extensions

Codinal already uses CM6 (Phase 49). There is **no official CM6 LSP package**; the ecosystem is two related repos.

### 3a. FurqanSoftware/codemirror-languageserver (canonical)
**Files (`src/`):** `index.ts`, `plugin.ts`, `jsonrpc.ts`, `initialization.ts`, `completion.ts`, `definition.ts`, `hover.ts`, `formatting.ts`, `highlight.ts`, `mouse.ts`, `pos.ts`, `rename.ts`, `changes.ts`. Latest release 1.13.7 (Mar 2025); ~162 commits.

**Transport:** **Browser WebSocket only by default.** `languageServer({ serverUri: "ws://..." })` instantiates a `WebSocketTransport`. This is the critical constraint: it cannot spawn a local stdio server from the browser. The escape hatch is `languageServerWithTransport(transport)` which accepts any object implementing the `Transport` interface — this is **the integration point for Codinal**.

**JSON-RPC client (`jsonrpc.ts`):** `JSONRPCClient` with a monotonic `nextId` counter, a `Map<id, PendingRequest{resolve, reject, timer}>`, and request/response matching plus per-request timeout. Clean and self-contained.

**The diagnostics pattern (`plugin.ts`) — read this carefully:**
> The plugin **does NOT use CM6's `Decoration` API** for diagnostics. `processDiagnostics` maps LSP severity→CM6 `DiagnosticSeverity`, then calls **`setDiagnostics(this.view.state, diagnostics)`** — routing everything through CM6's native **`@codemirror/lint`** extension.

This is the correct pattern: reuse `@codemirror/lint`'s gutter, underlines, and panel rather than reinventing them. `processNotification` handles `textDocument/publishDiagnostics` and dispatches the update.

**Hover/completion:** the plugin checks `this.client.capabilities!.hoverProvider` etc., calls `textDocumentHover`/`textDocumentCompletion`, and renders results by building **DOM nodes** (`formatContents` parses markdown→HTML; `allowHTMLContent` gates injection). Hover uses `hoverTooltip()`; completion uses `autocompletion()`.

**Sync:** `documentVersion` counter; `update(viewUpdate)` checks `docChanged`; switch on `SynchronizationMethod` (`Full` sends `state.doc.toString()`, `Incremental` uses `changeSetToEvents`).

**Goto-definition:** keymap `jumpToDefinitionKeymap`; `jumpToDefinition`, `formatDocument`, `formatSelection`, `renameSymbol` exported.

Server-specific `InitializationOptions` exported for Pyright, rust-analyzer, TypeScript, ESLint, Clangd, Gopls — handy reference for per-server config.

### 3b. marimo-team/codemirror-languageserver (fork)
Published as `@marimo-team/codemirror-languageserver`. ~267 commits, more active. Adds over FurqanSoftware:
- **Code Actions** (quick fixes, refactors)
- **Rename + goto-definition** (richer)
- **Completion resolve** + markdown code-block completions
- **Richer diagnostics** — severity, tags (`unnecessary`, `deprecated`), clickable related-info
- **`languageServerWithClient`** — share one `LanguageServerClient` across multiple CM6 views (different files, same workspace). **This is the right API shape for a multi-file editor like Codinal.**
- Linting/formatting/tests/CI via GitHub Actions

Transport via `@open-rpc/client-js` over WebSocket.

### Portability to Codinal
**Medium-high.** Both are TypeScript, MIT-ish (check license before vendoring). The core value is the **bridging pattern**, not the transport. Plan:
1. Rust shell owns the stdio LSP subprocess (Helix-style framing).
2. Tauri command exposes request/notify/listen to JS.
3. JS implements the `Transport` interface (or `LanguageServerClient`) on top of Tauri IPC instead of WebSocket.
4. Reuse FurqanSoftware/marimo `plugin.ts` logic: `@codemirror/lint` for diagnostics, `hoverTooltip`/`autocompletion` for the rest.

**Files to study first:** FurqanSoftware `src/plugin.ts` (the bridge) and `src/jsonrpc.ts` (client), then marimo `languageServerWithClient` (shared-client API).

---

## 4. OpenCode (`opencode-ai/opencode`) — Go

**Stack:** Go 1.24, Bubble Tea TUI. **Important caveat: OpenCode's LSP is for AI context, not editor UI.**

### Where the code lives (`internal/lsp/`)
- `client.go` — `Client` struct, subprocess spawn, readiness polling
- `transport.go` — `WriteMessage`/`ReadMessage` (Content-Length framing)
- `protocol.go` — `Message`, `ResponseError`, `NewRequest`, `NewNotification` (uses `json.RawMessage` for params/result)
- `handlers.go` — `HandleDiagnostics`, `HandleWorkspaceConfiguration`, `HandleRegisterCapability`, `HandleApplyEdit`, `HandleServerMessage`
- `language.go` — `DetectLanguageID` (extension → `protocol.LanguageKind`)
- `methods.go`, plus `protocol/`, `util/`, `watcher/` subpackages

### Architecture
- `Client` struct in `client.go`: owns `exec.CommandContext` child with piped stdin/stdout/stderr; `sync.RWMutex` + `atomic.Value` for state; in-memory `diagnostics map[DocumentUri][]Diagnostic`; `OpenFileInfo{Version, URI}` per open file.
- `NewClient` starts the process + background `handleMessages` goroutine that dispatches to three handler maps: response handlers, server-request handlers, notification handlers.
- `InitializeLSPClient` sends `initialize` with capabilities + registers handlers.
- `WaitForServerReady` polls via `pingServerByType` until success or timeout.
- `OpenFile`/`NotifyChange`/`CloseFile` manage textDocument sync.
- `ServerType` (gopls, tsserver, …) and `ServerState` (Starting/Ready/Error) enums.

**Framing (`transport.go`):** exactly the standard pattern — `fmt.Fprintf(w, "Content-Length: %d\r\n\r\n", len(data))` for writes; line-scan until empty line for reads, then `io.ReadFull` of N bytes. Same shape as Helix/Zed/Lapce — this is universal.

### The key insight
From the README (verbatim): **"currently only diagnostics are exposed to the AI assistant."** The `handlers.go` file confirms it: the only data-bearing notification implemented is `textDocument/publishDiagnostics` → `HandleDiagnostics`. Hover, goto, completion, document/workspace symbols are **not** wired to the editor. The AI consumes diagnostics via a `diagnostics` tool to suggest fixes.

### Lesson for Codinal
OpenCode validates a **deliberately minimal LSP surface**: if Phase 50's goal is "AI sees real errors", you can ship `publishDiagnostics` + a Python-side `diagnostics` tool and defer hover/completion UI to later phases. Don't feel obligated to build a full editor-LSP bridge on day one. OpenCode shipped a successful AI coding product with just diagnostics.

**Portability:** Low-medium (Go, not Rust/JS), but the framing and handler-map pattern is language-agnostic and trivial to port.

**Files to study first:** `internal/lsp/handlers.go` (minimal surface), `transport.go` (framing).

---

## 5. Lapce (`lapce/lapce`) — Rust

**Stack:** Rust + Floem UI. Uses a **proxy architecture**: the UI process talks to a separate `lapce-proxy` process that owns plugins and language servers.

### Where the code lives
- `lapce-proxy/src/plugin/lsp.rs` — **the LSP client** (`LspClient`, `LspRpc`, `read_message`, `parse_header`, `get_change_for_sync`, `format_semantic_tokens`)
- `lapce-proxy/src/plugin/mod.rs`, `catalog.rs`, `psp.rs`, `wasi.rs`, `dap.rs` — plugin system
- `lapce-proxy/src/{buffer,dispatch,lib,cli,terminal,watcher}.rs`

### Architecture
- **`LspClient`** owns a single language-server child process + a `PluginServerRpcHandler` + a `PluginHostHandler`. Identified by `(volt_id, plugin_id)` — i.e. servers are managed **per-plugin**, and a plugin can host multiple servers.
- **Multi-server coexistence:** the `PluginHostHandler` answers `method_registered(method)` and `document_supported(language_id/path)`, so requests are routed to the right server.
- **Spawn (`new`/`start`):** if the server URI is `file://`, Lapce `chmod +x` it on Unix. `process()` uses `std::process::Command` with cwd = workspace, args + env passed through, stdin/stdout/stderr piped. **On Windows it sets `creation_flags(0x08000000)` (`CREATE_NO_WINDOW`)** to suppress console popups — a detail Codinal (Tauri on Windows) should copy.
- **JSON-RPC:** two dedicated OS threads (not tokio):
  - **writer thread:** drains an unbounded `io_rx` channel, serializes each `LspRpc`, writes `"Content-Length: {}\r\n\r\n{}"` via `BufWriter` to stdin
  - **reader thread:** `BufReader` + `read_message` (parses headers via `parse_header`, reads N bytes), dispatches via `handle_plugin_server_message`
- **`LspRpc` enum:** `Request | Notification | Response | Error`.
- **Diagnostics:** not rendered in this file; the path is `handle_plugin_server_message` → `PluginServerHandler` → `PluginHostHandler::handle_host_notification` → forwarded over the core RPC to the UI. `format_semantic_tokens` converts LSP semantic tokens into Lapce `LineStyle` for highlighting.
- **Sync:** `get_change_for_sync_kind` picks `None`/`Full`/`Incremental` from server capabilities.
- **Trait `PluginServerHandler`:** implements `document_changes`, formatting, notification routing.

### Portability to Codinal
**Medium.** Apache-2.0 Rust, but the proxy/plugin indirection is heavier than Codinal needs (Lapce supports WASI plugins, DAP, etc.). The two practical takeaways:
1. **`CREATE_NO_WINDOW` on Windows** — copy this.
2. **Per-document `method_registered` / `document_supported` gating** before routing — simpler than Zed's `LanguageServerTree` if you only need a few servers.

The use of **plain OS threads + channels** (instead of tokio) shows the framing loop doesn't require an async runtime — relevant if Codinal wants to keep the LSP module off the tokio runtime.

**Files to study first:** `lapce-proxy/src/plugin/lsp.rs` (`read_message`, `parse_header`, `new`, `start`).

---

## Cross-Cutting Patterns (the universal LSP-client recipe)

Every surveyed project implements essentially the same 6-part recipe. Codinal should too:

1. **Subprocess with piped stdio.** Spawn with stdin/stdout/stderr piped; on Windows set `CREATE_NO_WINDOW` (Lapce); use `kill_on_drop` (Helix) or a `Drop` impl that calls `shutdown` + kill (Zed).
2. **Content-Length framing.** Outgoing: `"Content-Length: N\r\n\r\n" + json_bytes`. Incoming: line-scan headers until blank line, parse `Content-Length`, `read_exact(N)`. Identical in Helix/Zed/Lapce/OpenCode.
3. **Three loops** (read / write / err). Either tokio tasks (Helix, Zed) or OS threads (Lapce) or goroutines (OpenCode). The write loop must **buffer messages until `initialize` completes** (Helix `pending_messages`) to avoid the "request before init" protocol violation.
4. **ID correlation.** Monotonic counter + `Map<id, {resolver, timeout}>`. Every project does this the same way (FurqanSoftware `jsonrpc.ts` is the cleanest TS reference).
5. **Capability gating before every feature call.** Zed's `LspCommand::check_capabilities`, Helix's `supports_feature`, Lapce's `method_registered`. Never assume a server supports hover/completion.
6. **Diagnostics via the editor's native lint API, not custom decorations.** FurqanSoftware routes to `@codemirror/lint`'s `setDiagnostics`. This is the right call for Codinal's JS side.

---

## Recommended Codinal Phase 50–52 Plan

**Phase 50 — Rust LSP core (mirror Helix):**
- New crate/module `lsp` in the Tauri shell.
- `Transport` with 3 tokio tasks, Content-Length framing, `pending_messages` until init.
- `Client` with `kill_on_drop`, `OnceCell<ServerCapabilities>`, request/notify/on_notification.
- `FakeClient` for unit tests (Zed pattern).
- Spawn one server (e.g. pyright or rust-analyzer) end-to-end.

**Phase 51 — JS bridge + diagnostics (mirror FurqanSoftware):**
- Tauri commands: `lsp_request`, `lsp_notify`, `lsp_listen` (event).
- JS `Transport` impl wrapping Tauri IPC.
- `processDiagnostics` → `@codemirror/lint` `setDiagnostics`. No custom `Decoration`.
- Python-side `diagnostics` tool so the AI can read errors (OpenCode pattern).

**Phase 52 — Features (mirror Zed `LspCommand` + marimo plugin):**
- Rust trait per command (capability-check + encode + decode).
- JS: hover via `hoverTooltip`, completion via `autocompletion`, goto-definition keymap.
- Share one client across CM6 views (`languageServerWithClient` shape).

---

## Source Files Referenced (primary)

- Zed: `crates/lsp/src/{lsp.rs, input_handler.rs}`; `crates/project/src/{lsp_store.rs, lsp_command.rs}`
- Helix: `helix-lsp/src/{client.rs, transport.rs, jsonrpc.rs, lib.rs, file_event.rs}`
- FurqanSoftware/codemirror-languageserver: `src/{index.ts, plugin.ts, jsonrpc.ts, completion.ts, definition.ts, hover.ts, formatting.ts, rename.ts}`
- marimo-team/codemirror-languageserver: `languageServerWithClient`, `@marimo-team/codemirror-languageserver`
- OpenCode: `internal/lsp/{client.go, transport.go, protocol.go, handlers.go, language.go}`
- Lapce: `lapce-proxy/src/plugin/{lsp.rs, mod.rs}`
