# New machine — full setup (zero → coding from phone)

Ordered checklist. `🔧` = automated by install scripts. `✋` = manual (one-time logins / app toggles).

## 0. Prereqs (install by hand)
- macOS, homebrew, `git`, `node` (v18+)
- 🔧 **Claude Code CLI**: `brew install --cask claude-code@latest` (or official installer). Run `claude` once to log in.
- 🔧 **Hermes Agent**: install to `~/.local/bin/hermes` (its own setup script / `brew install hermes-agent`). Run once.
- 🔧 **9router**: `npm install -g 9router-app` (v0.5.15+). Then load its launchd agent (see `hermes/LaunchAgents/com.9router.autostart.plist`).
- 🔧 **Ollama** (optional, for free local extraction): `brew install ollama`.

## 1. Clone this repo
```bash
git clone git@github.com:pongsathonkheereekaew/easby-workflow.git
cd easby-workflow
```

## 2. 🔧 Desk side — Claude Code
```bash
./install.sh
```
Copies `claude/` → `~/.claude` (CLAUDE.md, hooks, scripts, plugins, agents), installs CLIs + plugins headless.

## 3. ✋ 9router providers + combo (the model router hermes depends on)
Open `http://127.0.0.1:20128/dashboard` (auth = `~/.9router/auth/cli-secret`). Log in each provider you use (OAuth/key):
| provider | login |
|---|---|
| gemini-cli, antigravity | Google (kpongsat@gmail.com) |
| github | GitHub account |
| kiro | Kiro/AWS account |
| glm (z.ai) | z.ai API key |
| deepseek | DeepSeek API key |
| openrouter | OpenRouter key |
| ollama, cloudflare-ai, gemini | local/free defaults |

Verify: `curl http://127.0.0.1:20128/dashboard` answers; combo `Frey-5.0` exists.

## 4. ✋ Telegram bot
- [@BotFather](https://t.me/BotFather) → `/newbot` → copy **token**
- Note your **chat id** (message @userinfobot) — needed for topic config

## 5. 🔧 Phone side — Hermes + Telegram + launchd
```bash
cd hermes
TELEGRAM_BOT_TOKEN=<bot_token> ./install.sh
#   prompts for z.ai ANTHROPIC_AUTH_TOKEN (same key as desk side)
cd ..
```
Renders config/SOUL/scripts/plist to `~`, starts gateway via launchd (auto on boot).

## 6. ✋ Telegram manual steps (in the app)
1. Open your bot → send any message → it replies with a **pairing code**
2. On the machine: `hermes pairing approve telegram <CODE>`
3. In the bot DM: tap bot name → enable **Topics** toggle (so Easby/Auric/Coding topics appear)
4. Send `/sethome` in the chat you want scheduled results in

## 7. ✋ Projects (paths the `/easby` `/auric` commands expect)
```bash
git clone <easby-remote>  ~/Downloads/Easby\ Plugins
git clone git@github.com:pongsathonkheereekaew/Auric.git ~/Downloads/AURIC
```

## 8. ✅ Verify
- `claude --version` works; `claude` runs
- `curl http://127.0.0.1:20128/dashboard` answers
- `hermes-handoff list` finds projects
- Telegram: bot responds; topics General/Coding/Easby/Auric exist
- Send a coding task in topic **Auric** → hermes routes to claude

## Secrets needed (gather before starting)
| secret | where | used by |
|---|---|---|
| Telegram bot token | @BotFather | hermes gateway |
| z.ai ANTHROPIC_AUTH_TOKEN | z.ai console | claude code (GLM routing) |
| 9router cli-secret | `~/.9router/auth/cli-secret` (auto-gen) | dashboard auth |
| provider logins | each provider (step 3) | 9router model routing |

> Tokens/keys are **never** in this repo — `install.sh` writes them to `~/.zshrc` + rendered plists only.

## Daily flow (after setup)
- **Desk**: `cd <project> && claude` (full power)
- **Leave**: `/handoff` (or ctx-guard auto at 80%)
- **Phone**: Telegram → topic → `continue` (hermes resumes the claude session)
- **Back**: `claude -c`
- Model tiers (hermes): default `gemini-3-flash` · `/model brain` glm-5.2 · `/model heavy` claude-thinking
