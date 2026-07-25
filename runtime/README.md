# runtime/

Codinal Python sidecar (OpenWorker-derived mechanics).

- `sessions/` — Phase 1.2 session lifecycle boundary (injected store/engine,
  roots, artifacts)
- `turn_engine/` — vendored from `coworker/engine.py` (TurnEngine, zero server deps)
- `providers/` — vendored `{base,router,anthropic,openai,gemini}_provider.py`
- `mcp/` — vendored transport
- `tools/` — tool implementations (manifest lives in `harness/policy`)
- `conformance/` — suite **runner** (executes provider calls) — cases/spec live in `harness/conformance`
- `storage/` — vendored conversation/event mechanics

Bridge to host: loopback HTTP+WS + mandatory per-session bearer token (see ADR D7). Policy enforced via `PermissionEngine` collaborator (harness-controlled) — runtime must not bypass.

See `docs/plan/openworker-boundary-map.md` for the verified vendor/extract/rewrite split per OpenWorker module.
