# runtime/

Codinal Python sidecar (OpenWorker-derived mechanics).

- `composition.py` — runtime composition root; injects policy, deny-by-default
  approval, roots, event sink, and live settings into every engine build
- `sessions/` — Phase 1.2 session lifecycle boundary (injected store/engine,
  roots, artifacts)
- `events/` — Phase 1.2 global/per-session async event fan-out
- `settings/` — Phase 1.2 atomic non-secret preferences; provider credentials
  remain behind the Phase 1.4 Keychain port
- `control_plane/` — Phase 1.3 FastAPI sidecar; loopback-only HTTP and
  WebSocket endpoints protected by one process-scoped bearer token
- `secrets/` — Phase 1.4 in-memory provider credential port; persistent
  storage is owned by the native Rust Keychain adapter
- `oauth/` — Phase 1.5 bounded, expiring, one-time OAuth state registry and
  provider-handler coordinator; browser callbacks carry authorization codes,
  never provider access or refresh tokens
- `turn_engine/` — vendored from `coworker/engine.py` (TurnEngine, zero server deps)
- `providers/` — Phase 2 provider contract and conformance bridge; normalized
  assistant tool calls are revalidated by the runtime policy parser before use;
  vendored OpenAI, Anthropic, and Gemini adapters resolve keys only from the
  native-backed memory store; the fail-closed router supports those providers
  plus loopback-only Ollama and invalidates cached SDK clients on key changes
- `mcp/` — vendored transport
- `tools/` — tool implementations (manifest lives in `harness/policy`)
- `conformance/` — Phase 1.6 provider-neutral suite runner; executes
  harness-owned cases through injected adapters and reports Tier 1/Tier 2/
  incompatible without exposing raw provider responses
- `storage/` — vendored conversation/event mechanics

Bridge to host: loopback HTTP+WS + mandatory per-session bearer token (see ADR D7). Policy enforced via `PermissionEngine` collaborator (harness-controlled) — runtime must not bypass.

The Tauri host starts the sidecar with `python -m runtime.control_plane`,
passes `CODINAL_SESSION_TOKEN`, `CODINAL_PORT`, and `CODINAL_DATA_DIR` in the
child environment, and never places the token in command-line arguments. The
sidecar consumes and deletes the token environment entry during startup so
later tool subprocesses cannot inherit it.

Native `codinal://oauth/callback` links are strictly parsed by the Tauri host
and relayed to the sidecar with both the control-plane bearer and the
native-only sync token. The sidecar atomically consumes the matching OAuth
state before invoking an injected provider handler.

See `docs/plan/openworker-boundary-map.md` for the verified vendor/extract/rewrite split per OpenWorker module.
