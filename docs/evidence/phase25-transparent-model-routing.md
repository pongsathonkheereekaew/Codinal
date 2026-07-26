# Phase 25 evidence — transparent capability-aware model routing

Evidence date: 2026-07-26

## Product result

Codinal now supports persisted Manual, Quality, Balanced, and Economy routing
profiles without hiding the concrete provider or model. Every turn resolves to
an exact provider, model, relative cost class, configured state, required
capabilities, explicit degradations, and a human-readable reason.

Manual preserves the exact selected model, including custom and local models.
Automatic profiles consider only configured allowlisted candidates and fail
closed when none is available. Native attachment support outranks profile cost
preference, so a PDF turn selects a configured native-PDF model before a
higher-ranked model that would require local extraction.

The desktop composer exposes the profile selector, exact resolution, fallback
warnings, model capabilities, credential state, and automatic-routing
eligibility. The selected concrete model remains synchronized with the
resolution.

## Durability, provenance, and failure behavior

- The global routing profile is persisted. A turn that omits routing fields
  still uses the persisted profile.
- The server reserves and overwrites `source.routing`; authenticated clients
  cannot forge a durable routing badge.
- The concrete model and a server-owned routing-decision audit notice are
  persisted atomically before a turn is accepted. Failed persistence rolls the
  live model, provider switch notice, and routing audit back together.
- Context resolution and automatic checkpoint creation happen before model
  rebinding. Rejected turns do not silently change the session model.
- Image and PDF requirements remain active on later text-only turns when those
  attachments exist in durable history.
- Routing-profile persistence rolls back its in-memory value when durable
  storage fails.
- Cold routing context loads the durable session once, scans the existing
  transcript without another list copy, and runs off the async control-plane
  thread. A regression blocks that load while confirming the health endpoint
  remains responsive.

## Verification

- `./verify.sh`: PASS — 676 Python tests; all Rust, desktop security, shell,
  layout, policy-invariant, and host-install gates passed.
- Phase-focused suite: PASS — 166 tests across routing, sessions, turn
  coordination, settings, authenticated routes, production runtime, and
  desktop UI contracts.
- Cold-routing regressions: PASS — a 10,000-message transcript loads once, and
  the control-plane health route remains responsive during a blocked routing
  load.
- Spec review: CLEAN.
- Standards/security review: CLEAN.
- `git diff --check HEAD`: PASS.

## Real product surface

The production desktop HTML and JavaScript ran against the authenticated
control plane and an isolated Git workspace. Selecting Economy resolved and
executed with:

`economy → gemini · gemini:gemini-2.5-flash · economy`

The exact resolution appeared beneath the user message, the concrete model
selector synchronized to `gemini:gemini-2.5-flash`, and the same routing badge
remained after a full page reload. At a 1440 × 1000 viewport, the composer
bottom remained exactly inside the 1,000-pixel viewport.

## Packaged artifact

- App:
  `desktop/src-tauri/target/release/bundle/macos/Codinal.app`
- Phase artifact:
  `desktop/src-tauri/target/release/bundle/Codinal-0.1.0-phase25-macos-arm64.zip`
- Size: 91,008,981 bytes
- SHA-256:
  `fde0e539000040ac582d037d54006ec3eca89ca4167132019521e1a8712c4d3c`
- ZIP integrity: PASS
- Packaged-app smoke: PASS
- `codesign --verify --deep --strict`: PASS
- Signing authority:
  `Developer ID Application: Pongsathon Kheereekaew (BL28MB2PM9)`

This local artifact is signed but is not notarized, stapled, tagged, pushed, or
published.
