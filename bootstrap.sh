#!/usr/bin/env bash
# One-shot: clone (if needed) + install + verify — new machine, zero tweak.
# Usage:
#   ./bootstrap.sh
#   # or from anywhere after first clone lives at ~/harness-flow:
#   curl not required — clone once, then forever: harness update
set -euo pipefail

REPO_SSH="${HARNESS_FLOW_SSH:-git@github.com:pongsathonkheereekaew/harness-flow.git}"
REPO_HTTPS="${HARNESS_FLOW_HTTPS:-https://github.com/pongsathonkheereekaew/harness-flow.git}"
DEST="${HARNESS_FLOW_HOME:-$HOME/harness-flow}"

need_cmd() {
  command -v "$1" >/dev/null 2>&1 || {
    echo "ERROR: missing '$1'. Install git (macOS: xcode-select --install or brew install git)." >&2
    exit 1
  }
}

need_cmd git
need_cmd python3

echo "=== harness-flow bootstrap → $DEST ==="

if [[ -d "$DEST/.git" ]]; then
  echo "repo exists — fast-forward pull"
  git -C "$DEST" pull --ff-only || {
    echo "WARN: pull failed (dirty tree or diverged). Continuing with local tree." >&2
  }
elif [[ -e "$DEST" ]]; then
  echo "ERROR: $DEST exists but is not a git repo. Move it aside and re-run." >&2
  exit 1
else
  echo "cloning…"
  if git ls-remote "$REPO_SSH" >/dev/null 2>&1; then
    git clone "$REPO_SSH" "$DEST"
  else
    echo "SSH clone unavailable — trying HTTPS"
    git clone "$REPO_HTTPS" "$DEST"
  fi
fi

cd "$DEST"
chmod +x install.sh verify.sh bootstrap.sh scripts/* 2>/dev/null || true
./install.sh
bash ./verify.sh

echo ""
echo "Bootstrap complete. Open Cursor or Claude Code in any project and start."
echo "Next time on this machine:  harness update"
