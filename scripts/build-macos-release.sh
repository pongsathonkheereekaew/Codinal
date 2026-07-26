#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
TAURI_ROOT="$ROOT/desktop/src-tauri"
RESOURCES="$TAURI_ROOT/resources"
LOCK="$ROOT/runtime/requirements.lock"
PYTHON_VERSION="3.12.13"
PYTHON_BUILD="20260718"
PYTHON_SHA256="62aeee6161d57303a71a138b75fd5cc6fb8c89c4b1d9c7f0a052d89fa0b6652b"
PYTHON_ARCHIVE_NAME="cpython-${PYTHON_VERSION}+${PYTHON_BUILD}-aarch64-apple-darwin-install_only.tar.gz"
PYTHON_URL="https://github.com/astral-sh/python-build-standalone/releases/download/${PYTHON_BUILD}/${PYTHON_ARCHIVE_NAME}"
CACHE_DIR="${CODINAL_RELEASE_CACHE:-/tmp/codinal-release-cache}"
ARCHIVE="${CODINAL_PYTHON_ARCHIVE:-$CACHE_DIR/$PYTHON_ARCHIVE_NAME}"

if [ "$(uname -s)" != "Darwin" ] || [ "$(uname -m)" != "arm64" ]; then
  echo "Codinal v1 release builds require Apple Silicon macOS" >&2
  exit 1
fi
if [ "$RESOURCES" != "$ROOT/desktop/src-tauri/resources" ]; then
  echo "invalid release resource path" >&2
  exit 1
fi
if ! TAURI_VERSION="$(cargo tauri --version 2>/dev/null)"; then
  echo "tauri-cli 2.11.4 is required: cargo install tauri-cli --version 2.11.4 --locked" >&2
  exit 1
fi
if [ "$TAURI_VERSION" != "tauri-cli 2.11.4" ]; then
  echo "tauri-cli 2.11.4 is required; found $TAURI_VERSION" >&2
  exit 1
fi
if [ -z "${TAURI_SIGNING_PRIVATE_KEY:-}" ] \
  && [ -z "${TAURI_SIGNING_PRIVATE_KEY_PATH:-}" ]; then
  echo "TAURI_SIGNING_PRIVATE_KEY or TAURI_SIGNING_PRIVATE_KEY_PATH is required" >&2
  exit 1
fi
if [ -z "${TAURI_SIGNING_PRIVATE_KEY:-}" ]; then
  if [ ! -f "$TAURI_SIGNING_PRIVATE_KEY_PATH" ]; then
    echo "TAURI_SIGNING_PRIVATE_KEY_PATH does not exist" >&2
    exit 1
  fi
  export TAURI_SIGNING_PRIVATE_KEY="$TAURI_SIGNING_PRIVATE_KEY_PATH"
fi
export TAURI_SIGNING_PRIVATE_KEY_PASSWORD="${TAURI_SIGNING_PRIVATE_KEY_PASSWORD:-}"

mkdir -p "$CACHE_DIR"
if [ ! -f "$ARCHIVE" ]; then
  curl --fail --location --proto '=https' --tlsv1.2 \
    --output "$ARCHIVE" "$PYTHON_URL"
fi
printf '%s  %s\n' "$PYTHON_SHA256" "$ARCHIVE" | shasum -a 256 -c -

BUILD_DIR="$(mktemp -d /tmp/codinal-release.XXXXXX)"
trap 'rm -rf "$BUILD_DIR"' EXIT
tar -xzf "$ARCHIVE" -C "$BUILD_DIR"
test -x "$BUILD_DIR/python/bin/python3"
APP_VERSION="$("$BUILD_DIR/python/bin/python3" -c \
  'import sys, tomllib; print(tomllib.load(open(sys.argv[1], "rb"))["package"]["version"])' \
  "$TAURI_ROOT/Cargo.toml")"
"$BUILD_DIR/python/bin/python3" -c \
  'import json, sys; assert json.load(open(sys.argv[1]))["version"] == sys.argv[2]' \
  "$TAURI_ROOT/tauri.conf.json" "$APP_VERSION"

"$BUILD_DIR/python/bin/python3" -m pip install \
  --disable-pip-version-check \
  --require-hashes \
  --requirement "$LOCK"

mkdir -p "$BUILD_DIR/resources/runtime"
ditto "$ROOT/runtime" "$BUILD_DIR/resources/runtime/runtime"
find "$BUILD_DIR/resources/runtime" \
  -type d -name __pycache__ -prune -exec rm -rf {} +
find "$BUILD_DIR/resources/runtime" \
  -type f \( -name '*.pyc' -o -name '.DS_Store' \) -delete
cp "$ROOT/LICENSE" "$ROOT/NOTICE" "$ROOT/runtime/requirements.lock" \
  "$BUILD_DIR/resources/runtime/"
