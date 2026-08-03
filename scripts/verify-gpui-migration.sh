#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

# This is deliberately a test/dogfood gate. It never switches runtime mode,
# publishes artifacts, or submits an app for notarization.
CI=true ./verify.sh
cargo test --manifest-path desktop/control-plane-client/Cargo.toml
cargo test --manifest-path desktop/native-host/Cargo.toml
TOOLCHAINS=Metal cargo check --manifest-path desktop/gpui/Cargo.toml
scripts/smoke-macos-release.sh

if [ "${CODINAL_REQUIRE_NOTARIZATION:-0}" = "1" ]; then
  scripts/smoke-macos-gatekeeper.sh
else
  echo "notarization gate skipped; set CODINAL_REQUIRE_NOTARIZATION=1 for a release candidate"
fi

echo "GPUI migration test gate passed"
