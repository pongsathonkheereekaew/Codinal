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

For a local release, store a fresh app-specific password in Keychain using the
secure prompt (the password does not enter shell history):

```bash
xcrun notarytool store-credentials codinal-release \
  --apple-id YOUR_APPLE_ID \
  --team-id BL28MB2PM9
```

Set the signing and updater variables, then run:

```bash
CODINAL_REQUIRE_SIGNING=1 \
CODINAL_REQUIRE_NOTARIZATION=1 \
CODINAL_NOTARY_PROFILE=codinal-release \
bash scripts/build-macos-release.sh
```

CI instead uses the Apple and updater secrets listed above. Do not reuse an
old credential profile after its password has been exposed or revoked.

## Local smoke and validation helpers

For local checks without signing/notarization, use:

```bash
CODINAL_REQUIRE_SIGNING=0 \
CODINAL_REQUIRE_NOTARIZATION=0 \
TAURI_SIGNING_PUBLIC_KEY_PATH=/tmp/codinal-tmp/tauri.keys.pub \
TAURI_SIGNING_PRIVATE_KEY_PATH=/tmp/codinal-tmp/tauri.keys \
TAURI_SIGNING_PRIVATE_KEY_PASSWORD=codinal-temp-pass \
bash scripts/build-macos-release.sh

bash scripts/smoke-macos-release.sh
CODINAL_REQUIRE_NOTARIZATION=0 \
CODINAL_SKIP_APP_LAUNCH=1 \
CODINAL_SKIP_EMBEDDED_IMPORTS=1 \
CODINAL_SKIP_CODESIGN_CHECK=1 \
bash scripts/smoke-macos-gatekeeper.sh
```

To generate a release manifest locally, set:

```bash
CODINAL_REQUIRE_SIGNING=0 \
CODINAL_REQUIRE_NOTARIZATION=0 \
CODINAL_UPDATE_MANIFEST_URL="https://example.com/releases/v0.1.0/Codinal-0.1.0-macos-arm64.app.tar.gz" \
CODINAL_UPDATE_MANIFEST_PATH=desktop/src-tauri/target/release/bundle/latest.json \
CODINAL_UPDATE_MANIFEST_NOTES="Codinal 0.1.0" \
CODINAL_UPDATE_MANIFEST_PUB_DATE="$(date -u +%Y-%m-%dT%H:%M:%SZ)" \
TAURI_SIGNING_PUBLIC_KEY_PATH=/tmp/codinal-tmp/tauri.keys.pub \
TAURI_SIGNING_PRIVATE_KEY_PATH=/tmp/codinal-tmp/tauri.keys \
TAURI_SIGNING_PRIVATE_KEY_PASSWORD=codinal-temp-pass \
bash scripts/build-macos-release.sh
```

`TAURI_SIGNING_PUBLIC_KEY_PATH` is optional when your updater public key already
matches `desktop/src-tauri/tauri.conf.json`; use it when you are validating a
local temporary keypair.

For a full local release run with matching artifacts and local signing checks, ensure:

- `codesign --verify --deep --strict`
- embedded Python and runtime resources are present
- updater `.app.tar.gz`, `.sig`, and SHA-256 files are present

### Checks by mode

| Mode | Signing | Notary/staple | Expected command gates |
| --- | --- | --- | --- |
| Local smoke | optional | disabled | `smoke-macos-release.sh`, `smoke-macos-gatekeeper.sh` with `CODINAL_REQUIRE_NOTARIZATION=0` |
| Release candidate (CI) | required | required | `smoke-macos-gatekeeper.sh` with default `CODINAL_REQUIRE_NOTARIZATION=1` |
| Public release | required | required | `.github/workflows/release.yml` + release workflow smoke |

For full notarized release validation (required for public shipping), also require:

- `xcrun stapler validate`
- `spctl --assess --type execute`

The release workflow is the source of truth for public artifacts. A locally
signed but unstapled build is not releasable.