"$BUILD_DIR/python/bin/python3" "$ROOT/scripts/generate_python_sbom.py" \
  "$ROOT/runtime/requirements.lock" \
  "$BUILD_DIR/resources/runtime/python-sbom.cdx.json" \
  --version "$APP_VERSION"
ditto "$BUILD_DIR/python" "$BUILD_DIR/resources/python"

rm -rf "$RESOURCES/runtime" "$RESOURCES/python"
mkdir -p "$RESOURCES"
ditto "$BUILD_DIR/resources/runtime" "$RESOURCES/runtime"
ditto "$BUILD_DIR/resources/python" "$RESOURCES/python"

SIGNING_IDENTITY="${APPLE_SIGNING_IDENTITY:-}"
if [ "${CODINAL_REQUIRE_SIGNING:-0}" = "1" ] && [ -z "$SIGNING_IDENTITY" ]; then
  echo "APPLE_SIGNING_IDENTITY is required for a release build" >&2
  exit 1
fi
if [ -n "$SIGNING_IDENTITY" ]; then
  while IFS= read -r -d '' candidate; do
    case "$(file -b "$candidate")" in
      Mach-O*)
        codesign --force --options runtime --timestamp \
          --sign "$SIGNING_IDENTITY" "$candidate"
        ;;
    esac
  done < <(find "$RESOURCES/python" -type f -print0)
fi

BUILD_LOG="$BUILD_DIR/tauri-build.log"
(
  cd "$TAURI_ROOT"
  cargo tauri build \
    --config "$TAURI_ROOT/tauri.release.conf.json" \
    --bundles app 2>&1 | tee "$BUILD_LOG"
)
if grep -q "updater secret key.*does not match" "$BUILD_LOG"; then
  echo "updater private key does not match the committed public key" >&2
  exit 1
fi

APP="$TAURI_ROOT/target/release/bundle/macos/Codinal.app"
test -x "$APP/Contents/MacOS/codinal"
test -x "$APP/Contents/Resources/python/bin/python3"
test -f "$APP/Contents/Resources/runtime/runtime/control_plane/__main__.py"
test -f "$APP/Contents/Resources/runtime/python-sbom.cdx.json"
codesign --verify --deep --strict --verbose=2 "$APP"

if [ "${CODINAL_REQUIRE_NOTARIZATION:-0}" = "1" ]; then
  NOTARY_ARCHIVE="$BUILD_DIR/Codinal-notary.zip"
  ditto -c -k --keepParent "$APP" "$NOTARY_ARCHIVE"

  if [ -n "${CODINAL_NOTARY_PROFILE:-}" ]; then
    xcrun notarytool submit "$NOTARY_ARCHIVE" \
      --keychain-profile "$CODINAL_NOTARY_PROFILE" \
      --wait
  elif [ -n "${APPLE_ID:-}" ] && [ -n "${APPLE_PASSWORD:-}" ] && [ -n "${APPLE_TEAM_ID:-}" ]; then
    xcrun notarytool submit "$NOTARY_ARCHIVE" \
      --apple-id "$APPLE_ID" \
      --password "@env:APPLE_PASSWORD" \
      --team-id "$APPLE_TEAM_ID" \
      --wait
  else
    echo "notarization credentials are required: set CODINAL_NOTARY_PROFILE or APPLE_ID/APPLE_TEAM_ID/APPLE_PASSWORD" >&2
    exit 1
  fi

  xcrun stapler staple "$APP"
  xcrun stapler validate "$APP"
  spctl --assess --type execute --verbose=2 "$APP"
fi

ARTIFACT="$TAURI_ROOT/target/release/bundle/Codinal-${APP_VERSION}-macos-arm64.zip"
ditto -c -k --sequesterRsrc --keepParent "$APP" "$ARTIFACT"
shasum -a 256 "$ARTIFACT" > "$ARTIFACT.sha256"

UPDATER_SOURCE="$TAURI_ROOT/target/release/bundle/macos/Codinal.app.tar.gz"
UPDATER_SOURCE_SIGNATURE="$UPDATER_SOURCE.sig"
UPDATER_ARTIFACT="$TAURI_ROOT/target/release/bundle/Codinal-${APP_VERSION}-macos-arm64.app.tar.gz"
test -f "$UPDATER_SOURCE"
test -s "$UPDATER_SOURCE_SIGNATURE"
cp "$UPDATER_SOURCE" "$UPDATER_ARTIFACT"
cp "$UPDATER_SOURCE_SIGNATURE" "$UPDATER_ARTIFACT.sig"
shasum -a 256 "$UPDATER_ARTIFACT" > "$UPDATER_ARTIFACT.sha256"

echo "release app: $APP"
echo "release artifact: $ARTIFACT"
echo "updater artifact: $UPDATER_ARTIFACT"
