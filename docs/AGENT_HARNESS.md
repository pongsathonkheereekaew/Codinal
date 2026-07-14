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
# In harness-flow
edit skills/ or AGENTS.md
./install.sh                         # → ~/.agents
~/.agents/scripts/harness sync
~/.agents/scripts/harness doctor
```

Or edit live `~/.agents` then `./backup.sh` before commit.

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

## What not to put here

- Hermes identity / gateway → `agentmonitor` repo → `~/.hermes`
- Claude hooks / memory plugins → `~/.claude` only
- Secrets / Telegram tokens — never
