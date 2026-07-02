#!/usr/bin/env bash
# Hermes + Telegram setup for a fresh machine. Idempotent.
# Usage:  TELEGRAM_BOT_TOKEN=xxxx ./install.sh
#    or:  ./install.sh  (will prompt for token)
set -euo pipefail

HERE="$(cd "$(dirname "$0")" && pwd)"
OLD_USER="/Users/pongsathonkheeereekaew"   # paths in bundled config reference this; rewrite to $HOME
HERMES="${HERMES_BIN:-$HOME/.local/bin/hermes}"

# --- token ---
TOKEN="${TELEGRAM_BOT_TOKEN:-}"
if [ -z "$TOKEN" ]; then
  read -rsp "Telegram bot token: " TOKEN; echo
fi
case "$TOKEN" in
  [0-9]*:[A-Za-z0-9_-]*) : ;;  # looks like a token
  *) echo "ERROR: token must look like 123:ABC..."; exit 1 ;;
esac

echo "## 1/5 hermes binary"
if [ ! -x "$HERMES" ]; then
  echo "  $HERMES not found. Install Hermes first (brew install hermes-agent, or run its setup script), then re-run."
  exit 1
fi
echo "  ok: $HERMES"

echo "## 2/5 config + SOUL"
mkdir -p "$HOME/.hermes"
[ -f "$HOME/.hermes/config.yaml" ] && cp "$HOME/.hermes/config.yaml" "$HOME/.hermes/config.yaml.bak.$(date +%s)"
# rewrite bundled username paths to this machine's $HOME, then copy
sed "s#$OLD_USER#$HOME#g" "$HERE/config.yaml" > "$HOME/.hermes/config.yaml"
cp "$HERE/SOUL.md" "$HOME/.hermes/SOUL.md"

echo "## 3/5 helper scripts"
mkdir -p "$HOME/.local/bin"
install -m 0755 "$HERE/bin/hermes-handoff" "$HOME/.local/bin/hermes-handoff"
install -m 0755 "$HERE/bin/project-ctx" "$HOME/.local/bin/project-ctx"

echo "## 4/5 token + launchd"
# token in shell rc (zsh/bash)
RC="$([ -f "$HOME/.zshrc" ] && echo "$HOME/.zshrc" || echo "$HOME/.bashrc")"
grep -q "TELEGRAM_BOT_TOKEN=" "$RC" 2>/dev/null \
  && sed -i '' "s#export TELEGRAM_BOT_TOKEN=.*#export TELEGRAM_BOT_TOKEN=\"$TOKEN\"#" "$RC" \
  || echo "export TELEGRAM_BOT_TOKEN=\"$TOKEN\"" >> "$RC"
# render plist from template
mkdir -p "$HOME/Library/LaunchAgents"
sed -e "s#__TELEGRAM_BOT_TOKEN__#$TOKEN#g" -e "s#$OLD_USER#$HOME#g" \
  "$HERE/LaunchAgents/com.nousresearch.hermes.plist" > "$HOME/Library/LaunchAgents/com.nousresearch.hermes.plist"
UID_=$(id -u)
launchctl bootout "gui/$UID_/com.nousresearch.hermes" 2>/dev/null || true
launchctl bootstrap "gui/$UID_" "$HOME/Library/LaunchAgents/com.nousresearch.hermes.plist"

echo "## 5/6 claude code z.ai routing"
ZAI="${ANTHROPIC_AUTH_TOKEN:-}"
if [ -z "$ZAI" ]; then
  read -rsp "z.ai ANTHROPIC_AUTH_TOKEN (blank to skip): " ZAI; echo
fi
if [ -n "$ZAI" ]; then
  python3 - "$HERE/claude/settings.zai.json" "$HOME/.claude/settings.json" "$ZAI" <<'PY'
import json,sys,os
tmpl,target,token=sys.argv[1],sys.argv[2],sys.argv[3]
env=json.load(open(tmpl))["env"]
env["ANTHROPIC_AUTH_TOKEN"]=token
os.makedirs(os.path.dirname(target),exist_ok=True)
cur=json.load(open(target)) if os.path.exists(target) else {}
cur.setdefault("env",{}).update(env)
json.dump(cur,open(target,"w"),indent=2)
print("  merged z.ai env into",target)
PY
else
  echo "  skipped (set ANTHROPIC_AUTH_TOKEN to route claude code via z.ai GLM)"
fi

echo "## 6/6 done. Next steps:"
cat <<EOF
  1. Wait ~10s, then in Telegram open your bot and send any message.
  2. If unrecognized, pair:  hermes pairing approve telegram <CODE>
  3. /sethome in the chat you want scheduled results in.
  4. In the DM, tap bot name -> enable Topics toggle (for Easby/Auric/Code topics).
  5. 9router must run on :20128 (separate install). Confirm: curl http://127.0.0.1:20128/dashboard
EOF
