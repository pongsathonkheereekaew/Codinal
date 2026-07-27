# Phase 36 evidence — extend tamper-evident audit to all domains + retention + export

Date: 2026-07-27
P1 roadmap item: "Add tamper-evident audit events, export API, retention controls, redaction, and zero-data-retention modes."

## What shipped

- **Retention** (`runtime/audit/ledger.py`): `_MAX_EVENTS` (default 10,000, env `CODINAL_AUDIT_MAX_EVENTS`) prunes the oldest rows on every `record()`. All surviving rows are re-chained from genesis so `verify_chain()` still passes after pruning.
- **Route-layer audit** (`runtime/control_plane/app.py`): `_audit_action` helper instruments 8 consequential routes: worker create/steer/cancel/adopt, session delete, terminal run/interrupt, approval resolve. Each records domain + action + subject + bounded payload (best-effort, no-op if no ledger).
- **Export API**: `GET /v1/audit/export?domain=` returns the full redacted audit log as a downloadable JSON file (`Content-Disposition: attachment; filename=codinal-audit.json`), including `chain_verified` + `total`. No 500-cap.

## Verification (fresh, 2026-07-27)

```
$ ./.venv/bin/pytest -q tests/audit/
........                                                                 [100%]
8 passed
```

```
$ CI= ./.venv/bin/pytest -q
835 passed, 1 skipped, 53 warnings in 87.89s
```

`verify.sh`: PASS.

## Coverage map (audit domains after Phase 36)

| Domain | Actions | Where instrumented |
|---|---|---|
| mcp | connect/disconnect/enable/disable/recover/recover_failed | MCPService._record (Phase 27) |
| git | push | git_push route (Phase 28) |
| worker | create/steer/cancel/adopt | route layer (Phase 36 NEW) |
| session | delete | route layer (Phase 36 NEW) |
| terminal | run/interrupt | route layer (Phase 36 NEW) |
| approval | resolve | route layer (Phase 36 NEW) |

## Non-goals (deferred)

- Zero-data-retention mode (full disable of the ledger — separate config).
- Audit for internal coordinator actions (worker auto-recovery, etc.).
- Audit log streaming (real-time feed).
- Per-domain retention policies (single global cap).
