# Hermes + Telegram setup

Bundled config for the personal Hermes Agent + Telegram bot, so a fresh machine
can be brought up in one command. Designed for a 1-person workflow: coding from
the phone via Claude Code, model-routed through 9router.

## What this installs
| File | Purpose |
|---|---|
| `config.yaml` | model (9router `Frey-5.0`), model aliases `light/heavy/think`, Telegram DM topics (General/Coding/Easby/Auric), quick commands `/easby` `/auric`, streaming on |
| `SOUL.md` | persona + handoff bridge + solo-mode rules (worktree/checkpoint/test-before-merge/verify) + Fable-5 planner discipline |
| `bin/hermes-handoff` | list/pick open Claude Code handoffs to continue a session from the phone |
| `bin/project-ctx` | `/easby` `/auric` quick-command backend (workdir + sub-project git state) |
| `LaunchAgents/com.nousresearch.hermes.plist` | launchd template — auto-starts the gateway on boot, restarts on crash |

## Install (new machine)
```bash
git clone git@github.com:pongsathonkheereekaew/claude-workflow.git
cd claude-workflow/hermes
# prerequisites: hermes binary at ~/.local/bin/hermes, 9router running on :20128
TELEGRAM_BOT_TOKEN=123:ABC... ./install.sh
```
`install.sh` rewrites the bundled `/Users/pongsathonkheeereekaew` paths to the
current `$HOME`, so it works under any username. Token is **never committed** —
it is written to `~/.zshrc` and the rendered plist only.

## Architecture (what talks to what)
```
Telegram bot ── hermes gateway (launchd) ── 9router :20128 ── upstream LLM
                       │                          (Frey-5.0 combo / glm / gemini / deepseek / kiro-claude)
                       └── claude-code skill ── `claude` CLI ── z.ai GLM (api.z.ai/api/anthropic)
```
Two token pools: hermes reasoning via 9router; coding via z.ai. No Anthropic key.

## Secrets
- `config.yaml` contains the Telegram **chat_id** (your user id) — not secret, needed for topics.
- Bot **token** is NOT in this repo. Get a fresh one from @BotFather per machine.

## Notes
- Telegram topic names/ids: General(215) Coding(234) Easby(219) Auric(236). Topic ids are
  per-bot; on a *new* bot they will differ — `install.sh` keeps the names; hermes recreates
  topics and rewrites ids into config on first gateway start.
- `/easby` `/auric` point at `~/Downloads/Easby Plugins` and `~/Downloads/AURIC` — clone those
  repos (or adjust paths) on the new machine.
