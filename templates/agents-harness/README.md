# Agent Harness starter (portable)

Minimal kit so another person can run the same **method** without your personal skills, SOUL, or secrets.

## Install

```bash
# from harness-flow repo root
bash templates/agents-harness/install.sh
```

Creates/updates `~/.agents/` with:

- `AGENTS.md` (lingua franca — **only if missing**, won’t clobber yours)
- `scripts/` (harness sync / rules / doctor)
- `standards/` starter + `skills/` + `commands/` dirs
- Wire adapters (Claude `@`, policy symlinks, Hermes `external_dirs` snippet printed)

Then:

```bash
~/.agents/scripts/harness sync
~/.agents/scripts/harness rules   # if you added standards
~/.agents/scripts/harness doctor
```

## Customize in 10 minutes

1. Edit `~/.agents/AGENTS.md` — language, verify command, skill table.
2. Add your skills under `~/.agents/skills/<name>/SKILL.md`.
3. Thin adapters:
   - Claude: keep `@../.agents/AGENTS.md` at top of `~/.claude/CLAUDE.md`
   - Hermes: slim `SOUL.md` + `skills.external_dirs` (see `adapters/`)
4. Do not maintain second real skill trees under each tool.

## What’s in this folder

| Path | Role |
|------|------|
| `AGENTS.md` | Starter lingua franca |
| `adapters/` | Example Claude / Hermes / Cursor wiring |
| `standards/` | Example shared rule body + Cursor meta |
| `scripts/` | Same harness CLI as the live pattern |
| `install.sh` | Idempotent bootstrap into `~/.agents` |

Full naming + usage: [`docs/AGENT_HARNESS.md`](../../docs/AGENT_HARNESS.md).
