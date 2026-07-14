# harness-flow

Private machine kit + **shareable templates** for [Agent Harness](docs/AGENT_HARNESS.md): one content hub, thin adapters, no skill copies per tool.

| Name | Meaning |
|------|---------|
| **Agent Harness** | The method |
| **`AGENTS.md`** | Lingua franca (shared policy — keep this filename) |
| **`~/.agents/`** | Live SSOT: skills, standards, commands, policy |
| **harness-flow** | This repo: bootstrap, templates, personal Claude/Hermes packs |

```text
tool safety → tool settings
  → ~/.agents/AGENTS.md
  → adapter (~/.claude/CLAUDE.md, ~/.hermes/SOUL.md, Cursor .mdc)
  → project ./AGENTS.md
  → skill → user → model
```

---

## Day to day

```bash
# Add a skill once
cp -R <skill> ~/.agents/skills/<name>
~/.agents/scripts/harness sync

# Shared writing / domain rules → Cursor .mdc
~/.agents/scripts/harness rules

# Drift check
~/.agents/scripts/harness doctor
```

| Change | Edit |
|--------|------|
| Policy / loop / skill map | `~/.agents/AGENTS.md` |
| Skills | `~/.agents/skills/` only |
| Claude-only (mem, hooks, RTK) | `~/.claude/…` |
| Hermes-only (cursor-agent, AgentMonitor) | `~/.hermes/SOUL.md` |
| Hermes shared skills | `skills.external_dirs: [~/.agents/skills]` in `~/.hermes/config.yaml` |

---

## Layout

| Path | Role |
|------|------|
| [`docs/AGENT_HARNESS.md`](docs/AGENT_HARNESS.md) | Naming + how to use |
| [`templates/agents-harness/`](templates/agents-harness/) | Portable starter for other people |
| [`templates/project-wiki/`](templates/project-wiki/) | Per-repo engineering wiki scaffold |
| [`claude/`](claude/) | Personal Claude packs (install → `~/.claude`) |
| [`hermes/`](hermes/) | Hermes bootstrap (SOUL, install, launchd helpers) |
| [`agentmonitor/`](agentmonitor/) | Pixel-office bridge / game / PWA |
| [`MANIFEST.md`](MANIFEST.md) | External CLIs, plugins, packs |
| [`NEW_MACHINE.md`](NEW_MACHINE.md) | Zero → phone coding checklist |

---

## Install

### A. Others / clean laptop (no personal skills)

```bash
bash templates/agents-harness/install.sh
~/.agents/scripts/harness sync
~/.agents/scripts/harness doctor
```

### B. Your full machine migrate

```bash
git clone git@github.com:pongsathonkheereekaew/harness-flow.git
cd harness-flow
./install.sh          # Agent Harness → ~/.agents + Claude packs + Cursor rules + Hermes files
# then follow NEW_MACHINE.md (9router, Telegram pairing, projects)
```

`./install.sh` will:

1. Bootstrap Agent Harness into `~/.agents` (does not overwrite an existing `AGENTS.md`)
2. Copy Cursor rules from `.cursor/rules/` (or regenerate later via `harness rules`)
3. Install Claude workflow from `claude/`
4. Copy Hermes kit files into `~/.hermes/` (review `SOUL.md` — keep it thin)

Prefer **private** for this GitHub repo until personal packs are stripped.

---

## Cursor rules

Live source of truth for rule *bodies* is `~/.agents/standards/` (+ `cursor.meta.yaml`).  
Repo `.cursor/rules/*.mdc` are snapshots for migrate / backup (`./backup.sh`).

Easby-scoped rules only apply under `Downloads/Easby Plugins/` via globs — they do not pollute unrelated projects.

---

## Hermes

- Identity / desk coding / AgentMonitor protocol → `~/.hermes/SOUL.md` (do not duplicate `AGENTS.md`)
- Shared skills → `skills.external_dirs` (see `templates/agents-harness/adapters/`)
- Hermes-native skills stay under `~/.hermes/skills/`

---

## AgentMonitor

`agentmonitor/` — mission bridge + pixel office UI. Hard gate on green verify before boss merge.  
See [`agentmonitor/README.md`](agentmonitor/README.md). Extractable via `agentmonitor/scripts/extract-repo.sh`.

---

## Project wiki

Per-repo `docs/wiki/` (incidents / patterns) — not a second memory system (claude-mem stays session memory).

```bash
bash templates/project-wiki/init-wiki.sh /path/to/your-repo
```

This repo’s own wiki: [`docs/wiki/`](docs/wiki/).

---

## Verify / sync back

```bash
bash ./verify.sh          # scripts + wiki scaffold + agentmonitor
./backup.sh               # pull live Cursor rules + SOUL.md into this repo before commit
```
