# New machine — Agent Harness only

Clean coding setup. **No Telegram.** Office stack is optional.

## 0. Prereqs
- macOS, Homebrew, `git`
- Coding agents you use (Cursor / Claude Code / Codex / …)

## 1. Clone + install harness-flow

```bash
git clone git@github.com:pongsathonkheereekaew/harness-flow.git ~/harness-flow
cd ~/harness-flow
./install.sh
~/.agents/scripts/harness doctor
```

This installs into `~/.agents/`: `AGENTS.md`, `skills/`, `standards/`, `commands/`, `scripts/`, plus adapter symlinks.

## 2. Optional — AgentMonitor + Hermes (office)

```bash
git clone git@github.com:pongsathonkheereekaew/agentmonitor.git ~/agentmonitor
cd ~/agentmonitor
./install.sh
```

- Pixel office: http://127.0.0.1:4777/
- Hermes kit → `~/.hermes` with `skills.external_dirs: [~/.agents/skills]`
- 9router on `:20128` if your models use it

## 3. Verify

```bash
cd ~/harness-flow && bash ./verify.sh
~/.agents/scripts/harness doctor
```

## Daily flow

| Job | Where |
|-----|--------|
| Policy / skills | `~/harness-flow` → `./install.sh` (or edit `~/.agents` + `./backup.sh`) |
| Desk coding | Cursor / Claude with `~/.agents` loaded |
| Office missions | `agentmonitor` repo (optional) |
