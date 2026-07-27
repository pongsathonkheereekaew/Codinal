# Phase 40 evidence — notarize + updater rollback

Date: 2026-07-27
P0 release floor: "Notarize/staple" + "Publish the stable updater channel and prove check, signature validation, download, install, restart, rollback."

## What shipped

The notarize + staple + Gatekeeper infrastructure already existed (release scripts, CI workflow, contract tests). This phase closes the **rollback gap** — the one missing piece from the roadmap's updater acceptance criteria.

- **Rust `rollback_update` command** (`desktop/src-tauri/src/lib.rs`): restores the `.app.backup` created by `install_update` before the last update. Swap-then-restart: moves the current (broken) `.app` aside, moves the backup into place, restarts. Atomic-ish: if the backup rename fails, the current is moved back.
- **`install_update` backup step**: before `download_and_install`, the current `.app` bundle is recursively copied to `<name>.app.backup` via `copy_dir_recursive`.
- **`copy_dir_recursive` utility + tests**: recursive directory copy (2 Rust tests: nested dirs + overwrite behavior).
- **UI**: "Rollback update" button in Settings (next to "Install and restart"), hidden by default.

## What already existed (verified)

- `notarytool submit` + `stapler staple` + `stapler validate` + `spctl --assess` in `build-macos-release.sh` (gated by `CODINAL_REQUIRE_NOTARIZATION`).
- Quarantine-unzip-launch on clean runner via `smoke-macos-gatekeeper.sh` + `release.yml`.
- Updater endpoint (`latest.json` on GitHub Releases), manifest generator, signature validation (tauri-plugin-updater internal).
- `check_for_update` + `install_update` Rust commands + UI.

## Verification

```
$ cargo test --lib  # desktop/src-tauri
test tests::copy_dir_recursive_copies_files_and_subdirs ... ok
test tests::copy_dir_recursive_overwrites_existing ... ok
9 passed
```

```
$ ./.venv/bin/pytest -q tests/desktop_ui/test_ui_contract.py
.....                                                                     [100%]
5 passed
```

```
$ CI= ./.venv/bin/pytest -q
862 passed, 1 skipped
```

`verify.sh`: PASS (Codinal verify). Rust clippy clean.
