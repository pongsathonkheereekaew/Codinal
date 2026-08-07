#!/usr/bin/env bash
# Self-hosting gate: CEDIA's own agent writes a change into a temporary
# worktree of this repository, then the repository verifies itself.
#
# Uses the offline mock provider by default; set CEDIA_PROFILE=mock/local.
# Full `bash verify.sh` (Rust gates) is the final production gate once real
# provider credentials and a browser binary are configured.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
EXT="$HOME/cedia-ide/extensions/cedia-agent"
WORKTREE="$(mktemp -d /tmp/cedia-selfhost.XXXXXX)"
trap 'git -C "$ROOT" worktree remove --force "$WORKTREE" 2>/dev/null || rm -rf "$WORKTREE"' EXIT

git -C "$ROOT" worktree add --detach "$WORKTREE" HEAD >/dev/null

cat > "$WORKTREE/verify-selfhost.sh" <<'SH'
#!/usr/bin/env bash
set -euo pipefail
python3 harness/scripts/harness_agent.py check
test -f CEDIA_SELF_HOST_PROBE.md
echo "self-host verify: PASS"
SH
chmod +x "$WORKTREE/verify-selfhost.sh"

export PATH="$HOME/.local/node24/bin:$PATH"
export CEDIA_AUTO_APPROVE="${CEDIA_AUTO_APPROVE:-1}"

node "$EXT/out/cli.js" \
  --workspace "$WORKTREE" \
  --harness-home "$ROOT" \
  --task "Create CEDIA_SELF_HOST_PROBE.md containing the text 'self-hosted by CEDIA'" \
  --verify verify-selfhost.sh

test -f "$WORKTREE/CEDIA_SELF_HOST_PROBE.md"
echo "self-host gate: PASS (agent authored $WORKTREE/CEDIA_SELF_HOST_PROBE.md)"
