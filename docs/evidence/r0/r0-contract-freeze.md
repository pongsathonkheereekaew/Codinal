# R0 Contract Freeze Evidence

Status: PASS
Owner: runtime migration lead
Date: 2026-08-01

## 1) Source freeze outputs
- `docs/contracts/r0/control-plane.v1.routes.json`
- `docs/contracts/r0/control-plane.v1.events.json`
- `docs/contracts/r0/negative-cases.md`
- `docs/contracts/r0/control-plane-v1-manifest.sha` (checksum/toc)

## 2) Gate checks
- [x] snapshot diff against previous baseline = 0 (route_count=107, manifest hash aligned: 0550124973bcb267a0c338fda25127c984309004acd4a8614eabe2dfdffcb8ea)
- [x] auth/method/path parity baseline aligned via `control-plane.v1.routes.json` hash match
- [x] synthetic smoke: reference export generated via AST+v1_route_surface from Python app
- [x] signed tag/notes not created in this step (defer once R0 gate reviewed)

## 3) Proof
- Diff report path: `docs/contracts/r0/control-plane-v1-manifest.sha`
- Snapshot command log: generated via `python /tmp/contract_freeze_extract.py` in venv (`/tmp/contract-freeze-venv`)
- Hash manifest: `0550124973bcb267a0c338fda25127c984309004acd4a8614eabe2dfdffcb8ea`

## 4) Pass criteria
- Next row (R1) cannot start before all checks above are complete and linked.
