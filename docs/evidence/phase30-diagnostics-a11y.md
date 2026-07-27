# Phase 30 evidence — diagnostics, health UI, and accessibility pass

Date: 2026-07-27
Two P0 roadmap reliability items:
- "Add structured redacted diagnostics, local support bundle, crash reports with explicit consent, health/status UI, and actionable provider/tool errors."
- "Make all primary workflows keyboard- and screen-reader-operable with visible focus, contrast, reduced-motion, and accessible status/approval announcements."

## What shipped

### Runtime
- `GET /v1/status` (auth-required) — structured, secret-safe health: version, uptime, components (audit chain verified/tampered, providers configured-flag-only, session count).
- `GET /v1/audit?domain=&limit=` (auth-required) — `{events, chain_verified}` from the Phase 27 ledger; limit bounded 1–500.
- `runtime/control_plane/diagnostics.py` `build_support_bundle` — assembles version/uptime/health + recent audit events (already redacted by the ledger). Never includes keys, message bodies, tool args/results, or file contents. Copy action = explicit consent (no telemetry, no auto-upload).
- `ControlPlaneServices` Protocol extended with `audit` field.

### Desktop UI
- **Diagnostics section** in Settings: runtime health line, audit-chain status (verified/tampered with visual flag), recent audit events list, "Copy support bundle" button → assembles redacted JSON to clipboard with a "secrets redacted" toast.
- **Runtime-status chip** is now `role="status"` + `aria-live="polite"` + dynamic `aria-label`; announcements on online/busy/offline transitions; `is-offline` state added.

### Accessibility pass
- **Skip-link** "Skip to conversation" as the first focusable element.
- **All 6 dialogs** now `aria-modal="true"` + `aria-labelledby="<dialog>-title"`; each title element has an `id`.
- **Labels on icon-only / unlabeled controls**: MCP server toggle checkbox (`aria-label="Enable MCP server <name>"`), provider API-key input + save button (`aria-label="<provider> API key"` / "Save/Update <provider> key").
- **Region roles**: `#diff-view` and `#terminal-output` now `role="log"` + `aria-label`; terminal switched off raw `aria-live` (was spammy) in favor of an explicit label.
- **Contrast**: `--faint` bumped from `#95959d` (~3.0:1, fails AA) to `#6e6e76` (~5.0:1, passes AA).
- **Toast**: duration 4200ms → 6000ms; hover-to-pause for SR/pointer users.
- (Existing floor preserved: global visible-focus rule, `prefers-reduced-motion`, `prefers-color-scheme` dark, `.sr-only`, native `<dialog>` + focus-on-open, `aria-live` toast/startup regions.)

## Verification (fresh, 2026-07-27)

```
$ ./.venv/bin/pytest -q tests/control_plane/test_status_route.py tests/control_plane/test_diagnostics.py
...........                                                               [100%]
11 passed in 0.40s
```

```
$ ./.venv/bin/pytest -q tests/desktop_ui/test_ui_contract.py
.....                                                                     [100%]
5 passed in 0.07s
```

Full local suite:

```
$ CI= ./.venv/bin/pytest -q
770 passed, 53 warnings in 69.26s
```

`verify.sh`: PASS.

## Secret-safety proof

`test_bundle_excludes_provider_keys_and_message_bodies` registers a real key (`sk-bundle-secret-...`), builds a bundle, and asserts the key string never appears in the JSON dump — and that the bundle schema has no `messages` / `tool_calls` fields. `/v1/status` test likewise asserts no key leaks.

## a11y checklist covered

- [x] Skip-link present and first-focusable.
- [x] All dialogs `aria-modal` + `aria-labelledby`.
- [x] Icon-only controls labelled (MCP toggle, provider input/button).
- [x] Log regions labelled (diff, terminal).
- [x] Status chip is an announced live region.
- [x] `--faint` meets WCAG AA 4.5:1.
- [x] Toast duration extended + pausable.
- [x] Visible focus, reduced-motion, dark mode, `.sr-only` (pre-existing, preserved).

## Non-goals (deferred)

- Automated crash reporting with telemetry (support bundle is local + on-demand; telemetry is a separate consent flow).
- Perf budgets / cold-start benchmarks (separate phase).
- A formal third-party a11y audit artifact (ships with release; this phase is the implementation pass).
- Crash-recovery completeness (separate phase).
