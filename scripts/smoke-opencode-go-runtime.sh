#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
KEYCHAIN_SERVICE="dev.codinal.desktop.provider-secrets"

read_keychain_secret() {
  local account="$1"
  KEYCHAIN_SERVICE="$KEYCHAIN_SERVICE" KEYCHAIN_ACCOUNT="$account" python3 - <<'PY'
import os
import subprocess
import sys

try:
    result = subprocess.run(
        [
            "security",
            "find-generic-password",
            "-s",
            os.environ["KEYCHAIN_SERVICE"],
            "-a",
            os.environ["KEYCHAIN_ACCOUNT"],
            "-w",
        ],
        check=True,
        capture_output=True,
        timeout=5,
    )
except (OSError, subprocess.SubprocessError):
    sys.exit(1)

secret = result.stdout.rstrip(b"\r\n")
if not secret:
    sys.exit(1)
sys.stdout.buffer.write(secret)
PY
}

if [ "${CODINAL_LIVE_OPENCODE_GO_API_KEY+x}" = "x" ]; then
  if [ -z "$CODINAL_LIVE_OPENCODE_GO_API_KEY" ]; then
    echo "CODINAL_LIVE_OPENCODE_GO_API_KEY is empty." >&2
    exit 2
  fi
elif [ "$(uname -s)" = "Darwin" ] && command -v security >/dev/null 2>&1; then
  if ! key="$(read_keychain_secret opencode-go)"; then
    echo "Codinal Keychain item opencode-go is empty or unavailable." >&2
    exit 2
  fi
  if [ -z "$key" ]; then
    echo "Codinal Keychain item opencode-go is empty or unavailable." >&2
    exit 2
  fi
  export CODINAL_LIVE_OPENCODE_GO_API_KEY="$key"
  unset key
else
  echo "Set CODINAL_LIVE_OPENCODE_GO_API_KEY or run on macOS with the Codinal Keychain item configured." >&2
  exit 2
fi

cd "$ROOT"
exec cargo test \
  --manifest-path crates/codinal-runtime/Cargo.toml \
  --lib live_opencode_go_turn_uses_real_provider_and_writes_terminal_receipt \
  -- --ignored --nocapture
