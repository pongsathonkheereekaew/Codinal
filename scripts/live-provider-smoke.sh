#!/usr/bin/env bash
# Live hosted-provider smoke: runs the CEDIA agent CLI against the active
# provider profile with a real API key. Skips cleanly when no key is set, so
# local/CI runs stay green without secrets.
#
# Env:
#   CEDIA_API_KEY          provider key (or use the configured env var name)
#   CEDIA_WORKSPACE        temp workspace override (defaults to a fresh temp)
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
EXT="$HOME/cedia-ide/extensions/cedia-agent"

if [ -z "${DEEPSEEK_API_KEY:-}" ] && [ -z "${CEDIA_API_KEY:-}" ]; then
  echo "live provider smoke: SKIP (no DEEPSEEK_API_KEY / CEDIA_API_KEY)"
  exit 0
fi

WORKSPACE="${CEDIA_WORKSPACE:-$(mktemp -d /tmp/cedia-live.XXXXXX)}"
export CEDIA_AUTO_APPROVE=1
if [ -n "${CEDIA_API_KEY:-}" ]; then
  export DEEPSEEK_API_KEY="$CEDIA_API_KEY"
fi

export PATH="$HOME/.local/node24/bin:$PATH"
node "$EXT/out/cli.js" \
  --workspace "$WORKSPACE" \
  --harness-home "$ROOT" \
  --task "Create LIVE_PROVIDER_PROBE.md containing the text 'live provider works'"

test -f "$WORKSPACE/LIVE_PROVIDER_PROBE.md"
echo "live provider smoke: PASS (workspace $WORKSPACE)"
