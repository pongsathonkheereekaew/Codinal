#!/usr/bin/env bash
# Hermes + Telegram health check. Run on the Mac when the bot stops responding.
# Usage: bash hermes/doctor.sh
set -uo pipefail

HERMES="${HERMES_BIN:-$HOME/.local/bin/hermes}"
UID_="$(id -u)"
PLIST="$HOME/Library/LaunchAgents/com.nousresearch.hermes.plist"
LOG_DIR="$HOME/.hermes/logs"
FAIL=0

ok()   { echo "  ✓ $*"; }
warn() { echo "  ⚠ $*"; }
bad()  { echo "  ✗ $*"; FAIL=1; }

echo "==> Hermes Telegram doctor"
echo

echo "## 1. Mac basics"
if pmset -g assertions 2>/dev/null | grep -q "PreventUserIdleSystemSleep"; then
  ok "Mac awake (no idle sleep assertion blocking)"
else
  warn "Mac may be asleep — wake it (tap keyboard / disable sleep while debugging)"
fi
if ping -c1 -W2 8.8.8.8 >/dev/null 2>&1; then
  ok "Internet reachable"
else
  bad "No internet — bot cannot reach Telegram"
fi

echo
echo "## 2. Hermes binary"
if [ -x "$HERMES" ]; then
  ok "hermes at $HERMES ($("$HERMES" --version 2>/dev/null || echo 'version unknown'))"
else
  bad "hermes not found at $HERMES — install: brew install hermes-agent (or official installer)"
fi

echo
echo "## 3. Bot token"
TOKEN=""
if [ -f "$PLIST" ]; then
  TOKEN="$(sed -n 's/.*<string>\(__TELEGRAM_BOT_TOKEN__\|[0-9]*:[^<]*\)<\/string>.*/\1/p' "$PLIST" | grep -E '^[0-9]+:' | head -1 || true)"
  [ "$TOKEN" = "__TELEGRAM_BOT_TOKEN__" ] && TOKEN=""
fi
[ -z "$TOKEN" ] && TOKEN="${TELEGRAM_BOT_TOKEN:-}"
if [ -z "$TOKEN" ] && [ -f "$HOME/.zshrc" ]; then
  TOKEN="$(grep '^export TELEGRAM_BOT_TOKEN=' "$HOME/.zshrc" 2>/dev/null | sed 's/.*="\([^"]*\)".*/\1/' | head -1 || true)"
fi
if [ -n "$TOKEN" ]; then
  ok "Token present (${TOKEN%%:*}:…)"
  API="$(curl -s --max-time 8 "https://api.telegram.org/bot${TOKEN}/getMe")"
  if echo "$API" | grep -q '"ok":true'; then
    ok "Telegram API getMe OK"
  else
    bad "Telegram rejected token — get new token from @BotFather, then re-run hermes/install.sh"
    echo "      response: $(echo "$API" | head -c 200)"
  fi
else
  bad "No TELEGRAM_BOT_TOKEN in plist or ~/.zshrc — re-run: cd harness-flow/hermes && TELEGRAM_BOT_TOKEN=xxx ./install.sh"
fi

echo
echo "## 4. launchd gateway"
if [ -f "$PLIST" ]; then
  ok "plist exists: $PLIST"
else
  bad "Missing $PLIST — run hermes/install.sh"
fi
if launchctl print "gui/${UID_}/com.nousresearch.hermes" >/dev/null 2>&1; then
  ok "launchd job loaded (gui/${UID_}/com.nousresearch.hermes)"
else
  bad "Gateway NOT loaded — fix:"
  echo "      launchctl bootstrap gui/${UID_} \"$PLIST\""
fi
if pgrep -fl "hermes gateway" >/dev/null 2>&1; then
  ok "hermes gateway process running"
  pgrep -fl "hermes gateway" | sed 's/^/      /'
else
  bad "No hermes gateway process — restart:"
  echo "      launchctl kickstart -k gui/${UID_}/com.nousresearch.hermes"
fi

echo
echo "## 5. Config files"
for f in "$HOME/.hermes/config.yaml" "$HOME/.hermes/SOUL.md"; do
  [ -f "$f" ] && ok "$(basename "$f")" || bad "Missing $f"
done

echo
echo "## 6. 9router (LLM router — bot may load but not reply intelligently)"
if curl -sf --max-time 3 http://127.0.0.1:20128/dashboard >/dev/null 2>&1; then
  ok "9router up on :20128"
else
  warn "9router not responding on :20128 — start it (see hermes/LaunchAgents/com.9router.autostart.plist)"
fi

echo
echo "## 7. Recent logs (last 15 lines)"
mkdir -p "$LOG_DIR"
for log in "$LOG_DIR/launchd.err" "$LOG_DIR/launchd.out" "$LOG_DIR/agent.log"; do
  if [ -f "$log" ]; then
    echo "--- tail $log ---"
    tail -15 "$log" 2>/dev/null | sed 's/^/      /'
  fi
done
[ ! -f "$LOG_DIR/launchd.err" ] && [ ! -f "$LOG_DIR/agent.log" ] && warn "No log files yet in $LOG_DIR"

echo
echo "## 8. Pairing (if bot receives but ignores you)"
echo "  Send any message in Telegram; if bot asks for a code, on Mac run:"
echo "    hermes pairing approve telegram <CODE>"

echo
if [ "$FAIL" -eq 0 ]; then
  echo "==> Looks healthy. Send a test message in Telegram."
  echo "    If still silent: launchctl kickstart -k gui/${UID_}/com.nousresearch.hermes"
else
  echo "==> Found problem(s). Fix ✗ items above, then:"
  echo "    launchctl kickstart -k gui/${UID_}/com.nousresearch.hermes"
fi
exit "$FAIL"
