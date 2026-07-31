# Rust-native runtime cutover

Status: proposed

## Decision

Replace the Python authenticated sidecar and Tauri/WebView shell with a
Rust-native Codinal runtime and GPUI desktop shell. Preserve the local
authenticated HTTP/WebSocket v1 contract, Keychain provider identifiers, and
durable user data through versioned, rollback-safe migrations. Agents, skills,
prompts, policies, routing profiles, and integration manifests remain
declarative and hot-reloadable. The only supported plugin assets in v1 are
bounded declarative agents, skills, MCP manifests, and provider manifests.

Tauri/Python remain a reference implementation until all cutover gates pass.
The approved final state removes both permanently; there is no post-cutover
Tauri fallback.

## Non-negotiable invariants

1. The Rust runtime binds only loopback, authenticates every v1 request, and
   keeps bearer/provider secrets out of URLs, logs, argv, persisted messages,
   and UI view models.
2. Consequential work passes one Rust permission/approval chokepoint; UI state
   never treats an action as complete until the runtime replies and audit state
   reloads.
3. Existing session, artifact, audit, checkpoint, settings, plugin, and MCP
   data are read-compatible before Rust becomes the default writer.
4. Provider IDs and Keychain schema remain stable: `openai`, `anthropic`,
   `gemini`, `ollama`, `omniroute`, and `custom:<slug>`.
5. Declarative assets are schema-validated, bounded, provenance-audited, and
   cannot carry executable hooks, scripts, installers, native libraries, or
   WASM in v1.
6. Exactly one runtime owns writes for a data directory. Shadow validation uses
   immutable snapshots or a separate copy; it never dual-writes production
   SQLite files.

## Target workspace

```text
crates/
  codinal-runtime/       # composition root, v1 control plane, lifecycle
  codinal-storage/       # SQLite compatibility, migrations, backup/recovery
  codinal-policy/        # risk, permissions, approvals, audit contract
  codinal-providers/     # OpenAI/Anthropic/Gemini/Ollama/OpenRouter/LM Studio
  codinal-turns/         # planner, router, context, parser, events, memory
  codinal-tools/         # sandboxed tools, Git, MCP, artifacts, workers
  codinal-integrations/  # declarative agents/skills/plugins and validation
  codinal-cli/           # native CLI over v1/in-process runtime
desktop/gpui/            # production GPUI application and accessibility layer
contracts/v1/            # golden HTTP/WebSocket, SQLite, event, plugin fixtures
```

`codinal-runtime` is the only composition root. GPUI, CLI, VS Code extension,
TUI, and any Web UI speak the same authenticated local v1 boundary. Browser
clients use a native bridge/extension host rather than exposing the loopback
bearer token to page JavaScript. Rust callers may use an in-process adapter
that is contract-tested against v1.

## Migration slices

### R0 — Freeze contracts and fixtures

- Export golden v1 REST/WebSocket fixtures from `runtime/control_plane/app.py`
  and `runtime/events`; version fixtures independently and include
  authorization-negative cases, ordering/reconnect cases, and redaction
  assertions.
- Inventory every SQLite file/table/schema version created by `build_services`
  in `runtime/control_plane/server.py` and generate read-only Rust fixture
  tests from real anonymized databases.
- Add a compatibility matrix for API fields, durable schemas, Keychain
  accounts, provider IDs, plugin manifests, and audit events.

Gate: Python and Rust contract suites consume the same fixtures with no secret
material in fixtures or test output.

### R1 — Rust host and storage foundation

- Replace `SidecarLaunch` with a Rust process/runtime launcher while retaining
  loopback token generation, data-directory validation, Keychain bootstrap,
  graceful shutdown, and exact v1 auth semantics.
- Implement SQLite repositories, forward-only migrations, pre-migration
  backup, integrity checks, crash recovery, and a read-compatibility mode.
- Make the Rust runtime a shadow reader of immutable data copies; Python
  remains the sole writer until R1 parity passes, then Rust becomes the sole
  writer in a transactional cutover.

Gate: migration/recovery/backup corpus passes against existing data snapshots;
Rust rejects malformed, oversized, symlinked, and corrupted inputs exactly as
the approved v1 contract requires.

### R2 — Security, policy, events, and declarative assets

- Port direct Keychain access and one-shot in-memory provider-secret bootstrap
  first; remove the Python stdin bootstrap before Rust provider adapters ship.
- Port policy manifest, risk classification, permission engine, approval
  broker, audit ledger, event hub, secret redaction, and managed policy.
- Port integration/plugin validation and expose hot-reload only after atomic
  validation; preserve `codinal.integration.v1` semantics.
- Add property/adversarial tests for path traversal, duplicate approval,
  restart during pending approval, secret exfiltration, and malformed plugin
  assets.

Gate: every Rust mutation route is unreachable without policy approval; audit
and redaction regression corpus passes.

### R3 — Providers, routing, tools, Git, MCP, and planner

- Implement direct Rust adapters for OpenAI, Anthropic, Gemini, Ollama,
  OpenRouter, and LM Studio, with capability negotiation and fail-closed
  routing.
- Port context construction, parser/stream normalization, planner/turn engine,
  sandbox, terminal boundary, Git/checkpoints, MCP transport, workers, search,
  and memory stores.
- Run recorded provider conformance plus opt-in live conformance without
  retaining request contents outside existing durable policy.

Gate: provider/tool/MCP/Git/checkpoint/worker v1 fixtures and live capability
matrix pass; no Python process starts in Rust dogfood.

### R4 — Production GPUI, client parity, and accessibility

- Promote the GPUI prototype to production panes: session tree/selection,
  conversation streaming, terminal, diff/review, approvals, evidence, Git,
  workers, settings, OAuth relay, and evidence-only preview.
- Implement virtualization and keyboard/screen-reader operation before native
  preview rendering; native preview remains loopback-only with packaged
  allow/deny redirect tests.
- Supply CLI and extension adapters over the same v1 contract; do not embed
  runtime logic in frontends.

Gate: functional replay/live parity, explicit confirmation/reload behavior,
accessibility audit, performance budgets, and packaged GPUI E2E pass.

### R5 — Cutover and retirement

- Run Rust runtime as default only after R0–R4 gates pass; verify ordinary
  upgrade of existing user data and an interrupted-session recovery path.
- Build/sign/notarize/staple the Rust/GPUI package; prove quarantined
  Gatekeeper launch, updater check/install/restart/rollback to a prior Rust
  package, and no bundled
  Python/Tauri/WebView assets.
- Delete Python runtime, Tauri shell/UI, release resources, dependencies, and
  obsolete tests in a dedicated cutover change. Update docs, SBOM, updater,
  and support bundle.

Gate: fresh installation and upgrade E2E pass; binary/resource inspection
proves no Python/Tauri/WebView remains; all release evidence is attached.

## Cutover blockers

- Apple signing/notarization/updater credentials and a real notarized artifact.
- Quantitative GPUI parity budgets (first interactive paint, P95 typing,
  terminal/tree/diff scale, RSS) baselined against the current release.
- Live provider credentials for the conformance matrix.
- No deletion until every R5 gate is evidenced.
