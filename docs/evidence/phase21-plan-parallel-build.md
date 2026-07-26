# Phase 21 evidence — selective parallel plan builds

Evidence date: 2026-07-26

## Product result

Codinal can now dispatch an approved plan task to two through four model
candidates in isolated Git worktrees, show each candidate's verification
criterion, report, and diff, persist an explicit human selection across
restart, and atomically adopt only the selected commits.

The authenticated control plane persists build, candidate, selection, and
adoption lifecycle state in a private SQLite database. Adoption pins the exact
reviewed commit hashes and uses durable `adopting` states. Safe conflicts roll
back to selection; uncertain post-apply, abort, or rollback-verification
failures remain `adopting` for idempotent recovery.

## Verification

- `./verify.sh`: PASS — 594 Python tests; all Rust, desktop security, shell,
  layout, and policy-invariant gates passed.
- Phase-focused suites: PASS — build coordinator, worker lifecycle, control
  plane, production restart E2E, Git worktree, and desktop UI contracts.
- Spec review: CLEAN.
- Standards review: CLEAN after exercising commit pinning, atomic multi-branch
  adoption, conflict rollback, post-merge metadata failure, abort failure, and
  rollback-probe failure.

## Isolation and restart evidence

The production control-plane E2E launched three comparison candidates. Each
child had empty tool/command grants and no extra roots. The provider never
received the seeded parent secret, and a candidate shell write targeting a
sibling worktree failed without creating the file.

Selection survived a service restart. Generic worker adoption endpoints
rejected both selected and unselected comparison candidates; only plan-build
adoption was accepted. Git tests proved all selected task commits merge in one
parent transaction, conflicts restore the parent, branch advancement after
review is rejected, and uncertain failures cannot reopen selection.

## Real product surface

The production desktop HTML and JavaScript ran against the authenticated
control plane and a deterministic provider. The test approved only the
`implement` task, started candidates on:

- `openai:gpt-test`
- `openai:gpt-5.6-sol`
- `anthropic:claude-sonnet-4-6`

The UI displayed all three reports and diffs. It selected
`openai:gpt-5.6-sol`, reloaded with the selection intact, reopened the reviewed
diff, and adopted the selected result. The selected candidate became
`adopted`; the other candidates remained isolated and `succeeded`. The parent
session worktree contained `openai:gpt-5.6-sol`, while the original source
checkout remained `base`.

## Packaged artifact

- App:
  `desktop/src-tauri/target/release/bundle/macos/Codinal.app`
- Phase artifact:
  `desktop/src-tauri/target/release/bundle/Codinal-0.1.0-phase21-macos-arm64.zip`
- Size: 87 MB
- SHA-256:
  `8dba5c453bfe0edac8c3918dce4b6dba6356cac0ad8818030d59a087f12bba41`
- Packaged-app smoke: PASS
- `codesign --verify --deep --strict`: PASS
- Signing authority:
  `Developer ID Application: Pongsathon Kheereekaew (BL28MB2PM9)`

This local artifact is signed but is not notarized, stapled, tagged, pushed, or
published.
