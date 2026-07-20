# Agent Harness — naming & how to use it

## Names

| Term | What it is |
|------|------------|
| **Agent Harness** | Method: one content hub + thin adapters |
| **Lingua franca** | `AGENTS.md` (keep this filename) |
| **`~/.agents/`** | Live SSOT after install |
| **harness-flow** | This repo — git SSOT for policy + skills |
| **agentmonitor** | Separate repo — Hermes kit + pixel office |

## Day to day

```bash
# In harness-flow (preferred — git is SSOT)
edit skills/ or AGENTS.md
./install.sh                         # → ~/.agents (backs up differing live AGENTS.md)
~/.agents/scripts/harness doctor
```

Or edit live `~/.agents` then `./backup.sh` before the next install overwrites policy.

Always-on `AGENTS.md` stays **thin** (core skill router). Full packs live under `skills/` and are matched by description / `ask-matt`. Durable prefs live under `~/.agents/memory/` (index `MEMORY.md`).

## Clean setup

```bash
git clone …/harness-flow && cd harness-flow && ./install.sh
```

Optional office:

```bash
git clone …/agentmonitor && cd agentmonitor && ./install.sh
```

## Precedence

```text
tool safety → tool settings → ~/.agents/AGENTS.md → adapter → project AGENTS.md → skill → user → model
```

**Cursor note:** product has no global `AGENTS.md`. `harness rules` writes `~/.cursor/rules/agents-policy.mdc` (`alwaysApply: true`) from `~/.agents/AGENTS.md`.

## What not to put here

- Hermes identity / gateway → `agentmonitor` repo → `~/.hermes`
- Claude hooks / memory plugins → `~/.claude` only
- Secrets / Telegram tokens — never
