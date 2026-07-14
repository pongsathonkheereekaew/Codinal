# harness-flow — Agent Harness

One **lingua franca** + shared skills for every coding agent. Install once → live SSOT at `~/.agents/`.

| Term | Meaning |
|------|---------|
| **Agent Harness** | The method: thin always-on policy + skills on demand |
| **`AGENTS.md`** | Shared policy (filename stays — keep it short) |
| **`~/.agents/`** | Live SSOT after `./install.sh` |
| **harness-flow** | This repo — git SSOT for that content |

Office / Hermes lives in a separate repo: [`agentmonitor`](https://github.com/pongsathonkheereekaew/agentmonitor). Not required for a clean coding setup.

```text
tool safety → tool settings
  → ~/.agents/AGENTS.md
  → tool adapter (CLAUDE.md, Cursor rules, …)
  → project ./AGENTS.md or ./CLAUDE.md
  → invoked skill → user message → model
```

## What you get

- **Thin always-on policy** — classify work, skill router, verify-before-done
- **~100 Agent Skills** under `skills/` (Matt Pocock flows, domain packs, …)
- **Standards + slash commands** synced into adapters
- **Adapters** for Claude Code, Cursor, Codex, Gemini, OpenCode, ZCode, Openclaw
- **Default engineering flow** (in `AGENTS.md`): fog → `wayfinder`; design/plan → `grilling`; clear build → `implement`/`tdd`; before a **final** plan/spec → `scrutinize`

Full design notes: [`docs/DESIGN-thinking-flow.md`](docs/DESIGN-thinking-flow.md) · eval: [`docs/eval/thinking-flow/`](docs/eval/thinking-flow/) · naming: [`docs/AGENT_HARNESS.md`](docs/AGENT_HARNESS.md)

## Layout

| Path | Role |
|------|------|
| [`AGENTS.md`](AGENTS.md) | Lingua franca (edit here, then install) |
| [`skills/`](skills/) | Shared Agent Skills (`SKILL.md`) |
| [`standards/`](standards/) | Rule bodies → Cursor `.mdc` via `harness rules` |
| [`commands/`](commands/) | Shared slash commands |
| [`scripts/`](scripts/) | `harness` — `sync` / `rules` / `doctor` |
| [`adapters/`](adapters/) | Thin tool snippets (e.g. Claude) |
| [`install.sh`](install.sh) | Repo → `~/.agents` (+ adapter links) |
| [`backup.sh`](backup.sh) | Live `~/.agents` → this repo |
| [`verify.sh`](verify.sh) | Smoke checks |
| [`NEW_MACHINE.md`](NEW_MACHINE.md) | Fresh-machine checklist |

## Clean setup

```bash
git clone git@github.com:pongsathonkheereekaew/harness-flow.git
cd harness-flow
./install.sh
~/.agents/scripts/harness doctor
```

## Day to day

**Edit in this repo, then install** (git is SSOT):

```bash
# edit AGENTS.md / skills / standards / commands
./install.sh
~/.agents/scripts/harness doctor
```

`install.sh` copies policy/skills/standards/commands/scripts into `~/.agents`, regenerates Cursor rules, and symlinks skill adapters. If live `AGENTS.md` differs, it is backed up to `~/.agents/AGENTS.md.bak.<timestamp>` then replaced from git.

If you edited live `~/.agents` instead, pull it back before the next install overwrites:

```bash
./backup.sh
git status   # review + commit in this repo
./install.sh # optional re-sync adapters
```

CLI on the machine after install:

```bash
~/.agents/scripts/harness sync    # skill symlink adapters
~/.agents/scripts/harness rules   # standards → Cursor rules
~/.agents/scripts/harness doctor  # health check
```

## Optional: AgentMonitor + Hermes

```bash
git clone git@github.com:pongsathonkheereekaew/agentmonitor.git
cd agentmonitor && ./install.sh   # SKIP_TELEGRAM=1 is fine
```

- Pixel office: http://127.0.0.1:4777
- Hermes reads skills via `skills.external_dirs → ~/.agents/skills`
- Telegram is not required for a clean setup

## What not to put here

| Keep out of harness-flow | Where it belongs |
|--------------------------|------------------|
| Hermes identity / gateway / SOUL | `agentmonitor` → `~/.hermes` |
| Claude hooks, claude-mem, RTK hooks | `~/.claude` only |
| Secrets, tokens, API keys | never in this repo |

## Verify

```bash
bash ./verify.sh
~/.agents/scripts/harness doctor
```
