# Phase 27 evidence — audited MCP lifecycle + restart coverage

Date: 2026-07-27
Closes roadmap Immediate frontier #2: "Complete the audited MCP lifecycle UI
and restart coverage."

## What shipped

- **Reusable tamper-evident audit ledger** (`runtime/audit/ledger.py`): hash-chained
  append-only SQLite ledger (`audit.db`, schema v1). Every event chains on the
  previous row's SHA-256; `verify_chain()` recomputes the chain and detects any
  tampered row. Same migration/backup/corruption-recovery primitives as
  `WorkerStore`/`GoalStore`.
- **Durable MCP connections** (`runtime/mcp/store.py`, `MCPStore`): MCP server
  connections now persist in `mcp.db` (schema v1). Connections survive restart;
  per-server `enabled` flag controls whether tools are registered.
- **MCPService lifecycle**: `connect`/`disconnect` now write the store + emit
  audit events; new `set_enabled` toggles a server's tools without dropping the
  durable row; new `async recover()` reconnects every durable+enabled server
  into its session engine on startup (called from the FastAPI lifespan).
- **Control-plane routes**: `PATCH /v1/sessions/{id}/mcp/servers/{name}` toggles
  enable/disable; `GET .../mcp/servers` now returns an `enabled` field per row
  (and surfaces durable-but-disabled servers so the UI can re-enable them).
- **Desktop UI**: per-server enable/disable checkbox next to Disconnect;
  `toggleMcpEnabled` calls the PATCH route. Reuses existing `mcp-server-list`.

## Verification (fresh, 2026-07-27)

```
$ ./.venv/bin/pytest -q tests/audit/ tests/mcp/ tests/control_plane/test_session_routes.py -k "mcp or ledger"
.....................................                                    [100%]
37 passed, 35 deselected in 0.53s
```

Restart E2E (`@skip_on_ci` — needs the real production runtime):

```
$ CI= ./.venv/bin/pytest -q tests/control_plane/test_production_runtime.py::test_mcp_connections_survive_restart_and_reconnect
.                                                                        [100%]
1 passed in 0.60s
```

The E2E proves: after connecting `docs` (enabled) + `cache` (disabled) and
rebuilding services from the same `data_dir`, the lifespan reconnects only
`docs` (its `mcp__docs__search` tool is registered) and leaves `cache`
dormant (`enabled=False`, no tools). The audit ledger chain survived the
restart intact (`verify_chain() is True`) and recorded connect / disable /
recover events.

Full local suite:

```
$ CI= ./.venv/bin/pytest -q
716 passed, 53 warnings in 61.49s
```

## Coverage map

| Layer | File | Tests |
|---|---|---|
| Audit ledger | `runtime/audit/ledger.py` | `tests/audit/test_ledger.py` (chain, tamper detection, restart, corrupt-DB recovery) |
| MCP store | `runtime/mcp/store.py` | `tests/mcp/test_mcp_store.py` (round-trip, enabled toggle, upsert replace, delete, corrupt-DB recovery) |
| MCP service | `runtime/mcp/service.py` | `tests/mcp/test_mcp_service.py` (store+audit hooks, set_enabled, recover, recover_failed) |
| Routes | `runtime/control_plane/app.py` | `tests/control_plane/test_session_routes.py` (PATCH 200/404/400/503, list `enabled`) |
| Restart E2E | `tests/control_plane/test_production_runtime.py` | `test_mcp_connections_survive_restart_and_reconnect` |
| Desktop UI | `desktop/ui/startup.js`, `index.html` | `tests/desktop_ui/test_ui_contract.py` (toggle, `mcp-server-toggle`, PATCH wiring) |

## Non-goals (deferred)

- Per-tool enable/disable (per-server only this phase).
- Tamper-evident audit for workers/goals/routing (the ledger is reusable;
  wiring those domains is later phases).
- MCP governance: signed provenance, versioning, update/removal (roadmap P1
  Ecosystem).
