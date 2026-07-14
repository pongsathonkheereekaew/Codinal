# harness-flow — Agent Harness

**Lingua franca + skills** for every coding agent. One install → `~/.agents/`.

| Name | Meaning |
|------|---------|
| **Agent Harness** | The method |
| **`AGENTS.md`** | Shared always-on policy |
| **`~/.agents/`** | Live SSOT after install |
| **harness-flow** | This git repo (source of that SSOT) |

Office / Hermes live in a **separate** repo: [`agentmonitor`](https://github.com/pongsathonkheereekaew/agentmonitor) (Hermes kit + pixel office). Not required for clean coding setup.

```text
tool safety → tool settings
  → ~/.agents/AGENTS.md
  → tool adapter
  → project ./AGENTS.md
  → skill → user → model
```

## Layout

| Path | Role |
|------|------|
| [`AGENTS.md`](AGENTS.md) | Lingua franca |
| [`skills/`](skills/) | Shared Agent Skills |
| [`standards/`](standards/) | Rule bodies (+ Cursor meta) |
| [`commands/`](commands/) | Shared slash commands |
| [`scripts/`](scripts/) | `harness` sync / rules / doctor |
| [`adapters/`](adapters/) | Thin Claude / Hermes snippets |
| [`docs/AGENT_HARNESS.md`](docs/AGENT_HARNESS.md) | Naming & usage |

## Clean setup (new machine)

```bash
git clone git@github.com:pongsathonkheereekaew/harness-flow.git
cd harness-flow
./install.sh
~/.agents/scripts/harness doctor
```

Day to day:

```bash
# edit policy / skills in this repo (or in ~/.agents then backup)
./install.sh                  # re-sync → ~/.agents
~/.agents/scripts/harness sync
```

## Optional: AgentMonitor + Hermes

```bash
git clone git@github.com:pongsathonkheereekaew/agentmonitor.git
cd agentmonitor && ./install.sh
```

Primary UI: http://127.0.0.1:4777 — Telegram not required. Hermes reads skills via `skills.external_dirs → ~/.agents/skills`.

## Verify / backup

```bash
bash ./verify.sh
./backup.sh    # pull live ~/.agents + Cursor rules into this repo before commit
```
