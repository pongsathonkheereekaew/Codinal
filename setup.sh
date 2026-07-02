#!/usr/bin/env bash
# setup.sh — one-command new-machine setup. Idempotent; safe to re-run.
# Does the automatable 70%, then prints the manual steps it can't (OAuth/Telegram/pairing).
# Usage:  TELEGRAM_BOT_TOKEN=xxx ANTHROPIC_AUTH_TOKEN=yyy ./setup.sh
set -uo pipefail
HERE="$(cd "$(dirname "$0")" && pwd)"; UID_=$(id -u)
step(){ printf "\n\033[1;36m== %s ==\033[0m\n" "$1"; }
have(){ command -v "$1" >/dev/null 2>&1; }

step "0. prereqs (homebrew + CLIs)"
have brew || { echo "✋ install Homebrew first: https://brew.sh"; exit 1; }
brew install -q node git jq 2>/dev/null || true
have claude || brew install --cask claude-code@latest 2>/dev/null || echo "  (claude-code cask: install manually if this failed)"
have ollama || brew install ollama 2>/dev/null || true
# hermes — own installer, not always a brew formula
[ -x "$HOME/.local/bin/hermes" ] || echo "✋ Hermes not at ~/.local/bin/hermes — run its setup script, then re-run ./setup.sh"
# 9router (npm global)
have 9router || npm install -g 9router-app 2>/dev/null || echo "  (9router-app npm install: may need sudo / fix npm prefix)"

step "1. 9router auto-start (launchd)"
if [ -f "$HERE/hermes/LaunchAgents/com.9router.autostart.plist" ]; then
  cp "$HERE/hermes/LaunchAgents/com.9router.autostart.plist" "$HOME/Library/LaunchAgents/" 2>/dev/null || true
  launchctl bootout "gui/$UID_/com.9router.autostart" 2>/dev/null || true
  launchctl bootstrap "gui/$UID_" "$HOME/Library/LaunchAgents/com.9router.autostart.plist" 2>/dev/null || true
fi

step "2. desk side — Claude Code"
"$HERE/install.sh"

step "3. phone side — Hermes + Telegram"
TOKEN="${TELEGRAM_BOT_TOKEN:-}"
[ -z "$TOKEN" ] && { read -rsp "Telegram bot token: " TOKEN; echo; }
( cd "$HERE/hermes" && TELEGRAM_BOT_TOKEN="$TOKEN" ANTHROPIC_AUTH_TOKEN="${ANTHROPIC_AUTH_TOKEN:-}" ./install.sh )

step "4. projects (paths /easby /auric expect)"
[ -d "$HOME/Downloads/AURIC" ] || git clone git@github.com:pongsathonkheereekaew/Auric.git "$HOME/Downloads/AURIC" 2>/dev/null || echo "  ✋ clone Auric manually"
[ -d "$HOME/Downloads/Easby Plugins" ] || echo "  ✋ clone Easby Plugins to ~/Downloads/Easby Plugins (remote not bundled)"

step "5. DONE automated part. Now the MANUAL steps:"
cat <<EOF
  ✋ 1. 9router dashboard  http://127.0.0.1:20128  (auth: ~/.9router/auth/cli-secret)
        → log in each provider: Google (gemini-cli/antigravity), GitHub, Kiro, z.ai, DeepSeek, OpenRouter
        → confirm combo "Frey-5.0" exists
  ✋ 2. claude login: run  claude  once (browser OAuth) — if not already logged in
  ✋ 3. Telegram: open your bot → send any message → copy pairing code → run:
            hermes pairing approve telegram <CODE>
  ✋ 4. Telegram: tap bot name → enable Topics toggle (so General/Coding/Easby/Auric appear)
  ✋ 5. In the bot chat:  /sethome
  ✋ 6. Verify: hermes-handoff list  → should find projects
EOF
echo "\nThen: desk → \`claude\` in a project; phone → Telegram topic → \"continue\"."
