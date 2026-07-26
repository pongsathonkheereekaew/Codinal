# Phase 20 evidence — durable editable plans

Evidence date: 2026-07-26

## Product result

Codinal now persists structured plans with editable summaries, task
descriptions, and per-task verification criteria. A user can select a subset of
tasks, approve that selection, continue the same provider conversation exactly
once, and inspect the approved artifact after reload.

The authenticated control plane exposes saved plan revisions through
`GET /v1/sessions/{session_id}/plans`. SQLite schema version 7 stores draft,
approved, and revision-requested artifacts atomically with the interaction
decision.

## Verification

- `./verify.sh`: PASS — 572 Python tests; all Rust, Clippy, formatting,
  documentation, and policy-invariant checks passed.
- Focused plan suite: 54 tests passed.
- Spec review: CLEAN, with legacy v6 recovery, fingerprints, exact-once
  continuation, and artifact evidence covered.
- Standards review: CLEAN; typed plan models centralize validation and the
  interaction broker remains orchestration.
- Restart E2E: a legacy v6 pending plan migrated to v7, rejected the generated
  placeholder verification, accepted a concrete criterion, resumed the
  provider once, and persisted one approved artifact.

## Real product surface

The production desktop HTML and JavaScript ran against the authenticated
control plane and a deterministic provider. The test edited the summary and
verification criterion, deselected one task, approved the remaining task, and
continued the same conversation. Reload preserved revision 2, the approved
status, and the selected/unselected task state.

Observed persisted result:

```text
approved|2|Implement only|["implement"]
```

## Packaged artifact

- App:
  `desktop/src-tauri/target/release/bundle/macos/Codinal.app`
- Phase artifact:
  `desktop/src-tauri/target/release/bundle/Codinal-0.1.0-phase20-macos-arm64.zip`
- Size: 87 MB
- SHA-256:
  `bdfd337d8e5f7d259a3480b5557f780bf93ebc95969339a6fccbfac91a9fc6d4`
- Packaged-app smoke: PASS
- `codesign --verify --deep --strict`: PASS
- Signing authority:
  `Developer ID Application: Pongsathon Kheereekaew (BL28MB2PM9)`

This local artifact is signed but is not notarized, stapled, tagged, pushed, or
published.
