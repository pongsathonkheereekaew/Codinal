# Phase 22 evidence — persistent audited goals

Evidence date: 2026-07-26

## Product result

Codinal now stores persistent goals per session with explicit requirements,
manual continuation, optional elapsed-time and model-agnostic estimated-token
budgets, an append-only evidence ledger, and strict terminal audits.

A completed audit maps every requirement to passing verification evidence from
the same goal. A blocked audit requires the same blocker on the latest three
consecutive continuations. Terminal goals retain the full ledger, audit
summary, and requirement-to-evidence mapping in the desktop UI.

## Durability and accounting

Goal records use a private optimistic-concurrency SQLite store. Continuations
bind to stable turn IDs. Conversation schema v8 atomically persists each
terminal turn receipt—outcome and message boundary—with the idle checkpoint
and messages before the turn is released.

Recovery prefers the exact bound receipt and fails closed when it is absent.
An unstarted continuation may use only a newer receipt whose message count is
strictly beyond its baseline. Missing or failed terminal persistence records
an interrupted attempt with zero estimated tokens and never cites
non-durable messages.

Regression coverage includes:

- restart while a goal continuation is waiting for user input;
- crash after turn completion but before goal evidence finalization;
- crash after the running marker but before turn start;
- missing bound receipt followed by a later ordinary turn;
- terminal conversation persistence failure;
- later-turn outcome/message contamination and UTF-8 byte bounds.

## Verification

- `./verify.sh`: PASS — 612 Python tests; all Rust, desktop security, shell,
  layout, policy-invariant, and host-install gates passed.
- Phase-focused broad suite: PASS — 185 tests covering storage migrations,
  sessions, turns, goals, authenticated routes, production restart E2E, and
  desktop UI contracts.
- Spec review: CLEAN.
- Standards review: CLEAN after durable-receipt and fail-closed race fixes.
- `git diff --cached --check`: PASS.

## Real product surface

The production desktop HTML and JavaScript ran against the authenticated
control plane and deterministic provider. The UI created “Ship verified
release” with a 10,000 estimated-token and 60-minute budget, continued it once,
and displayed `74/10000 est. tokens`.

It added `Release suite · PASS`, enabled the completion audit, completed the
goal, and reloaded. The reloaded terminal card retained the full ledger and
displayed:

`Audit evidence · Release verification passes: Release suite — PASS`

## Packaged artifact

- App:
  `desktop/src-tauri/target/release/bundle/macos/Codinal.app`
- Phase artifact:
  `desktop/src-tauri/target/release/bundle/Codinal-0.1.0-phase22-macos-arm64.zip`
- Size: 87 MB
- SHA-256:
  `8dc9f743a705afd115a3cc37e30c37dc34a8101e9f087fb00024e2588910ba62`
- ZIP integrity: PASS
- Packaged-app smoke: PASS
- `codesign --verify --deep --strict`: PASS
- Signing authority:
  `Developer ID Application: Pongsathon Kheereekaew (BL28MB2PM9)`

This local artifact is signed but is not notarized, stapled, tagged, pushed, or
published.
