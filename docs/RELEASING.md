# Releasing Codinal for macOS

Codinal releases are Apple Silicon `.app` bundles with an embedded, hash-locked
Python runtime. Every Mach-O file is signed with hardened runtime, the complete
bundle is notarized and stapled, and updater archives are signed independently
with the Tauri updater key.

## One-time setup

Configure these GitHub Actions secrets:

- `APPLE_CERTIFICATE_BASE64`: base64-encoded Developer ID Application `.p12`
- `APPLE_CERTIFICATE_PASSWORD`, `APPLE_KEYCHAIN_PASSWORD`
- `APPLE_SIGNING_IDENTITY`, `APPLE_TEAM_ID`
- `APPLE_ID`, `APPLE_PASSWORD`: Apple ID and app-specific password for notarization
- `TAURI_SIGNING_PRIVATE_KEY`, `TAURI_SIGNING_PRIVATE_KEY_PASSWORD`

The updater private key must match the public key committed in
`desktop/src-tauri/tauri.conf.json`. Never commit or log the private key.

## Release

1. Set the same version in `desktop/src-tauri/Cargo.toml` and
   `desktop/src-tauri/tauri.conf.json`.
2. Run `bash verify.sh`.
3. Create and push a signed `v<version>` tag.
4. The `release` workflow verifies source, builds the embedded runtime, signs
   every executable, notarizes and staples the app, validates Gatekeeper, and
   extracts it as a transported artifact, applies quarantine, and smoke-tests
   it on a clean hosted macOS runner before publishing the app, checksums,
   updater signature, and `latest.json`.

The workflow can also be dispatched manually for an existing v-prefixed tag.
It never creates a release from an untagged commit.

## Local release check

Set the same signing, notarization, and updater variables used by CI, then run:

```bash
CODINAL_REQUIRE_SIGNING=1 \
CODINAL_REQUIRE_NOTARIZATION=1 \
bash scripts/build-macos-release.sh
```

Success requires all of these checks to pass:

- `codesign --verify --deep --strict`
- `xcrun stapler validate`
- `spctl --assess --type execute`
- embedded Python and runtime resources are present
- updater `.app.tar.gz`, `.sig`, and SHA-256 files are present

The release workflow is the source of truth for public artifacts. A locally
signed but unstapled build is not releasable.
