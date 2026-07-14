# New machine — full setup (zero → coding from phone)

Ordered checklist. `🔧` = automated by install scripts. `✋` = manual (one-time logins / app toggles).

> Live shared policy & skills live in **`~/.agents/`** (Agent Harness). This repo bootstraps that plus personal Claude/Hermes packs. Details: [`docs/AGENT_HARNESS.md`](docs/AGENT_HARNESS.md).

## 0. Prereqs (install by hand)
- macOS, homebrew, `git`, `node` (v18+)
- 🔧 **Claude Code CLI**: `brew install --cask claude-code@latest` (or official installer). Run `claude` once to log in.
- 🔧 **Hermes Agent**: install to `~/.local/bin/hermes` (its own setup script / `brew install hermes-agent`). Run once.
- 🔧 **9router**: `npm install -g 9router-app` (v0.5.15+). Then load its launchd agent (see `hermes/LaunchAgents/com.9router.autostart.plist`).
- 🔧 **Ollama** (optional, for free local extraction): `brew install ollama`.

## 1. Clone this repo
```bash
git clone git@github.com:pongsathonkheereekaew/harness-flow.git
cd harness-flow
```

> Old repos `easby-workflow` / `claude-skills` are deprecated — use `harness-flow`.

## 2. 🔧 Desk — Agent Harness + Claude Code
```bash
./install.sh
```
Bootstraps `~/.agents` (keeps existing `AGENTS.md`), copies Cursor rule snapshots, installs `claude/` → `~/.claude`, copies Hermes kit files.

Then:
```bash
~/.agents/scripts/harness sync
~/.agents/scripts/harness doctor
```

## 3. ✋ 9router providers + combo (the model router hermes depends on)
Open `http://127.0.0.1:20128/dashboard` (auth = `~/.9router/auth/cli-secret`). Log in each provider you use (OAuth/key):
| provider | login |
|---|---|
| gemini-cli, antigravity | Google |
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

Ensure `~/.hermes/config.yaml` has:
```yaml
skills:
  external_dirs:
    - ~/.agents/skills
```

Keep `~/.hermes/SOUL.md` thin (Hermes-only). Do not paste full `AGENTS.md` into it.

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
- `bash ./verify.sh` at repo root (includes AgentMonitor + wiki scaffold)
- `claude --version` works; `claude` runs
- `~/.agents/scripts/harness doctor` clean
- `curl http://127.0.0.1:20128/dashboard` answers
- `hermes-handoff list` finds projects
- Telegram: bot responds; topics General/Coding/Easby/Auric exist
- Send a coding task in topic **Auric** → hermes routes to local coding agent

## Secrets needed (gather before starting)
| secret | where | used by |
|---|---|---|
| Telegram bot token | @BotFather | hermes gateway |
| z.ai ANTHROPIC_AUTH_TOKEN | z.ai console | claude code (GLM routing) |
| 9router cli-secret | `~/.9router/auth/cli-secret` (auto-gen) | dashboard auth |
| provider logins | each provider (step 3) | 9router model routing |

> Tokens/keys are **never** in this repo — install scripts write them to local env / plists only.

## Daily flow (after setup)
- **Desk**: work in the project with Cursor / Claude; shared policy from `~/.agents/AGENTS.md`
- **Leave**: `/handoff` (or Claude ctx-guard auto at 80%)
- **Phone**: Telegram → topic → hermes dispatches local `cursor-agent` / coding flow
- **Back**: continue desk session from handoff / goal files
- Model tiers (hermes): see `~/.hermes/SOUL.md` / `config.yaml` aliases
