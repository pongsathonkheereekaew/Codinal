# MANIFEST — Agent Harness

**This repo** is the git SSOT for portable policy + skills.  
**Live path** after `./install.sh`: `~/.agents/`.

| Layer | Location |
|-------|----------|
| Lingua franca | `AGENTS.md` → `~/.agents/AGENTS.md` |
| Durable memory | `memory/` → `~/.agents/memory/` |
| Skills | `skills/` → `~/.agents/skills/` |
| Standards / commands | `standards/`, `commands/` |
| CLI | `scripts/harness` → sync / rules / doctor / **update** |
| New machine | `bootstrap.sh` (clone + install + verify) |
| Office + Hermes | **not here** — [`agentmonitor`](https://github.com/pongsathonkheereekaew/agentmonitor) |

## Install once

```bash
git clone git@github.com:pongsathonkheereekaew/harness-flow.git ~/harness-flow && ~/harness-flow/bootstrap.sh
```

Then open Cursor / Claude Code — no harness tweaks required.

## Optional CLIs

```bash
brew install jq node   # optional tooling
# Do NOT use `skills add -a '*'` into adapter dirs — install into this repo's skills/ then ./install.sh
```

After adding a skill into this repo’s `skills/`:

```bash
./install.sh
# or: rsync skills → ~/.agents/skills && harness sync
```

## Out of scope

- Claude hooks runtime bodies (tool-private under `~/.claude`) — defaults for plugins are merged from `adapters/claude-settings.defaults.json`
- Hermes gateway / AgentMonitor bridge (see `agentmonitor` repo)
- API keys / Telegram tokens (never commit)

Durable prefs live in `memory/` (shared). Do not reintroduce a second auto-capture store.
