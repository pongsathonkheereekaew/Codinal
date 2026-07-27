# Phase 38 evidence — extension governance (package manifest + signed provenance)

Date: 2026-07-27
P1 roadmap item: "Manage skills, plugins, hooks, MCP servers, and agent definitions with signed provenance, versioning, requested permissions, enable/disable, update, and removal."

## What shipped

- **ExtensionPackage model** (`runtime/extensions/models.py`): id, kind (skill|plugin|hook|mcp|agent), name, version, publisher, requested_permissions, enabled, manifest_hash. `validate_manifest` enforces shape.
- **ExtensionRegistry** (`runtime/extensions/registry.py`): SQLite (`extensions.db`, schema v1). `register` validates + hashes the manifest; `verify` re-computes and compares to detect tampering. `list`/`get`/`set_enabled`/`remove`.
- **Routes**: `GET /v1/extensions`, `POST /v1/extensions` (register), `PATCH /v1/extensions/{id}` (enable/disable), `DELETE /v1/extensions/{id}`, `GET /v1/extensions/{id}/verify`. All audited.
- **Wiring**: `ExtensionRegistry` constructed in `build_services`, threaded through `compose_runtime` → `RuntimeServices.extensions`.

## Verification (fresh, 2026-07-27)

```
$ ./.venv/bin/pytest -q tests/extensions/
.......                                                                   [100%]
7 passed
```

```
$ CI= ./.venv/bin/pytest -q
854 passed, 1 skipped, 53 warnings in 81.80s
```

`verify.sh`: PASS.

## Non-goals (deferred)

- Full marketplace (download/update from remote registry).
- Code-level plugin loading.
- Per-skill signed manifests (skills are markdown; the manifest layer wraps them).
