# MANIFEST — Agent Harness

**This repo** is the git SSOT for portable policy + skills.  
**Live path** after `./install.sh`: `~/.agents/`.

| Layer | Location |
|-------|----------|
| Lingua franca | `AGENTS.md` → `~/.agents/AGENTS.md` |
| Skills | `skills/` → `~/.agents/skills/` |
| Standards / commands | `standards/`, `commands/` |
| CLI | `scripts/harness` → sync / rules / doctor |
| Office + Hermes | **not here** — [`agentmonitor`](https://github.com/pongsathonkheereekaew/agentmonitor) |

## Optional CLIs

```bash
brew install jq node
npm i -g skills   # optional: third-party skill packs into ~/.agents/skills
```

After adding a skill into this repo’s `skills/`:

```bash
./install.sh
# or: rsync skills → ~/.agents/skills && ~/.agents/scripts/harness sync
```

## Out of scope

- Claude hooks / claude-mem settings (tool-private under `~/.claude`)
- Hermes gateway / AgentMonitor bridge (see `agentmonitor` repo)
- API keys / Telegram tokens (never commit)
