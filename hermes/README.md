# Hermes + Telegram setup

Bundled config for the personal Hermes Agent + Telegram bot, so a fresh machine
can be brought up in one command. Designed for a 1-person workflow: **desk coding
in Cursor IDE**, **phone coding via Cursor Cloud Agents** (Hermes as thin router),
model-routed through 9router.

## What this installs
| File | Purpose |
|---|---|
| `config.yaml` | model (9router), Telegram topics, anti-duplicate display settings, gateway streaming off for mobile stability |
| `SOUL.md` | persona + **Cursor Cloud Agents bridge** (anti-loop rules) + handoff bridge + solo-mode rules |
| `bin/hermes-handoff` | list/pick open desktop handoffs (GOAL.md / HANDOFF.md) for phone continuation |
| `bin/project-ctx` | `/easby` `/auric` quick-command backend (workdir + sub-project git state) |
| `LaunchAgents/com.nousresearch.hermes.plist` | launchd template — auto-starts the gateway on boot, restarts on crash |

## Install (new machine)
```bash
git clone git@github.com:pongsathonkheereekaew/harness-flow.git
cd harness-flow/hermes
# prerequisites: hermes binary at ~/.local/bin/hermes, 9router running on :20128
TELEGRAM_BOT_TOKEN=123:ABC... ./install.sh
```
`install.sh` rewrites the bundled `/Users/pongsathonkheeereekaew` paths to the
current `$HOME`, so it works under any username. Token is **never committed** —
it is written to `~/.zshrc` and the rendered plist only.

## Apply config fix on an existing machine
If Telegram messages duplicate or sessions loop on the same old prompt:

**One command (Terminal on Mac, or ask Hermes to run it):**
```bash
curl -fsSL https://raw.githubusercontent.com/pongsathonkheereekaew/harness-flow/main/hermes/apply-fix.sh | bash
```

**Or from Telegram** (after the first apply adds `/fix-loop`):
```
/fix-loop
```

Manual copy also works:
```bash
cd harness-flow && git pull
bash hermes/apply-fix.sh
```
Also install the Cursor bridge skill/plugin (one of):
- `cursor-cloud-agents` skill (Cursor Cloud Agents API)
- [cursor-hermes-plugin](https://github.com/fernandoabolafio/cursor-hermes-plugin)

Upgrade Hermes to latest — duplicate-reply bugs were fixed upstream in PRs
[#10235](https://github.com/NousResearch/hermes-agent/pull/10235) (interrupt race)
and [#44120](https://github.com/NousResearch/hermes-agent/pull/44120) (session DB persistence).

## Architecture (what talks to what)
```
Telegram bot ── hermes gateway (launchd) ── 9router :20128 ── upstream LLM (router)
                       │
                       └── Cursor Cloud Agents API ── Cursor sandbox (GitHub repo)
Desk: Cursor IDE (reads ~/.cursor/rules from harness-flow)
```
Hermes is a **thin router** on phone — it launches/follows up Cursor agents, not double-plans.

## Troubleshooting: duplicate messages / session loop

| Symptom | Cause | Fix in this bundle |
|---|---|---|
| Two bubbles per turn (code block + answer) | `interim_assistant_messages: true` (Telegram default) | `display.interim_assistant_messages: false` |
| Same answer twice after interrupt | Interrupt race in older Hermes | Upgrade Hermes + restart gateway |
| Broken partial + reformulated full reply | Streaming `transport: edit` + flood control | `gateway.streaming.enabled: false` |
| Agent re-answers old messages | Assistant rows not persisted to session DB | Upgrade Hermes (PR #44120) |
| Cursor agent launched repeatedly | SOUL had no dedup rules | SOUL anti-loop rules + removed forced `skill: claude-code` on topics |

## Secrets
- `config.yaml` contains the Telegram **chat_id** (your user id) — not secret, needed for topics.
- Bot **token** is NOT in this repo. Get a fresh one from @BotFather per machine.
- Cursor Cloud Agents API key: set in Hermes env or plugin config (not committed).

## Notes
- Telegram topic names/ids: General(215) Coding(234) Easby(219) Auric(236). Topic ids are
  per-bot; on a *new* bot they will differ — `install.sh` keeps the names; hermes recreates
  topics and rewrites ids into config on first gateway start.
- `/easby` `/auric` point at `~/Downloads/Easby Plugins` and `~/Downloads/AURIC` — clone those
  repos (or adjust paths) on the new machine.
- Coding topics no longer force `skill: claude-code` — SOUL routes to Cursor Cloud Agents by default.
