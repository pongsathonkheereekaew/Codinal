# Phase 23 evidence — bounded project search

Evidence date: 2026-07-26

## Product result

Codinal now provides authenticated, multi-root text and symbol search in the
desktop project panel. Results show root, path, line, preview, symbol kind, and
can be added directly to the exact project context sent with the next turn.

Search is latest-wins per session and globally concurrency-bounded. Every
request has a two-second end-to-end deadline including semaphore wait, plus
limits of 5,000 files, 32 MiB total input, 1 MiB per file, 4 MiB Git stdout,
100 results, and 16 roots.

## Containment and resource safety

- Git enumeration disables filesystem monitors, hooks, untracked cache, global
  config, prompts, and optional locks.
- Files are opened relative to the bound root descriptor with `O_NOFOLLOW` and
  `O_NONBLOCK`; root device/inode identity is revalidated.
- Ignore files are opened through the same descriptor path, must be regular
  files, and are read at most 64 KiB. Oversized, malformed, interrupted, or
  incomplete ignore reads fail closed.
- Symlinks, FIFOs, invalid UTF-8, control-byte binaries, oversized files, root
  escapes, stale queries, expired deadlines, and unbounded Git records are
  skipped or truncated without crossing the request budget.
- Symbol parsing distinguishes Go functions from receiver methods and rejects
  call expressions such as `return doThing()`, `await fetch()`, and
  `new Service()`.

## Verification

- `./verify.sh`: PASS — 630 Python tests; all Rust, desktop security, shell,
  layout, policy-invariant, and host-install gates passed.
- Phase-focused suite: PASS — 70 tests covering search, coordination,
  authenticated routes, production restart, and desktop UI contracts.
- Spec review: CLEAN.
- Standards review: CLEAN after deadline, FIFO, ignore-containment,
  cancellation, Git-output, relevance, and symbol-declaration fixes.
- `git diff --cached --check`: PASS.

## Real product surface

The production desktop HTML and JavaScript ran against the authenticated
control plane and an isolated Git worktree. Symbol search for
`SessionService` returned one result across 985 files in 613–696 ms:

`harness-flow/runtime/sessions/service.py:186 · class SessionService`

Rapidly replacing `Session` with `SessionService` retained only the latest
result. Selecting the result added the file to the composer as project context
with its SHA-256 fingerprint.

## Packaged artifact

- App:
  `desktop/src-tauri/target/release/bundle/macos/Codinal.app`
- Phase artifact:
  `desktop/src-tauri/target/release/bundle/Codinal-0.1.0-phase23-macos-arm64.zip`
- Size: 87 MB
- SHA-256:
  `a7ab09db78ff958c98828aece100c8f3502033e1354bdde377cd1674f2530a13`
- ZIP integrity: PASS
- Packaged-app smoke: PASS
- `codesign --verify --deep --strict`: PASS
- Signing authority:
  `Developer ID Application: Pongsathon Kheereekaew (BL28MB2PM9)`

This local artifact is signed but is not notarized, stapled, tagged, pushed, or
published.
