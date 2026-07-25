# runtime/

Codinal Python sidecar (OpenWorker-derived mechanics).

- `composition.py` — runtime composition root; injects policy, deny-by-default
  approval, roots, event sink, and live settings into every engine build
- `sessions/` — Phase 1.2 session lifecycle boundary (injected store/engine,
  roots, artifacts)
- `events/` — Phase 1.2 global/per-session async fan-out plus the Phase 2
  provider-neutral turn event contract
- `settings/` — Phase 1.2 atomic non-secret preferences; provider credentials
  remain behind the Phase 1.4 Keychain port
- `control_plane/` — Phase 1.3 FastAPI sidecar; loopback-only HTTP and
  WebSocket endpoints protected by one process-scoped bearer token; bounded
  session turn/interrupt routes delegate only to the turn coordinator
- `secrets/` — Phase 1.4 in-memory provider credential port; persistent
  storage is owned by the native Rust Keychain adapter
- `oauth/` — Phase 1.5 bounded, expiring, one-time OAuth state registry and
  provider-handler coordinator; browser callbacks carry authorization codes,
  never provider access or refresh tokens
- `turn_engine/` — Phase 2 policy-bound agent loop vendored from
  `coworker/engine.py`; all model-requested tools require a manifest-bound
  registry entry and a `PermissionEngine` decision before execution.
  Provider/tool exceptions are value-sanitized, and PDF fallback runs locally
  without mutating canonical conversation history
- `turns/` — one-active-turn-per-session coordinator; bridges typed engine
  events to the authenticated session WebSocket and persists in `finally`
- `providers/` — Phase 2 provider contract and conformance bridge; normalized
  assistant tool calls are revalidated by the runtime policy parser before use;
  vendored OpenAI, Anthropic, and Gemini adapters resolve keys only from the
  native-backed memory store; the fail-closed router supports those providers
  plus loopback-only Ollama and invalidates cached SDK clients on key changes
- `mcp/` — Phase 2 official-SDK transport adapted from OpenWorker; connections
  require an explicit approved host action, remote HTTP is HTTPS or loopback,
  stdio receives only a minimal safe environment, and registered tools are
  always manifest-declared `external` actions requiring approval
- `tools/` — manifest-bound implementation registry; requires explicit strict
  schemas and refuses undeclared tools; production currently exposes bounded
  root-scoped `read_file`, `list_files`, and literal `grep` without spawning
  subprocesses (write/shell tools wait for the Phase 3 sandbox)
- `conformance/` — Phase 1.6 provider-neutral suite runner; executes
  harness-owned cases through injected adapters and reports Tier 1/Tier 2/
  incompatible without exposing raw provider responses
- `storage/` — Phase 2 transactional SQLite conversation store adapted from
  OpenWorker; metadata and ordered messages commit together, session ids are
  revalidated at the storage boundary, and files are owner-only

Bridge to host: loopback HTTP+WS + mandatory per-session bearer token (see ADR D7). Policy enforced via `PermissionEngine` collaborator (harness-controlled) — runtime must not bypass.

The Tauri host starts the sidecar with `python -m runtime.control_plane`,
passes `CODINAL_SESSION_TOKEN`, `CODINAL_PORT`, and `CODINAL_DATA_DIR` in the
child environment, and never places the token in command-line arguments. The
sidecar consumes and deletes the token environment entry during startup so
later tool subprocesses cannot inherit it.

Standalone startup now composes the transactional conversation store,
provider router, policy-bound TurnEngine, live-root read registry, session
coordinator, and authenticated HTTP/WebSocket surfaces. A new public session
is created only when its first turn supplies an absolute existing workspace.

Native `codinal://oauth/callback` links are strictly parsed by the Tauri host
and relayed to the sidecar with both the control-plane bearer and the
native-only sync token. The sidecar atomically consumes the matching OAuth
state before invoking an injected provider handler.

See `docs/plan/openworker-boundary-map.md` for the verified vendor/extract/rewrite split per OpenWorker module.
